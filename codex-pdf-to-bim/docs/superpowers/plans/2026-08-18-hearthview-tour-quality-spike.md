# HearthView Tour Quality Spike Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Produce one geometry-faithful, warm residential kitchen–family-room scene and a polished browser tour so the homeowner can judge realism and navigation before the approach expands.

**Architecture:** Keep the spike isolated under `spikes/tour_quality/` and a dedicated `/tour-spike` web route. Blender authors and validates one real-scale GLB plus poster and manifest; React Three Fiber loads that display artifact and layers a deterministic three-mode navigation controller over authored walkable and collision metadata. The existing canonical viewer and backend remain untouched.

**Tech Stack:** Python 3.12 scene contract, Blender 5.2 LTS Python API and glTF exporter, React 19, TypeScript 7, Three.js 0.185, React Three Fiber 9, Drei 10, Vitest, Playwright.

**Spec:** `docs/superpowers/specs/2026-08-18-hearthview-tour-quality-spike.md`

## Global Constraints

- The route is `/tour-spike`; existing app routes and `ModelViewer.tsx` remain unchanged.
- Printed dimensions are authoritative: 30′-1″ span, 15′-11″ north-wall-to-south-transition depth, 8′-5″ ceiling, 8′-7″ × 4′-3″ island, 3′-6″ west- and north-counter-face clearances, 6′-0″ south transition, and 14′-9″ living clear width. The vertical chain leaves a 2′-2″ counter zone.
- The spike says “Quality spike · visual staging” and never presents its display GLB as canonical geometry.
- Cabinet fronts, hardware, finishes, furnishings, décor, and undimensioned offsets are provisional visual staging.
- Orbit is the default; move-here accepts only walkable floor; walking uses 1.65 m eye height; Escape, Exit walk, Overhead, and Reset always recover the camera.
- Every homeowner control has a visible label and plain-language tooltip/help text.
- External authored assets are CC0 and recorded with source URL and license URL.
- The optimized browser payload target is at most 45 MB; the scene must remain usable without a network connection after assets are prepared.
- Tests exercise observable geometry/navigation behavior, derive literals independently, and do not assert source text or mocks.

---

### Task 1: Authoritative spike scene contract

**Files:**
- Create: `spikes/tour_quality/__init__.py`
- Create: `spikes/tour_quality/scene_contract.py`
- Create: `tests/backend/test_tour_scene_contract.py`
- Create: `spikes/tour_quality/README.md`

**Interfaces:**
- Produces: `build_scene_contract() -> SceneContract`, `SceneContract.to_manifest() -> dict[str, object]`, `validate_scene_contract(contract: SceneContract) -> tuple[str, ...]`, and literal meter constants consumed by the Blender builder.

- [ ] **Step 1: Write the failing contract tests**

  Test hand-derived meter literals: span `9.1694`, ceiling `2.5654`, island width `2.6162`, island depth `1.2954`, west and north clearances `1.0668`, south transition `1.8288`, living clear width `4.4958`, and eye height `1.65`. Test that the contract names `cabinetry_detail`, `hardware`, `finishes`, `furniture`, `decor`, and `undimensioned_offsets` as provisional. Mutate each required object/dimension and assert validation returns an actionable error.

- [ ] **Step 2: Run the tests and observe the missing-module failure**

  Run: `uv run pytest tests/backend/test_tour_scene_contract.py -q`

- [ ] **Step 3: Implement immutable dataclasses and independent validation**

  Include envelope bounds, named wall openings, island footprint, cabinet/appliance order, walkable polygon, collision rectangles, camera presets, printed-dimension sources, and provisional categories. Serialize only JSON primitives with stable ordering.

- [ ] **Step 4: Run the focused and backend suites**

  Run: `uv run pytest tests/backend/test_tour_scene_contract.py -q && uv run pytest tests/backend -q`

- [ ] **Step 5: Document the isolated build/run contract and commit**

  The README must say this is a throwaway proof until the geometry, realism, and navigation gates pass; document the exact Blender command and generated file locations without claiming success.

