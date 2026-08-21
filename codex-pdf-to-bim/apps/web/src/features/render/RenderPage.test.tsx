import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import { api } from "../../api/client";
import { RenderPage, type BlenderCapability } from "./RenderPage";


const availableBlender: BlenderCapability = {
  available: true,
  executable: "/opt/blender",
  version: "Blender 4.5 LTS",
  message: "Blender is ready for local photoreal rendering.",
  action: null,
};


describe("RenderPage", () => {
  afterEach(() => vi.restoreAllMocks());

  it("explains the warm furnished default without hiding controls", () => {
    render(
      <MemoryRouter>
        <RenderPage capability={availableBlender} projectId="project-1" geometryArtifactId="a" />
      </MemoryRouter>,
    );

    expect(screen.getByLabelText("Visual style")).toHaveValue("Warm Blank Slate");
    expect(screen.getByText("Lightly furnished with warm, neutral finishes")).toBeVisible();
    expect(screen.getByLabelText("Render quality")).toBeVisible();
    expect(screen.getByLabelText("Camera view")).toBeVisible();
    expect(screen.getByLabelText("Image size")).toBeVisible();
  });

  it("keeps 3D available while explaining a missing Blender install", () => {
    render(
      <MemoryRouter>
        <RenderPage capability={{ ...availableBlender, available: false, executable: null, version: null, action: "Install Blender LTS, then restart HearthView." }} />
      </MemoryRouter>,
    );

    expect(screen.getByRole("button", { name: "Create polished render" })).toBeDisabled();
    expect(screen.getByText("Install Blender LTS, then restart HearthView.")).toBeVisible();
    expect(screen.getByRole("link", { name: "Keep exploring in 3D" })).toBeVisible();
  });

  it("restores the latest render for the current verified model", async () => {
    vi.spyOn(api, "get").mockResolvedValue({
      id: "job-1",
      status: "COMPLETE",
      geometry_hash: "geometry-1",
      image_url: "/api/render-jobs/job-1/image",
      message: "Your polished render is ready.",
    });

    render(
      <MemoryRouter>
        <RenderPage capability={availableBlender} projectId="project-1" geometryArtifactId="a" />
      </MemoryRouter>,
    );

    expect(await screen.findByText("Render ready")).toBeVisible();
    expect(screen.getByAltText("Warm Blank Slate photoreal render")).toHaveAttribute(
      "src",
      "/api/render-jobs/job-1/image",
    );
  });
});
