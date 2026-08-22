import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { ReviewWorkspace } from "./ReviewPage";


const queue = [
  {
    id: "review_a1_region",
    title: "Use the proposed first-floor plan?",
    question: "Is this the proposed first-floor plan you want to explore?",
    help_text: "Confirming keeps it separate from the existing plan.",
    source_ref_id: "src_a1_region",
    field_name: null,
    value: null,
    state: "UNREVIEWED" as const,
  },
  {
    id: "review_a1_island",
    title: "Confirm the kitchen island",
    question: "Is the kitchen island 8 feet 7 inches by 4 feet 3 inches?",
    help_text: "Printed dimensions control every view.",
    source_ref_id: "src_a1_island",
    field_name: "island_size",
    value: "8'-7\" × 4'-3\"",
    state: "UNREVIEWED" as const,
  },
];


describe("ReviewWorkspace", () => {
  it("shows one understandable decision and advances after confirmation", async () => {
    const user = userEvent.setup();
    const onConfirm = vi.fn().mockResolvedValue({ revision: 1, eventId: "event-1" });
    render(<ReviewWorkspace queue={queue} revision={0} onConfirm={onConfirm} onUndo={vi.fn().mockResolvedValue(2)} />);

    expect(screen.getByText("1 of 2")).toBeVisible();
    expect(screen.getByRole("heading", { name: queue[0].title })).toBeVisible();
    await user.click(screen.getByRole("button", { name: "Confirm and continue" }));

    expect(onConfirm).toHaveBeenCalledWith(queue[0], 0, { operation: "APPROVE_REVIEW", payload: {} });
    expect(screen.getByRole("heading", { name: queue[1].title })).toBeVisible();
    expect(screen.getByLabelText("Island width")).toBeVisible();
    expect(screen.getByLabelText("Island depth")).toBeVisible();
  });

  it("undoes the saved event before returning to the prior card", async () => {
    const user = userEvent.setup();
    const onConfirm = vi.fn().mockResolvedValue({ revision: 1, eventId: "event-1" });
    const onUndo = vi.fn().mockResolvedValue(2);
    render(<ReviewWorkspace queue={queue} revision={0} onConfirm={onConfirm} onUndo={onUndo} />);

    await user.click(screen.getByRole("button", { name: "Confirm and continue" }));
    await user.click(screen.getByRole("button", { name: "Go back" }));

    expect(onUndo).toHaveBeenCalledWith("event-1", 1);
    expect(screen.getByRole("heading", { name: queue[0].title })).toBeVisible();
  });

  it("uses a corrected dimension when confirm is clicked without pressing Enter", async () => {
    const user = userEvent.setup();
    const onConfirm = vi.fn()
      .mockResolvedValueOnce({ revision: 1, eventId: "event-1" })
      .mockResolvedValueOnce({ revision: 2, eventId: "event-2" });
    render(<ReviewWorkspace queue={queue} revision={0} onConfirm={onConfirm} onUndo={vi.fn().mockResolvedValue(3)} />);

    await user.click(screen.getByRole("button", { name: "Confirm and continue" }));
    const width = screen.getByLabelText("Island width");
    await user.clear(width);
    await user.type(width, `8'-6"`);
    await user.click(screen.getByRole("button", { name: "Confirm and continue" }));

    expect(onConfirm).toHaveBeenLastCalledWith(queue[1], 1, {
      operation: "EDIT_AND_APPROVE",
      payload: { width: `8'-6"`, depth: `4'-3"` },
    });
  });
});
