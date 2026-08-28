import { mkdirSync, readFileSync, writeFileSync } from 'node:fs';
import { dirname } from 'node:path';
import { parseRailDateTime, toRailDateString } from '@nypenn/shared';

/**
 * Client for NJ Transit's real-time rail feed.
 *
 * NJT has shipped two API generations and the current portal issues a bearer
 * token in exchange for portal credentials. The request shape lives here and
 * nowhere else, so pointing this at a different generation is a one-file
 * change. Field extraction is deliberately tolerant: the two generations use
 * UPPER_SNAKE and PascalCase respectively for the same values.
 */

export interface NjtConfig {
  baseUrl: string;
  username: string;
  password: string;
  station: string;
  requestTimeoutMs: number;
  /**
   * Where the bearer token is cached between runs. getToken is capped at 10
   * calls per day, so a token held only in memory would be spent by restarts
   * alone -- see the budget in NjtClient.
   */
  tokenPath: string;
  /** Conservative ceiling on getToken calls per service day. API cap is 10. */
  maxTokensPerDay: number;
}

/** A departure row as the feed reports it, normalised. */
export interface RawDeparture {
  trainId: string;
  line: string;
  lineCode: string;
  destination: string;
  scheduledDep: Date;
  /** null when NJT has not yet posted a track. */
  track: string | null;
  status: string;
  secondsLate: number;
}

/** Pull the first present key from an object, whatever its casing. */
function field(row: Record<string, unknown>, ...names: string[]): string {
  for (const name of names) {
    const hit = Object.keys(row).find(
      (k) => k.toLowerCase().replace(/[_\s]/g, '') === name.toLowerCase().replace(/[_\s]/g, ''),
    );
    if (hit) {
      const value = row[hit];
      if (value !== null && value !== undefined && String(value).trim() !== '') {
        return String(value).trim();
      }
    }
  }
  return '';
}

/**
 * NJT reports an unassigned track inconsistently — empty string, a single
 * dash, or the literal "TBD". All of them mean "not yet announced", and
 * collapsing them to null keeps that ambiguity out of the history table.
 */
function normaliseTrack(raw: string): string | null {
  const t = raw.trim();
  if (!t || t === '-' || /^tbd$/i.test(t)) return null;
  return t.toUpperCase();
}

interface TokenCache {
  token: string;
  /** Rail service date the counter below belongs to. */
  day: string;
  issuedToday: number;
}

export class NjtClient {
  private cache: TokenCache | null = null;

  constructor(private readonly cfg: NjtConfig) {}

