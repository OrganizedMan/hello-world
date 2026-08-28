import assert from 'node:assert/strict';
import { test } from 'node:test';
import { dayTypeOf, parseRailDateTime, serviceDateOf } from '@nypenn/shared';
import { NjtClient } from '../src/njt.js';

const client = new NjtClient({
  baseUrl: 'http://example.invalid',
  username: 'u',
  password: 'p',
  station: 'NY',
  requestTimeoutMs: 1000,
});

test('parses the timestamp formats NJT has used', () => {
  // 17:31 Eastern on 27 Aug is EDT (UTC-4) => 21:31Z
  const dmy = parseRailDateTime('27-Aug-2026 05:31:00 PM');
  assert.equal(dmy?.toISOString(), '2026-08-27T21:31:00.000Z');

  const mdy = parseRailDateTime('8/27/2026 5:31:00 PM');
  assert.equal(mdy?.toISOString(), '2026-08-27T21:31:00.000Z');

  const iso = parseRailDateTime('2026-08-27T17:31:00');
  assert.equal(iso?.toISOString(), '2026-08-27T21:31:00.000Z');
});

test('respects standard time outside DST', () => {
  // 09:00 Eastern in January is EST (UTC-5) => 14:00Z
  const winter = parseRailDateTime('15-Jan-2026 09:00:00 AM');
  assert.equal(winter?.toISOString(), '2026-01-15T14:00:00.000Z');
});

test('rejects unparseable input instead of yielding an Invalid Date', () => {
  assert.equal(parseRailDateTime('not a date'), null);
  assert.equal(parseRailDateTime(''), null);
});

test('assigns after-midnight trains to the previous service day', () => {
  // 00:45 ET on the 28th belongs to the 27th's operating day.
  const lateNight = parseRailDateTime('28-Aug-2026 12:45:00 AM')!;
  assert.equal(serviceDateOf(lateNight), '2026-08-27');

  const evening = parseRailDateTime('27-Aug-2026 05:31:00 PM')!;
  assert.equal(serviceDateOf(evening), '2026-08-27');

  // 04:00 ET is past the cutoff and starts a new operating day.
  const earlyMorning = parseRailDateTime('28-Aug-2026 04:00:00 AM')!;
  assert.equal(serviceDateOf(earlyMorning), '2026-08-28');
});

test('classifies day types, treating holidays as Sunday service', () => {
  assert.equal(dayTypeOf('2026-08-27'), 'weekday'); // Thursday
  assert.equal(dayTypeOf('2026-08-29'), 'saturday');
  assert.equal(dayTypeOf('2026-08-30'), 'sunday');
  assert.equal(dayTypeOf('2026-07-04'), 'sunday'); // holiday, a Saturday
  assert.equal(dayTypeOf('2026-12-25'), 'sunday'); // holiday, a Friday
});

test('reads the nested UPPER_SNAKE payload shape', () => {
  const payload = {
    STATION: {
      STATION_2CHAR: 'NY',
      ITEMS: {
        ITEM: [
          {
            TRAIN_ID: '3856',
            LINE: 'Morris & Essex Line',
            LINEABBREVIATION: 'ME',
            DESTINATION: 'Dover',
            SCHED_DEP_DATE: '27-Aug-2026 05:31:00 PM',
            TRACK: '4',
            STATUS: 'ON TIME',
            SEC_LATE: '0',
          },
        ],
      },
    },
  };

  const rows = client.parseBoard(payload);
  assert.equal(rows.length, 1);
  assert.equal(rows[0].trainId, '3856');
  assert.equal(rows[0].lineCode, 'ME');
  assert.equal(rows[0].track, '4');
  assert.equal(rows[0].scheduledDep.toISOString(), '2026-08-27T21:31:00.000Z');
});

test('reads a flat PascalCase payload from the other API generation', () => {
  const rows = client.parseBoard([
    {
      trainId: '3856',
      line: 'Morris & Essex Line',
      destination: 'Dover',
      scheduledDepartureDate: '2026-08-27T17:31:00',
      track: '4',
      status: 'ON TIME',
      secondsLate: 0,
    },
  ]);
  assert.equal(rows.length, 1);
  assert.equal(rows[0].trainId, '3856');
  assert.equal(rows[0].track, '4');
});

test('collapses every "no track yet" spelling to null', () => {
  const rows = client.parseBoard(
    ['', '   ', '-', 'TBD', 'tbd'].map((track, i) => ({
      TRAIN_ID: `100${i}`,
      DESTINATION: 'Dover',
      SCHED_DEP_DATE: '27-Aug-2026 05:31:00 PM',
      TRACK: track,
    })),
  );
  assert.equal(rows.length, 5);
  for (const row of rows) assert.equal(row.track, null);
});

test('drops rows that cannot be joined to history', () => {
  const rows = client.parseBoard([
    { TRAIN_ID: '', SCHED_DEP_DATE: '27-Aug-2026 05:31:00 PM' },
    { TRAIN_ID: '3856', SCHED_DEP_DATE: 'garbage' },
    { TRAIN_ID: '3857', SCHED_DEP_DATE: '27-Aug-2026 05:31:00 PM' },
  ]);
  assert.equal(rows.length, 1);
  assert.equal(rows[0].trainId, '3857');
});

test('reports a payload it cannot understand rather than silently collecting nothing', () => {
  assert.throws(() => client.parseBoard({ error: 'invalid token' }), /could not locate/);
});
