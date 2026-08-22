import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import { HomePage } from "./HomePage";


describe("HomePage import", () => {
  afterEach(() => vi.unstubAllGlobals());

  it("creates a local project, uploads the PDF, and opens plan review", async () => {
    const responses = [
      new Response(JSON.stringify({ id: "project-1", name: "My renovation", revision: 0 }), {
        status: 201,
        headers: { "Content-Type": "application/json" },
      }),
      new Response(
        JSON.stringify({
          id: "source-1",
          display_name: "plans.pdf",
          sha256: "a".repeat(64),
          byte_count: 9,
          page_count: 4,
        }),
        { status: 201, headers: { "Content-Type": "application/json" } },
      ),
    ];
    vi.stubGlobal("fetch", vi.fn().mockImplementation(() => Promise.resolve(responses.shift())));
    const user = userEvent.setup();
    render(
      <MemoryRouter initialEntries={["/"]}>
        <Routes>
          <Route path="/" element={<HomePage />} />
          <Route path="/projects/:projectId/plans" element={<p>Plans ready to review</p>} />
        </Routes>
      </MemoryRouter>,
    );

    await user.upload(
      screen.getByLabelText("Add plan PDFs"),
      new File(["pdf bytes"], "plans.pdf", { type: "application/pdf" }),
    );

    expect(await screen.findByText("Plans ready to review")).toBeVisible();
  });
});
