# HearthView tour-quality spike

**Quality spike · visual staging**

This is an isolated, throwaway proof of quality. It remains unproven until the
geometry, realism, and navigation gates all pass. Its display GLB is not
canonical HearthView geometry.

`scene_contract.py` is the only source for the A-1 printed dimensions and
spatial metadata consumed by later spike work. Cabinet fronts, hardware,
finishes, furnishings, decor, and undimensioned offsets are provisional visual
staging rather than measured claims.

Generate the browser-ready artifact set with Blender 5.2 or newer. The external
asset directory must contain the files recorded in `assets/provenance.json`.

```sh
/Applications/Blender.app/Contents/MacOS/Blender \
  --background \
  --factory-startup \
  --python spikes/tour_quality/build_scene.py \
  -- \
  --repo "$PWD" \
  --assets "/absolute/path/to/tour-quality-assets" \
  --output-dir "$PWD/apps/web/public/tour-spike"
```

The generated and validated artifact set is:

- `apps/web/public/tour-spike/hearthview-kitchen-family.glb`
- `apps/web/public/tour-spike/manifest.json`
- `apps/web/public/tour-spike/poster.webp`
- `apps/web/public/tour-spike/environment.hdr`

Validate a generated set independently from Blender:

```sh
uv run python -m spikes.tour_quality.validate_artifact \
  --glb apps/web/public/tour-spike/hearthview-kitchen-family.glb \
  --manifest apps/web/public/tour-spike/manifest.json \
  --public-dir apps/web/public/tour-spike
```

The approved spike payload is 24,604,690 bytes. Furniture, decor, and finishes
remain provisional staging; approval covers the measurable envelope, openings,
cabinetry, island placement, artifact contract, and browser payload gate.
