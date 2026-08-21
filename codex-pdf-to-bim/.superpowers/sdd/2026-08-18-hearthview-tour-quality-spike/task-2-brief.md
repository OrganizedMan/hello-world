# Task 2 — Detailed Blender display scene and validation artifacts

## Context

Task 1 established the sole geometry contract in `spikes/tour_quality/scene_contract.py`. This task turns it into one real-scale, browser-ready kitchen–family-room GLB, one 1920×1080 validation poster, one local HDR environment, and one manifest. The result is an isolated quality spike, never canonical BIM geometry. The next task consumes its runtime navigation metadata.

The worker cannot write the user-authorized repo directly. Stage all relative outputs under:

`/Users/jackgarrigan/Documents/Codex/2026-08-18/bui/work/task-2-staging`

Read Task 1 code from:

`/Users/jackgarrigan/Developer/hello-world/codex-pdf-to-bim`

The controller will mechanically transfer the reviewed staged files.

## Binding global constraints

- Consume Task 1 constants; do not re-derive: span `9.1694`, room depth `4.8514`, counter zone `0.6604`, ceiling `2.5654`, island `2.6162 × 1.2954`, west/north counter-face clearance `1.0668`, south transition `1.8288`, living clear width `4.4958`, eye height `1.65` meters.
- Blender authoring coordinates are X width, Y depth from north to south, Z up. glTF is Y-up; runtime metadata must explicitly convert a source `(x,y)` floor point to Three.js `(x,0,-y)`.
- Every artifact says `Quality spike · visual staging`, `canonical_geometry: false`, and names the six Task 1 provisional categories.
- Existing HearthView backend, canonical geometry, and web features are untouched.
- Browser payload (`GLB + environment HDR + poster + manifest`) must be at most 45,000,000 bytes.
- Assets are local after preparation; generated browser files contain no HTTP(S) resource dependency.
- PBR authoring uses actual base-color, OpenGL normal, and roughness/ARM maps. Do not substitute procedural noise for the hero floor, stone, plaster, or linen surfaces.
- Preserve a warm, furnished but generic blank-slate character. No personal photos, brands, bold art, or clutter.
- Tests exercise artifact behavior, not source strings or mocks.

## Files

Stage these new source files:

- `spikes/tour_quality/build_scene.py` — Blender CLI/orchestration, scene assembly, render/export, manifest/hashes.
- `spikes/tour_quality/blender_builders.py` — focused bpy helpers for PBR materials, beveled objects, cabinets, openings, furniture, metadata roots, and imports.
- `spikes/tour_quality/validate_artifact.py` — pure Python GLB/manifest/hash/payload validator runnable outside Blender.
- `spikes/tour_quality/assets/provenance.json` — exact downloaded inputs and transformations.
- `spikes/tour_quality/assets/LICENSES.md` — concise license/source pages, not copied site text.
- `tests/backend/test_tour_artifact_validation.py` — TDD coverage for the real validator.

Stage these generated browser files:

- `apps/web/public/tour-spike/hearthview-kitchen-family.glb`
- `apps/web/public/tour-spike/manifest.json`
- `apps/web/public/tour-spike/poster.webp`
- `apps/web/public/tour-spike/environment.hdr`

Write the full report to:

`/Users/jackgarrigan/Documents/Codex/2026-08-18/bui/work/task-2-staging/task-2-report.md`

Do not commit and do not spawn subagents.

## Required interfaces and schema

`validate_artifact(glb_path: Path, manifest_path: Path, *, public_dir: Path | None = None) -> tuple[str, ...]`

`main()` in `validate_artifact.py` accepts optional `--glb`, `--manifest`, and `--public-dir`; defaults resolve the staged/repo public paths when run from the repo. It prints each error and exits non-zero, or prints a short validated size/hash summary and exits zero.

Manifest schema is exactly `hearthview-tour-spike/v1`. Start from `build_scene_contract().to_manifest()` and add:

