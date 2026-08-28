import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { createApp } from './app.js';
import { LazyServices } from './services.js';

const here = dirname(fileURLToPath(import.meta.url));

const PORT = Number(process.env.PORT ?? 3005);
const DB_PATH = process.env.NYPENN_DB ?? 'data/nypenn.db';

/** Cold-start fallbacks, used only until a train has real history. */
const linePriors = JSON.parse(process.env.LINE_PRIORS ?? '{}') as Record<string, string>;

// Read-only, and opened lazily: the collector owns every write, and it may not
// have created the file yet. See services.ts — binding the port regardless is
// what makes the failure diagnosable instead of a refused connection.
const services = new LazyServices(DB_PATH, linePriors);

const app = createApp({ services: () => services.get(), clientDir: join(here, '../../client/dist') });

app.listen(PORT, () => {
  console.log(`nypenn server listening on :${PORT} (db ${DB_PATH}, read-only)`);
  if (!services.get()) {
    console.warn(
      `waiting for ${DB_PATH}; the collector creates it. The board will load ` +
        `and report itself unhealthy until then. Check: systemctl status nypenn-collector`,
    );
  }
});
