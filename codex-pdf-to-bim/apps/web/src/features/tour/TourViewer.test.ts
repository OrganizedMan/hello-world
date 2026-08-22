import { BoxGeometry, DirectionalLight, Mesh, MeshStandardMaterial, PerspectiveCamera, Scene } from "three";
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

  it("applies the north-up vector before aiming an overhead camera", () => {
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

    expect(camera.position.toArray()).toEqual([4.5847, 8, -2.4257]);
    expect(upAtLookAt).toEqual([0, 0, 1]);
  });
});
