import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { LengthField } from "./LengthField";


describe("LengthField", () => {
  it("keeps its label, units, format help, and corrective error visible", async () => {
    const user = userEvent.setup();
    const onCommit = vi.fn();
    const initialLength = `8'-7"`;
    render(
      <LengthField
        id="island-width"
        label="Island width"
        value={initialLength}
        onCommit={onCommit}
      />,
    );

    const input = screen.getByLabelText("Island width");
    expect(input).toHaveAccessibleDescription("Enter feet and inches, for example 8'-7\".");
    expect(screen.getByText("ft / in")).toBeVisible();
    await user.clear(input);
    await user.type(input, "banana{Enter}");

    expect(screen.getByRole("alert")).toHaveTextContent("Use a length such as 5' 0\"");
    expect(onCommit).not.toHaveBeenCalled();
  });

  it("commits a clearly formatted length", async () => {
    const user = userEvent.setup();
    const onCommit = vi.fn();
    const initialLength = `5'-0"`;
    render(
      <LengthField
        id="opening"
        label="Opening width"
        value={initialLength}
        onCommit={onCommit}
      />,
    );

    await user.click(screen.getByLabelText("Opening width"));
    await user.keyboard("{Enter}");

    expect(onCommit).toHaveBeenCalledWith("5'-0\"");
  });
});
