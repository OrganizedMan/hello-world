import {
  dayTypeOf,
  type Confidence,
  type DayType,
  type Db,
  type PredictionSource,
  type TrackPrediction,
} from '@nypenn/shared';

/** How far back to look for a train's own history. */
const HISTORY_DAYS = 60;

/** Recency weighting: an observation this old counts half as much. */
const HALF_LIFE_DAYS = 21;

/**
 * Confidence thresholds on the weighted modal share. These decide what the
 * board shows in green rather than orange, so they are deliberately strict —
 * a track shown confidently and wrongly sends you to the wrong end of Penn,
 * which is worse than showing no prediction at all.
 */
const HIGH_CONFIDENCE = 0.8;
const MEDIUM_CONFIDENCE = 0.5;

/**
 * A prediction from a single past run is not evidence. Shrink the score
 * toward zero until there is a real sample behind it, so a lone data point
 * can never surface as high confidence.
 */
const SHRINKAGE = 2.5;

interface HistoryRow {
  serviceDate: string;
  finalTrack: string;
}

/**
 * Predicts which track a train will depart from, before NJ Transit posts it.
 *
 * Track assignment at NY Penn is overwhelmingly a function of train number
 * and day type, so a recency-weighted modal track over past runs captures
 * most of the available signal — and unlike a black box, it can show its
 * work, which is what makes the confidence colour trustworthy.
 */
export class Predictor {
  private readonly trainHistory;
  private readonly lineHistory;

  /**
   * Hand-seeded fallbacks for the cold-start case, before any history exists.
   * Deliberately capped at low confidence: these are rules of thumb about
   * which tracks a line generally uses, not evidence about a given train.
   */
  private readonly linePriors: Record<string, string> = {};

  constructor(private readonly db: Db, priors: Record<string, string> = {}) {
    this.linePriors = priors;

    this.trainHistory = db.prepare(`
      SELECT service_date AS serviceDate, final_track AS finalTrack
        FROM departures
       WHERE train_id = ?
         AND final_track IS NOT NULL
         AND service_date >= ?
       ORDER BY service_date DESC
    `);

    this.lineHistory = db.prepare(`
      SELECT service_date AS serviceDate, final_track AS finalTrack
        FROM departures
       WHERE line = ?
         AND final_track IS NOT NULL
         AND service_date >= ?
       ORDER BY service_date DESC
       LIMIT 500
    `);
  }

  /**
   * Predict the track for one train on one service date.
   *
   * `asOf` exists so the backtest can ask "what would we have said that
   * morning?" without leaking the answer from later rows.
   */
  predict(
    trainId: string,
    line: string,
    serviceDate: string,
    asOf: string = serviceDate,
  ): TrackPrediction | null {
    const dayType = dayTypeOf(serviceDate);
    const since = shiftDate(asOf, -HISTORY_DAYS);

    const own = (this.trainHistory.all(trainId, since) as HistoryRow[]).filter(
      (r) => r.serviceDate < asOf && dayTypeOf(r.serviceDate) === dayType,
    );

    const fromTrain = this.score(own, asOf, 'train-history');
    if (fromTrain) return fromTrain;

    // The train itself is unknown — a new number, or a first run on this day
    // type. Fall back to what its line generally does.
    const lineRows = (this.lineHistory.all(line, since) as HistoryRow[]).filter(
      (r) => r.serviceDate < asOf && dayTypeOf(r.serviceDate) === dayType,
    );

    const fromLine = this.score(lineRows, asOf, 'line-history');
    if (fromLine) return { ...fromLine, confidence: cap(fromLine.confidence, 'medium') };

    const prior = this.linePriors[line];
    if (prior) {
      return {
        track: prior,
        score: 0,
        confidence: 'low',
        source: 'line-prior',
        sampleSize: 0,
      };
    }

    return null;
  }

  /** Weighted-mode over history rows, or null if there is nothing to go on. */
  private score(
    rows: HistoryRow[],
    asOf: string,
    source: PredictionSource,
  ): TrackPrediction | null {
    if (rows.length === 0) return null;

    const weights = new Map<string, number>();
    let total = 0;

    for (const row of rows) {
      const ageDays = daysBetween(row.serviceDate, asOf);
      const weight = Math.pow(0.5, ageDays / HALF_LIFE_DAYS);
      weights.set(row.finalTrack, (weights.get(row.finalTrack) ?? 0) + weight);
      total += weight;
    }

    let best = '';
    let bestWeight = 0;
    for (const [track, weight] of weights) {
      if (weight > bestWeight) {
        best = track;
        bestWeight = weight;
      }
    }

    if (!best || total === 0) return null;

    // Shrink toward zero on thin evidence: the raw share of a single
    // observation is 1.0, which would otherwise read as certainty. Adding a
    // constant to the denominator costs a consistent train little once it has
    // a few weeks behind it, but keeps a lone run well out of the green band.
    const score = bestWeight / (total + SHRINKAGE);

    return {
      track: best,
      score: round(score),
      confidence: bandOf(score),
      source,
      sampleSize: rows.length,
    };
  }

