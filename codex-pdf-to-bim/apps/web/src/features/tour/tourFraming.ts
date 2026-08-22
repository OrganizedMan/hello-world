import { Box3, Mesh, Object3D, Vector3 } from "three";

import type { TourCameraPreset } from "./tourManifest";


/** Does this object belong to the storey held in `node`? */
export function isPartOfStorey(name: string, node: string): boolean {
  // A glTF mesh with several primitives -- ours has one per material -- is
  // loaded as a Group named for the node, holding meshes named `<node>_0`,
  // `<node>_1` and so on. Matching the node name alone leaves those children
  // unmatched, and they are where all the geometry actually lives.
  return name === node || name.startsWith(`${node}_`);
}


/** Show only the named storey nodes; an empty list shows every storey. */
export function setStoreyVisibility(scene: Object3D, visible: readonly string[]): void {
  scene.traverse((child) => {
    if (!child.name.startsWith("storey_")) return;
    child.visible =
      visible.length === 0 || visible.some((node) => isPartOfStorey(child.name, node));
  });
}


function isCeiling(name: string): boolean {
  return name.includes("CEILING") || name.includes("_ceiling");
}


/**
 * Show or hide the ceilings, without contradicting the storey switch.
 *
 * Ceilings are their own glTF nodes (`storey_a1_ceiling`), which means their
 * names fall inside the storey names -- so putting a ceiling back needs to know
 * which storeys are on show, or hiding one and revealing it again resurrects
 * three floors that were meant to stay hidden. The old kitchen spike keeps its
 * single `HV_CEILING` mesh, which belongs to no storey and so always returns.
 */
export function setCeilingVisibility(
  scene: Object3D,
  hidden: boolean,
  storeys: readonly string[] = [],
): void {
  scene.traverse((child) => {
    if (!isCeiling(child.name)) return;
    child.visible = hidden
      ? false
      : storeys.length === 0
        || !child.name.startsWith("storey_")
        || storeys.some((node) => isPartOfStorey(child.name, node));
  });
}


/**
 * Should the ceilings be out of the way?
 *
 * Looking down into a closed box shows you a ceiling, which is exactly the
 * complaint about overhead. The same is true of picking a single floor: you
 * asked to see that floor, not the underside of the one above it. Walking is
 * the one case where you are underneath the ceiling and want it there.
 */
export function ceilingsAreInTheWay(
  mode: "orbit" | "move" | "walk",
  preset: string,
  visibleStoreys: readonly string[],
): boolean {
  if (mode === "walk") return false;
  return preset === "overhead" || visibleStoreys.length > 0;
}


/** Which storey node owns this object, if any. */
function storeyOwner(object: Object3D): string | null {
  let current: Object3D | null = object;
  while (current) {
    if (current.name.startsWith("storey_")) {
      // Climb to the outermost storey name so `storey_a1_0` reports the group.
      let outermost = current.name;
      let above: Object3D | null = current.parent;
      while (above) {
        if (above.name.startsWith("storey_")) outermost = above.name;
        above = above.parent;
      }
      return outermost;
    }
    current = current.parent;
  }
  return null;
}


/**
 * World bounds of the storeys on show, or of the whole scene when it has none.
 *
 * `Box3.setFromObject` walks hidden children too, so framing a single floor has
 * to select the geometry by name rather than trusting the visibility flags.
 */
export function boundsOfStoreys(scene: Object3D, storeys: readonly string[]): Box3 | null {
  const box = new Box3();
  let found = false;
  scene.updateWorldMatrix(false, true);
  scene.traverse((child) => {
    if (!(child instanceof Mesh)) return;
    const owner = storeyOwner(child);
    if (owner !== null && storeys.length > 0
        && !storeys.some((node) => isPartOfStorey(owner, node))) {
      return;
    }
    box.expandByObject(child);
    found = true;
  });
  return found && !box.isEmpty() ? box : null;
}


export type Framing = {
  position: [number, number, number];
  target: [number, number, number];
  /** Camera-to-target distance, so orbit limits can be widened to suit. */
  distance: number;
};


