/**
 * Populate a database with plausible history and a live board.
 *
 * Real predictions need weeks of collection, so this exists to exercise the
 * whole stack today: it produces a board with posted tracks, confident
 * predictions, shaky ones, and trains with no history at all, so every state
 * the UI can render is visible before real data exists.
 *
 * Never point this at the production database.
 */
import { mkdirSync } from 'node:fs';
import { dirname } from 'node:path';
import { openDb, serviceDateOf } from '@nypenn/shared';
import { Store } from '../src/store.js';

const dbPath = process.argv[2] ?? 'data/demo.db';
if (dbPath.includes('nypenn.db')) {
  console.error('Refusing to seed the production database. Pass a different path.');
  process.exit(1);
}

mkdirSync(dirname(dbPath), { recursive: true });
const db = openDb(dbPath);
new Store(db); // applies the schema

db.exec('DELETE FROM departures; DELETE FROM live_board; DELETE FROM observations;');

const LINES: [string, string, string[]][] = [
  ['Morris & Essex Line', 'ME', ['4']],
  ['North Jersey Coast Line', 'NJCL', ['2']],
  ['Northeast Corridor', 'NEC', ['1', '2', '3', '4']], // erratic on purpose
  ['Raritan Valley Line', 'RVL', ['3']],
];
const DESTS = ['Dover', 'Long Branch', 'Trenton', 'Raritan'];

const now = new Date();
const insertDep = db.prepare(`
  INSERT OR REPLACE INTO departures
    (train_id, service_date, line, line_code, destination, scheduled_dep,
     final_track, track_posted_at, seconds_late, resolved_at)
  VALUES (?, ?, ?, ?, ?, ?, ?, ?, 0, ?)
`);

let seed = 7;
const rand = () => ((seed = (seed * 1103515245 + 12345) & 0x7fffffff) / 0x7fffffff);

// Six weeks of weekday history for four trains.
let historyRows = 0;
db.transaction(() => {
  for (let back = 1; back <= 42; back++) {
    const day = new Date(now.getTime() - back * 86400_000);
    const weekday = day.getUTCDay();
    if (weekday === 0 || weekday === 6) continue;
    const serviceDate = day.toISOString().slice(0, 10);

    LINES.forEach(([line, code, tracks], i) => {
      const track = tracks[Math.floor(rand() * tracks.length)];
      const dep = new Date(day);
      dep.setUTCHours(21, 31 + i * 7, 0, 0);
      insertDep.run(
        String(3850 + i), serviceDate, line, code, DESTS[i],
        dep.toISOString(), track, dep.toISOString(), dep.toISOString(),
      );
      historyRows++;
    });
  }
})();

// A live board: some tracks posted, some awaiting prediction, one unknown train.
const insertLive = db.prepare(`
  INSERT OR REPLACE INTO live_board
    (train_id, service_date, line, line_code, destination, scheduled_dep,
     track, status, seconds_late, track_posted_at, updated_at)
  VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, NULL, ?)
`);

const board: [string, number, number, string | null, string, number][] = [
  ['3850', 0, 6, '4', 'BOARDING', 0],       // posted
  ['3851', 1, 18, null, 'ON TIME', 0],      // predicted, consistent
  ['3852', 2, 27, null, 'DELAYED', 480],    // predicted, erratic line
  ['3853', 3, 39, null, 'ON TIME', 0],      // predicted, consistent
  ['9001', 2, 52, null, 'ON TIME', 0],      // no history at all
];

db.transaction(() => {
  for (const [trainId, lineIdx, minutes, track, status, late] of board) {
    const [line, code] = LINES[lineIdx];
    const dep = new Date(now.getTime() + minutes * 60_000);
    insertLive.run(
      trainId, serviceDateOf(dep), line, code, DESTS[lineIdx],
      dep.toISOString(), track, status, late, new Date().toISOString(),
    );
  }
  db.prepare(`UPDATE collector_state SET last_poll_at = ? WHERE id = 1`)
    .run(new Date().toISOString());
})();

db.close();
console.log(`Seeded ${dbPath}: ${historyRows} history rows, ${board.length} live departures.`);
