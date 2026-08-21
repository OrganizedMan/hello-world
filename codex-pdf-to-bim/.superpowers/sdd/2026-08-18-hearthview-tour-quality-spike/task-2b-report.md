# Task 2B — Blender scene authoring/build handoff

Date: 2026-08-18  
Status: `DONE_WITH_CONCERNS`

Task 2B's complete Blender authoring implementation, build orchestration, input provenance, and license summary are staged. The required Blender invocation was attempted, but sandboxed Blender 5.2.0 LTS crashed in Metal backend detection before Python started. Consequently, no generated browser artifacts exist yet and no visual poster loop or real-output validation can be claimed.

## Staged implementation

Task 2A's reviewed validator and tests were consumed without modification.

- `spikes/tour_quality/build_scene.py`
  - 1,246 lines; SHA-256 `1db171c18e8bb0dca0088a488264312524dc62e7e825559613a7fb76948e6ff6`.
  - Requires Blender 5.2 or newer and validates Task 1 with `validate_scene_contract(build_scene_contract())` before scene work.
  - Loads the Task 1 envelope, island, clearances, openings, transitions, walkable polygon, collision rectangles, camera presets, printed dimensions, label, canonical boundary, and provisional categories rather than copying the binding dimensions.
  - Validates every provenance record against a computed SHA-256 and validates every supplied upstream MD5/SHA-256 before clearing or writing the four exact output paths.
  - Assembles the architecture, navigation meshes, detailed kitchen, exact island structure, furnished living area, imported local models, real lights, cameras, local HDR world, and mapped materials.
  - Renders a 1920×1080 WebP at quality 95 with a 38 mm in-envelope hero camera, Eevee Next, AgX/high-contrast preference, 1.0 exposure, HDR/daylight areas, sun, ceiling bounce, and warm pendant practicals.
  - Exports a self-contained GLB with UVs, normals, tangents, materials, extras/custom properties, cameras, punctual lights, Y-up conversion, and Draco disabled. Export arguments are filtered against Blender's runtime RNA properties for version tolerance.
  - Rewrites the GLB JSON chunk to place `Quality spike · visual staging`, `canonical_geometry: false`, and the exact six provisional categories in `asset.extras`, preserving all other chunks and updating the GLB length.
  - Copies the source HDR byte-for-byte to `environment.hdr`, hashes generated outputs, converges manifest byte count deterministically without self-hashing, enforces the 45,000,000-byte payload ceiling, and invokes Task 2A's real validator through the repository `uv` environment.
  - Emits one `HEARTHVIEW_BUILD_METRICS=...` JSON record containing Blender version, render/export/total duration, object/mesh/triangle/material/image/light/camera counts, browser byte counts, SHA-256 values, provenance count, and validator output.
- `spikes/tour_quality/blender_builders.py`
  - 686 lines; SHA-256 `92817cf61f74db98f6681196ce77b5741847908cf960eeef60c19324a7d8c9b2`.
  - Provides focused helpers for mapped PBR materials, physically plausible Principled/glass/metal/emissive materials, beveled primitives, raycastable planes, curves, Shaker millwork, cabinet units, stools, segmented sofa, local glTF imports with meter-scale normalization/reassignment, cameras, lights, root metadata, and parent discipline.
  - Actual hero materials use the required base-color, OpenGL normal, and roughness maps. Normal and roughness maps are explicitly non-color. The floor is UV-tiled at the documented 1.7 m scale; travertine, plaster, and linen each use the named real map set rather than procedural noise.
- `spikes/tour_quality/assets/provenance.json`
  - 246 lines; SHA-256 `bf2316d8c16b5204c452fce977a41ed970d1a080cce5e97ec9f652f78ac6e03a`.
  - Records 8 source assets and 32 exact input files, including every model's adjacent BIN and texture resources, source/license pages, authoring role, computed SHA-256, supplied upstream digest where available, material reassignments/retints, UV scale, import scale, placement, and environment transformation.
- `spikes/tour_quality/assets/LICENSES.md`
  - 28 lines; SHA-256 `0fcd5407de1400ec082ba3add653cc018449427019b34141a1bd2fc68045edb9`.
  - Concisely records only provider license/source pages and the visual-staging boundary; it copies no provider site description, preview, logo, or brand artwork.

## Scene/fidelity coverage in the implementation

