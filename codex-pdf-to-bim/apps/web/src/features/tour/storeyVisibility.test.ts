import { Group, Mesh, Object3D } from "three";
import { describe, expect, it } from "vitest";

import { setStoreyVisibility } from "./TourViewer";

/**
 * Mirrors how GLTFLoader actually loads our building: each storey node holds a
 * mesh with one primitive per material, so it arrives as a Group named for the
 * node whose children are `<node>_0`, `<node>_1`... The geometry is in those
 * children, so a check that only matches the group name hides everything.
 */
function buildingScene(): Object3D {
  const root = new Group();
  for (const node of ["storey_a0", "storey_a1", "storey_a2"]) {
    const group = new Group();
    group.name = node;
    for (let index = 0; index < 3; index += 1) {
      const mesh = new Mesh();
      mesh.name = `${node}_${index}`;
      group.add(mesh);
    }
    root.add(group);
  }
  return root;
}

const named = (scene: Object3D, name: string) => scene.getObjectByName(name)!;

describe("setStoreyVisibility", () => {
  it("shows the geometry of the chosen storey, not just its group", () => {
    const scene = buildingScene();

    setStoreyVisibility(scene, ["storey_a1"]);

    expect(named(scene, "storey_a1").visible).toBe(true);
    expect(named(scene, "storey_a1_0").visible).toBe(true);
    expect(named(scene, "storey_a1_2").visible).toBe(true);
  });

  it("hides the other storeys and their geometry", () => {
    const scene = buildingScene();

    setStoreyVisibility(scene, ["storey_a1"]);

    expect(named(scene, "storey_a0").visible).toBe(false);
    expect(named(scene, "storey_a0_0").visible).toBe(false);
    expect(named(scene, "storey_a2_1").visible).toBe(false);
  });

  it("shows every storey when nothing is selected", () => {
    const scene = buildingScene();
    setStoreyVisibility(scene, ["storey_a1"]);

    setStoreyVisibility(scene, []);

    for (const name of ["storey_a0", "storey_a0_0", "storey_a2", "storey_a2_2"]) {
      expect(named(scene, name).visible).toBe(true);
    }
  });

  it("does not touch anything that is not a storey", () => {
    const scene = buildingScene();
    const other = new Mesh();
    other.name = "HV_CEILING";
    other.visible = true;
    scene.add(other);

    setStoreyVisibility(scene, ["storey_a1"]);

    expect(other.visible).toBe(true);
  });
});
