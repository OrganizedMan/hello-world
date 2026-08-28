import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { openDb } from '@nypenn/shared';
import { BoardService } from './board.js';
import { Predictor } from './predictor.js';
import { createApp } from './app.js';

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

const app = createApp({ board, predictor, clientDir: join(here, '../../client/dist') });

app.listen(PORT, () => {
  console.log(`nypenn server listening on :${PORT} (db ${DB_PATH}, read-only)`);
});
