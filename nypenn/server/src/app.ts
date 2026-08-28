import { readFileSync } from 'node:fs';
import { join } from 'node:path';
import express, { type Express } from 'express';
import helmet from 'helmet';
import type { BoardService } from './board.js';
import type { Predictor } from './predictor.js';

export interface AppDeps {
  board: BoardService;
  predictor: Predictor;
  /** Directory holding the built client (index.html and assets/). */
  clientDir: string;
}

/**
 * Helmet's defaults assume the app is served over TLS. This one is not: it
 * runs on a Pi at http://<address>:3005 on the LAN and over Tailscale, where
 * there is no certificate and no way to get one for a bare address.
 *
 * Two of those defaults are actively wrong here:
 *
 *   upgrade-insecure-requests  The browser rewrites the page's own bundle URL
 *                              from http:// to https://. Nothing is listening
 *                              for TLS on 3005, so the script and stylesheet
 *                              fail to load, #root is never mounted, and the
 *                              page renders blank with no visible error.
 *                              localhost is exempt from the upgrade, so this
 *                              breaks every device except the Pi itself.
 *   Strict-Transport-Security  Ignored by browsers when it arrives over plain
 *                              HTTP (RFC 6797 §8.1), so it only ever misleads
 *                              whoever reads the headers next.
 *
 * Cross-Origin-Opener-Policy is dropped for the same reason: the browser
 * discards it on an insecure origin and logs an error for it, which is a red
 * herring for anyone debugging this page.
 *
 * Everything else helmet sets — the rest of the CSP, nosniff, frameguard,
 * referrer policy — works fine over plain HTTP and is kept.
 */
function localNetworkHelmet() {
  return helmet({
    contentSecurityPolicy: {
      useDefaults: true,
      directives: { upgradeInsecureRequests: null },
    },
    strictTransportSecurity: false,
    crossOriginOpenerPolicy: false,
  });
}

export function createApp({ board, predictor, clientDir }: AppDeps): Express {
  const app = express();
  app.use(localNetworkHelmet());

  app.get('/api/health', (_req, res) => res.json(board.health()));

  app.get('/api/board', (_req, res) => {
    res.json({ departures: board.departures(), health: board.health() });
  });

  app.get('/api/train/:trainId/history', (req, res) => {
    res.json({ history: board.trainHistory(req.params.trainId) });
  });

  app.get('/api/accuracy', (req, res) => {
    const to = typeof req.query.to === 'string' ? req.query.to : today();
    const from = typeof req.query.from === 'string' ? req.query.from : shift(to, -30);
    res.json(predictor.backtest(from, to));
  });

  // Serve the built client, falling through to index.html for client routing.
  app.use(express.static(clientDir));
  app.get('*', (_req, res) => {
    try {
      res.type('html').send(readFileSync(join(clientDir, 'index.html'), 'utf8'));
    } catch {
      res.status(404).json({ error: 'client not built; run npm run build' });
    }
  });

  return app;
}

function today(): string {
  return new Date().toISOString().slice(0, 10);
}

function shift(date: string, days: number): string {
  return new Date(Date.parse(`${date}T12:00:00Z`) + days * 86400_000).toISOString().slice(0, 10);
}
