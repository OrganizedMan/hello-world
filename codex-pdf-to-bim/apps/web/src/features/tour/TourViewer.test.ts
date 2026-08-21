import { BoxGeometry, DirectionalLight, Mesh, MeshStandardMaterial, Scene } from "three";
import { describe, expect, it } from "vitest";

import { prepareTourSceneForBrowser, setOverheadVisibility } from "./TourViewer";


describe("TourViewer browser scene preparation", () => {
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
});