  /**
   * Every method is POST with multipart/form-data, and the token travels as a
   * form field named `token` rather than in an Authorization header. Both are
   * from the published contract; sending urlencoded instead makes the API see
   * no parameters at all and answer "Missing user account." to getToken, which
   * reads exactly like a credentials problem and is not one.
   *
   * Content-Type is deliberately not set by hand -- fetch derives it from the
   * FormData along with the multipart boundary, and a hand-written header
   * without a boundary is unparseable.
   */
  private async request(path: string, fields: Record<string, string>): Promise<unknown> {
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), this.cfg.requestTimeoutMs);

    try {
      const form = new FormData();
      for (const [key, value] of Object.entries(fields)) form.append(key, value);

      const res = await fetch(`${this.cfg.baseUrl.replace(/\/$/, '')}/${path}`, {
        method: 'POST',
        headers: { Accept: 'text/plain' },
        body: form,
        signal: controller.signal,
      });

      const text = (await res.text()).trim();

      if (!res.ok) {
        throw new NjtError(`${path} returned HTTP ${res.status}`, res.status, oneLine(text));
      }

      // The API answers 200 for its own failures, so status is not the signal.
      // A bare "Null" is what it returns for a missing or malformed parameter.
      if (!text || /^null$/i.test(text)) {
        throw new NjtError(
          `${path} returned Null, which means it saw no usable parameters`,
          res.status,
        );
      }

      let payload: unknown;
      try {
        payload = JSON.parse(text);
      } catch {
        throw new NjtError(`${path} returned a non-JSON body`, res.status, oneLine(text));
      }

      const message = errorMessageOf(payload);
      if (message) throw new NjtError(`${path} refused the request`, res.status, message);

      return payload;
    } finally {
      clearTimeout(timer);
    }
  }

  // --- token -------------------------------------------------------------

  private loadCache(): TokenCache | null {
    if (this.cache) return this.cache;
    try {
      const parsed = JSON.parse(readFileSync(this.cfg.tokenPath, 'utf8')) as Partial<TokenCache>;
      // An empty token is still worth loading: the day's attempt count lives
      // in the same record, and losing it is how the daily cap gets blown.
      this.cache = {
        token: typeof parsed.token === 'string' ? parsed.token : '',
        day: typeof parsed.day === 'string' ? parsed.day : '',
        issuedToday: Number(parsed.issuedToday) || 0,
      };
    } catch {
      // No cache yet, or an unreadable one. Either way, authenticate.
    }
    return this.cache;
  }

  private saveCache(cache: TokenCache): void {
    this.cache = cache;
    try {
      mkdirSync(dirname(this.cfg.tokenPath), { recursive: true });
      // 0600: this is a credential, and the Pi is a shared-ish machine.
      writeFileSync(this.cfg.tokenPath, JSON.stringify(cache), { mode: 0o600 });
    } catch {
      // A token that cannot be persisted still works for this process; the
      // cost is one more getToken after the next restart, not a failed poll.
    }
  }

  /**
   * Exchange portal credentials for a token, at most maxTokensPerDay times.
   *
   * The cap is ours, not the API's, and it exists because the API's own cap is
   * 10 a day and blowing it locks the account out until midnight -- taking the
   * rest of the day's history with it. A poll loop that re-authenticated on
   * every failure would spend all ten within four minutes.
   */
  private async authenticate(): Promise<string> {
    const today = toRailDateString(new Date());
    const cache = this.loadCache();
    const usedToday = cache && cache.day === today ? cache.issuedToday : 0;

    if (usedToday >= this.cfg.maxTokensPerDay) {
      throw new NjtError(
        `refusing to call getToken again today (${usedToday}/${this.cfg.maxTokensPerDay} used; ` +
          `the API allows 10 and locks the account out past that)`,
        429,
      );
    }

    // Counted before the call, not after. The API's cap counts accesses, so a
    // getToken that fails has still been spent -- and counting only successes
    // is exactly how a wrong password burns all ten of them in four minutes.
    this.saveCache({ token: '', day: today, issuedToday: usedToday + 1 });

    const data = (await this.request('getToken', {
      username: this.cfg.username,
      password: this.cfg.password,
    })) as Record<string, unknown>;

    // Documented shape is {"Authenticated":"True","UserToken":"..."}; the
    // older generation used Authorization. Accept either.
    const token = field(data, 'UserToken', 'Authorization', 'token');
    if (!token) {
      const authenticated = field(data, 'Authenticated');
      throw new NjtError(
        authenticated && !/true/i.test(authenticated)
          ? 'getToken rejected these credentials (Authenticated: False)'
          : 'getToken returned no token',
        401,
      );
    }

    this.saveCache({ token, day: today, issuedToday: usedToday + 1 });
    return token;
  }

  private async token(): Promise<string> {
    return this.loadCache()?.token || (await this.authenticate());
  }

  // --- board -------------------------------------------------------------

  /**
   * The next departures for the configured station.
   *
   * getTrainSchedule, not getStationSchedule: this one is the DepartureVision
   * feed -- the live board, with TRACK and STATUS per train, which is the
   * whole point of collecting. getStationSchedule is the flat 27-hour timetable
   * and is capped at 200 calls a day, so polling it every 20s would exhaust the
   * day's allowance before 08:00 and still never report a track.
   *
   * An expired token comes back as HTTP 200 with {"errorMessage":"Invalid
   * token."}, so re-authentication keys off that message rather than a 401 --
   * the API does not use one.
   */
  async fetchBoard(): Promise<RawDeparture[]> {
    try {
      return this.parseBoard(
        await this.request('getTrainSchedule', {
          token: await this.token(),
          station: this.cfg.station,
        }),
      );
    } catch (err) {
      if (!(err instanceof NjtError) || !err.invalidToken) throw err;

      this.cache = null;
      return this.parseBoard(
        await this.request('getTrainSchedule', {
          token: await this.authenticate(),
          station: this.cfg.station,
        }),
      );
    }
  }

  /**
   * Dig the departure array out of the response and normalise each row.
   *
   * getTrainSchedule nests them under ITEMS beside STATIONMSGS; another
   * generation returned a bare array, so we search rather than assume.
   */
  parseBoard(payload: unknown): RawDeparture[] {
    const items = findItemArray(payload);
    if (!items) {
      throw new NjtError('could not locate a departure array in the response', 0);
    }

    const out: RawDeparture[] = [];
    for (const entry of items) {
      if (typeof entry !== 'object' || entry === null) continue;
      const row = entry as Record<string, unknown>;

      const trainId = field(row, 'TRAIN_ID', 'trainId', 'train');
      const schedRaw = field(row, 'SCHED_DEP_DATE', 'scheduledDepartureDate', 'schedDepDate');
      const scheduledDep = parseRailDateTime(schedRaw);

      // A row without an identity or a departure time cannot be joined to
      // history later, so it is worthless rather than merely incomplete.
      if (!trainId || !scheduledDep) continue;

      out.push({
        trainId,
        line: field(row, 'LINE', 'line', 'TRAIN_LINE') || 'Unknown',
        lineCode: field(row, 'LINEABBREVIATION', 'lineCode', 'LINE_ABBREVIATION'),
        destination: field(row, 'DESTINATION', 'destination') || 'Unknown',
        scheduledDep,
        track: normaliseTrack(field(row, 'TRACK', 'track')),
        status: field(row, 'STATUS', 'status'),
        secondsLate: Number(field(row, 'SEC_LATE', 'secondsLate', 'secLate') || 0) || 0,
      });
    }
    return out;
  }
}

