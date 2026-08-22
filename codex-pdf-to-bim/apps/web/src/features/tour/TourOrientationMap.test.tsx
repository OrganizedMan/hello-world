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
});
