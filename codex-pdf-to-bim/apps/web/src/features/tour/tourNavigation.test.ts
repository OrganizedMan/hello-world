import { describe, expect, it } from "vitest";

import {
  cameraPositionForFloor,
  isWalkablePlacement,
  resolveMovement,
  type Barrier,
  type WalkableBounds,
} from "./tourNavigation";


const bounds: WalkableBounds = {
  minX: 0,
  maxX: 10,
  minZ: -6,
  maxZ: 0,
};

const island: Barrier = {
  name: "island",
  minX: 4,
  maxX: 6,
  minZ: -4,
  maxZ: -2,
};


describe("tour navigation", () => {
  it("keeps unrestricted movement relative to the current view", () => {
    expect(
      resolveMovement(
        { x: 2, z: -5 },
        { x: 1, z: 0.5 },
        [island],
        bounds,
        0.3,
      ),
    ).toEqual({ x: 3, z: -4.5 });
  });

  it("blocks the visitor radius before the camera enters an obstacle", () => {
    expect(
      resolveMovement(
        { x: 3.65, z: -3 },
        { x: 0.1, z: 0 },
        [island],
        bounds,
        0.3,
      ),
    ).toEqual({ x: 3.65, z: -3 });
  });

  it("slides along a barrier instead of sticking when only one axis is blocked", () => {
    expect(
      resolveMovement(
        { x: 3.65, z: -3 },
        { x: 0.5, z: 0.4 },
        [island],
        bounds,
        0.3,
      ),
    ).toEqual({ x: 3.65, z: -2.6 });
  });

  it("rejects movement that would put the visitor outside the floor boundary", () => {
    expect(
      resolveMovement(
        { x: 0.35, z: -1 },
        { x: -0.1, z: 0 },
        [],
        bounds,
        0.3,
      ),
    ).toEqual({ x: 0.35, z: -1 });
  });

  it("accepts only unobstructed points on the walkable floor", () => {
    expect(isWalkablePlacement({ x: 2, y: 0, z: -1 }, bounds, [island])).toBe(true);
    expect(isWalkablePlacement({ x: 5, y: 0, z: -3 }, bounds, [island])).toBe(false);
    expect(isWalkablePlacement({ x: 3.85, y: 0, z: -3 }, bounds, [island])).toBe(false);
    expect(isWalkablePlacement({ x: 0.1, y: 0, z: -1 }, bounds, [island])).toBe(false);
    expect(isWalkablePlacement({ x: 2, y: 0.12, z: -1 }, bounds, [island])).toBe(false);
    expect(isWalkablePlacement({ x: 11, y: 0, z: -1 }, bounds, [island])).toBe(false);
  });

  it("places walking cameras at the required 1.65 meter eye height", () => {
    expect(cameraPositionForFloor({ x: 4.5, y: 0, z: -4.1 })).toEqual({
      x: 4.5,
      y: 1.65,
      z: -4.1,
    });
  });
});