/** Recursively locate the first array of departure-shaped objects. */
function findItemArray(payload: unknown, depth = 0): unknown[] | null {
  if (depth > 6 || payload === null || typeof payload !== 'object') return null;

  if (Array.isArray(payload)) {
    const looksLikeDepartures = payload.some(
      (e) =>
        typeof e === 'object' &&
        e !== null &&
        Object.keys(e).some((k) => /train_?id/i.test(k)),
    );
    return looksLikeDepartures ? payload : null;
  }

  for (const value of Object.values(payload as Record<string, unknown>)) {
    const found = findItemArray(value, depth + 1);
    if (found) return found;
  }
  return null;
}

export class NjtError extends Error {
  constructor(
    message: string,
    readonly status: number,
    /** What the API said, when it said anything. Empty if it sent no body. */
    readonly detail = '',
  ) {
    super(detail ? `${message}: ${detail}` : message);
    this.name = 'NjtError';
  }

  /** The token is stale and a new one will help. Reported as 200, not 401. */
  get invalidToken(): boolean {
    return /invalid token/i.test(this.detail);
  }

  /**
   * The account is locked out until midnight. Nothing to do but wait, and in
   * particular do not spend the remaining getToken calls finding out again.
   */
  get rateLimited(): boolean {
    return this.status === 429 || /daily usage limit/i.test(this.detail);
  }
}

/** The API reports its own failures as {"errorMessage": "..."} with HTTP 200. */
function errorMessageOf(payload: unknown): string {
  if (typeof payload !== 'object' || payload === null) return '';
  const value = (payload as Record<string, unknown>).errorMessage;
  return typeof value === 'string' ? value.trim() : '';
}

/** Collapse a body to one bounded line, fit to log every 20 seconds. */
function oneLine(text: string): string {
  const flat = text.replace(/\s+/g, ' ').trim();
  if (!flat) return '';
  return flat.length > 200 ? `${flat.slice(0, 200)}...` : flat;
}

