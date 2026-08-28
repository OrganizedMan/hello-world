import assert from 'node:assert/strict';
import { mkdtempSync, mkdirSync, writeFileSync, rmSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { test } from 'node:test';
import type { AddressInfo } from 'node:net';
import type { Server } from 'node:http';
import Database from 'better-sqlite3';
import { createApp } from '../src/app.js';
import { LazyServices } from '../src/services.js';

/**
 * The collector owns the database and the server only reads it, so the server
 * routinely starts before the file exists — on every fresh install, and
 * indefinitely whenever the collector is misconfigured and dies before
 * creating it. Opening it eagerly turned that into SQLITE_CANTOPEN at import
 * time, so the process died before listen() and the port refused connections
 * while systemd restarted it every five seconds.
 *
 * These assert the server is reachable and honest in that state, because a
 * refused connection tells whoever is debugging it nothing at all.
 */

/** The schema the collector applies, as the only writer of this database. */
const SCHEMA = `
  CREATE TABLE collector_state (id INTEGER PRIMARY KEY, last_poll_at TEXT);
  CREATE TABLE departures (
    train_id TEXT NOT NULL, service_date TEXT NOT NULL, line TEXT NOT NULL,
    line_code TEXT NOT NULL DEFAULT '', destination TEXT NOT NULL DEFAULT '',
    scheduled_dep TEXT NOT NULL DEFAULT '', final_track TEXT,
    track_posted_at TEXT, seconds_late INTEGER NOT NULL DEFAULT 0,
    resolved_at TEXT NOT NULL DEFAULT '',
    PRIMARY KEY (train_id, service_date)
  );
  CREATE VIEW live_board AS
    SELECT train_id, service_date, line, line_code, destination, scheduled_dep,
           final_track AS track, '' AS status, seconds_late
      FROM departures;
`;

async function serve(dbPath: string): Promise<{ origin: string; close: () => void }> {
  const lazy = new LazyServices(dbPath, {});
  const app = createApp({ services: () => lazy.get(), clientDir: mkdtempSync(join(tmpdir(), 'c-')) });
  const server = await new Promise<Server>((resolve) => {
    const s: Server = app.listen(0, '127.0.0.1', () => resolve(s));
  });
  return {
    origin: `http://127.0.0.1:${(server.address() as AddressInfo).port}`,
    close: () => server.close(),
  };
}

test('the server still listens when the collector has not created the database', async () => {
  const missing = join(mkdtempSync(join(tmpdir(), 'nypenn-')), 'nypenn.db');
  const { origin, close } = await serve(missing);
  try {
    const res = await fetch(`${origin}/api/health`);
    assert.equal(res.status, 200, 'the port must answer, not refuse the connection');
    const health = (await res.json()) as { ok: boolean; lastPollAt: string | null };
    assert.equal(health.ok, false, 'it must not claim to be healthy with no data behind it');
    assert.equal(health.lastPollAt, null);
  } finally {
    close();
  }
});

test('the board renders empty rather than erroring while the collector is missing', async () => {
  const missing = join(mkdtempSync(join(tmpdir(), 'nypenn-')), 'nypenn.db');
  const { origin, close } = await serve(missing);
  try {
    const res = await fetch(`${origin}/api/board`);
    assert.equal(res.status, 200);
    const body = (await res.json()) as { departures: unknown[]; health: { ok: boolean } };
    assert.deepEqual(body.departures, []);
    assert.equal(body.health.ok, false);
  } finally {
    close();
  }
});

test('accuracy says which service to go look at instead of returning zeroes', async () => {
  const missing = join(mkdtempSync(join(tmpdir(), 'nypenn-')), 'nypenn.db');
  const { origin, close } = await serve(missing);
  try {
    const res = await fetch(`${origin}/api/accuracy`);
    assert.equal(res.status, 503);
    assert.match(((await res.json()) as { error: string }).error, /nypenn-collector/);
  } finally {
    close();
  }
});

test('the collector appearing later is picked up without restarting the server', async () => {
  const dir = mkdtempSync(join(tmpdir(), 'nypenn-'));
  const dbPath = join(dir, 'nypenn.db');
  const { origin, close } = await serve(dbPath);
  try {
    const before = (await (await fetch(`${origin}/api/accuracy`)).json()) as { error?: string };
    assert.ok(before.error, 'expected the waiting state first');

    // The collector starts up and creates its database.
    const db = new Database(dbPath);
    db.exec(SCHEMA);
    db.close();

    const after = await fetch(`${origin}/api/accuracy`);
    assert.equal(after.status, 200, 'the server must recover on its own, with no restart');
  } finally {
    close();
    rmSync(dir, { recursive: true, force: true });
  }
});

test('a database that exists but has no schema yet is treated as not ready', async () => {
  const dir = mkdtempSync(join(tmpdir(), 'nypenn-'));
  const dbPath = join(dir, 'nypenn.db');
  // The collector creates the file, then applies the DDL. In between, the
  // prepared statements in BoardService cannot resolve.
  new Database(dbPath).close();

  const { origin, close } = await serve(dbPath);
  try {
    const res = await fetch(`${origin}/api/health`);
    assert.equal(res.status, 200, 'a half-created database must not crash the server');
    assert.equal(((await res.json()) as { ok: boolean }).ok, false);
  } finally {
    close();
    rmSync(dir, { recursive: true, force: true });
  }
});

// Keeps the fixture helpers above honest about what a built client looks like.
test('the client directory is served from wherever it is handed in', async () => {
  const dir = mkdtempSync(join(tmpdir(), 'nypenn-client-'));
  mkdirSync(join(dir, 'assets'));
  writeFileSync(join(dir, 'index.html'), '<!doctype html><div id="root"></div>');

  const lazy = new LazyServices(join(dir, 'nope.db'), {});
  const app = createApp({ services: () => lazy.get(), clientDir: dir });
  const server = await new Promise<Server>((resolve) => {
    const s: Server = app.listen(0, '127.0.0.1', () => resolve(s));
  });
  try {
    const res = await fetch(`http://127.0.0.1:${(server.address() as AddressInfo).port}/`);
    assert.equal(res.status, 200);
    assert.match(await res.text(), /id="root"/);
  } finally {
    server.close();
    rmSync(dir, { recursive: true, force: true });
  }
});
