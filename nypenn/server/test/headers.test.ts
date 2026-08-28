import assert from 'node:assert/strict';
import { mkdtempSync, mkdirSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { after, before, test } from 'node:test';
import type { AddressInfo } from 'node:net';
import type { Server } from 'node:http';
import { createApp } from '../src/app.js';
import type { Services } from '../src/services.js';

/**
 * These assert on the response the Pi actually sends, not on the helmet options
 * that produced it. The bug this guards against shipped as a correct-looking
 * config: helmet's defaults added `upgrade-insecure-requests`, every browser
 * except the one on localhost rewrote the bundle URL to https://, the request
 * died against a plain-HTTP port, and the board rendered as an empty page with
 * a 200 in the access log and nothing in the server's output.
 */

/** A built client, reduced to the two files that have to load for anything to render. */
function fixtureClientDir(): string {
  const dir = mkdtempSync(join(tmpdir(), 'nypenn-client-'));
  mkdirSync(join(dir, 'assets'));
  writeFileSync(
    join(dir, 'index.html'),
    `<!doctype html><html><head><script type="module" crossorigin src="/assets/app.js"></script>` +
      `</head><body><div id="root"></div></body></html>`,
  );
  writeFileSync(join(dir, 'assets', 'app.js'), 'export const mounted = true;\n');
  return dir;
}

const stubServices = () =>
  ({
    board: { health: () => ({}), departures: () => [], trainHistory: () => [] },
    predictor: { backtest: () => ({}) },
  }) as unknown as Services;

let server: Server;
let origin: string;

before(async () => {
  const app = createApp({ services: stubServices, clientDir: fixtureClientDir() });
  await new Promise<void>((resolve) => {
    server = app.listen(0, '127.0.0.1', resolve);
  });
  origin = `http://127.0.0.1:${(server.address() as AddressInfo).port}`;
});

after(() => server.close());

test('the page does not ask the browser to upgrade its own bundle to https', async () => {
  const res = await fetch(`${origin}/`);
  const csp = res.headers.get('content-security-policy') ?? '';

  assert.ok(csp.length > 0, 'expected a Content-Security-Policy to still be set');
  assert.ok(
    !csp.includes('upgrade-insecure-requests'),
    'upgrade-insecure-requests rewrites the bundle URL to https, which nothing serves ' +
      'on this port. Every device except localhost gets a blank page.',
  );
});

test('no HSTS, which a browser discards over plain HTTP anyway', async () => {
  const res = await fetch(`${origin}/`);
  assert.equal(res.headers.get('strict-transport-security'), null);
});

test('the CSP still allows the scripts and styles the page loads', async () => {
  const res = await fetch(`${origin}/`);
  const csp = res.headers.get('content-security-policy') ?? '';

  // Everything the client needs is same-origin; anything else should stay blocked.
  assert.ok(csp.includes("script-src 'self'"), csp);
  assert.ok(csp.includes("object-src 'none'"), csp);
  assert.ok(csp.includes("default-src 'self'"), csp);
});

test('the bundle the page references is served over the scheme it was requested on', async () => {
  const html = await (await fetch(`${origin}/`)).text();
  const src = /<script[^>]+src="([^"]+)"/.exec(html)?.[1];
  assert.ok(src, `no script tag in the served index.html: ${html}`);

  const asset = await fetch(new URL(src, origin));
  assert.equal(asset.status, 200, `the page's own bundle did not load: ${src}`);
});

test('an unbuilt client says so instead of serving a blank page', async () => {
  const app = createApp({
    services: stubServices,
    clientDir: join(tmpdir(), 'nypenn-client-does-not-exist'),
  });
  const s = await new Promise<Server>((resolve) => {
    const listening = app.listen(0, '127.0.0.1', () => resolve(listening));
  });
  try {
    const res = await fetch(`http://127.0.0.1:${(s.address() as AddressInfo).port}/`);
    assert.equal(res.status, 404);
    const body = (await res.json()) as { error: string };
    assert.match(body.error, /client not built/);
  } finally {
    s.close();
  }
});
