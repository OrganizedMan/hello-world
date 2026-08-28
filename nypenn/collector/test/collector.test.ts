import assert from 'node:assert/strict';
import { test } from 'node:test';
import { openDb } from '@nypenn/shared';
import { Collector } from '../src/collector.js';
import type { Config } from '../src/config.js';
import type { RawDeparture } from '../src/njt.js';
import { Store } from '../src/store.js';

const cfg: Config = {
  dbPath: ':memory:',
  njt: { baseUrl: '', username: '', password: '', station: 'NY', requestTimeoutMs: 1000 },
  pollIntervalMs: 20_000,
  flushIntervalMs: 0, // flush every poll, so assertions see committed state
  heartbeatIntervalMs: 300_000,
  resolveGraceMs: 120_000,
  observationRetentionDays: 14,
};

/** A client stub whose board the test drives directly. */
class FakeClient {
  board: RawDeparture[] = [];
  calls = 0;
  async fetchBoard(): Promise<RawDeparture[]> {
    this.calls += 1;
    return this.board;
  }
}

function train(over: Partial<RawDeparture> = {}): RawDeparture {
  return {
    trainId: '3856',
    line: 'Morris & Essex Line',
    lineCode: 'ME',
    destination: 'Dover',
    scheduledDep: new Date('2026-08-27T21:31:00Z'),
    track: null,
    status: 'ON TIME',
    secondsLate: 0,
    ...over,
  };
}

function harness(config: Config = cfg) {
  const db = openDb(':memory:');
  const store = new Store(db);
  const client = new FakeClient();
  const collector = new Collector(config, client as never, store, () => {});
  collector.start();
  const count = (table: string) =>
    (db.prepare(`SELECT COUNT(*) AS n FROM ${table}`).get() as { n: number }).n;
  return { db, store, client, collector, count };
}

test('a first sighting is recorded once', async () => {
  const h = harness();
  h.client.board = [train()];
  await h.collector.poll(new Date('2026-08-27T20:00:00Z'));
  assert.equal(h.count('observations'), 1);
  assert.equal(h.count('live_board'), 1);
});

test('an unchanged board writes nothing further', async () => {
  const h = harness();
  h.client.board = [train()];

  await h.collector.poll(new Date('2026-08-27T20:00:00Z'));
  const afterFirst = h.count('observations');

  // Twenty more polls with an identical board — the common case all day.
  for (let i = 1; i <= 20; i++) {
    await h.collector.poll(new Date(Date.parse('2026-08-27T20:00:00Z') + i * 20_000));
  }

  assert.equal(h.client.calls, 21, 'should still poll the API every cycle');
  assert.equal(
    h.count('observations'),
    afterFirst,
    'an unchanging board must not produce any rows beyond the first sighting',
  );
});

test('a track posting is captured as a transition', async () => {
  const h = harness();
  h.client.board = [train()];
  await h.collector.poll(new Date('2026-08-27T20:00:00Z'));

  h.client.board = [train({ track: '4' })];
  await h.collector.poll(new Date('2026-08-27T21:25:00Z'));

  assert.equal(h.count('observations'), 2);
  const latest = h.db
    .prepare(`SELECT track FROM observations ORDER BY id DESC LIMIT 1`)
    .get() as { track: string };
  assert.equal(latest.track, '4');
});

test('status and delay changes are captured, and repeats are not', async () => {
  const h = harness();
  h.client.board = [train()];
  await h.collector.poll(new Date('2026-08-27T20:00:00Z'));

  h.client.board = [train({ status: 'DELAYED', secondsLate: 300 })];
  await h.collector.poll(new Date('2026-08-27T20:01:00Z'));
  await h.collector.poll(new Date('2026-08-27T20:02:00Z'));
  await h.collector.poll(new Date('2026-08-27T20:03:00Z'));

  assert.equal(h.count('observations'), 2, 'one baseline plus one change');
});

