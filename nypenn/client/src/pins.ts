const PINS_KEY = 'nypenn.pins';

/**
 * Pinned trains, per device. Deliberately local rather than server-side:
 * two people share one account, and each wants their own commute on top.
 */
export function loadPins(): string[] {
  try {
    const raw = localStorage.getItem(PINS_KEY);
    return raw ? (JSON.parse(raw) as string[]) : [];
  } catch {
    return [];
  }
}

export function savePins(pins: string[]): void {
  try {
    localStorage.setItem(PINS_KEY, JSON.stringify(pins));
  } catch {
    // Pins are a convenience; losing them must not break the board.
  }
}