- Roots: `HV_ARCHITECTURE`, `HV_CABINETRY`, `HV_FURNITURE`, `HV_LIGHTING`, and `HV_NAVIGATION`; all authored object hierarchies are parented under exactly one root.
- Exact meshes: `HV_FLOOR` is authored at Task 1 X/Y bounds with no bevel; `HV_ISLAND_STRUCTURE` uses the exact Task 1 footprint and 0.91 m height before a separate eased 42 mm slab; `HV_WALKABLE` uses the 0.18 m contract inset.
- Navigation: every `HV_COLLIDER_<contract name>` uses the contract rectangle and stores source min/max custom properties. Runtime metadata converts `(x,y,z)` to `(x,z,-y)` and was statically checked for literal equality with Task 2A's expected walkable, barrier, and camera values.
- Architecture: 0.14 m provisional walls; contract-derived north window/deck-door openings, east mudroom opening, south living threshold/open returns, `HV_CEILING`, baseboard/crown, casing, mullions, glazing, and sills.
- North kitchen order: tower → dishwasher → 0.99 m sink base centered on the contract kitchen-window opening → trash pullout → tower. The authored north counter face is exactly Y `0.6604`.
- West kitchen order: upper cabinet → real-scale 36-inch range/hood with burners, knobs, oven glass and handle → upper cabinet → detailed refrigerator. The authored west counter face is exactly X `0.6604`.
- Cabinetry: separate carcasses, 2.5 mm reveals, inset panels, rails/stiles, toe kicks, crown/filler, eased counter overhangs, and small brass pulls rather than plain face cubes.
- Island: detailed four-side paneling, pale honed mapped travertine, four stools, restrained bowl, exact west/north face clearances, and exact south-transition relationship from the Task 1 footprint.
- Living: rounded segmented mapped-linen sofa, imported/reassigned Modern Arm Chair 01, imported Modern Coffee Table 01, neutral low-pile rug, generic TV/media element, plant, one ceramic, and two neutral books.
- Lighting/imports: three imported Modern Ceiling Lamp 01 instances, emissive bulbs plus warm point lights, north-opening area lights, ceiling bounce, and sun. All three model types are imported from local `.gltf`/`.bin`/texture hierarchies and placed without an HTTP dependency.

## Blender build attempt

The binding command was run exactly:

```sh
/Applications/Blender.app/Contents/MacOS/Blender --background --factory-startup \
  --python /Users/jackgarrigan/Documents/Codex/2026-08-18/bui/work/task-2-staging/spikes/tour_quality/build_scene.py -- \
  --repo /Users/jackgarrigan/Developer/hello-world/codex-pdf-to-bim \
  --assets /Users/jackgarrigan/Documents/Codex/2026-08-18/bui/work/tour-quality-assets \
  --output-dir /Users/jackgarrigan/Documents/Codex/2026-08-18/bui/work/task-2-staging/apps/web/public/tour-spike
```

Observed result:

- Exit code: `139`.
- Wall time: about `0.69 s`.
- Blender identified itself as `Blender 5.2.0 LTS`, hash `fbe6228777e7`.
- Blender produced no `HEARTHVIEW BUILD ERROR` or `HEARTHVIEW_BUILD_METRICS` line and the crash report contains an empty `# Python backtrace`, proving Python did not execute.
- Native backtrace:

```text
supports_barycentric_whitelist
MTLBackend::metal_is_supported
GPU_backend_type_selection_detect
wm_homefile_read_ex
WM_init
main
```

- Crash report path: `/var/folders/71/m4h535c11k3g33zrghqfc4ch0000gn/T/blender.crash.txt`.
- No generated file was present under the staged `apps/web/public/tour-spike` directory after the crash.
- Per the controller's instruction for this precise pre-Python Metal crash, no approval/escalated retry was requested.

## Verification evidence

### Static implementation and provenance

Fresh final command outcomes:

```text
python3 -m py_compile build_scene.py blender_builders.py
PASS

python3 -m json.tool assets/provenance.json
PASS

computed SHA-256 plus supplied upstream digest verification
PASS: 2 modules, 8 source assets, 32 exact input files
```

A Blender-free import harness with only `bpy`/`mathutils` import stubs exercised real pure builder functions and reported:

```text
pure builder seams verified: 8 assets; runtime/GLB/manifest exact
```

That harness independently verified:

- Task 1 contract import and validation;
- every provenance file and digest;
- exact equality between generated runtime walkable/barriers/cameras and Task 2A validator constants;
- GLB header/chunk preservation and injected `asset.extras` values;
- deterministic manifest byte count, exact three hash keys, and actual total calculation.

The installed Blender 5.2 add-on source was also inspected read-only and confirms the used runtime option names, including `import_pack_images`, `export_texcoords`, `export_normals`, `export_tangents`, `export_cameras`, `export_lights`, `export_extras`, `export_yup`, `export_apply`, `export_keep_originals`, and `export_draco_mesh_compression_enable`. The installed scripts also confirm Eevee's `DITHERED`/`BLENDED` material render methods.

