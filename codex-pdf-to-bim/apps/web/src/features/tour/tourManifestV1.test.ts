import { describe, expect, it } from "vitest";

import blenderManifest from "./__fixtures__/blender-kitchen-family-manifest.json";
import { manifestSchema } from "./tourManifest";

describe("Blender-authored kitchen/family manifest", () => {
  it("still validates now that the schema is a v1/v2 union", () => {
    const result = manifestSchema.safeParse(blenderManifest);

    if (!result.success) {
      console.log(JSON.stringify(result.error.issues.slice(0, 10), null, 1));
    }
    expect(result.success).toBe(true);
  });

  it("keeps the spike labelled as unmeasured staging", () => {
    const parsed = manifestSchema.parse(blenderManifest);

    expect(parsed.schema).toBe("hearthview-tour-spike/v1");
    expect(parsed.canonical_geometry).toBe(false);
    expect(parsed.artifact.glb).toBe("hearthview-kitchen-family.glb");
  });
});