```json
{
  "artifact": {
    "glb": "hearthview-kitchen-family.glb",
    "poster": "poster.webp",
    "environment": "environment.hdr",
    "sha256": {"glb": "…", "poster": "…", "environment": "…"},
    "bytes": {"glb": 0, "poster": 0, "environment": 0, "manifest": 0},
    "total_browser_bytes": 0
  },
  "runtime": {
    "coordinate_rule": "three_x=source_x;three_y=source_z;three_z=-source_y",
    "eye_height_meters": 1.65,
    "walkable": {"min_x": 0.18, "max_x": 8.9894, "min_z": -4.6714, "max_z": -0.18},
    "barriers": [
      {"name": "west_counter", "min_x": 0.0, "max_x": 0.6604, "min_z": -2.75, "max_z": 0.0},
      {"name": "north_counter", "min_x": 0.0, "max_x": 3.70, "min_z": -0.6604, "max_z": 0.0},
      {"name": "island", "min_x": 1.7272, "max_x": 4.3434, "min_z": -3.0226, "max_z": -1.7272},
      {"name": "tv_wall", "min_x": 8.9894, "max_x": 9.1694, "min_z": -2.80, "max_z": -1.25}
    ],
    "camera_presets": [
      {"name": "kitchen_overview", "position": [0.70, 1.65, -4.3014], "target": [4.3434, 0.90, -3.0226]},
      {"name": "walk_start", "position": [4.15, 1.65, -4.2014], "target": [5.20, 1.65, -2.10]},
      {"name": "overhead", "position": [4.5847, 8.0, -2.4257], "target": [4.5847, 0.0, -2.4257]}
    ]
  },
  "scene_nodes": ["HV_ARCHITECTURE", "HV_CABINETRY", "HV_FURNITURE", "HV_LIGHTING", "HV_NAVIGATION", "HV_FLOOR", "HV_ISLAND_STRUCTURE", "HV_WALKABLE"]
}
```

`bytes.manifest` and `total_browser_bytes` may be finalized by a two-pass deterministic write. The manifest must not hash itself.

## Authoring inputs

Read-only source root:

`/Users/jackgarrigan/Documents/Codex/2026-08-18/bui/work/tour-quality-assets`

Use:

- `drackenstein_quarry_puresky_1k.hdr` — Poly Haven Drackenstein Quarry Pure Sky; MD5 `34e990b4ca82563ca7a8b7aef30bb30f`.
- `wood_floor_{diff,nor_gl,rough}_2k.jpg` — Poly Haven Wood Floor; MD5s `d209b7416b022ed06093aef068c7fe23`, `e1d8a588c1fc3d62cc60da1e4cd1a689`, `325868b3352d71059753498b1c94385b`.
- `beige_wall_001_{diff,nor_gl,rough}_1k.jpg` — Poly Haven Beige Wall 001; MD5s `a99610d7d72ec6fb20ae991ad69b3eb7`, `2f5fc5b63c425b359089468f4d719ef5`, `40d8616d65055c4c984a2807ce933287`.
- `Travertine009/Travertine009_2K-JPG_{Color,NormalGL,Roughness}.jpg` — ambientCG Travertine 009; parent ZIP SHA-256 `927ca19b99e32ed65be9ae1e4c572a6c4809dc41a8b6026c76338a0359b16959`.
- `rough_linen_{diff,nor_gl,rough}_1k.jpg` — Poly Haven Rough Linen; MD5s `663db789fb075462b685c1f740e58930`, `3350269a2e9c472aa406bd3cc1eaf2c8`, `a380b24cc43cff88c39510305ebf0020`.
- `models/modern_arm_chair_01/modern_arm_chair_01_1k.gltf`, `models/modern_coffee_table_01/modern_coffee_table_01_1k.gltf`, and `models/modern_ceiling_lamp_01/modern_ceiling_lamp_01_1k.gltf`, with their adjacent `.bin` and `textures/` — Poly Haven.

Record each asset's source page, exact input files and computed SHA-256, authoring role, and any material reassignment/retint/scale in `provenance.json`. License URLs are `https://polyhaven.com/license` and `https://docs.ambientcg.com/license/`. Do not include website previews, logos, or copied descriptive text.

## TDD sequence

### RED

Write `tests/backend/test_tour_artifact_validation.py` first. Use `trimesh` to make a tiny temporary GLB fixture with named nodes/geometry; do not fake the validator. Hand-build its manifest with literal expected values. At minimum, each test must catch one production break:

