/**
 * Simulate a full service day against the real collector and report what it
 * writes to disk.
 *
 * This exists to answer one question with evidence rather than estimate:
 * is continuous collection safe on a Raspberry Pi's SD card? Run it before
 * trusting the deployment, and again if the poll interval or change-detection
 * logic is ever altered.
 */
import { openDb } from '@nypenn/shared';
import { Collector } from '../src/collector.js';
import type { Config } from '../src/config.js';
import type { RawDeparture } from '../src/njt.js';
import { Store } from '../src/store.js';
import { mkdtempSync, statSync, rmSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';

const TRAINS_PER_DAY = 380;      // NJT departures from NY Penn on a weekday
const POLL_INTERVAL_MS = 20_000;
const BOARD_LOOKAHEAD_MS = 45 * 60_000;
const TRACK_POST_LEAD_MS = 5 * 60_000;
const DEPART_GRACE_MS = 2 * 60_000;

const cfg: Config = {
  dbPath: ':memory:',
  njt: { baseUrl: '', username: '', password: '', station: 'NY', requestTimeoutMs: 1000 },
  pollIntervalMs: POLL_INTERVAL_MS,
  flushIntervalMs: 30_000,
  heartbeatIntervalMs: 300_000,
  resolveGraceMs: 120_000,
  observationRetentionDays: 14,
};

const LINES = [
  ['Morris & Essex Line', 'ME', ['1', '2', '3', '4']],
  ['North Jersey Coast Line', 'NJCL', ['1', '2', '5']],
  ['Northeast Corridor', 'NEC', ['1', '2', '3', '4']],
  ['Raritan Valley Line', 'RVL', ['3', '4']],
  ['Montclair-Boonton Line', 'MOBO', ['2', '3']],
] as const;

const dayStart = Date.parse('2026-08-27T09:00:00Z'); // 05:00 ET

/** Deterministic pseudo-random, so repeated runs are comparable. */
let seed = 42;
function rand(): number {
  seed = (seed * 1103515245 + 12345) & 0x7fffffff;
  return seed / 0x7fffffff;
}

interface Plan {
  train: RawDeparture;
  departsAt: number;
  trackAt: number;
  statusChanges: { at: number; status: string; secondsLate: number }[];
}

// Spread departures across a 20-hour service day.
const plans: Plan[] = [];
for (let i = 0; i < TRAINS_PER_DAY; i++) {
  const [line, code, tracks] = LINES[i % LINES.length];
  const departsAt = dayStart + Math.floor((i / TRAINS_PER_DAY) * 20 * 3600_000);
  const track = tracks[Math.floor(rand() * tracks.length)];

  // Most trains run clean; a minority pick up a delay, sometimes twice.
  const statusChanges: Plan['statusChanges'] = [];
  const roll = rand();
  if (roll > 0.7) {
    const late = Math.floor(rand() * 900) + 60;
    statusChanges.push({ at: departsAt - 20 * 60_000, status: 'DELAYED', secondsLate: late });
    if (roll > 0.92) {
      statusChanges.push({ at: departsAt - 8 * 60_000, status: 'DELAYED', secondsLate: late + 300 });
    }
  }
  statusChanges.push({ at: departsAt - 3 * 60_000, status: 'BOARDING', secondsLate: 0 });

  plans.push({
    train: {
      trainId: String(3000 + i),
      line,
      lineCode: code,
      destination: 'Dover',
      scheduledDep: new Date(departsAt),
      track: null,
      status: 'ON TIME',
      secondsLate: 0,
    },
    departsAt,
    trackAt: departsAt - TRACK_POST_LEAD_MS,
    statusChanges,
  });
}

/** The board as NJT would report it at a given instant. */
function boardAt(t: number): RawDeparture[] {
  const out: RawDeparture[] = [];
  for (const p of plans) {
    if (t < p.departsAt - BOARD_LOOKAHEAD_MS) continue;
    if (t > p.departsAt + DEPART_GRACE_MS) continue;

    let status = 'ON TIME';
    let secondsLate = 0;
    for (const change of p.statusChanges) {
      if (t >= change.at) {
        status = change.status;
        secondsLate = change.secondsLate;
      }
    }
    out.push({
      ...p.train,
      track: t >= p.trackAt ? '4' : null,
      status,
      secondsLate,
    });
  }
  return out;
}

const dir = mkdtempSync(join(tmpdir(), 'nypenn-sim-'));
const dbPath = join(dir, 'sim.db');

try {
  const db = openDb(dbPath);
  const store = new Store(db);

  let flushes = 0;
  const originalFlush = store.flush.bind(store);
  store.flush = (args) => { flushes += 1; return originalFlush(args); };

  const client = {
    board: [] as RawDeparture[],
    async fetchBoard() { return this.board; },
  };

  const collector = new Collector(cfg, client as never, store, () => {});
  collector.start();

  const dayEnd = dayStart + 21 * 3600_000;
  let polls = 0;
  for (let t = dayStart; t <= dayEnd; t += POLL_INTERVAL_MS) {
    client.board = boardAt(t);
    await collector.poll(new Date(t));
    polls += 1;
  }
  collector.flush(new Date(dayEnd));

  const one = (sql: string) => (db.prepare(sql).get() as { n: number }).n;
  const observations = one('SELECT COUNT(*) AS n FROM observations');
  const departures = one('SELECT COUNT(*) AS n FROM departures');
  const withTrack = one('SELECT COUNT(*) AS n FROM departures WHERE final_track IS NOT NULL');

  db.pragma('wal_checkpoint(TRUNCATE)');
  db.close();

  const bytes = statSync(dbPath).size;
  // Roughly 25 trains sit on the board at any moment, so a naive snapshot log
  // would write that many rows on every single poll.
  const snapshotRows = polls * 25;

  console.log('--- simulated service day -------------------------------');
  console.log(`polls                  ${polls}`);
  console.log(`commits                ${flushes}`);
  console.log(`observation rows       ${observations}`);
  console.log(`departure rows         ${departures} (${withTrack} with a final track)`);
  console.log(`db size                ${(bytes / 1024).toFixed(0)} KiB`);
  console.log(`per day on disk        ~${(bytes / 1024 / 1024).toFixed(2)} MiB`);
  // Upper bound: ignores the 14-day observation purge, which holds the real
  // steady state well below this.
  console.log(`projected per year     <${((bytes * 365) / 1024 / 1024 / 1024).toFixed(2)} GiB (upper bound)`);
  console.log('');
  console.log(`snapshot-log rows would have been ~${snapshotRows} (${(snapshotRows / observations).toFixed(0)}x more)`);
  console.log('---------------------------------------------------------');
} finally {
  rmSync(dir, { recursive: true, force: true });
}
