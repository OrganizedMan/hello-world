import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it } from "vitest";

import { PlansPage } from "./PlansPage";


describe("PlansPage", () => {
  it("shows A-1 with labeled source and zoom controls", async () => {
    const user = userEvent.setup();
    render(
      <MemoryRouter>
        <PlansPage projectId="project-1" sourceId="source-1" pageCount={4} />
      </MemoryRouter>,
    );

    expect(screen.getByRole("heading", { name: "Choose the proposed plan" })).toBeVisible();
    expect(screen.getByRole("img", { name: "Sheet A-1 proposed first-floor plan" })).toBeVisible();
    expect(screen.getByLabelText("Plan zoom")).toHaveValue("100");
    await user.click(screen.getByRole("button", { name: "Use proposed first floor" }));
    expect(screen.getByText("Proposed first floor selected")).toBeVisible();
  });

  it("shows every PDF page and prevents a non-A-1 page from being mislabeled", async () => {
    const user = userEvent.setup();
    render(
      <MemoryRouter>
        <PlansPage projectId="project-1" sourceId="source-1" pageCount={4} />
      </MemoryRouter>,
    );

    expect(screen.getByRole("button", { name: "Page 1" })).toBeVisible();
    expect(screen.getByRole("button", { name: "Page 4" })).toBeVisible();
    await user.click(screen.getByRole("button", { name: "Page 3" }));

    expect(screen.getByRole("button", { name: "Use proposed first floor" })).toBeDisabled();
    expect(screen.getByRole("alert")).toHaveTextContent("Select page 2");
  });
});