/**
 * A camera that frames the given bounds.
 *
 * Switching floors used to leave the camera exactly where it was, framed for
 * the whole house: the basement showed a slab from far above and the second
 * floor put you inside a wall. Distance comes from whichever field of view is
 * narrower -- on a wide canvas that is the vertical one -- so the box fits in
 * both directions rather than only across.
 */
export function framingForBounds(
  box: Box3,
  options: { fovDegrees: number; aspect: number; overhead: boolean },
): Framing {
  const centre = box.getCenter(new Vector3());
  const size = box.getSize(new Vector3());
  const radius = Math.max(0.5 * size.length(), 0.5);

  const vertical = (options.fovDegrees * Math.PI) / 180;
  const horizontal = 2 * Math.atan(Math.tan(vertical / 2) * Math.max(options.aspect, 0.2));
  const distance = (radius / Math.sin(Math.min(vertical, horizontal) / 2)) * 1.06;

  // Overhead looks very nearly straight down. Not exactly: a camera whose view
  // direction is parallel to its up vector has no defined roll, and orbiting
  // from there is degenerate. The slight lean south also puts north at the top
  // of the frame, which is how the plan is drawn.
  const direction = options.overhead
    ? new Vector3(0, 1, 0.16).normalize()
    : new Vector3(0.78, 0.62, 0.98).normalize();
  const position = centre.clone().addScaledVector(direction, distance);

  return {
    position: [position.x, position.y, position.z],
    target: [centre.x, centre.y, centre.z],
    distance,
  };
}


/**
 * A preset OrbitControls can actually hold.
 *
 * The overhead preset was authored with `up` set to -Z so that looking straight
 * down had a defined roll. OrbitControls measures its polar angle from the
 * camera's up vector, so under that up a camera directly overhead sits at 90
 * degrees -- past `maxPolarAngle` -- and the controls swung it away the moment
 * they took over. Keeping up as +Y and leaning the camera off vertical instead
 * gives the same view and a polar angle near zero.
 */
export function resolvePreset(preset: TourCameraPreset): TourCameraPreset {
  const [px, py, pz] = preset.position;
  const [tx, ty, tz] = preset.target;
  const horizontalReach = Math.hypot(tx - px, tz - pz);
  const drop = Math.abs(ty - py);
  if (horizontalReach >= drop * 0.12) {
    return { ...preset, up: [0, 1, 0] };
  }
  const lean = Math.max(drop * 0.16, 0.5);
  return { ...preset, position: [px, py, pz + lean], up: [0, 1, 0] };
}


/**
 * Is this object actually on screen, parents included?
 *
 * three.js raycasts hidden objects: `visible` controls drawing, not hit
 * testing. So a click meant for the first floor could be answered by the
 * second floor's slab hanging invisibly above it, and the camera would land on
 * a storey nobody had asked to see.
 */
export function isEffectivelyVisible(object: Object3D | null): boolean {
  for (let node = object; node; node = node.parent) {
    if (!node.visible) return false;
  }
  return object !== null;
}


/**
 * Is this click a spot on a floor a person could stand on?
 *
 * The first-floor tour recognised floors by the mesh name `HV_WALKABLE`, which
 * the traced building has none of -- its geometry is merged per material inside
 * a storey node, so nothing is named after what it is. A floor is instead an
 * up-facing surface at a storey's own base height; a countertop is up-facing
 * too, but it is 900mm above the nearest base and so fails the second test.
 */
export function isFloorHit(
  point: { y: number },
  normal: { x: number; y: number; z: number } | null | undefined,
  storeyBases: readonly number[],
  tolerance = 0.08,
): boolean {
  if (!Number.isFinite(point.y)) return false;
  if (normal) {
    const length = Math.hypot(normal.x, normal.y, normal.z);
    if (length > 0 && normal.y / length < 0.7) return false;
  }
  const bases = storeyBases.length > 0 ? storeyBases : [0];
  return bases.some((base) => Math.abs(point.y - base) <= tolerance);
}


/** The storey floor at or just below `y`, used to stand the camera up. */
export function floorBeneath(y: number, storeyBases: readonly number[]): number {
  let best = 0;
  let seen = false;
  for (const base of storeyBases) {
    if (base <= y + 0.08 && (!seen || base > best)) {
      best = base;
      seen = true;
    }
  }
  return seen ? best : (storeyBases[0] ?? 0);
}
