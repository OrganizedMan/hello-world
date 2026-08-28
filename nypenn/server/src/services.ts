import { existsSync } from 'node:fs';
import type { HealthStatus } from '@nypenn/shared';
import { openDb } from '@nypenn/shared';
import { BoardService } from './board.js';
import { Predictor } from './predictor.js';

export interface Services {
  board: BoardService;
  predictor: Predictor;
}

/**
 * What the board reports before the collector has ever run. `lastPollAt: null`
 * is already the "never polled" case the client renders as a stale banner, so
 * this needs no special handling in the UI.
 */
export const WAITING_HEALTH: HealthStatus = {
  ok: false,
  lastPollAt: null,
  secondsSinceLastPoll: null,
  departuresToday: 0,
  historyDays: 0,
};

/**
 * The collector creates and owns the database; the server only ever reads it.
 *
 * That ordering used to be fatal. Opening the file read-only at startup throws
 * SQLITE_CANTOPEN when it does not exist yet, which killed the process before
 * it ever called listen(). systemd restarted it every 5s, so port 3005 refused
 * connections indefinitely — and the reason was not in the server's journal at
 * all, but in the collector's. Two ways to land there:
 *
 *   - A fresh install. install.sh enables both units at once with no ordering
 *     between them, so the server usually wins the race to a database that
 *     does not exist yet.
 *   - Wrong or missing NJT credentials. loadConfig() checks those before it
 *     opens the database, so the collector dies without ever creating the file
 *     and the server then crash-loops forever alongside it.
 *
 * So the handle is opened on first use and retried on every later request. The
 * server listens immediately and truthfully reports itself unhealthy until the
 * collector shows up, which is a diagnosable state rather than a closed port.
 */
export class LazyServices {
  private services: Services | null = null;

  constructor(
    private readonly dbPath: string,
    private readonly linePriors: Record<string, string>,
  ) {}

  /** The services, or null while the collector has not produced a database. */
  get(): Services | null {
    if (this.services) return this.services;

    // Checked before opening: openDb throws on a missing file, and paying for
    // an exception on every request while the collector is down is wasteful.
    if (!existsSync(this.dbPath)) return null;

    const db = openDb(this.dbPath, { readonly: true });
    try {
      const predictor = new Predictor(db, this.linePriors);
      this.services = { board: new BoardService(db, predictor), predictor };
    } catch {
      // The file can exist before its schema is applied — the collector
      // creates it and then runs the DDL — and the prepared statements in
      // BoardService fail until it has. Drop the handle and retry next time
      // rather than caching a connection that cannot answer anything.
      db.close();
      return null;
    }

    return this.services;
  }
}
