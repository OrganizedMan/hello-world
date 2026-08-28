import type { Departure, HealthStatus } from '@nypenn/shared';

export interface BoardResponse {
  departures: Departure[];
  health: HealthStatus;
}

export interface TrainHistoryEntry {
  serviceDate: string;
  finalTrack: string;
  dayType: string;
}

async function request<T>(path: string): Promise<T> {
  const res = await fetch(path);
  if (!res.ok) throw new Error(`${path} failed with HTTP ${res.status}`);
  return (await res.json()) as T;
}

export const fetchBoard = () => request<BoardResponse>('/api/board');

export const fetchTrainHistory = (trainId: string) =>
  request<{ history: TrainHistoryEntry[] }>(
    `/api/train/${encodeURIComponent(trainId)}/history`,
  );