1. valid literal fixture returns `()`;
2. wrong schema;
3. `canonical_geometry: true` or wrong label;
4. missing printed dimension and >3 mm dimension drift;
5. absent required scene node;
6. absent walkable/barrier/camera runtime metadata;
7. wrong coordinate rule or eye height;
8. wrong SHA-256 or byte count;
9. remote/missing external image URI in the GLB JSON;
10. total payload over 45,000,000 bytes;
11. actual `HV_FLOOR` X span/depth or `HV_ISLAND_STRUCTURE` footprint drifts over 3 mm from the contract.

Run with staged test precedence:

```sh
UV_CACHE_DIR=/private/tmp/hearthview-uv-cache \
PYTHONPATH=/Users/jackgarrigan/Documents/Codex/2026-08-18/bui/work/task-2-staging:/Users/jackgarrigan/Developer/hello-world/codex-pdf-to-bim \
uv run pytest -p no:cacheprovider /Users/jackgarrigan/Documents/Codex/2026-08-18/bui/work/task-2-staging/tests/backend/test_tour_artifact_validation.py -q
```

Record the real missing-module/function failures.

### GREEN — validator

Implement the smallest pure validator. Decode the GLB JSON chunk to inspect node names, images (`bufferView` is local; reject `http:`, `https:`, `data:` and missing relative files), and asset metadata. Use `trimesh` for actual named mesh world bounds. Never trust dimensions or hashes merely because the manifest says them.

### GREEN — scene

Use `/Applications/Blender.app/Contents/MacOS/Blender` 5.2 LTS:

```sh
/Applications/Blender.app/Contents/MacOS/Blender --background --factory-startup \
  --python /Users/jackgarrigan/Documents/Codex/2026-08-18/bui/work/task-2-staging/spikes/tour_quality/build_scene.py -- \
  --repo /Users/jackgarrigan/Developer/hello-world/codex-pdf-to-bim \
  --assets /Users/jackgarrigan/Documents/Codex/2026-08-18/bui/work/tour-quality-assets \
  --output-dir /Users/jackgarrigan/Documents/Codex/2026-08-18/bui/work/task-2-staging/apps/web/public/tour-spike
```

The script must fail fast with plain errors for missing/wrong-hash inputs, Task 1 contract errors, Blender earlier than 5.2, or a non-empty output validator result.

## Scene content and fidelity

Create parent empties named `HV_ARCHITECTURE`, `HV_CABINETRY`, `HV_FURNITURE`, `HV_LIGHTING`, `HV_NAVIGATION`; all authored objects are parented under one.

Envelope and navigation:

- 30′-1″ × 15′-11″ floor exactly (`HV_FLOOR`); 8′-5″ wall/ceiling height; wall thickness roughly 0.14 m as provisional.
- `HV_WALKABLE` is a nearly invisible, raycastable plane inside the 0.18 m walkable bounds; navigation colliders are named `HV_COLLIDER_<contract name>` and carry min/max custom properties.
- `HV_ISLAND_STRUCTURE` bounds are exactly the Task 1 island footprint and 0.91 m height before the separate 30–40 mm counter slab.
- The 3′-6″ west/north clearances are visibly from the authored counter faces.
- North wall has a trimmed kitchen window group over the sink run and a broad trimmed deck door/window group facing the living room. East wall contains the mudroom transition and solid TV section. South boundary contains the existing-living-room opening/transition; do not close the space into a misleading rectangle.
- Add a ceiling named `HV_CEILING` for poster/walk lighting; the browser may hide it for orbit/overhead.

Kitchen:

- North order left-to-right: tower, dishwasher, 36-inch sink centered under windows, trash pullout, tower.
- West order north-to-south: upper cabinets, realistic 36-inch range + hood, upper cabinets, 36-inch refrigerator.
- Use detailed warm off-white/putty Shaker fronts: separate face slabs, four frame rails/stiles, inset panel, consistent 2–3 mm reveals, toe kicks, counter overhangs, crown/filler where plausible, and small dark/brass pulls. No face should read as one undecorated cube.
- Island is 8′-7″ × 4′-3″ with detailed panel faces, pale honed stone slab, subtle eased edges, overhang, and four real-scale stools on the south side.
- Model sink basin, gooseneck faucet, range burners/knobs/oven glass, fridge doors/handles, hood, dishwasher front, and restrained countertop objects.

