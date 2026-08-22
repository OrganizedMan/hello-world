import { BoxGeometry, DirectionalLight, DoubleSide, FrontSide, Mesh, MeshStandardMaterial, PerspectiveCamera, Scene } from "three";
import { describe, expect, it, vi } from "vitest";

import { applyCameraPreset, frameLoopForMode, prepareTourSceneForBrowser, setOverheadVisibility } from "./TourViewer";


describe("TourViewer browser scene preparation", () => {
  it("renders continuously only while walking", () => {
    expect(frameLoopForMode("orbit")).toBe("demand");
    expect(frameLoopForMode("move")).toBe("demand");
    expect(frameLoopForMode("walk")).toBe("always");
  });

  it("keeps authored geometry but disables Blender lights that would double-light the room", () => {
    const source = new Scene();
    const light = new DirectionalLight("white", 1200);
    light.name = "HV_LIGHTING_SUN";
    const cabinet = new Mesh(new BoxGeometry(), new MeshStandardMaterial());
    cabinet.name = "HV_CABINETRY_TEST";
    source.add(light, cabinet);

    const prepared = prepareTourSceneForBrowser(source);
    const preparedLight = prepared.getObjectByName("HV_LIGHTING_SUN");
    const preparedCabinet = prepared.getObjectByName("HV_CABINETRY_TEST") as Mesh;

    expect(prepared).not.toBe(source);
    expect(preparedLight?.visible).toBe(false);
    expect(light.visible).toBe(true);
    expect(preparedCabinet.castShadow).toBe(true);
    expect(preparedCabinet.receiveShadow).toBe(true);
  });

  /**
   * The model culls back faces, and three.js then derives shadowSide as
   * BackSide -- which, with the depth bias these thin walls need, cancelled
   * every shadow in the house and left it looking like white cardboard.
   */
  it("casts shadows from both sides of a front-side material", () => {
    const source = new Scene();
    const wall = new Mesh(new BoxGeometry(), new MeshStandardMaterial({ side: FrontSide }));
    wall.name = "HV_WALL_TEST";
    source.add(wall);

    const prepared = prepareTourSceneForBrowser(source);
    const material = (prepared.getObjectByName("HV_WALL_TEST") as Mesh).material as MeshStandardMaterial;

    expect(material.shadowSide).toBe(DoubleSide);
  });

  it("removes only the ceiling from an overhead view and restores it afterward", () => {
    const scene = new Scene();
    const ceiling = new Mesh(new BoxGeometry(), new MeshStandardMaterial());
    ceiling.name = "HV_CEILING";
    const kitchen = new Mesh(new BoxGeometry(), new MeshStandardMaterial());
    kitchen.name = "HV_CABINETRY_TEST";
    scene.add(ceiling, kitchen);

    setOverheadVisibility(scene, true);
    expect(ceiling.visible).toBe(false);
    expect(kitchen.visible).toBe(true);

    setOverheadVisibility(scene, false);
    expect(ceiling.visible).toBe(true);
  });

  /**
   * The overhead preset was authored with `up` along Z so a camera looking
   * straight down had a defined roll. OrbitControls measures polar angle from
   * the camera's up vector, so under that up an overhead camera sits at 90
   * degrees -- past maxPolarAngle -- and the controls swung it off the plan the
   * moment they took over. Leaning the camera south of vertical under a normal
   * +Y up gives the same picture and a polar angle near zero.
   */
  it("keeps overhead cameras upright and off the vertical axis", () => {
    const camera = new PerspectiveCamera();
    let upAtLookAt: [number, number, number] | undefined;
    vi.spyOn(camera, "lookAt").mockImplementation(() => {
      upAtLookAt = camera.up.toArray();
    });

    applyCameraPreset(camera, {
      name: "overhead",
      position: [4.5847, 8, -2.4257],
      target: [4.5847, 0, -2.4257],
      up: [0, 0, 1],
    });

    expect(upAtLookAt).toEqual([0, 1, 0]);
    const [x, y, z] = camera.position.toArray();
    expect([x, y]).toEqual([4.5847, 8]);
    // South of the target, so the plan reads north-up.
    expect(z).toBeGreaterThan(-2.4257);
    expect(z).toBeLessThan(0);
  });

  it("leaves a preset that already looks sideways where it was", () => {
    const camera = new PerspectiveCamera();
    applyCameraPreset(camera, {
      name: "kitchen_overview",
      position: [19.3459, 14.804, 5.469],
      target: [6.064, 2.6289, -7.8129],
      up: [0, 1, 0],
    });

    expect(camera.position.toArray()).toEqual([19.3459, 14.804, 5.469]);
  });
});
