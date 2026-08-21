import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";

import { ModelPage, type GeometryArtifact } from "./ModelPage";


vi.mock("./ModelViewer", () => ({
  ModelViewer: ({ onSelect }: { onSelect: (id: string) => void }) => (
    <button type="button" onClick={() => onSelect("kitchen_island")}>Select kitchen island in 3D</button>
  ),
}));


const artifact: GeometryArtifact = {
  artifact_id: "artifact-1",
  model_hash: "model-abc123",
  geometry_hash: "geometry-abc123",
  glb_file_hash: "file-abc123",
  island_dimensions: `8'-6" × 4'-2"`,
  primitive_count: 11,
  bounds_ticks: ["0", "0", "0", "1", "1", "1"],
  download_url: "/model.glb",
};


describe("ModelPage", () => {
  it("keeps geometry identity visible while cameras change", async () => {
    const user = userEvent.setup();
    render(<MemoryRouter><ModelPage artifact={artifact} projectId="project-1" sourceId="source-1" /></MemoryRouter>);

    expect(screen.getByTestId("geometry-hash")).toHaveTextContent("geometry-abc123");
    await user.click(screen.getByRole("button", { name: "Kitchen view" }));
    expect(screen.getByTestId("geometry-hash")).toHaveTextContent("geometry-abc123");
    expect(screen.getByText("Kitchen camera selected")).toBeVisible();
  });

  it("links a selected 3D element back to its plan evidence", async () => {
    const user = userEvent.setup();
    render(<MemoryRouter><ModelPage artifact={artifact} projectId="project-1" sourceId="source-1" /></MemoryRouter>);

    await user.click(screen.getByRole("button", { name: "Select kitchen island in 3D" }));
    expect(screen.getByRole("heading", { name: "Kitchen island" })).toBeVisible();
    expect(screen.getByText(`8'-6" × 4'-2" confirmed during guided review.`)).toBeVisible();
    expect(screen.getByRole("img", { name: "A-1 evidence for Kitchen island" })).toHaveAttribute(
      "src",
      "/api/projects/project-1/evidence/src_a1_island/preview?max_width=900",
    );
  });

  it("offers a keyboard-accessible element list alongside canvas selection", async () => {
    const user = userEvent.setup();
    render(<MemoryRouter><ModelPage artifact={artifact} projectId="project-1" sourceId="source-1" /></MemoryRouter>);

    await user.click(screen.getByRole("button", { name: "Kitchen island" }));

    expect(screen.getByRole("heading", { name: "Kitchen island" })).toBeVisible();
  });
});
