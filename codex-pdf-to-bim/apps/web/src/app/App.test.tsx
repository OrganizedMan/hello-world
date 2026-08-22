import { render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { App } from "./App";


vi.mock("../features/tour/TourViewer", () => ({
  TourViewer: ({ onReady }: { onReady: () => void }) => {
    queueMicrotask(onReady);
    return <div>Tour room canvas</div>;
  },
}));


describe("HearthView welcome screen", () => {
  beforeEach(() => {
    window.history.pushState({}, "", "/");
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("introduces the homeowner workflow and local processing", () => {
    render(<App />);

    expect(
      screen.getByRole("heading", { name: "See your plans come to life" }),
    ).toBeVisible();
    expect(screen.getByText("Your plans stay on this Mac")).toBeVisible();
  });

  it("opens the isolated tour route without changing the homeowner workflow", async () => {
    vi.stubGlobal("fetch", vi.fn(() => Promise.resolve({
      ok: true,
      json: () => Promise.resolve({
        schema: "hearthview-tour-spike/v1",
        label: "Quality spike · visual staging",
        canonical_geometry: false,
        canonical_model_hash: "a".repeat(64),
        canonical_geometry_hash: "b".repeat(64),
        island_footprint: { name: "island", min_x: 1.7272, min_y: 1.7272, max_x: 4.3434, max_y: 3.0226 },
        orientation: {
          bounds: { name: "focused_a1", min_x: 0, min_y: 0, max_x: 9.1694, max_y: 4.8514 },
          north_vector: [0, -1],
          north_up: true,
          regions: [
            { name: "kitchen", min_x: 0, min_y: 0, max_x: 4.6736, max_y: 4.8514 },
            { name: "family_room", min_x: 4.6736, min_y: 0, max_x: 9.1694, max_y: 4.8514 },
          ],
          openings: [
            { name: "south_living_opening", wall: "south", footprint: { name: "south_living_opening", min_x: 6.6802, min_y: 4.699, max_x: 8.2042, max_y: 4.8514 } },
          ],
        },
        provisional_categories: ["cabinetry_detail", "hardware", "finishes", "furniture", "decor", "undimensioned_offsets"],
        artifact: { glb: "hearthview-kitchen-family.glb", poster: "poster.webp", environment: "environment.hdr", total_browser_bytes: 24_604_690 },
        runtime: {
          eye_height_meters: 1.65,
          walkable: { min_x: 0.18, max_x: 8.9894, min_z: -4.6714, max_z: -0.18 },
          barriers: [],
          camera_presets: [
            { name: "kitchen_overview", position: [0.7, 1.65, -4.3014], target: [4.3434, 0.9, -3.0226], up: [0, 1, 0] },
            { name: "walk_start", position: [4.15, 1.65, -4.2014], target: [5.2, 1.65, -2.1], up: [0, 1, 0] },
            { name: "overhead", position: [4.5847, 8, -2.4257], target: [4.5847, 0, -2.4257], up: [0, 0, 1] },
          ],
        },
      }),
    } as Response)));
    window.history.pushState({}, "", "/tour-spike");

    render(<App />);

    expect(await screen.findByRole("heading", { name: "Explore the proposed kitchen and family room" })).toBeVisible();
    expect(screen.getByRole("navigation", { name: "Project workflow" })).toBeVisible();
  });
});
