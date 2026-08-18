import type { FamilyRoomMeshResponse, FamilyRoomResponse, FamilyRoomSource, TiersResponse } from './types'

async function getJSON<T>(path: string): Promise<T> {
  const res = await fetch(path)
  if (!res.ok) {
    throw new Error(`${path} -> ${res.status} ${res.statusText}`)
  }
  return res.json() as Promise<T>
}

export const api = {
  familyRoom: (source: FamilyRoomSource = 'hand_traced') =>
    getJSON<FamilyRoomResponse>(`/api/family-room?source=${source}`),
  familyRoomMesh: (source: FamilyRoomSource = 'hand_traced') =>
    getJSON<FamilyRoomMeshResponse>(`/api/family-room/mesh?source=${source}`),
  tiers: () => getJSON<TiersResponse>('/api/tiers'),
  sourceImageUrl: (key: string, dpi = 100) => `/api/source-image/${key}?dpi=${dpi}`,
}
