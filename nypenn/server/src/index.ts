import { readFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import express from 'express';
import helmet from 'helmet';
import { openDb } from '@nypenn/shared';
import { BoardService } from './board.js';
import { Predictor } from './predictor.js';

const here = dirname(fileURLToPath(import.meta.url));

const PORT = Number(process.env.PORT ?? 3005);
const DB_PATH = process.env.NYPENN_DB ?? 'data/nypenn.db';

/** Cold-start fallbacks, used only until a train has real history. */
const linePriors = JSON.parse(process.env.LINE_PRIORS ?? '{}') as Record<string, string>;

// Read-only: the collector owns every write, and opening read-only makes it
// impossible for a server bug to corrupt the history.
const db = openDb(DB_PATH, { readonly: true });
const predictor = new Predictor(db, linePriors);
const board = new BoardService(db, predictor);

const app = express();
app.use(helmet());
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
