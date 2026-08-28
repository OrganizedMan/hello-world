import assert from 'node:assert/strict';
import { mkdtempSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { test } from 'node:test';
import { dayTypeOf, parseRailDateTime, serviceDateOf } from '@nypenn/shared';
import { NjtClient, NjtError } from '../src/njt.js';

const makeClient = () =>
  new NjtClient({
    baseUrl: 'http://example.invalid',
    username: 'u',
    password: 'p',
    station: 'NY',
    requestTimeoutMs: 1000,
    tokenPath: join(mkdtempSync(join(tmpdir(), 'njt-')), 'token.json'),
    maxTokensPerDay: 4,
  });

const client = makeClient();

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

/**
 * A feed error has to say enough to act on. The report that prompted this was
 * 120 consecutive `getToken returned HTTP 500` lines over ten hours -- enough
 * to know something was wrong, not enough to know what, because the status
 * alone cannot distinguish the portal being down from it rejecting the shape
 * of the request. NJT's own body says which; it was being discarded.
 */
test('a failed request carries what the API said, not just the status', async () => {
  const original = globalThis.fetch;
  globalThis.fetch = (async () =>
    new Response('{"error":"invalid client"}', { status: 500 })) as typeof fetch;

  try {
    await assert.rejects(
      () => client.fetchBoard(),
      (err: Error) => {
        assert.match(err.message, /getToken returned HTTP 500/);
        assert.match(err.message, /invalid client/, 'the response body must survive');
        return true;
      },
    );
  } finally {
    globalThis.fetch = original;
  }
});

test('an error body that is huge or empty stays loggable every 20 seconds', async () => {
  const original = globalThis.fetch;

  globalThis.fetch = (async () =>
    new Response('x'.repeat(10_000), { status: 502 })) as typeof fetch;
  try {
    await assert.rejects(
      () => client.fetchBoard(),
      (err: Error) => {
        assert.ok(err.message.length < 300, `unbounded error message: ${err.message.length}`);
        assert.match(err.message, /\.\.\.$/);
        return true;
      },
    );

    globalThis.fetch = (async () => new Response('', { status: 503 })) as typeof fetch;
    await assert.rejects(
      () => client.fetchBoard(),
      (err: Error) => {
        // No body, so no trailing colon dangling off the end of the message.
        assert.equal(err.message, 'getToken returned HTTP 503');
        return true;
      },
    );
  } finally {
    globalThis.fetch = original;
  }
});

/**
 * The published contract, from NJTRANSIT_RailData_API_V2.
 *
 * These are the parts that were guessed wrong for months and could not be
 * caught by any test that did not know the real shapes: multipart rather than
 * urlencoded, the token as a form field rather than a header, getTrainSchedule
 * rather than getStationSchedule, and application errors reported with HTTP
 * 200 rather than a status.
 */

interface Sent {
  url: string;
  contentType: string;
  fields: Record<string, string>;
}

/** Stub fetch, recording each request and replying from a queue of bodies. */
function stubFetch(replies: Array<{ status?: number; body: string }>): {
  sent: Sent[];
  restore: () => void;
} {
  const original = globalThis.fetch;
  const sent: Sent[] = [];
  let n = 0;

  globalThis.fetch = (async (url: string, init: RequestInit) => {
    // Built as a real Request so the Content-Type under test is the one fetch
    // derives from the body, boundary and all -- not one the test invented.
    const req = new Request(String(url), init);
    const fields: Record<string, string> = {};
    for (const [k, v] of await req.formData()) fields[k] = String(v);
    sent.push({
      url: String(url),
      contentType: req.headers.get('content-type') ?? '',
      fields,
    });
    const reply = replies[Math.min(n++, replies.length - 1)];
    return new Response(reply.body, { status: reply.status ?? 200 });
  }) as unknown as typeof fetch;

  return { sent, restore: () => { globalThis.fetch = original; } };
}

const TOKEN_OK = JSON.stringify({ Authenticated: 'True', UserToken: 'tok-123' });
const BOARD = JSON.stringify({
  STATION_2CHAR: 'NY',
  STATIONNAME: 'New York Penn Station',
  STATIONMSGS: [],
  ITEMS: [
    {
      SCHED_DEP_DATE: '30-May-2024 11:56:00 AM',
      DESTINATION: 'Dover',
      TRACK: '4',
      LINE: 'Morris & Essex Line',
      TRAIN_ID: '6643',
      STATUS: 'in 13 Min',
      SEC_LATE: '120',
      LINEABBREVIATION: 'ME',
    },
  ],
});

test('authenticates and polls exactly as the published contract specifies', async () => {
  const { sent, restore } = stubFetch([{ body: TOKEN_OK }, { body: BOARD }]);
  try {
    const departures = await makeClient().fetchBoard();

    const [token, board] = sent;
    assert.match(token.url, /\/getToken$/);
    assert.match(
      token.contentType,
      /^multipart\/form-data; boundary=/,
      'urlencoded makes the API see no parameters and answer "Missing user account."',
    );
    assert.deepEqual(token.fields, { username: 'u', password: 'p' });

    assert.match(board.url, /\/getTrainSchedule$/, 'getStationSchedule is capped at 200/day');
    assert.equal(board.fields.token, 'tok-123', 'the token is a form field, not a header');
    assert.equal(board.fields.station, 'NY');
    assert.equal(board.fields.username, 'u', 'the portal examples send username with the token');

    assert.equal(departures.length, 1);
    assert.equal(departures[0].trainId, '6643');
    assert.equal(departures[0].track, '4');
    assert.equal(departures[0].secondsLate, 120);
  } finally {
    restore();
  }
});

test('an application error reported with HTTP 200 is still an error', async () => {
  const { restore } = stubFetch([{ body: JSON.stringify({ errorMessage: 'Missing user account.' }) }]);
  try {
    await assert.rejects(
      () => makeClient().fetchBoard(),
      (err: Error) => {
        assert.match(err.message, /Missing user account/);
        return true;
      },
    );
  } finally {
    restore();
  }
});

test('a bare Null says the API saw no parameters, rather than parsing as data', async () => {
  const { restore } = stubFetch([{ body: 'Null' }]);
  try {
    await assert.rejects(() => makeClient().fetchBoard(), /no usable parameters/);
  } finally {
    restore();
  }
});

test('an expired token is renewed once, since the API reports it as 200', async () => {
  const { sent, restore } = stubFetch([
    { body: TOKEN_OK },
    { body: JSON.stringify({ errorMessage: 'Invalid token.' }) },
    { body: JSON.stringify({ Authenticated: 'True', UserToken: 'tok-456' }) },
    { body: BOARD },
  ]);
  try {
    const departures = await makeClient().fetchBoard();
    assert.equal(departures.length, 1);
    assert.deepEqual(
      sent.map((s) => s.url.split('/').pop()),
      ['getToken', 'getTrainSchedule', 'getToken', 'getTrainSchedule'],
    );
    assert.equal(sent[3].fields.token, 'tok-456');
  } finally {
    restore();
  }
});

test('the token is cached on disk, so restarts do not spend the daily allowance', async () => {
  const tokenPath = join(mkdtempSync(join(tmpdir(), 'njt-')), 'token.json');
  const cfg = {
    baseUrl: 'http://example.invalid',
    username: 'u',
    password: 'p',
    station: 'NY',
    requestTimeoutMs: 1000,
    tokenPath,
    maxTokensPerDay: 4,
  };

  const first = stubFetch([{ body: TOKEN_OK }, { body: BOARD }]);
  try {
    await new NjtClient(cfg).fetchBoard();
    assert.equal(first.sent.length, 2);
  } finally {
    first.restore();
  }

  // A brand-new client, as after a systemd restart: no getToken this time.
  const second = stubFetch([{ body: BOARD }]);
  try {
    await new NjtClient(cfg).fetchBoard();
    assert.deepEqual(second.sent.map((s) => s.url.split('/').pop()), ['getTrainSchedule']);
    assert.equal(second.sent[0].fields.token, 'tok-123');
  } finally {
    second.restore();
  }
});

test('it stops asking for tokens before the API locks the account out', async () => {
  const tokenPath = join(mkdtempSync(join(tmpdir(), 'njt-')), 'token.json');
  const cfg = {
    baseUrl: 'http://example.invalid',
    username: 'u',
    password: 'p',
    station: 'NY',
    requestTimeoutMs: 1000,
    tokenPath,
    maxTokensPerDay: 2,
  };

  // Every board call rejects the token, so each poll wants a fresh one.
  const { sent, restore } = stubFetch([
    { body: TOKEN_OK },
    { body: JSON.stringify({ errorMessage: 'Invalid token.' }) },
  ]);
  try {
    for (let i = 0; i < 6; i += 1) {
      await assert.rejects(() => new NjtClient(cfg).fetchBoard());
    }
    const tokenCalls = sent.filter((s) => s.url.endsWith('getToken')).length;
    assert.ok(
      tokenCalls <= 2,
      `spent ${tokenCalls} getToken calls against a budget of 2; the API allows 10 a day`,
    );
  } finally {
    restore();
  }
});

test('a rate-limit reply is recognised, so the loop does not chase it', async () => {
  const { restore } = stubFetch([
    { body: JSON.stringify({ errorMessage: 'Daily usage limit:10. Your current daily usage: 11' }) },
  ]);
  try {
    await assert.rejects(
      () => makeClient().fetchBoard(),
      (err: NjtError) => {
        assert.ok(err.rateLimited, 'must be recognisable as a lockout, not a transient failure');
        return true;
      },
    );
  } finally {
    restore();
  }
});
