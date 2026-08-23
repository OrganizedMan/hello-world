import { BoxGeometry, Group, Mesh, Object3D } from "three";
import { describe, expect, it } from "vitest";

import {
  boundsOfStoreys,
  ceilingsAreInTheWay,
  EXPOSURE,
  exposureFor,
  floorBeneath,
  framingForBounds,
  isEffectivelyVisible,
  isFloorHit,
  setCeilingVisibility,
  setStoreyVisibility,
} from "./tourFraming";

/** Storey elevations as the traced building exports them, in metres. */
const BASES = [-2.3622, 0, 2.8702, 5.6134];


/**
 * The building as GLTFLoader delivers it: a group per storey holding one mesh
 * per material, and the ceiling of each storey as a node of its own.
 */
function building(): Object3D {
  const root = new Group();
  BASES.forEach((base, index) => {
    const node = `storey_a${index}`;
    const group = new Group();
    group.name = node;
    for (let part = 0; part < 2; part += 1) {
      const mesh = new Mesh(new BoxGeometry(12, 2.5, 16));
      mesh.name = `${node}_${part}`;
      mesh.position.set(6, base + 1.25, -8);
      group.add(mesh);
    }
    root.add(group);

    const ceiling = new Group();
    ceiling.name = `${node}_ceiling`;
    const slab = new Mesh(new BoxGeometry(12, 0.12, 16));
    slab.name = `${node}_ceiling_0`;
    slab.position.set(6, base + 2.5, -8);
    ceiling.add(slab);
    root.add(ceiling);
  });
  return root;
}

const named = (scene: Object3D, name: string) => scene.getObjectByName(name)!;


describe("boundsOfStoreys", () => {
  it("measures only the storey asked for", () => {
    const box = boundsOfStoreys(building(), ["storey_a2"])!;

    expect(box.min.y).toBeCloseTo(2.8702, 3);
    expect(box.max.y).toBeCloseTo(2.8702 + 2.56, 3);
  });

  it("includes that storey's ceiling, which shares its name", () => {
    const box = boundsOfStoreys(building(), ["storey_a0"])!;

    expect(box.max.y).toBeCloseTo(-2.3622 + 2.56, 2);
  });

  it("measures the whole building when no storey is chosen", () => {
    const box = boundsOfStoreys(building(), [])!;

    expect(box.min.y).toBeCloseTo(-2.3622, 3);
    expect(box.max.y).toBeCloseTo(5.6134 + 2.56, 2);
  });

  /**
   * Box3.setFromObject walks hidden children too, so framing the chosen floor
   * has to pick geometry by name. Hiding everything else first and measuring
   * the scene would have returned the whole house every time.
   */
  it("ignores the visibility flags", () => {
    const scene = building();
    setStoreyVisibility(scene, ["storey_a3"]);

    const box = boundsOfStoreys(scene, ["storey_a1"])!;

    expect(box.min.y).toBeCloseTo(0, 3);
  });
});


describe("framingForBounds", () => {
  it("puts the whole house in frame from outside it", () => {
    const box = boundsOfStoreys(building(), [])!;

    const framing = framingForBounds(box, { fovDegrees: 58, aspect: 1.6, overhead: false });

    const centre = box.getCenter(box.getCenter(box.max.clone()));
    expect(framing.target[1]).toBeCloseTo(centre.y, 3);
    // Far enough out that the bounding sphere fits the narrower field of view.
    const radius = 0.5 * box.getSize(box.max.clone()).length();
    expect(framing.distance).toBeGreaterThan(radius);
    expect(framing.position[1]).toBeGreaterThan(box.max.y);
  });

  it("comes in close for a single floor", () => {
    const whole = framingForBounds(
      boundsOfStoreys(building(), [])!,
      { fovDegrees: 58, aspect: 1.6, overhead: false },
    );
    const oneFloor = framingForBounds(
      boundsOfStoreys(building(), ["storey_a2"])!,
      { fovDegrees: 58, aspect: 1.6, overhead: false },
    );

    expect(oneFloor.distance).toBeLessThan(whole.distance);
  });

  it("rises to the floor it is framing", () => {
    const basement = framingForBounds(
      boundsOfStoreys(building(), ["storey_a0"])!,
      { fovDegrees: 58, aspect: 1.6, overhead: false },
    );
    const top = framingForBounds(
      boundsOfStoreys(building(), ["storey_a3"])!,
      { fovDegrees: 58, aspect: 1.6, overhead: false },
    );

    expect(top.target[1] - basement.target[1]).toBeCloseTo(5.6134 + 2.3622, 3);
    expect(top.position[1]).toBeGreaterThan(basement.position[1]);
  });

  /**
   * Straight down has no defined roll, and orbiting from there is degenerate.
   * The lean is south so that north ends up at the top of the frame.
   */
  it("looks nearly, but not exactly, straight down when overhead", () => {
    const box = boundsOfStoreys(building(), ["storey_a1"])!;

    const framing = framingForBounds(box, { fovDegrees: 58, aspect: 1.6, overhead: true });

    const drop = framing.position[1] - framing.target[1];
    const sideways = Math.hypot(
      framing.position[0] - framing.target[0],
      framing.position[2] - framing.target[2],
    );
    expect(drop).toBeGreaterThan(0);
    expect(sideways).toBeGreaterThan(0);
    expect(sideways / drop).toBeLessThan(0.3);
    expect(framing.position[2]).toBeGreaterThan(framing.target[2]);
  });
});


