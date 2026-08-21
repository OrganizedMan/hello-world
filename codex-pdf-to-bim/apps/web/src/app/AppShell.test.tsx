import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { App } from "./App";


describe("AppShell", () => {
  it("shows the complete workflow and local-only reassurance", () => {
    render(<App />);

    expect(screen.getByRole("navigation", { name: "Project workflow" })).toBeVisible();
    for (const step of ["Plans", "Review", "Model", "Render", "Report"]) {
      expect(screen.getByText(step)).toBeVisible();
    }
    expect(screen.getByText("Local & private")).toBeVisible();
  });
});
