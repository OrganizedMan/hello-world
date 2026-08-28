import { readFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import type { Db } from '@nypenn/shared';

const here = dirname(fileURLToPath(import.meta.url));

/** A buffered state transition, awaiting the next flush. */
export interface ObservationRow {
  observedAt: string;
  trainId: string;
  serviceDate: string;
  line: string;
  destination: string;
  scheduledDep: string;
  track: string | null;
  status: string;
  secondsLate: number;
}

/** A train currently on the board, as we last saw it. */
export interface LiveRow {
  trainId: string;
  serviceDate: string;
  line: string;
  lineCode: string;
  destination: string;
  scheduledDep: string;
  track: string | null;
  status: string;
  secondsLate: number;
  trackPostedAt: string | null;
}

/** A train that has left the board, ready for the permanent history table. */
export interface ResolvedDeparture extends LiveRow {
  resolvedAt: string;
}

/**
 * All database writes for the collector.
 *
 * Every write path is a prepared statement executed inside a single
 * transaction per flush: on an SD card the number of commits matters as much
 * as the number of bytes, so we never write outside `flush`.
 */
export class Store {
  private readonly insertObservation;
  private readonly upsertLive;
  private readonly deleteLive;
  private readonly upsertDeparture;
  private readonly touchState;
  private readonly recordError;

  constructor(private readonly db: Db) {
    db.exec(readFileSync(join(here, 'schema.sql'), 'utf8'));

    this.insertObservation = db.prepare(`
      INSERT INTO observations
        (observed_at, train_id, service_date, line, destination,
         scheduled_dep, track, status, seconds_late)
      VALUES (@observedAt, @trainId, @serviceDate, @line, @destination,
              @scheduledDep, @track, @status, @secondsLate)
    `);

    this.upsertLive = db.prepare(`
      INSERT INTO live_board
        (train_id, service_date, line, line_code, destination, scheduled_dep,
         track, status, seconds_late, track_posted_at, updated_at)
      VALUES (@trainId, @serviceDate, @line, @lineCode, @destination, @scheduledDep,
              @track, @status, @secondsLate, @trackPostedAt, @updatedAt)
      ON CONFLICT(train_id) DO UPDATE SET
        service_date = excluded.service_date,
        line = excluded.line,
        line_code = excluded.line_code,
        destination = excluded.destination,
        scheduled_dep = excluded.scheduled_dep,
        track = excluded.track,
        status = excluded.status,
        seconds_late = excluded.seconds_late,
        track_posted_at = excluded.track_posted_at,
        updated_at = excluded.updated_at
    `);

    this.deleteLive = db.prepare(`DELETE FROM live_board WHERE train_id = ?`);

    // A re-resolved train overwrites its row: the later sighting is closer to
    // the truth, and this keeps restarts idempotent.
    this.upsertDeparture = db.prepare(`
      INSERT INTO departures
        (train_id, service_date, line, line_code, destination, scheduled_dep,
         final_track, track_posted_at, seconds_late, resolved_at)
      VALUES (@trainId, @serviceDate, @line, @lineCode, @destination, @scheduledDep,
              @track, @trackPostedAt, @secondsLate, @resolvedAt)
      ON CONFLICT(train_id, service_date) DO UPDATE SET
        final_track = COALESCE(excluded.final_track, departures.final_track),
        track_posted_at = COALESCE(excluded.track_posted_at, departures.track_posted_at),
        seconds_late = excluded.seconds_late,
        resolved_at = excluded.resolved_at
    `);

    this.touchState = db.prepare(`
      UPDATE collector_state
         SET last_poll_at = ?, poll_count = poll_count + ?
       WHERE id = 1
    `);

    this.recordError = db.prepare(`
      UPDATE collector_state SET last_error = ?, last_error_at = ? WHERE id = 1
    `);
  }

  /** Load in-flight trains so a restart resumes rather than restarts history. */
  loadLiveBoard(): LiveRow[] {
    const rows = this.db.prepare(`
      SELECT train_id AS trainId, service_date AS serviceDate, line, line_code AS lineCode,
             destination, scheduled_dep AS scheduledDep, track, status,
             seconds_late AS secondsLate, track_posted_at AS trackPostedAt
        FROM live_board
    `).all();
    return rows as LiveRow[];
  }

  /**
   * Persist one cycle's worth of work atomically. Callers batch into this
   * rather than writing per poll.
   */
  flush(args: {
    observations: ObservationRow[];
    live: LiveRow[];
    departed: ResolvedDeparture[];
    lastPollAt: string;
    pollsSinceFlush: number;
  }): void {
    const run = this.db.transaction(() => {
      for (const obs of args.observations) this.insertObservation.run(obs);

      const updatedAt = args.lastPollAt;
      for (const row of args.live) this.upsertLive.run({ ...row, updatedAt });

      for (const dep of args.departed) {
        this.upsertDeparture.run(dep);
        this.deleteLive.run(dep.trainId);
      }

      this.touchState.run(args.lastPollAt, args.pollsSinceFlush);
    });
    run();
  }

  noteError(message: string): void {
    this.recordError.run(message.slice(0, 500), new Date().toISOString());
  }

  /**
   * Drop transition rows past the retention window. `departures` is never
   * touched — that is the training data and it is not reproducible.
   */
  purgeObservations(retentionDays: number): number {
    const cutoff = new Date(Date.now() - retentionDays * 86400_000).toISOString();
    const info = this.db.prepare(`DELETE FROM observations WHERE observed_at < ?`).run(cutoff);
    if (info.changes > 0) {
      // Reclaim the freed pages rather than growing the file forever.
      this.db.pragma('incremental_vacuum');
    }
    return info.changes;
  }
}