### Focused Task 2A validator suite

Fresh final result using staged precedence:

```text
...........................                                              [100%]
27 passed in 0.25s
```

The repository's read-only environment emitted the known non-fatal `uv` warning: `Failed to acquire environment lock: Could not create temporary file`.

### Combined backend scope

The brief's exact combined command exited `2` at collection because the source repository now also has `tests/backend/test_tour_artifact_validation.py`; pytest imported that basename first and rejected the staged file as an import-file mismatch. No test body ran in that exact attempt.

The same combined scope was rerun with pytest's documented basename-isolation mode, `--import-mode=importlib`:

```text
187 passed, 1 skipped, 5 warnings in 2.10s
```

The five warnings were Hypothesis falling back to an in-memory example database because the read-only repository's default `.hypothesis/examples` path is unusable.

### Real-output validator

The validator was invoked against the required staged output paths. It exited `1` with the expected truthful result:

```text
manifest is missing: /Users/jackgarrigan/Documents/Codex/2026-08-18/bui/work/task-2-staging/apps/web/public/tour-spike/manifest.json
```

This is not claimed as a successful artifact validation.

## Generated browser artifact state

| Required artifact | State | Bytes | SHA-256 |
|---|---:|---:|---:|
| `hearthview-kitchen-family.glb` | missing; Blender never reached Python | unavailable | unavailable |
| `poster.webp` | missing; Blender never reached Python | unavailable | unavailable |
| `environment.hdr` | missing; Blender never reached Python | unavailable | unavailable |
| `manifest.json` | missing; Blender never reached Python | unavailable | intentionally not self-hashed |

Therefore browser payload bytes, rendered/export durations, final triangle/material/image counts, and real generated hashes are unavailable. The implementation will print all of them in `HEARTHVIEW_BUILD_METRICS` after an outside-sandbox run.

## Required controller continuation

Run the exact Blender command from the “Blender build attempt” section outside the sandbox. On success:

1. Preserve the emitted `HEARTHVIEW_BUILD_METRICS` JSON in the controller's final Task 2 report.
2. Confirm the script's internal validator completed successfully, then rerun `validate_artifact.py` independently against the four staged outputs.
3. Inspect `poster.webp` at full 1920×1080 and iterate the builder if any of these are visible: primitive/block furniture, slab cabinet faces, wrong wall-item order, weak island dimensions/clearances, missing or mis-scaled maps, black/magenta material, dark interior, blown glazing, light leak, z-fighting, floating furniture, clipped hero framing, or a closed/misleading south transition.
4. Record each actual poster defect and concrete code change. No visual iteration is recorded here because no poster exists.
5. Re-run the focused 27 tests and combined backend scope after any iteration, then record final artifact bytes, SHA-256, total payload, Blender durations, triangle/material/image counts, and warnings.

## Self-review

- Contract reuse: complete in source; Task 1 validates before scene work and drives the exact floor, island, navigation, transitions, openings, cameras, and runtime conversion.
- Manifest/actual geometry agreement: implemented and independently pure-tested; cannot be verified against a real Blender export until the controller run.
- Local-only resources: build inputs are exact local files; GLB export is binary/embedded; generated metadata contains no HTTP dependency. Provenance/license source documents intentionally retain attribution URLs.
- License/provenance accuracy: all 32 recorded files and every supplied upstream digest verified against disk.
- Browser payload: enforced at 45,000,000 bytes after deterministic manifest finalization; actual size unavailable.
- Canonical boundary: source, root metadata, GLB asset extras, manifest base, provenance, and license summary all declare `Quality spike · visual staging` / `canonical_geometry: false` and the exact six provisional categories.
- Existing backend/canonical/web features: untouched by this worker.
- User-authorized source repository: no writes were made by this worker; only the staged path was edited.
- Commits/subagents: none.
- Poster defects: unassessed because the pre-Python Blender crash produced no poster.

## Concerns

1. The Blender implementation has not executed in any Blender Python process. Static verification and installed add-on API inspection are strong, but only the controller's outside-sandbox run can reveal a runtime API/context or renderer-specific issue.
2. The four required browser artifacts do not exist; real hashes, byte counts, payload, scene metrics, duration, and validator success are unavailable.
3. The required full-size visual inspection/iteration loop has not begun.
4. The brief's exact combined pytest command currently collides on duplicate test basenames; `--import-mode=importlib` verifies the intended combined scope successfully.
5. `ruff` is not installed in the repository environment, so the attempted optional `ruff --select E9,F` pass could not run. Python compilation and the targeted pure harness passed instead.
