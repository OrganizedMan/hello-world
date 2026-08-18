import type { FamilyRoomMeshResponse, FamilyRoomResponse, TiersResponse } from './types'

async function getJSON<T>(path: string): Promise<T> {
  const res = await fetch(path)
  if (!res.ok) {
    throw new Error(`${path} -> ${res.status} ${res.statusText}`)
  }
  return res.json() as Promise<T>
}

export const api = {
  familyRoom: () => getJSON<FamilyRoomResponse>('/api/family-room'),
  familyRoomMesh: () => getJSON<FamilyRoomMeshResponse>('/api/family-room/mesh'),
  tiers: () => getJSON<TiersResponse>('/api/tiers'),
  sourceImageUrl: (key: string, dpi = 100) => `/api/source-image/${key}?dpi=${dpi}`,
}
