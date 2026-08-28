import assert from 'node:assert/strict';
import { test } from 'node:test';
import { openDb, type Db } from '@nypenn/shared';
import { Predictor } from '../src/predictor.js';

/** A database seeded with resolved departures, as the collector would leave it. */
function seed(rows: { trainId: string; line: string; date: string; track: string }[]): Db {
  const db = openDb(':memory:');
  db.exec(`
    CREATE TABLE departures (
      train_id TEXT NOT NULL, service_date TEXT NOT NULL, line TEXT NOT NULL,
      line_code TEXT NOT NULL DEFAULT '', destination TEXT NOT NULL DEFAULT 'Dover',
      scheduled_dep TEXT NOT NULL DEFAULT '', final_track TEXT,
      track_posted_at TEXT, seconds_late INTEGER NOT NULL DEFAULT 0,
      resolved_at TEXT NOT NULL DEFAULT '',
      PRIMARY KEY (train_id, service_date)
    );
  `);
  const insert = db.prepare(
    `INSERT INTO departures (train_id, service_date, line, final_track) VALUES (?, ?, ?, ?)`,
  );
  for (const r of rows) insert.run(r.trainId, r.date, r.line, r.track);
  return db;
}

/** N consecutive weekdays ending the day before `before`. */
function weekdaysBefore(before: string, n: number): string[] {
  const out: string[] = [];
  let cursor = Date.parse(`${before}T12:00:00Z`) - 86400_000;
  while (out.length < n) {
    const d = new Date(cursor);
    const day = d.getUTCDay();
    if (day !== 0 && day !== 6) out.push(d.toISOString().slice(0, 10));
    cursor -= 86400_000;
  }
  return out;
}

const ME = 'Morris & Essex Line';
const TARGET = '2026-08-27'; // a Thursday

test('a consistently assigned train predicts its usual track with high confidence', () => {
  const rows = weekdaysBefore(TARGET, 25).map((date) => ({
    trainId: '3856', line: ME, date, track: '4',
  }));
  const p = new Predictor(seed(rows)).predict('3856', ME, TARGET);

  assert.equal(p?.track, '4');
  assert.equal(p?.confidence, 'high');
  assert.equal(p?.source, 'train-history');
  assert.ok(p!.score > 0.8, `expected a strong score, got ${p!.score}`);
});

test('a single past run never reads as confident', () => {
  const p = new Predictor(
    seed([{ trainId: '3856', line: ME, date: weekdaysBefore(TARGET, 1)[0], track: '4' }]),
  ).predict('3856', ME, TARGET);

  assert.equal(p?.track, '4', 'still the best guess available');
  assert.equal(p?.sampleSize, 1);
  assert.equal(p?.confidence, 'low', 'one observation is not evidence');
});

test('an erratic train is reported as low confidence', () => {
  const tracks = ['1', '2', '3', '4', '1', '2', '3', '4', '1', '2', '3', '4'];
  const rows = weekdaysBefore(TARGET, 12).map((date, i) => ({
    trainId: '3856', line: ME, date, track: tracks[i],
  }));
  const p = new Predictor(seed(rows)).predict('3856', ME, TARGET);

  assert.equal(p?.confidence, 'low');
  assert.ok(p!.score < 0.5, `expected a weak score, got ${p!.score}`);
});

test('recent assignments outweigh stale ones after a schedule change', () => {
  const days = weekdaysBefore(TARGET, 40);
  // Track 2 for the last three weeks, track 4 before that.
  const rows = days.map((date, i) => ({
    trainId: '3856', line: ME, date, track: i < 15 ? '2' : '4',
  }));
  const p = new Predictor(seed(rows)).predict('3856', ME, TARGET);

  assert.equal(p?.track, '2', 'the current pattern should win over the old one');
});

test('weekday history does not leak into a weekend prediction', () => {
  const rows = weekdaysBefore(TARGET, 20).map((date) => ({
    trainId: '3856', line: ME, date, track: '4',
  }));
  const predictor = new Predictor(seed(rows));

  // 2026-08-29 is a Saturday, with no Saturday history for this train.
  const weekend = predictor.predict('3856', ME, '2026-08-29');
  assert.notEqual(
    weekend?.source,
    'train-history',
    'weekday runs must not be used to predict a Saturday',
  );
});

test('an unknown train falls back to its line, capped below high confidence', () => {
  const rows = weekdaysBefore(TARGET, 30).flatMap((date) => [
    { trainId: '1000', line: ME, date, track: '4' },
    { trainId: '1001', line: ME, date, track: '4' },
  ]);
  const p = new Predictor(seed(rows)).predict('9999', ME, TARGET);

  assert.equal(p?.track, '4');
  assert.equal(p?.source, 'line-history');
  assert.notEqual(p?.confidence, 'high', 'line-level evidence is weaker than the train itself');
});

test('with no history at all, a seeded prior is offered at low confidence', () => {
  const p = new Predictor(seed([]), { [ME]: '3' }).predict('3856', ME, TARGET);

  assert.equal(p?.track, '3');
  assert.equal(p?.source, 'line-prior');
  assert.equal(p?.confidence, 'low');
  assert.equal(p?.sampleSize, 0);
});

test('with neither history nor a prior, it declines to guess', () => {
  assert.equal(new Predictor(seed([])).predict('3856', ME, TARGET), null);
});

test('a prediction never uses data from its own day or later', () => {
  const days = weekdaysBefore(TARGET, 10);
  const rows = days.map((date) => ({ trainId: '3856', line: ME, date, track: '4' }));
  // The answer for the target day itself, plus a later day.
  rows.push({ trainId: '3856', line: ME, date: TARGET, track: '9' });
  rows.push({ trainId: '3856', line: ME, date: '2026-08-28', track: '9' });

  const p = new Predictor(seed(rows)).predict('3856', ME, TARGET);
  assert.equal(p?.track, '4', 'must not peek at the day being predicted');
});

test('backtesting scores predictions against what actually happened', () => {
  const days = weekdaysBefore('2026-08-28', 40);
  const rows = days.map((date) => ({ trainId: '3856', line: ME, date, track: '4' }));
  const report = new Predictor(seed(rows)).backtest(days[9], days[0]);

  assert.ok(report.predicted > 0, 'should have made predictions');
  assert.equal(report.accuracy, 1, 'a perfectly consistent train is perfectly predictable');
  assert.equal(report.byLine[ME].accuracy, 1);
});

test('backtesting reports the errors of a genuinely unpredictable train', () => {
  const days = weekdaysBefore('2026-08-28', 40);
  const rows = days.map((date, i) => ({
    trainId: '3856', line: ME, date, track: String((i % 4) + 1),
  }));
  const report = new Predictor(seed(rows)).backtest(days[19], days[0]);

  assert.ok(report.accuracy < 0.6, `a rotating track should score poorly, got ${report.accuracy}`);
  assert.ok(report.predicted > 0);
});

test('history is returned newest first for the explanation panel', () => {
  const days = weekdaysBefore(TARGET, 15);
  const rows = days.map((date, i) => ({
    trainId: '3856', line: ME, date, track: i === 0 ? '3' : '4',
  }));
  const history = new Predictor(seed(rows)).history('3856', 5);

  assert.equal(history.length, 5);
  assert.equal(history[0].serviceDate, days[0]);
  assert.equal(history[0].finalTrack, '3');
});
