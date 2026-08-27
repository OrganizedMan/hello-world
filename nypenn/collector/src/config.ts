/** Collector configuration, all overridable by environment. */
export interface Config {
  dbPath: string;
  njt: {
    baseUrl: string;
    username: string;
    password: string;
    station: string;
    requestTimeoutMs: number;
  };
  pollIntervalMs: number;
  /** Max age of buffered changes before they are committed. */
  flushIntervalMs: number;
  /** Heartbeat cadence, so a flush happens even on a completely quiet board. */
  heartbeatIntervalMs: number;
  /** Grace after scheduled departure before a vanished train is resolved. */
  resolveGraceMs: number;
  observationRetentionDays: number;
}

function required(name: string): string {
  const value = process.env[name];
  if (!value) {
    throw new Error(
      `Missing required environment variable ${name}. ` +
        `Copy nypenn/.env.example to nypenn/.env and fill it in.`,
    );
  }
  return value;
}

function num(name: string, fallback: number): number {
  const raw = process.env[name];
  if (!raw) return fallback;
  const parsed = Number(raw);
  if (!Number.isFinite(parsed)) throw new Error(`${name} must be a number, got "${raw}"`);
  return parsed;
}

export function loadConfig(): Config {
  return {
    dbPath: process.env.NYPENN_DB ?? 'data/nypenn.db',
    njt: {
      baseUrl: process.env.NJT_BASE_URL ?? 'https://raildata.njtransit.com/api/TrainData',
      username: required('NJT_USERNAME'),
      password: required('NJT_PASSWORD'),
      // "NY" is New York Penn Station in NJT's two-character station codes.
      station: process.env.NJT_STATION ?? 'NY',
      requestTimeoutMs: num('NJT_TIMEOUT_MS', 15_000),
    },
    pollIntervalMs: num('POLL_INTERVAL_MS', 20_000),
    flushIntervalMs: num('FLUSH_INTERVAL_MS', 30_000),
    heartbeatIntervalMs: num('HEARTBEAT_INTERVAL_MS', 300_000),
    resolveGraceMs: num('RESOLVE_GRACE_MS', 120_000),
    observationRetentionDays: num('OBSERVATION_RETENTION_DAYS', 14),
  };
}