### Task 2: Detailed Blender display scene and validation artifacts

**Files:**
- Create: `spikes/tour_quality/build_scene.py`
- Create: `spikes/tour_quality/validate_artifact.py`
- Create: `spikes/tour_quality/assets/provenance.json`
- Create: `spikes/tour_quality/assets/LICENSES.md`
- Create: `tests/backend/test_tour_artifact_validation.py`
- Generate: `apps/web/public/tour-spike/hearthview-kitchen-family.glb`
- Generate: `apps/web/public/tour-spike/manifest.json`
- Generate: `apps/web/public/tour-spike/poster.webp`

**Interfaces:**
- Consumes: Task 1 `SceneContract` and meter constants.
- Produces: a GLB in meters/Y-up, manifest schema `hearthview-tour-spike/v1`, poster, `HV_WALKABLE` floor metadata, `HV_COLLIDER_*` objects, `HV_TELEPORT_*` targets, named `HV_ARCHITECTURE`, `HV_CABINETRY`, `HV_FURNITURE`, and `HV_LIGHTING` collections, plus `validate_artifact(glb_path, manifest_path) -> tuple[str, ...]`.

- [ ] **Step 1: Write failing artifact-validation tests**

  Build small temporary manifests/GLBs and test rejection of wrong schema, missing dimension, greater-than-3-mm drift, absent collections, missing walkable/collider metadata, unknown license, missing texture URI, payload over 45 MB, and output hash mismatch. Test one literal valid fixture.

- [ ] **Step 2: Run the focused tests and observe failures**

  Run: `uv run pytest tests/backend/test_tour_artifact_validation.py -q`

- [ ] **Step 3: Implement the validator, then the Blender authoring script**

  The scene must include the real-scale envelope and openings; detailed shaker base/tall/upper cabinets with toe kicks, reveals, pulls, and crown; fridge, range/hood, sink/faucet, dishwasher, island waterfall/top and four stools; trimmed windows/deck doors; oak plank floor; plaster/stone/linen/metal/glass PBR materials; restrained sofa, rug, table, chairs, pendants, plant and minimal décor; exterior deck/sky cards; bevels and weighted/smooth normals. Use AgX, Eevee ray tracing where available, sun/sky plus window area lights and warm practicals. Export only display geometry/materials/cameras and metadata; render a 1920 × 1080 validation poster; hash every output into the manifest.

- [ ] **Step 4: Prepare only CC0 authoring inputs and record provenance**

  Use the approved Poly Haven/ambientCG asset URLs from the spec research. Record asset ID, source page, downloaded file hash, license URL, role, and transformations. Do not copy website preview images or logos.

- [ ] **Step 5: Generate, validate, and inspect the artifact**

  Run Blender 5.2 in background with `build_scene.py`, then run `validate_artifact.py`. Inspect the poster at full size for missing textures, black materials, light leaks, z-fighting, clipped cabinetry, and incorrect opening/cabinet order. Iterate until validation is clean.

- [ ] **Step 6: Run backend tests and commit**

  Run: `uv run pytest tests/backend/test_tour_scene_contract.py tests/backend/test_tour_artifact_validation.py -q && uv run pytest tests/backend -q`

### Task 3: Homeowner hybrid tour controller

**Files:**
- Create: `apps/web/src/features/tour/TourPage.tsx`
- Create: `apps/web/src/features/tour/TourViewer.tsx`
- Create: `apps/web/src/features/tour/tourNavigation.ts`
- Create: `apps/web/src/features/tour/tourNavigation.test.ts`
- Create: `apps/web/src/features/tour/TourPage.test.tsx`
- Modify: `apps/web/src/app/App.tsx`
- Modify: `apps/web/src/styles.css`

