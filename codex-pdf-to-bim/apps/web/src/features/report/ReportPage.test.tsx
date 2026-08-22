import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it } from "vitest";

import { ReportPage, type HomeownerReport } from "./ReportPage";


const report: HomeownerReport = {
  status: "READY_TO_VIEW",
  blocking_count: 0,
  evidence_coverage_percent: 100,
  source_name: "Garrigan plans.pdf",
  source_hash: "source-1234567890",
  model_hash: "model-1234567890",
  geometry_hash: "geometry-1234567890",
  island_dimensions: `8'-6" × 4'-2"`,
  validator_version: "hearthview-validator-0.1.0",
  issues: [],
};


describe("ReportPage", () => {
  it("summarizes readiness, evidence, and all three identities", () => {
    render(<MemoryRouter><ReportPage report={report} /></MemoryRouter>);

    expect(screen.getByRole("heading", { name: "Your plan-to-3D report" })).toBeVisible();
    expect(screen.getByText("of modeled elements linked to evidence")).toBeVisible();
    expect(screen.getByText("source-1234567890")).toBeVisible();
    expect(screen.getByText("model-1234567890")).toBeVisible();
    expect(screen.getByText("geometry-1234567890")).toBeVisible();
    expect(screen.getByText("Ready to view and render")).toBeVisible();
    expect(screen.getByText(`8'-6" × 4'-2"`)).toBeVisible();
  });
});
