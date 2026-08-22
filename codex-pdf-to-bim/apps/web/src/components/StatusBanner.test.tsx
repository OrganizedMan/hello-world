import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { StatusBanner } from "./StatusBanner";


describe("StatusBanner", () => {
  it("translates model status into homeowner language", () => {
    render(<StatusBanner status="NEEDS_INPUT" remaining={3} />);

    expect(screen.getByRole("status")).toHaveTextContent("Needs your input");
    expect(screen.getByText("3 drawing details left to confirm")).toBeVisible();
  });
});