**Interfaces:**
- Consumes: Task 2 GLB and manifest at `/tour-spike/…`, authored `HV_WALKABLE`, `HV_COLLIDER_*`, and camera nodes.
- Produces: pure `resolveMovement(position, delta, barriers, walkableBounds, radius)`, `isWalkablePlacement(point, bounds, obstacles)`, and route-level `TourPage`.

- [ ] **Step 1: Write failing pure-navigation tests**

  Test literal examples for unrestricted movement, radius blocking, tangential wall sliding, obstacle blocking, bounds rejection, floor-only placement, and 1.65 m eye-height placement. Each test names the break it catches.

- [ ] **Step 2: Write failing homeowner-page tests**

  Render the real `TourPage` with canvas setup isolated at the browser boundary. Assert visible labels and help for Orbit, Move here, Walk, Overhead, Reset, Exit walk, WASD/arrow keys, mouse/drag look, experimental staging notice, loading progress, and recoverable load error. Assert existing routes still render.

- [ ] **Step 3: Run the focused tests and observe failures**

  Run: `npm --workspace apps/web test -- --run apps/web/src/features/tour/tourNavigation.test.ts apps/web/src/features/tour/TourPage.test.tsx`

- [ ] **Step 4: Implement pure collision/placement and the three-mode viewer**

  Orbit uses `OrbitControls`; Move here raycasts only `HV_WALKABLE`; Walk holds a 1.65 m camera height, reads WASD/arrows each frame, resolves a 0.30 m radius against authored axis-aligned barriers, rejects floor-boundary exits, and uses pointer lock when supported with drag-look fallback. Escape/unlock returns to orbit. Overhead and Reset exit walk, preserve the scene, and move to authored camera poses. Set `ACESFilmicToneMapping` or AgX-equivalent supported by Three 0.185, correct output color space, physically plausible shadow settings, environment/background, and adaptive DPR.

- [ ] **Step 5: Implement the polished route shell and accessibility**

  Use plain homeowner language, persistent labels, tooltips/help text, keyboard focus styles, mode/status announcements, a compact orientation map, quality-spike warning, provisional-style explanation, local-only note, and responsive controls. Never expose BIM jargon.

- [ ] **Step 6: Run focused tests, the full frontend suite, and build**

  Run: `npm --workspace apps/web test -- --run && npm run build`

- [ ] **Step 7: Commit**

### Task 4: Browser acceptance and evidence package

**Files:**
- Create: `tests/e2e/tour-spike.spec.ts`
- Create: `spikes/tour_quality/acceptance.md`
- Generate: `outputs/hearthview-tour-spike-overview.png` outside the repo for user delivery

**Interfaces:**
- Consumes: completed `/tour-spike` route and generated artifact.
- Produces: reproducible evidence for all three spike gates and an explicit pass/fail table.

- [ ] **Step 1: Write the failing Playwright acceptance**

  Test route load, quality warning, initial orbit mode, Move here state, a valid floor selection, Walk entry, Exit walk, Overhead, Reset, and that no page error/console error occurs. Use real rendered controls; do not mock the viewer.

- [ ] **Step 2: Run the acceptance and observe the first failing behavior**

  Run: `npm run test:e2e -- tests/e2e/tour-spike.spec.ts`

- [ ] **Step 3: Fix only acceptance defects through the owning task interfaces**

  Keep the route isolated and preserve every global constraint.

- [ ] **Step 4: Run complete verification**

  Run: `npm test && npm run build && npm run test:e2e -- tests/e2e/tour-spike.spec.ts && uv run python spikes/tour_quality/validate_artifact.py`

- [ ] **Step 5: Perform headed visual/navigation QA and record evidence**

  Inspect the poster and browser at desktop and narrow widths. Exercise orbit, click-to-move, person-height walking/free look, collision, Exit walk, Overhead, and Reset. Record actual artifact bytes, load time, viewport, browser, observed interaction quality, known provisional items, and a pass/fail result for geometry, realism, navigation, and performance. Do not declare the architecture successful if any gate is unproven.

- [ ] **Step 6: Copy the approved overview and acceptance report to the user-facing outputs folder and commit**
