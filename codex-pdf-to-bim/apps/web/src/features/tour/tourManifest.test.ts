import { describe, expect, it } from "vitest";

import { manifestSchema } from "./tourManifest";


describe("tour manifest integrity boundary", () => {
  it.each(["canonical_model_hash", "canonical_geometry_hash", "orientation"])(
    "rejects a manifest missing %s",
    (field) => {
      const result = manifestSchema.safeParse({
        schema: "hearthview-tour-spike/v1",
        label: "Quality spike · visual staging",
        canonical_geometry: false,
        [field === "canonical_model_hash" ? "canonical_geometry_hash" : "canonical_model_hash"]: "a".repeat(64),
      });

      expect(result.success).toBe(false);
    },
  );
});
