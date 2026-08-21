import { Object3D } from "three";
import { render, screen } from "@testing-library/react";
import type { ReactNode } from "react";
import { describe, expect, it } from "vitest";

import { canonicalElementIdFromObject, ModelLoadBoundary } from "./ModelViewer";


describe("ModelViewer selection", () => {
  it("finds the immutable element identity on a selected object's parent", () => {
    const wall = new Object3D();
    wall.userData.canonicalElementId = "family_east";
    const face = new Object3D();
    wall.add(face);

    expect(canonicalElementIdFromObject(face)).toBe("family_east");
  });

  it("does not invent an identity for decorative scene objects", () => {
    expect(canonicalElementIdFromObject(new Object3D())).toBeNull();
  });

  it("shows recovery guidance when the GLB cannot load", () => {
    function BrokenModel(): ReactNode {
      throw new Error("failed");
    }

    render(<ModelLoadBoundary><BrokenModel /></ModelLoadBoundary>);

    expect(screen.getByRole("alert")).toHaveTextContent("The 3D model could not be displayed");
    expect(screen.getByRole("alert")).toHaveTextContent("Build the model again");
  });
});