describe("ceilings", () => {
  it("gets out of the way overhead", () => {
    expect(ceilingsAreInTheWay("orbit", "overhead", [])).toBe(true);
  });

  it("gets out of the way when one floor is chosen", () => {
    expect(ceilingsAreInTheWay("orbit", "kitchen_overview", ["storey_a2"])).toBe(true);
  });

  it("stays put for the whole house seen from outside", () => {
    expect(ceilingsAreInTheWay("orbit", "kitchen_overview", [])).toBe(false);
  });

  it("stays put while walking, where you are underneath it", () => {
    expect(ceilingsAreInTheWay("walk", "overhead", ["storey_a1"])).toBe(false);
  });

  it("never turns a hidden storey back on", () => {
    const scene = building();
    setStoreyVisibility(scene, ["storey_a1"]);

    setCeilingVisibility(scene, false, ["storey_a1"]);

    expect(named(scene, "storey_a1_ceiling_0").visible).toBe(true);
    expect(named(scene, "storey_a3_ceiling_0").visible).toBe(false);
  });

  it("hides the storey ceilings the traced building exports", () => {
    const scene = building();
    setStoreyVisibility(scene, []);

    setCeilingVisibility(scene, true);

    expect(named(scene, "storey_a1_ceiling").visible).toBe(false);
    expect(named(scene, "storey_a1_ceiling_0").visible).toBe(false);
    expect(named(scene, "storey_a1_0").visible).toBe(true);
  });
});


describe("isFloorHit", () => {
  const up = { x: 0, y: 1, z: 0 };

  it("accepts an upward face at any storey's floor", () => {
    expect(isFloorHit({ y: 2.8702 }, up, BASES)).toBe(true);
    expect(isFloorHit({ y: -2.3622 }, up, BASES)).toBe(true);
  });

  it("rejects a countertop, which is up-facing but not a floor", () => {
    expect(isFloorHit({ y: 0.92 }, up, BASES)).toBe(false);
  });

  it("rejects a wall face at floor height", () => {
    expect(isFloorHit({ y: 0 }, { x: 1, y: 0, z: 0 }, BASES)).toBe(false);
  });

  it("falls back to the ground when no storeys are listed", () => {
    expect(isFloorHit({ y: 0 }, up, [])).toBe(true);
    expect(isFloorHit({ y: 2.87 }, up, [])).toBe(false);
  });
});


describe("floorBeneath", () => {
  it("finds the slab you are standing on", () => {
    expect(floorBeneath(4.1, BASES)).toBeCloseTo(2.8702, 4);
    expect(floorBeneath(2.8702, BASES)).toBeCloseTo(2.8702, 4);
  });

  it("uses the lowest slab when you are below them all", () => {
    expect(floorBeneath(-9, BASES)).toBeCloseTo(-2.3622, 4);
  });
});


describe("isEffectivelyVisible", () => {
  /**
   * three.js raycasts hidden objects -- `visible` decides drawing, not hit
   * testing -- so a click on the first floor was answered by the second
   * floor's slab hanging invisibly above it.
   */
  it("rejects geometry whose storey is switched off", () => {
    const scene = building();
    setStoreyVisibility(scene, ["storey_a1"]);

    expect(isEffectivelyVisible(named(scene, "storey_a2_0"))).toBe(false);
    expect(isEffectivelyVisible(named(scene, "storey_a1_0"))).toBe(true);
  });

  it("rejects a hidden ceiling inside a storey that is shown", () => {
    const scene = building();
    setStoreyVisibility(scene, []);
    setCeilingVisibility(scene, true);

    expect(isEffectivelyVisible(named(scene, "storey_a1_ceiling_0"))).toBe(false);
    expect(isEffectivelyVisible(named(scene, "storey_a1_0"))).toBe(true);
  });

  it("rejects nothing at all", () => {
    expect(isEffectivelyVisible(null)).toBe(false);
  });
});


describe("exposureFor", () => {
  /**
   * A white wall exposed for the sunlit outside renders at sRGB 75, which is
   * brown -- and that is what the model shipped as until it was measured. One
   * exposure cannot serve both: baked light is linear, and an interior sits far
   * below the exterior that sets the top of the range.
   */
  it("opens up when the camera is standing in the room", () => {
    const box = boundsOfStoreys(building(), ["storey_a1"])!;

    expect(exposureFor(box, { x: 6, y: 1.6, z: -8 })).toBe(EXPOSURE.interior);
  });

  it("stops down when the camera is outside looking at the model", () => {
    const box = boundsOfStoreys(building(), ["storey_a1"])!;

    expect(exposureFor(box, { x: 30, y: 20, z: 25 })).toBe(EXPOSURE.exterior);
  });

  it("stops down for a camera above an open-topped floor", () => {
    const box = boundsOfStoreys(building(), ["storey_a1"])!;

    expect(exposureFor(box, { x: 6, y: box.max.y + 4, z: -8 })).toBe(EXPOSURE.exterior);
  });

  it("meters for the exterior when nothing is on screen yet", () => {
    expect(exposureFor(null, { x: 0, y: 0, z: 0 })).toBe(EXPOSURE.exterior);
  });

  it("is a real stop apart, not a nudge", () => {
    expect(EXPOSURE.interior / EXPOSURE.exterior).toBeGreaterThan(2);
  });
});
