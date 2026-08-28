/**
 * Service-date and day-type helpers.
 *
 * These must stay identical between the collector (which labels history) and
 * the predictor (which looks it up); a mismatch silently misfiles every row,
 * so both import from here rather than reimplementing.
 */

export const RAIL_TZ = 'America/New_York';

/**
 * Trains after midnight belong to the previous operating day. NJT's late-night
 * departures run to roughly 02:00, so 03:00 ET is a safe cutoff.
 */
const SERVICE_DAY_CUTOFF_HOURS = 3;

/** Format a Date as YYYY-MM-DD in the railroad's timezone. */
export function toRailDateString(date: Date): string {
  // en-CA gives ISO-ordered parts, which sidesteps manual reassembly.
  return new Intl.DateTimeFormat('en-CA', {
    timeZone: RAIL_TZ,
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
  }).format(date);
}

/** The operating day a departure belongs to. */
export function serviceDateOf(scheduledDep: Date): string {
  const shifted = new Date(
    scheduledDep.getTime() - SERVICE_DAY_CUTOFF_HOURS * 60 * 60 * 1000,
  );
  return toRailDateString(shifted);
}

export type DayType = 'weekday' | 'saturday' | 'sunday';

/**
 * Major holidays on which NJ Transit runs a weekend-style schedule, so track
 * patterns follow Sunday rather than the weekday they fall on. Dates are
 * service dates (YYYY-MM-DD); extend as needed.
 */
export const HOLIDAYS = new Set<string>([
  '2026-01-01', // New Year's Day
  '2026-05-25', // Memorial Day
  '2026-07-04', // Independence Day
  '2026-09-07', // Labor Day
  '2026-11-26', // Thanksgiving
  '2026-12-25', // Christmas
  '2027-01-01',
]);

/** Classify a service date into the categories track assignment varies by. */
export function dayTypeOf(serviceDate: string): DayType {
  if (HOLIDAYS.has(serviceDate)) return 'sunday';

  // Parse as UTC noon: the date string is already timezone-resolved, and noon
  // keeps the weekday stable regardless of any offset arithmetic.
  const day = new Date(`${serviceDate}T12:00:00Z`).getUTCDay();
  if (day === 6) return 'saturday';
  if (day === 0) return 'sunday';
  return 'weekday';
}

/** Milliseconds to add to a UTC instant to get the railroad's wall clock. */
function railOffsetMs(instant: Date): number {
  const parts = new Intl.DateTimeFormat('en-US', {
    timeZone: RAIL_TZ,
    hour12: false,
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
  }).formatToParts(instant);

  const get = (type: string) => Number(parts.find((p) => p.type === type)!.value);
  // Intl renders midnight as hour 24 in some runtimes; normalise it.
  const hour = get('hour') % 24;

  const asUtc = Date.UTC(
    get('year'), get('month') - 1, get('day'),
    hour, get('minute'), get('second'),
  );
  return asUtc - instant.getTime();
}

const MONTHS: Record<string, number> = {
  jan: 0, feb: 1, mar: 2, apr: 3, may: 4, jun: 5,
  jul: 6, aug: 7, sep: 8, oct: 9, nov: 10, dec: 11,
};

/**
 * Parse an NJ Transit timestamp into a real instant.
 *
 * The feed reports local (Eastern) wall-clock time with no offset, in a format
 * that has varied across API generations, so we accept the shapes seen in the
 * wild: `27-Aug-2026 05:31:00 PM`, `8/27/2026 5:31:00 PM`, and ISO 8601.
 * Returns null rather than an Invalid Date so callers must handle bad input.
 */
export function parseRailDateTime(raw: string): Date | null {
  const s = raw?.trim();
  if (!s) return null;

  // Already an instant with an explicit offset — trust it.
  if (/[zZ]$|[+-]\d{2}:\d{2}$/.test(s)) {
    const d = new Date(s);
    return Number.isNaN(d.getTime()) ? null : d;
  }

  let y: number, mo: number, d: number, hh = 0, mi = 0, ss = 0, ampm = '';

  const dmy = s.match(
    /^(\d{1,2})-([A-Za-z]{3})-(\d{4})(?:\s+(\d{1,2}):(\d{2})(?::(\d{2}))?\s*([AaPp][Mm])?)?$/,
  );
  const mdy = s.match(
    /^(\d{1,2})\/(\d{1,2})\/(\d{4})(?:\s+(\d{1,2}):(\d{2})(?::(\d{2}))?\s*([AaPp][Mm])?)?$/,
  );
  const iso = s.match(
    /^(\d{4})-(\d{2})-(\d{2})[T ](\d{2}):(\d{2})(?::(\d{2}))?$/,
  );

  if (dmy) {
    d = +dmy[1]; mo = MONTHS[dmy[2].toLowerCase()]; y = +dmy[3];
    hh = +(dmy[4] ?? 0); mi = +(dmy[5] ?? 0); ss = +(dmy[6] ?? 0); ampm = dmy[7] ?? '';
    if (mo === undefined) return null;
  } else if (mdy) {
    mo = +mdy[1] - 1; d = +mdy[2]; y = +mdy[3];
    hh = +(mdy[4] ?? 0); mi = +(mdy[5] ?? 0); ss = +(mdy[6] ?? 0); ampm = mdy[7] ?? '';
  } else if (iso) {
    y = +iso[1]; mo = +iso[2] - 1; d = +iso[3];
    hh = +iso[4]; mi = +iso[5]; ss = +(iso[6] ?? 0);
  } else {
    return null;
  }

  const suffix = ampm.toLowerCase();
  if (suffix === 'pm' && hh !== 12) hh += 12;
  if (suffix === 'am' && hh === 12) hh = 0;

  // Treat the parsed fields as Eastern wall time, then correct to a true
  // instant. Applying the offset twice converges across DST boundaries.
  const naive = Date.UTC(y, mo, d, hh, mi, ss);
  let utc = naive - railOffsetMs(new Date(naive));
  utc = naive - railOffsetMs(new Date(utc));

  const result = new Date(utc);
  return Number.isNaN(result.getTime()) ? null : result;
}