  /**
   * Backtest every resolved departure in a window: for each, predict using
   * only earlier data, then compare against what actually happened.
   *
   * Without this there is no way to know whether the board is worth trusting,
   * and no baseline to judge a future model against.
   */
  backtest(fromDate: string, toDate: string): BacktestReport {
    const rows = this.db.prepare(`
      SELECT train_id AS trainId, line, service_date AS serviceDate,
             final_track AS finalTrack
        FROM departures
       WHERE final_track IS NOT NULL
         AND service_date BETWEEN ? AND ?
       ORDER BY service_date
    `).all(fromDate, toDate) as {
      trainId: string; line: string; serviceDate: string; finalTrack: string;
    }[];

    const byLine = new Map<string, { n: number; hit: number }>();
    const byConfidence = new Map<Confidence, { n: number; hit: number }>();
    let predicted = 0;
    let correct = 0;

    for (const row of rows) {
      const p = this.predict(row.trainId, row.line, row.serviceDate, row.serviceDate);
      if (!p) continue;

      const hit = p.track === row.finalTrack;
      predicted += 1;
      if (hit) correct += 1;

      const line = byLine.get(row.line) ?? { n: 0, hit: 0 };
      line.n += 1;
      if (hit) line.hit += 1;
      byLine.set(row.line, line);

      const band = byConfidence.get(p.confidence) ?? { n: 0, hit: 0 };
      band.n += 1;
      if (hit) band.hit += 1;
      byConfidence.set(p.confidence, band);
    }

    return {
      window: { from: fromDate, to: toDate },
      totalDepartures: rows.length,
      predicted,
      correct,
      accuracy: predicted ? round(correct / predicted) : 0,
      coverage: rows.length ? round(predicted / rows.length) : 0,
      byLine: Object.fromEntries(
        [...byLine].map(([k, v]) => [k, { n: v.n, accuracy: round(v.hit / v.n) }]),
      ),
      byConfidence: Object.fromEntries(
        [...byConfidence].map(([k, v]) => [k, { n: v.n, accuracy: round(v.hit / v.n) }]),
      ),
    };
  }

  /** Recent runs for one train, for the UI's "show me why" panel. */
  history(trainId: string, limit = 10): { serviceDate: string; finalTrack: string }[] {
    return this.db.prepare(`
      SELECT service_date AS serviceDate, final_track AS finalTrack
        FROM departures
       WHERE train_id = ? AND final_track IS NOT NULL
       ORDER BY service_date DESC
       LIMIT ?
    `).all(trainId, limit) as { serviceDate: string; finalTrack: string }[];
  }
}

export interface BacktestReport {
  window: { from: string; to: string };
  totalDepartures: number;
  predicted: number;
  correct: number;
  accuracy: number;
  /** Share of departures we were willing to predict at all. */
  coverage: number;
  byLine: Record<string, { n: number; accuracy: number }>;
  byConfidence: Record<string, { n: number; accuracy: number }>;
}

function bandOf(score: number): Confidence {
  if (score >= HIGH_CONFIDENCE) return 'high';
  if (score >= MEDIUM_CONFIDENCE) return 'medium';
  return 'low';
}

const ORDER: Confidence[] = ['low', 'medium', 'high'];

/** Clamp a confidence band to at most `ceiling`. */
function cap(value: Confidence, ceiling: Confidence): Confidence {
  return ORDER.indexOf(value) > ORDER.indexOf(ceiling) ? ceiling : value;
}

function daysBetween(from: string, to: string): number {
  return Math.abs(Date.parse(`${to}T12:00:00Z`) - Date.parse(`${from}T12:00:00Z`)) / 86400_000;
}

function shiftDate(date: string, days: number): string {
  return new Date(Date.parse(`${date}T12:00:00Z`) + days * 86400_000)
    .toISOString()
    .slice(0, 10);
}

function round(n: number): number {
  return Math.round(n * 1000) / 1000;
}

export type { DayType };
