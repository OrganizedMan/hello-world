/** Shared domain types for the NY Penn board. */

/** A single live row on the departure board, as served to the client. */
export interface Departure {
  trainId: string;
  line: string;
  lineCode: string;
  destination: string;
  /** Scheduled departure, ISO 8601. */
  scheduledDep: string;
  /** Track posted by NJ Transit, or null if not yet announced. */
  track: string | null;
  status: string;
  secondsLate: number;
  /** Present only while `track` is null. */
  prediction: TrackPrediction | null;
}

/** Confidence bands, mirroring how the board colours a predicted track. */
export type Confidence = 'high' | 'medium' | 'low';

/** Which rung of the fallback chain produced a prediction. */
export type PredictionSource =
  | 'train-history'
  | 'line-history'
  | 'line-prior';

export interface TrackPrediction {
  track: string;
  /** Share of the modal track among weighted history, 0..1. */
  score: number;
  confidence: Confidence;
  source: PredictionSource;
  /** Number of past service days backing this prediction. */
  sampleSize: number;
}

/** One resolved historical departure — the predictor's training row. */
export interface HistoricalDeparture {
  trainId: string;
  serviceDate: string;
  line: string;
  destination: string;
  scheduledDep: string;
  finalTrack: string;
  /** Seconds between track posting and scheduled departure. */
  postedLeadSeconds: number | null;
}

/** Collector liveness, surfaced for monitoring. */
export interface HealthStatus {
  ok: boolean;
  lastPollAt: string | null;
  secondsSinceLastPoll: number | null;
  departuresToday: number;
  historyDays: number;
}