test('a departed train resolves into permanent history with its final track', async () => {
  const h = harness();
  h.client.board = [train({ track: '4' })];
  await h.collector.poll(new Date('2026-08-27T21:25:00Z'));

  // Train leaves the board after its scheduled departure.
  h.client.board = [];
  await h.collector.poll(new Date('2026-08-27T21:40:00Z'));

  const dep = h.db.prepare(`SELECT * FROM departures`).get() as Record<string, unknown>;
  assert.equal(dep.train_id, '3856');
  assert.equal(dep.service_date, '2026-08-27');
  assert.equal(dep.final_track, '4');
  assert.equal(dep.track_posted_at, '2026-08-27T21:25:00.000Z');
  assert.equal(h.count('live_board'), 0, 'resolved trains leave the live board');
});

test('the first track posting time is kept, not the latest', async () => {
  const h = harness();
  h.client.board = [train()];
  await h.collector.poll(new Date('2026-08-27T21:00:00Z'));

  h.client.board = [train({ track: '4' })];
  await h.collector.poll(new Date('2026-08-27T21:20:00Z'));

  // A later change must not reset the posting time we measure lead time from.
  h.client.board = [train({ track: '4', status: 'BOARDING' })];
  await h.collector.poll(new Date('2026-08-27T21:28:00Z'));

  h.client.board = [];
  await h.collector.poll(new Date('2026-08-27T21:40:00Z'));

  const dep = h.db.prepare(`SELECT track_posted_at FROM departures`).get() as { track_posted_at: string };
  assert.equal(dep.track_posted_at, '2026-08-27T21:20:00.000Z');
});

test('a train still on the board before departure is not resolved early', async () => {
  const h = harness();
  h.client.board = [train({ track: '4' })];
  await h.collector.poll(new Date('2026-08-27T21:00:00Z'));

  // Momentarily absent from the feed, but not yet due to depart.
  h.client.board = [];
  await h.collector.poll(new Date('2026-08-27T21:05:00Z'));

  assert.equal(h.count('departures'), 0);
});

test('a train that never gets a track still records a history row', async () => {
  const h = harness();
  h.client.board = [train()];
  await h.collector.poll(new Date('2026-08-27T21:00:00Z'));
  h.client.board = [];
  await h.collector.poll(new Date('2026-08-27T21:40:00Z'));

  const dep = h.db.prepare(`SELECT final_track FROM departures`).get() as { final_track: null };
  assert.equal(dep.final_track, null);
});

test('resuming from a restart keeps in-flight trains and their posting times', async () => {
  const db = openDb(':memory:');
  const store = new Store(db);
  const client = new FakeClient();

  const first = new Collector(cfg, client as never, store, () => {});
  first.start();
  client.board = [train({ track: '4' })];
  await first.poll(new Date('2026-08-27T21:20:00Z'));

  // Restart against the same database.
  const second = new Collector(cfg, client as never, store, () => {});
  second.start();
  assert.equal(second.inFlight, 1, 'in-flight trains survive a restart');

  client.board = [];
  await second.poll(new Date('2026-08-27T21:40:00Z'));

  const dep = db.prepare(`SELECT track_posted_at, final_track FROM departures`).get() as {
    track_posted_at: string;
    final_track: string;
  };
  assert.equal(dep.final_track, '4');
  assert.equal(dep.track_posted_at, '2026-08-27T21:20:00.000Z');
});

test('purging trims observations but never touches departures', async () => {
  const h = harness();
  h.client.board = [train({ track: '4' })];
  await h.collector.poll(new Date('2026-08-27T21:25:00Z'));
  h.client.board = [];
  await h.collector.poll(new Date('2026-08-27T21:40:00Z'));

  assert.equal(h.count('departures'), 1);
  assert.ok(h.count('observations') > 0);

  h.store.purgeObservations(0);

  assert.equal(h.count('observations'), 0, 'transition log is disposable');
  assert.equal(h.count('departures'), 1, 'history is not');
});
