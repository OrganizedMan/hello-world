import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import type { A1TraceResponse } from "../../api/types";
import { A1TraceCanvas } from "./A1TraceCanvas";


const trace: A1TraceResponse = {
  page_number: 2,
  page_width_points: 2592,
  page_height_points: 1728.24,
  proposed_crop: { x0: 1120, y0: 300, x1: 2220, y1: 1630 },
  summary: { verified: 1, traced: 1, ambiguous: 1 },
  approval_blocked: true,
  records: [
    { id: "wall.north.kitchen", kind: "wall", room: "kitchen", provenance: "linework_traced", geometry: { points: [[1260, 570], [1720, 570], [1720, 584], [1260, 584]], closed: true }, source_page: 2, dimension_labels: [] },
    { id: "ambiguous.example", kind: "opening", room: "kitchen", provenance: "ambiguous", geometry: { points: [[1600, 570], [1708, 570], [1708, 586], [1600, 586]], closed: true }, source_page: 2, dimension_labels: [] },
  ],
};


describe("A1TraceCanvas", () => {
  it("keeps trace paths in the source-coordinate viewBox", () => {
    render(<A1TraceCanvas trace={trace} mode="overlay" provenanceFilter="all" selectedId={null} onSelect={() => {}} />);

    expect(screen.getByLabelText("A-1 proposed-plan trace")).toHaveAttribute("viewBox", "1120 300 1100 1330");
    expect(screen.getByTestId("trace-wall.north.kitchen")).toBeVisible();
  });

  it("distinguishes linework-traced and ambiguous records", () => {
    render(<A1TraceCanvas trace={trace} mode="trace" provenanceFilter="all" selectedId={null} onSelect={() => {}} />);

    expect(screen.getByTestId("trace-wall.north.kitchen")).toHaveAttribute("data-provenance", "linework_traced");
    expect(screen.getByTestId("trace-ambiguous.example")).toHaveAttribute("data-provenance", "ambiguous");
  });
});
