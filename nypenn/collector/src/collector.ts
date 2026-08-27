import { serviceDateOf } from '@nypenn/shared';
import type { Config } from './config.js';
import type { NjtClient, RawDeparture } from './njt.js';
import type { LiveRow, ObservationRow, ResolvedDeparture, Store } from './store.js';

/** Composite key: a train number is only unique within a service day. */
function keyOf(trainId: string, serviceDate: string): string {
  return `${trainId}|${serviceDate}`;
}

/** Has anything worth recording changed since we last saw this train? */
function hasChanged(prev: LiveRow, next: Omit<LiveRow, 'trackPostedAt'>): boolean {
  return (
    prev.track !== next.track ||
    prev.status !== next.status ||
    prev.secondsLate !== next.secondsLate ||
    prev.scheduledDep !== next.scheduledDep
  );
}

/**
 * Polls the NJT board, records state transitions, and resolves departed
 * trains into permanent history.
 *
 * The board is overwhelmingly static between polls, so this writes a
 * transition log rather than a snapshot log: a poll that changes nothing
 * produces no rows at all. That is what keeps continuous collection viable on
 * an SD card without giving up any information.
 */
export class Collector {
  /** Trains currently on the board, keyed by train+service date. */
  private readonly tracked = new Map<string, LiveRow>();

  private pending: ObservationRow[] = [];
  private departed: ResolvedDeparture[] = [];
  private dirty = false;

  private lastFlush = 0;
  private lastPollAt = '';
  private pollsSinceFlush = 0;
  private lastPurgeDate = '';

  constructor(
    private readonly cfg: Config,
    private readonly client: NjtClient,
    private readonly store: Store,
    private readonly log: (level: 'info' | 'warn' | 'error' | 'debug', msg: string) => void,
  ) {}

  /** Resume from the last run so in-flight trains keep their posting times. */
  start(): void {
    for (const row of this.store.loadLiveBoard()) {
      this.tracked.set(keyOf(row.trainId, row.serviceDate), row);
    }
    this.log('info', `resumed with ${this.tracked.size} train(s) in flight`);
  }

  /** One poll cycle. Throws only on unrecoverable errors; callers retry. */
  async poll(now = new Date()): Promise<void> {
    const board = await this.client.fetchBoard();
    this.lastPollAt = now.toISOString();
    this.pollsSinceFlush += 1;

    const seen = new Set<string>();

    for (const row of board) {
      const serviceDate = serviceDateOf(row.scheduledDep);
      const key = keyOf(row.trainId, serviceDate);
      seen.add(key);

      const next = this.toLiveRow(row, serviceDate);
      const prev = this.tracked.get(key);

      if (!prev) {
        // First sighting. Record it so history has a baseline to diff against.
        this.tracked.set(key, {
          ...next,
          trackPostedAt: next.track ? this.lastPollAt : null,
        });
        this.buffer(next, serviceDate);
        continue;
      }

      if (!hasChanged(prev, next)) continue;

      this.tracked.set(key, {
        ...next,
        // Keep the *first* time a track appeared; a later re-post of the same
        // track must not overwrite the lead time we are trying to measure.
        trackPostedAt: prev.trackPostedAt ?? (next.track ? this.lastPollAt : null),
      });
      this.buffer(next, serviceDate);
    }

    this.resolveDeparted(seen, now);
    this.flushIfDue(now);
    this.purgeIfDue(now);
  }

  private toLiveRow(row: RawDeparture, serviceDate: string): Omit<LiveRow, 'trackPostedAt'> {
    return {
      trainId: row.trainId,
      serviceDate,
      line: row.line,
      lineCode: row.lineCode,
      destination: row.destination,
      scheduledDep: row.scheduledDep.toISOString(),
      track: row.track,
      status: row.status,
      secondsLate: row.secondsLate,
    };
  }

  private buffer(row: Omit<LiveRow, 'trackPostedAt'>, serviceDate: string): void {
    this.pending.push({
      observedAt: this.lastPollAt,
      trainId: row.trainId,
      serviceDate,
      line: row.line,
      destination: row.destination,
      scheduledDep: row.scheduledDep,
      track: row.track,
      status: row.status,
      secondsLate: row.secondsLate,
    });
    this.dirty = true;
  }

  /**
   * A train that has dropped off the board past its departure time has left.
   * The last track we saw is the ground truth for that run.
   */
  private resolveDeparted(seen: Set<string>, now: Date): void {
    const staleCutoff = now.getTime() - 6 * 60 * 60 * 1000;

    for (const [key, row] of this.tracked) {
      if (seen.has(key)) continue;

      const departsAt = Date.parse(row.scheduledDep);
      const isDeparted = now.getTime() > departsAt + this.cfg.resolveGraceMs;
      // Backstop: a train we somehow never saw leave must not be tracked
      // forever, or the map grows without bound.
      const isStale = departsAt < staleCutoff;

      if (!isDeparted && !isStale) continue;

      this.departed.push({ ...row, resolvedAt: now.toISOString() });
      this.tracked.delete(key);
      this.dirty = true;

      if (!row.track) {
        this.log('debug', `${row.trainId} on ${row.serviceDate} left with no track ever posted`);
      }
    }
  }

  /**
   * Commit when there is something to say and the buffer has aged out, or on
   * the heartbeat so monitoring can tell a quiet board from a dead collector.
   */
  private flushIfDue(now: Date): void {
    const elapsed = now.getTime() - this.lastFlush;
    const due = this.dirty && elapsed >= this.cfg.flushIntervalMs;
    const heartbeat = elapsed >= this.cfg.heartbeatIntervalMs;
    if (!due && !heartbeat) return;

    this.flush(now);
  }

  /**
   * Force a commit — used by the heartbeat, and on shutdown.
   *
   * Takes the current time rather than reading the clock itself: every other
   * time decision in the cycle comes from the poll's timestamp, and mixing a
   * second clock in here would leave the flush interval comparing two
   * unrelated time bases.
   */
  flush(at: Date = new Date()): void {
    if (!this.lastPollAt) return;

    this.store.flush({
      observations: this.pending,
      live: [...this.tracked.values()],
      departed: this.departed,
      lastPollAt: this.lastPollAt,
      pollsSinceFlush: this.pollsSinceFlush,
    });

    if (this.pending.length || this.departed.length) {
      this.log(
        'debug',
        `flushed ${this.pending.length} transition(s), ${this.departed.length} resolved`,
      );
    }

    this.pending = [];
    this.departed = [];
    this.dirty = false;
    this.pollsSinceFlush = 0;
    this.lastFlush = at.getTime();
  }

  /** Trim the transition log once a day, well away from the peaks. */
  private purgeIfDue(at: Date): void {
    const today = at.toISOString().slice(0, 10);
    if (this.lastPurgeDate === today) return;
    if (at.getUTCHours() < 8) return; // ~03:00-04:00 ET

    const removed = this.store.purgeObservations(this.cfg.observationRetentionDays);
    this.lastPurgeDate = today;
    if (removed) this.log('info', `purged ${removed} observation row(s)`);
  }

  /** Exposed for the health endpoint and tests. */
  get inFlight(): number {
    return this.tracked.size;
  }
}