Living/furnishing:

- Living starts at X `4.6736` and remains at least 14′-9″ clear in the contract direction.
- Add a rounded, segmented warm-linen sofa (base, seat/back cushions, arms, feet), one imported/reassigned Modern Arm Chair 01, imported Modern Coffee Table 01, neutral low-pile rug, TV/media element, plant, and no more than a few ceramics/books.
- Use two or three Modern Ceiling Lamp 01 instances above the island with emissive bulbs plus real warm lights.
- Imported objects must be scaled in meters, positioned without blocking required walk routes, parented under the correct root, and use shared/retinted linen/oak/stone materials where feasible.

Architecture/material details:

- Real-scale baseboard, window/door casing, mullions, glazing, sills, ceiling trim where appropriate, and 2–5 mm bevels on visible hard edges.
- Floor uses the actual Poly Haven Wood Floor maps with UV tiling at its documented 1.7 m scale.
- Plaster, stone, and linen use the named actual maps and correct non-color normal/roughness inputs. Painted cabinetry may use a physically plausible Principled material with fine roughness; glass and metal must have physically plausible Principled values.
- Use smooth shading only where appropriate; preserve crisp cabinet/architectural planes. No black/magenta missing material.

Lighting/render/export:

- World uses the local HDR at restrained strength, AgX view transform, medium-high look/contrast, 1.0 exposure unless the poster proves another value, sun/sky direction aligned with north glazing, large area lights outside window/door openings, subtle ceiling bounce, and 2700–3000 K practicals.
- Eevee Next with ambient occlusion/ray-traced shadows where Blender 5.2 exposes them; 1920×1080; transparent off; high-quality TAA; contact shadows; 35–42 mm hero camera at person height. Keep the hero camera inside the envelope with no clipped objects.
- Render `poster.webp` at quality 92 or greater. It must show the island, perimeter kitchen detail, glazing/daylight, and living-room connection in one plausible composition.
- Export GLB with UVs, normals/tangents, materials, textures embedded, custom properties/extras, cameras and punctual lights. Do not use Draco or a CDN-dependent decoder.
- Copy the 1K HDR to `environment.hdr`. The GLB must be self-contained: no external texture URI.
- Hash outputs; finalize manifest; run `validate_artifact`; fail build on errors.

## Visual inspection loop

After a successful build, inspect `poster.webp` at full size. Iterate if any of these are visible: primitive block furniture, cabinet slabs without joinery, incorrect order, island dimensions/clearances not reading, missing textures, texture scale/orientation errors, black materials, overly dark interior, blown windows, light leaks, z-fighting, floating furniture, clipped hero camera, or a closed/misleading south transition. Record each iteration in the report with the concrete defect and change.

## Verification

Run focused tests, then:

```sh
HEARTHVIEW_DATA_DIR=/Users/jackgarrigan/Documents/Codex/2026-08-18/bui/work/task-2-staging/runtime-data \
UV_CACHE_DIR=/private/tmp/hearthview-uv-cache \
PYTHONPATH=/Users/jackgarrigan/Documents/Codex/2026-08-18/bui/work/task-2-staging:/Users/jackgarrigan/Developer/hello-world/codex-pdf-to-bim \
uv run pytest -p no:cacheprovider tests/backend \
  /Users/jackgarrigan/Documents/Codex/2026-08-18/bui/work/task-2-staging/tests/backend/test_tour_artifact_validation.py -q
```

Then run staged validator on the real outputs. Report exact test counts, artifact byte counts and SHA-256, Blender export/render duration, scene triangle/material/image counts if available, and any warnings. Self-review for: contract reuse, manifest/actual-geometry agreement, local-only resources, license manifest accuracy, browser payload, no accidental canonical claim, no repo edits, and poster defects.

Return only status (`DONE`, `DONE_WITH_CONCERNS`, `NEEDS_CONTEXT`, or `BLOCKED`), one-line tests/artifact summary, and concerns.
