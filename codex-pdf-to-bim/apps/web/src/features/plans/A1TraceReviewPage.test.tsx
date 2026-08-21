import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it } from "vitest";

import type { A1TraceResponse } from "../../api/types";
import { A1TraceReviewPage } from "./A1TraceReviewPage";


const trace: A1TraceResponse = {
  page_number: 2,
  page_width_points: 2592,
  page_height_points: 1728.24,
  proposed_crop: { x0: 1120, y0: 300, x1: 2220, y1: 1630 },
  summary: { verified: 2, traced: 3, ambiguous: 0 },
  approval_blocked: false,
  records: [
    { id: "wall.north.kitchen", kind: "wall", room: "kitchen", provenance: "linework_traced", geometry: { points: [[1260, 570], [1720, 570], [1720, 584], [1260, 584]], closed: true }, source_page: 2, dimension_labels: [] },
    { id: "fixed.island", kind: "fixed", room: "kitchen", provenance: "dimension_verified", geometry: { points: [[1450, 770], [1618, 770], [1618, 870], [1450, 870]], closed: true }, source_page: 2, dimension_labels: ["8'-7\""] },
  ],
};


describe("A1TraceReviewPage", () => {
  it("lets the homeowner switch to an overlay and inspect source provenance", async () => {
    const user = userEvent.setup();
    render(<MemoryRouter><A1TraceReviewPage projectId="project-1" sourceId="source-1" trace={trace} /></MemoryRouter>);

    await user.click(screen.getByRole("button", { name: "Overlay" }));
    await user.click(within(screen.getByLabelText("Trace records")).getByRole("button", { name: /kitchen wall/i }));

    expect(screen.getByText("Trace approval: pending")).toBeVisible();
    expect(screen.getByText("Position follows visible A-1 linework; no printed offset is claimed.")).toBeVisible();
    expect(screen.getByLabelText("A-1 proposed-plan trace")).toBeVisible();
  });
});
