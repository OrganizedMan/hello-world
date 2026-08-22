export type FloorPoint = {
  x: number;
  z: number;
};

export type ScenePoint = FloorPoint & {
  y: number;
};

export type WalkableBounds = {
  minX: number;
  maxX: number;
  minZ: number;
  maxZ: number;
};

export type Barrier = WalkableBounds & {
  name: string;
};


const FLOOR_TOLERANCE_METERS = 0.05;
const PLACEMENT_RADIUS_METERS = 0.3;
export const WALK_EYE_HEIGHT_METERS = 1.65;


function isFinitePoint(point: FloorPoint): boolean {
  return Number.isFinite(point.x) && Number.isFinite(point.z);
}


function circleIntersectsBarrier(
  point: FloorPoint,
  barrier: Barrier,
  radius: number,
): boolean {
  const nearestX = Math.max(barrier.minX, Math.min(point.x, barrier.maxX));
  const nearestZ = Math.max(barrier.minZ, Math.min(point.z, barrier.maxZ));
  const distanceX = point.x - nearestX;
  const distanceZ = point.z - nearestZ;
  return (distanceX * distanceX) + (distanceZ * distanceZ) <= radius * radius;
}


function canOccupy(
  point: FloorPoint,
  barriers: readonly Barrier[],
  bounds: WalkableBounds,
  radius: number,
): boolean {
  if (!isFinitePoint(point) || !Number.isFinite(radius) || radius < 0) return false;
  if (
    point.x - radius < bounds.minX
    || point.x + radius > bounds.maxX
    || point.z - radius < bounds.minZ
    || point.z + radius > bounds.maxZ
  ) {
    return false;
  }
  return !barriers.some((barrier) => circleIntersectsBarrier(point, barrier, radius));
}


export function resolveMovement(
  position: FloorPoint,
  delta: FloorPoint,
  barriers: readonly Barrier[],
  walkableBounds: WalkableBounds,
  radius: number,
): FloorPoint {
  if (!isFinitePoint(position) || !isFinitePoint(delta)) return position;

  const afterX = { x: position.x + delta.x, z: position.z };
  const resolvedX = canOccupy(afterX, barriers, walkableBounds, radius)
    ? afterX.x
    : position.x;
  const afterZ = { x: resolvedX, z: position.z + delta.z };
  const resolvedZ = canOccupy(afterZ, barriers, walkableBounds, radius)
    ? afterZ.z
    : position.z;

  return { x: resolvedX, z: resolvedZ };
}


export function isWalkablePlacement(
  point: ScenePoint,
  bounds: WalkableBounds,
  obstacles: readonly Barrier[],
  floorElevation = 0,
): boolean {
  // The point has to be on a floor rather than on top of something standing on
  // one. Which floor is the caller's business: a house has four of them, and
  // measuring against zero confined the whole tour to the first storey.
  if (!Number.isFinite(point.y) || Math.abs(point.y - floorElevation) > FLOOR_TOLERANCE_METERS) {
    return false;
  }
  return canOccupy(point, obstacles, bounds, PLACEMENT_RADIUS_METERS);
}


export function cameraPositionForFloor(
  point: ScenePoint,
  eyeHeight = WALK_EYE_HEIGHT_METERS,
): ScenePoint {
  return { x: point.x, y: point.y + eyeHeight, z: point.z };
}
