import Database from 'better-sqlite3';

export type Db = Database.Database;

export interface OpenOptions {
  readonly?: boolean;
}

/**
 * Open the history database with pragmas tuned for continuous logging on a
 * Raspberry Pi's SD card: WAL so readers never block the collector, NORMAL
 * sync so we aren't fsyncing on every commit, and a generous autocheckpoint
 * so WAL rollover happens in occasional batches rather than constantly.
 */
export function openDb(path: string, opts: OpenOptions = {}): Db {
  const db = new Database(path, { readonly: opts.readonly ?? false });

  // Must be set before any table exists, so incremental_vacuum can later
  // reclaim space from purged observations without a full VACUUM rewrite.
  db.pragma('auto_vacuum = INCREMENTAL');
  db.pragma('journal_mode = WAL');
  db.pragma('synchronous = NORMAL');
  db.pragma('temp_store = MEMORY');
  db.pragma('busy_timeout = 5000');

  if (!opts.readonly) {
    // ~4MB of WAL before a checkpoint, instead of the 1000-page default.
    db.pragma('wal_autocheckpoint = 1000');
  }

  return db;
}
