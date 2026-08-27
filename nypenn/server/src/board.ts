import { dayTypeOf, type Db, type Departure, type HealthStatus } from '@nypenn/shared';
import type { Predictor } from './predictor.js';

/** How long a departure stays on the board after its scheduled time. */
const KEEP_AFTER_DEPARTURE_MS = 5 * 60_000;

/** Beyond this, the collector is presumed dead rather than merely quiet. */
const STALE_AFTER_MS = 3 * 60_000;

interface LiveRow {
  trainId: string;
  serviceDate: string;
  line: string;
  lineCode: string;
  destination: string;
  scheduledDep: string;
  track: string | null;
  status: string;
  secondsLate: number;
}

/**
 * Assembles the board the client renders: live rows from the collector, with
 * a prediction attached to every train whose track NJT has not yet posted.
 *
 * Reads the collector's database rather than calling NJT, so the two
 * processes stay independent and the UI never adds load to the feed.
 */
export class BoardService {
  private readonly liveRows;
  private readonly state;

  constructor(private readonly db: Db, private readonly predictor: Predictor) {
    this.liveRows = db.prepare(`
      SELECT train_id AS trainId, service_date AS serviceDate, line,
             line_code AS lineCode, destination, scheduled_dep AS scheduledDep,
             track, status, seconds_late AS secondsLate
        FROM live_board
       ORDER BY scheduled_dep
    `);

    this.state = db.prepare(`SELECT last_poll_at AS lastPollAt FROM collector_state WHERE id = 1`);
  }

  /** The current board, newest predictions attached. */
  departures(now = new Date()): Departure[] {
    const rows = this.liveRows.all() as LiveRow[];
    const cutoff = now.getTime() - KEEP_AFTER_DEPARTURE_MS;

    return rows
      .filter((row) => Date.parse(row.scheduledDep) >= cutoff)
      .map((row) => ({
        trainId: row.trainId,
        line: row.line,
        lineCode: row.lineCode,
        destination: row.destination,
        scheduledDep: row.scheduledDep,
        track: row.track,
        status: row.status,
        secondsLate: row.secondsLate,
        // A posted track is fact; never show a guess alongside one.
        prediction: row.track
          ? null
          : this.predictor.predict(row.trainId, row.line, row.serviceDate),
      }));
  }

  /** Past runs behind a prediction, for the UI's explanation panel. */
  trainHistory(trainId: string) {
    const rows = this.predictor.history(trainId, 10);
    return rows.map((r) => ({ ...r, dayType: dayTypeOf(r.serviceDate) }));
  }

  /**
   * Collector liveness. The board is only as good as the last poll, so this
   * is what tells you the difference between a quiet night and a dead feed.
   */
  health(now = new Date()): HealthStatus {
    const row = this.state.get() as { lastPollAt: string | null } | undefined;
    const lastPollAt = row?.lastPollAt ?? null;
    const age = lastPollAt ? now.getTime() - Date.parse(lastPollAt) : null;

    const counts = this.db.prepare(`
      SELECT
        (SELECT COUNT(*) FROM departures WHERE service_date = ?) AS today,
        (SELECT COUNT(DISTINCT service_date) FROM departures) AS days
    `).get(now.toISOString().slice(0, 10)) as { today: number; days: number };

    return {
      ok: age !== null && age < STALE_AFTER_MS,
      lastPollAt,
      secondsSinceLastPoll: age === null ? null : Math.round(age / 1000),
      departuresToday: counts.today,
      historyDays: counts.days,
    };
  }
}
