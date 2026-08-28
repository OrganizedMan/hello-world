import { parseRailDateTime } from '@nypenn/shared';

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

export class NjtClient {
  private token: string | null = null;

  constructor(private readonly cfg: NjtConfig) {}

  private async request(path: string, body: Record<string, string>, auth: boolean): Promise<unknown> {
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), this.cfg.requestTimeoutMs);

    try {
      const form = new URLSearchParams(body);
      const headers: Record<string, string> = {
        'Content-Type': 'application/x-www-form-urlencoded',
        Accept: 'application/json',
      };
      if (auth && this.token) headers.Authorization = this.token;

      const res = await fetch(`${this.cfg.baseUrl.replace(/\/$/, '')}/${path}`, {
        method: 'POST',
        headers,
        body: form,
        signal: controller.signal,
      });

      if (!res.ok) {
        // The status alone is not enough to act on: a 500 from getToken looks
        // identical whether the portal is down or it is rejecting the shape of
        // this request. The body is where the API says which, so carry it.
        throw new NjtError(`${path} returned HTTP ${res.status}`, res.status, await snippet(res));
      }
      return await res.json();
    } finally {
      clearTimeout(timer);
    }
  }

  /** Exchange portal credentials for a bearer token. */
  private async authenticate(): Promise<void> {
    const data = (await this.request(
      'getToken',
      { username: this.cfg.username, password: this.cfg.password },
      false,
    )) as Record<string, unknown>;

    const token = field(data, 'Authorization', 'UserToken', 'token');
    if (!token) {
      throw new NjtError('getToken returned no Authorization value', 401);
    }
    this.token = token;
  }

  /**
   * Fetch the current board for the configured station.
   *
   * Retries once through a fresh token on a 401/403, since the portal expires
   * tokens without warning and a silent auth lapse would otherwise look like
   * an outage and cost us a day of history.
   */
  async fetchBoard(): Promise<RawDeparture[]> {
    if (!this.token) await this.authenticate();

    let payload: unknown;
    try {
      payload = await this.request('getStationSchedule', { station: this.cfg.station }, true);
    } catch (err) {
      if (err instanceof NjtError && (err.status === 401 || err.status === 403)) {
        this.token = null;
        await this.authenticate();
        payload = await this.request('getStationSchedule', { station: this.cfg.station }, true);
      } else {
        throw err;
      }
    }

    return this.parseBoard(payload);
  }

  /**
   * Dig the departure array out of the response and normalise each row.
   *
   * The payload has been nested under STATION.ITEMS.ITEM in one generation and
   * returned as a bare array in another, so we search rather than assume.
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
}

/**
 * The first line of an error body, bounded. NJT returns HTML error pages as
 * well as JSON, and a stack trace in the journal every 20 seconds would wear
 * the SD card faster than the history it is meant to protect.
 */
async function snippet(res: Response): Promise<string> {
  try {
    const text = (await res.text()).trim();
    if (!text) return '';
    const oneLine = text.replace(/\s+/g, ' ');
    return oneLine.length > 200 ? `${oneLine.slice(0, 200)}...` : oneLine;
  } catch {
    return '';
  }
}
