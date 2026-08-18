// Mirrors packages/server/src/server/serialize.py and app.py response shapes.

export interface NmField {
  nm: number | null
  display: string
}

export interface Opening {
  id: string
  kind: string
  t_start: NmField
  t_end: NmField
  width: NmField
  sill: NmField
  head: NmField
  connects: [string, string] | null
  annotation: string | null
  provenance_state: string
}

export interface WallSegment {
  id: string
  level_id: string
  variant: string
  construction: string
  baseline: [{ x_nm: number; y_nm: number }, { x_nm: number; y_nm: number }]
  length: NmField
  thickness: NmField
  base_z: NmField
  top_z: NmField
  provenance_state: string
  openings: Opening[]
  solid_intervals: { t_start: NmField; t_end: NmField }[]
}

export type CheckStatus = 'pass' | 'warn' | 'block'

export interface CheckResult {
  check_id: string
  status: CheckStatus
  message: string
  details: string[]
}

export interface ValidationReport {
  is_blocking: boolean
  has_warnings: boolean
  checks: CheckResult[]
}

export type FamilyRoomSource = 'hand_traced' | 'extracted'

export interface DimensionMatchInfo {
  text: string
  axis: string
  error_in: number
}

export interface FamilyRoomResponse {
  source: FamilyRoomSource
  walls: WallSegment[]
  tv_wall_interval: { wall_id: string; t_start_nm: number; t_end_nm: number }
  validation: ValidationReport
  geometry_hash: string
  dimension_matches?: DimensionMatchInfo[]
}

export interface MeshData {
  vertices: [number, number, number][]
  triangles: [number, number, number][]
}

export type FamilyRoomMeshResponse = Record<string, MeshData>

export interface TierInfo {
  filename: string
  tier: 'A' | 'B' | 'C'
  effort_estimate: string
  vector_path_count: number
  text_span_count: number
  image_area_fraction: number
}

export type TiersResponse = Record<string, TierInfo>
