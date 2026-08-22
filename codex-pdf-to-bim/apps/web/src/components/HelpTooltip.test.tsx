import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import { HelpTooltip } from "./HelpTooltip";


describe("HelpTooltip", () => {
  it("opens from the keyboard and closes with Escape", async () => {
    const user = userEvent.setup();
    render(
      <HelpTooltip label="How local processing works">
        Your PDF is processed by the local service and never uploaded.
      </HelpTooltip>,
    );

    await user.tab();
    await user.keyboard("{Enter}");
    expect(screen.getByRole("tooltip")).toHaveTextContent("never uploaded");

    await user.keyboard("{Escape}");
    expect(screen.queryByRole("tooltip")).not.toBeInTheDocument();
  });
});
