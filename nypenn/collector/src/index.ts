import { mkdirSync } from 'node:fs';
import { dirname } from 'node:path';
import { openDb } from '@nypenn/shared';
import { Collector } from './collector.js';
import { loadConfig } from './config.js';
import { NjtClient } from './njt.js';
import { Store } from './store.js';

const LEVELS = ['error', 'warn', 'info', 'debug'] as const;
type Level = (typeof LEVELS)[number];

const threshold = (process.env.LOG_LEVEL as Level) ?? 'info';

/**
 * Per-poll detail is logged at debug and stays off by default: on a Pi,
 * chatty journald output wears the SD card faster than the database does.
 */
function log(level: Level, msg: string): void {
  if (LEVELS.indexOf(level) > LEVELS.indexOf(threshold)) return;
  const line = `${new Date().toISOString()} [${level}] ${msg}`;
  if (level === 'error' || level === 'warn') console.error(line);
  else console.log(line);
}

const sleep = (ms: number) => new Promise((r) => setTimeout(r, ms));

async function main(): Promise<void> {
  const cfg = loadConfig();

  mkdirSync(dirname(cfg.dbPath), { recursive: true });
  const db = openDb(cfg.dbPath);
  const store = new Store(db);
  const collector = new Collector(cfg, new NjtClient(cfg.njt), store, log);

  collector.start();
  log('info', `polling ${cfg.njt.station} every ${cfg.pollIntervalMs / 1000}s -> ${cfg.dbPath}`);

  let stopping = false;
  let consecutiveFailures = 0;

  const shutdown = (signal: string) => {
    if (stopping) return;
    stopping = true;
    log('info', `${signal} received, flushing before exit`);
    try {
      collector.flush();
    } catch (err) {
      log('error', `final flush failed: ${(err as Error).message}`);
    }
    db.close();
    process.exit(0);
  };

  process.on('SIGINT', () => shutdown('SIGINT'));
  process.on('SIGTERM', () => shutdown('SIGTERM'));

  while (!stopping) {
    const startedAt = Date.now();

    try {
      await collector.poll();
      if (consecutiveFailures > 0) {
        log('info', `recovered after ${consecutiveFailures} failed poll(s)`);
        consecutiveFailures = 0;
      }
    } catch (err) {
      consecutiveFailures += 1;
      const message = (err as Error).message;
      // Log the first failure and then every tenth, so a long outage does not
      // fill the journal with identical lines.
      if (consecutiveFailures === 1 || consecutiveFailures % 10 === 0) {
        log('error', `poll failed (${consecutiveFailures}x): ${message}`);
      }
      try {
        store.noteError(message);
      } catch {
        // A failed error-note must never take the loop down.
      }
    }

    // Back off on sustained failure rather than hammering a struggling API,
    // capped so we recover promptly once it returns.
    const backoff = consecutiveFailures
      ? Math.min(cfg.pollIntervalMs * 2 ** Math.min(consecutiveFailures, 5), 5 * 60_000)
      : cfg.pollIntervalMs;

    const wait = Math.max(0, backoff - (Date.now() - startedAt));
    await sleep(wait);
  }
}

main().catch((err) => {
  log('error', `fatal: ${err instanceof Error ? err.stack ?? err.message : String(err)}`);
  process.exit(1);
});
