import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { App } from "./App";


describe("HearthView welcome screen", () => {
  it("introduces the homeowner workflow and local processing", () => {
    render(<App />);

    expect(
      screen.getByRole("heading", { name: "See your plans come to life" }),
    ).toBeVisible();
    expect(screen.getByText("Your plans stay on this Mac")).toBeVisible();
  });
});
