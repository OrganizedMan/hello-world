import type { Departure, HealthStatus } from '@nypenn/shared';

const TOKEN_KEY = 'nypenn.token';

export interface BoardResponse {
  departures: Departure[];
  health: HealthStatus;
}

export interface TrainHistoryEntry {
  serviceDate: string;
  finalTrack: string;
  dayType: string;
}

export function getToken(): string | null {
  try {
    return localStorage.getItem(TOKEN_KEY);
  } catch {
    // Private browsing and blocked site data both throw here.
    return null;
  }
}

export function setToken(token: string | null): void {
  try {
    if (token) localStorage.setItem(TOKEN_KEY, token);
    else localStorage.removeItem(TOKEN_KEY);
  } catch {
    // Non-fatal: the session simply will not survive a reload.
  }
}

/** Raised when the token is missing or rejected, so the UI can log out. */
export class Unauthorized extends Error {}

async function request<T>(path: string): Promise<T> {
  const token = getToken();
  const res = await fetch(path, {
    headers: token ? { Authorization: `Bearer ${token}` } : {},
  });

  if (res.status === 401) throw new Unauthorized('session expired');
  if (!res.ok) throw new Error(`${path} failed with HTTP ${res.status}`);
  return (await res.json()) as T;
}

export const fetchBoard = () => request<BoardResponse>('/api/board');

export const fetchTrainHistory = (trainId: string) =>
  request<{ history: TrainHistoryEntry[] }>(
    `/api/train/${encodeURIComponent(trainId)}/history`,
  );

export async function login(username: string, password: string): Promise<string> {
  const res = await fetch('/api/login', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ username, password }),
  });

  if (res.status === 401) throw new Error('Incorrect username or password.');
  if (res.status === 429) throw new Error('Too many attempts. Wait a few minutes.');
  if (!res.ok) throw new Error('Could not reach the server.');

  const { token } = (await res.json()) as { token: string };
  return token;
}
