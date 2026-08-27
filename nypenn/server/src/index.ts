import { readFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import express from 'express';
import helmet from 'helmet';
import rateLimit from 'express-rate-limit';
import { openDb } from '@nypenn/shared';
import { issueToken, parseAccounts, requireAuth, verify } from './auth.js';
import { BoardService } from './board.js';
import { Predictor } from './predictor.js';

const here = dirname(fileURLToPath(import.meta.url));

const PORT = Number(process.env.PORT ?? 3005);
const DB_PATH = process.env.NYPENN_DB ?? 'data/nypenn.db';
const JWT_SECRET = process.env.JWT_SECRET;

if (!JWT_SECRET) {
  console.error('JWT_SECRET is required. Generate one with: openssl rand -hex 32');
  process.exit(1);
}

const accounts = parseAccounts(process.env.NYPENN_USERS);
if (accounts.length === 0) {
  console.error('NYPENN_USERS is empty. Add an account with: npm run adduser -w @nypenn/server');
  process.exit(1);
}

/** Cold-start fallbacks, used only until a train has real history. */
const linePriors = JSON.parse(process.env.LINE_PRIORS ?? '{}') as Record<string, string>;

// Read-only: the collector owns every write, and opening read-only makes it
// impossible for a server bug to corrupt the history.
const db = openDb(DB_PATH, { readonly: true });
const predictor = new Predictor(db, linePriors);
const board = new BoardService(db, predictor);

const app = express();
app.use(helmet());
app.use(express.json({ limit: '8kb' }));

app.post(
  '/api/login',
  rateLimit({ windowMs: 15 * 60_000, limit: 10, standardHeaders: true, legacyHeaders: false }),
  (req, res) => {
    const { username, password } = req.body ?? {};
    const account = accounts.find((a) => a.username === username);

    // Same response either way, so the endpoint does not reveal which
    // usernames exist.
    if (!account || typeof password !== 'string' || !verify(account, password)) {
      res.status(401).json({ error: 'invalid credentials' });
      return;
    }
    res.json({ token: issueToken(account.username, JWT_SECRET), username: account.username });
  },
);

// Unauthenticated so an uptime check can reach it without a token; it exposes
// only liveness counters, never departure data.
app.get('/api/health', (_req, res) => res.json(board.health()));

const auth = requireAuth(JWT_SECRET);

app.get('/api/board', auth, (_req, res) => {
  res.json({ departures: board.departures(), health: board.health() });
});

app.get('/api/train/:trainId/history', auth, (req, res) => {
  res.json({ history: board.trainHistory(req.params.trainId) });
});

app.get('/api/accuracy', auth, (req, res) => {
  const to = typeof req.query.to === 'string' ? req.query.to : today();
  const from = typeof req.query.from === 'string' ? req.query.from : shift(to, -30);
  res.json(predictor.backtest(from, to));
});

// Serve the built client, falling through to index.html for client routing.
const clientDir = join(here, '../../client/dist');
app.use(express.static(clientDir));
app.get('*', (_req, res) => {
  try {
    res.type('html').send(readFileSync(join(clientDir, 'index.html'), 'utf8'));
  } catch {
    res.status(404).json({ error: 'client not built; run npm run build' });
  }
});

app.listen(PORT, () => {
  console.log(`nypenn server listening on :${PORT} (db ${DB_PATH}, read-only)`);
});

function today(): string {
  return new Date().toISOString().slice(0, 10);
}

function shift(date: string, days: number): string {
  return new Date(Date.parse(`${date}T12:00:00Z`) + days * 86400_000).toISOString().slice(0, 10);
}
