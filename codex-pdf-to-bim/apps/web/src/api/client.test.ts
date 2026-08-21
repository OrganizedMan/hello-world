import { afterEach, describe, expect, it, vi } from "vitest";

import { ApiError, requestJson } from "./client";


describe("API client", () => {
  afterEach(() => vi.unstubAllGlobals());

  it("preserves plain-language recovery guidance from the local service", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        new Response(
          JSON.stringify({
            code: "INVALID_PDF",
            message: "HearthView could not read this PDF.",
            action: "Choose an unencrypted architectural PDF and try again.",
          }),
          { status: 422, headers: { "Content-Type": "application/json" } },
        ),
      ),
    );

    await expect(requestJson("/api/projects/one/sources")).rejects.toEqual(
      new ApiError(
        422,
        "INVALID_PDF",
        "HearthView could not read this PDF.",
        "Choose an unencrypted architectural PDF and try again.",
      ),
    );
  });
});
