import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { TourOrientationMap } from "./TourOrientationMap";


describe("TourOrientationMap", () => {
  it("draws regions and openings from canonical manifest geometry", () => {
    const { container } = render(
      <TourOrientationMap orientation={{
        bounds: { name: "focused_a1", min_x: 0, min_y: 0, max_x: 10.9982, max_y: 6.6802 },
        north_vector: [0, -1],
        north_up: true,
        regions: [
          { name: "kitchen", min_x: 0, min_y: 0, max_x: 4.6736, max_y: 4.8514 },
          { name: "family_room", min_x: 4.6736, min_y: 0, max_x: 9.1694, max_y: 4.8514 },
          { name: "mudroom_context", min_x: 9.1694, min_y: 3.3528, max_x: 10.9982, max_y: 5.7912 },
        ],
        openings: [
          { name: "family_east_window", wall: "east", footprint: { name: "family_east_window", min_x: 9.1694, min_y: 0.3048, max_x: 9.3218, max_y: 1.524 } },
          { name: "mudroom_opening", wall: "east", footprint: { name: "mudroom_opening", min_x: 9.1694, min_y: 3.3528, max_x: 9.3218, max_y: 5.7912 } },
        ],
      }} />,
    );

    expect(screen.getByText("Kitchen")).toBeVisible();
    expect(screen.getByText("Family room")).toBeVisible();
    expect(screen.getByText("Mudroom")).toBeVisible();
    expect(screen.getByText("N")).toBeVisible();
    expect(container.querySelectorAll("[data-tour-region]")).toHaveLength(3);
    expect(container.querySelectorAll("[data-tour-opening]")).toHaveLength(2);
    const kitchen = container.querySelector('[data-tour-region="kitchen"] rect');
    const family = container.querySelector('[data-tour-region="family_room"] rect');
    expect(Number(family?.getAttribute("x"))).toBeLessThan(Number(kitchen?.getAttribute("x")));
  });

  it("draws the traced +y-north frame as a north-up, east-right plan", () => {
    // The traced pipeline authors +y north with no mirror anywhere, so the
    // kitchen (west) must land left of the family room (east) and the north
    // wall must land above the south wall.
    const { container } = render(
      <TourOrientationMap orientation={{
        bounds: { name: "kitchen_family", min_x: 0, min_y: 0, max_x: 8.7986, max_y: 5.9639 },
        north_vector: [0, 1],
        north_up: true,
        regions: [
          { name: "kitchen", min_x: 0, min_y: 0, max_x: 3.3308, max_y: 5.9639 },
          { name: "family_room", min_x: 4.8471, min_y: 1.5201, max_x: 8.4486, max_y: 5.6139 },
        ],
        openings: [
          { name: "hv_north_window_1", wall: "north", footprint: { name: "hv_north_window_1", min_x: 1.51, min_y: 5.8114, max_x: 2.85, max_y: 5.9639 } },
        ],
      }} />,
    );

    const kitchen = container.querySelector('[data-tour-region="kitchen"] rect');
    const family = container.querySelector('[data-tour-region="family_room"] rect');
    expect(Number(kitchen?.getAttribute("x"))).toBeLessThan(Number(family?.getAttribute("x")));
    // The kitchen arm runs to the south wall; the family room's clear area
    // stops short of both walls, so it is inset from the top of the map.
    expect(Number(kitchen?.getAttribute("y"))).toBeLessThan(Number(family?.getAttribute("y")));
    // The window is on the north wall, so it draws near the top edge.
    const window = container.querySelector('[data-tour-opening="hv_north_window_1"]');
    expect(Number(window?.getAttribute("y1"))).toBeLessThan(6);
  });
});
