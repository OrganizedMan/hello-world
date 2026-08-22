# HearthView Canonical Tour Geometry Implementation Plan

> **Required sub-skill:** Use `superpowers:executing-plans` to implement this plan task by task. Use `superpowers:test-driven-development` for every behavior change and `superpowers:verification-before-completion` before reporting success.

**Goal:** Replace the tour spike's hand-authored room layout with a deterministic adapter from one canonical A-1 spatial model, regenerate the detailed artifact, and re-verify geometry and controls against the source PDF.

**Architecture:** A pure-Python `A1SpatialModel` owns all measured ticks, reviewed topology, provenance, regions, and north orientation. The Phase 0A `ProjectModel`, tour contract, Blender architecture, navigation manifest, orientation map, and artifact validator become projections of that model. Blender may add provisional appearance only through named anchors; browser presentation consumes generated orientation metadata.

**Tech Stack:** Python 3.13, Pydantic, pytest, Blender Python API, glTF/GLB, React 19, TypeScript, Three.js, Vitest, Playwright.

**Spec:** `docs/superpowers/specs/2026-08-21-hearthview-canonical-tour-geometry-design.md`

## Global Constraints

- Store architectural measurements as integer `Tick` values at 1/1024 inch; convert to meters only at rendering boundaries.
- Treat PDF page A-1 as the evidence source. Keep printed measurements, reviewed topology, and provisional appearance distinct.
- Do not add tour-owned measured coordinates. Tests must prove the fixture and tour derive from the same spatial object.
- Preserve the existing Orbit, Move here, Walk, Escape/Exit walk, Overhead, and Reset behavior.
- Keep canonical and staging nodes separately named and hashed.
- Follow RED → GREEN → REFACTOR for each task and commit after each green task.

## Task 1: Establish the canonical A-1 spatial source

**Files:**

- Create: `services/hearthview/a1_spatial.py`
- Create: `tests/backend/test_a1_spatial.py`
- Modify: `services/hearthview/fixture.py`
- Modify: `tests/backend/test_fixture.py`
- Modify: `services/hearthview/validation.py`
- Modify: `tests/backend/test_validation.py`

**Interfaces:**

```python
@dataclass(frozen=True)
class A1SpatialModel:
    bounds: PlanBounds
    walls: tuple[SpatialWall, ...]
    regions: tuple[SpatialRegion, ...]
    ceiling_zones: tuple[CeilingZone, ...]
    island: SpatialRect
    anchors: tuple[SpatialAnchor, ...]
    north_vector: tuple[int, int]

    def to_project_model(self, *, source_document: str) -> ProjectModel: ...
    def canonical_payload(self) -> dict[str, object]: ...
    def canonical_hash(self) -> str: ...

def build_a1_spatial_model() -> A1SpatialModel: ...
```

### Steps

- [ ] Add a failing `test_a1_spatial.py` asserting the 361 × 191-inch main bounds, 101-inch ceiling, island `(68, 68, 103, 51)`, 177-inch living width, north vector `(0, -1)`, and source references.
- [ ] Add failing topology assertions for east `WINDOW → SOLID_MOUNT_ZONE → UNFRAMED_OPENING` at 12/60/132/228 inches and south `SOLID → UNFRAMED_OPENING → SOLID` at 0/37/97/134 inches on global Y=191 inches.
- [ ] Add failing determinism tests proving equal canonical payloads and hashes across independent builds, while provisional appearance data is excluded from the measured geometry hash.
- [ ] Run `UV_CACHE_DIR=/private/tmp/hearthview-uv-cache uv run pytest tests/backend/test_a1_spatial.py -q` and confirm collection/import fails because the module does not exist.
- [ ] Implement frozen spatial records, one `build_a1_spatial_model()` factory, strict opening containment/non-overlap checks, and deterministic JSON/hash serialization.
- [ ] Refactor `build_fixture()` to call `build_a1_spatial_model().to_project_model(...)`; remove its duplicated measured wall, island, and TV literals.
- [ ] Add a regression test that the fixture south wall has global Y=191 inches and that both fixture walls exactly match the spatial projection.
- [ ] Extend canonical validation for full measured bounds, island clearances, topology, TV containment, and north metadata without weakening existing errors.
- [ ] Run `UV_CACHE_DIR=/private/tmp/hearthview-uv-cache uv run pytest tests/backend/test_a1_spatial.py tests/backend/test_fixture.py tests/backend/test_validation.py tests/backend/test_geometry.py -q`.
- [ ] Commit with `git commit -m "Create canonical A-1 spatial model"`.

## Task 2: Derive the tour contract from canonical geometry

**Files:**

- Modify: `spikes/tour_quality/scene_contract.py`
- Modify: `tests/backend/test_tour_scene_contract.py`
- Modify: `tests/backend/test_tour_artifact_validation.py`

**Interfaces:**

```python
def build_scene_contract(spatial: A1SpatialModel | None = None) -> SceneContract: ...

@dataclass(frozen=True)
class SceneContract:
    canonical_model_hash: str
    canonical_geometry_hash: str
    canonical_nodes: tuple[CanonicalNodeSpec, ...]
    regions: tuple[RegionSpec, ...]
    orientation: OrientationSpec
    appearance_anchors: tuple[AppearanceAnchorSpec, ...]
```

### Steps

- [ ] Replace literal-value tests with failing adapter tests that compare every measured wall/opening/island coordinate to `build_a1_spatial_model()` after exact tick-to-meter conversion.
- [ ] Add the regression that rejects the old east mudroom opening near the north corner and the old unrelated south returns.
- [ ] Add failing assertions for canonical/staging roots, canonical hashes, geometry-derived regions, north-up camera metadata, walkable polygon, and barriers.
- [ ] Run `UV_CACHE_DIR=/private/tmp/hearthview-uv-cache uv run pytest tests/backend/test_tour_scene_contract.py -q` and confirm the new assertions fail against the hand-authored contract.
- [ ] Refactor `scene_contract.py` so all architecture, region, opening, island, fixed-object, camera, and navigation values are computed from the canonical spatial model; retain only visual-quality constants as staging settings.
- [ ] Serialize `canonical_model_hash`, `canonical_geometry_hash`, provenance, orientation, regions, and provisional anchors into the manifest payload.
- [ ] Ensure camera coordinates are converted explicitly between canonical `+Y south/+Z up` and Three/Blender coordinates, with overhead north at screen top.
- [ ] Run `UV_CACHE_DIR=/private/tmp/hearthview-uv-cache uv run pytest tests/backend/test_tour_scene_contract.py tests/backend/test_tour_artifact_validation.py -q`.
- [ ] Commit with `git commit -m "Derive tour contract from A-1 geometry"`.

## Task 3: Rebuild Blender architecture and validate the actual GLB

**Files:**

- Modify: `spikes/tour_quality/build_scene.py`
- Modify: `spikes/tour_quality/validate_artifact.py`
- Modify: `tests/backend/test_tour_artifact_validation.py`
- Regenerate: `apps/web/public/tour-spike/hearthview-tour.glb`
- Regenerate: `apps/web/public/tour-spike/tour-manifest.json`
- Regenerate: `apps/web/public/tour-spike/textures/*`

### Steps

- [ ] Add failing artifact tests using a deliberately shifted canonical GLB node; prove changing only manifest numbers cannot make it pass.
- [ ] Add failing checks for the east window/TV/mudroom sequence, south 37/60/37 chain, island footprint/clearances, canonical node metadata, staging-root separation, and ≤3 mm transformed-bound tolerance.
- [ ] Run `UV_CACHE_DIR=/private/tmp/hearthview-uv-cache uv run pytest tests/backend/test_tour_artifact_validation.py -q` and capture the expected failures.
- [ ] Replace `_build_architecture` freehand panels with iteration over canonical wall solids, openings, floors, thresholds, ceiling zones, and context regions.
- [ ] Move cabinetry, TV, sofa, stools, lighting, and decor to named appearance anchors. Reject staging collision with openings or measured clearance envelopes.
- [ ] Parent architecture under `HearthView_Canonical` and appearance under `HearthView_Staging`; attach element IDs, source IDs, category, and hashes as custom properties.
- [ ] Extend `validate_artifact.py` to parse actual GLB nodes/accessors/transforms and compare their world-space bounds to canonical node specs, then check textures, payload size, hashes, and navigation geometry.
- [ ] Regenerate with `/Applications/Blender.app/Contents/MacOS/Blender --background --factory-startup --python spikes/tour_quality/build_scene.py -- --repo "$PWD" --assets /Users/jackgarrigan/Documents/Codex/2026-08-18/bui/work/tour-quality-assets --output-dir "$PWD/apps/web/public/tour-spike"`.
- [ ] Run `UV_CACHE_DIR=/private/tmp/hearthview-uv-cache uv run python spikes/tour_quality/validate_artifact.py --repo "$PWD" --output-dir "$PWD/apps/web/public/tour-spike"`.
- [ ] Run `UV_CACHE_DIR=/private/tmp/hearthview-uv-cache uv run pytest tests/backend/test_tour_artifact_validation.py tests/backend/test_tour_scene_contract.py -q`.
- [ ] Commit with `git commit -m "Rebuild tour from canonical geometry"`.

## Task 4: Make browser orientation geometry-driven and north-up

**Files:**

- Create: `apps/web/src/features/tour/tourManifest.ts`
- Create: `apps/web/src/features/tour/TourOrientationMap.tsx`
- Create: `apps/web/src/features/tour/TourOrientationMap.test.tsx`
- Modify: `apps/web/src/features/tour/TourPage.tsx`
- Modify: `apps/web/src/features/tour/TourPage.test.tsx`
- Modify: `apps/web/src/features/tour/TourViewer.tsx`
- Modify: `apps/web/src/features/tour/TourViewer.test.ts`
- Modify: `apps/web/src/styles.css`
- Modify: `tests/e2e/tour-spike.spec.ts`

**Interfaces:**

```ts
export type TourOrientation = {
  bounds: [number, number, number, number];
  northVector: [number, number];
  regions: TourRegion[];
  openings: TourOpening[];
};

export function applyCameraPreset(camera: PerspectiveCamera, preset: CameraPreset): void;
export function TourOrientationMap(props: { orientation: TourOrientation }): JSX.Element;
```

### Steps

- [ ] Extract manifest parsing and add failing tests that reject missing/mismatched canonical hashes or orientation fields.
- [ ] Add failing viewer tests proving `applyCameraPreset` applies `camera.up` before `lookAt` and that overhead north maps to screen top.
- [ ] Add failing component tests proving the orientation SVG derives region, island, opening, and north-arrow geometry from manifest values rather than static spans.
- [ ] Run `npm --workspace apps/web test -- --run src/features/tour/TourPage.test.tsx src/features/tour/TourViewer.test.ts src/features/tour/TourOrientationMap.test.tsx` and confirm expected failures.
- [ ] Implement the typed parser, camera helper, and accessible geometry-derived SVG map; remove the static decorative map markup/CSS.
- [ ] Preserve current responsive controls and integrity-error retry behavior.
- [ ] Extend Playwright checks for overhead north-up state, manifest geometry labels, Move here, Walk, Escape, Exit walk, Reset, and compact layout.
- [ ] Run `npm --workspace apps/web test -- --run` and `npm run build`.
- [ ] Commit with `git commit -m "Align tour orientation with canonical plan"`.

## Task 5: Re-verify controls, geometry, performance, and visual fidelity

**Files:**

- Modify: `docs/superpowers/specs/2026-08-18-hearthview-tour-quality-spike.md`
- Regenerate: `../outputs/hearthview-tour-spike-overview.png`

### Steps

- [ ] Run the full backend and frontend suite: `UV_CACHE_DIR=/private/tmp/hearthview-uv-cache npm test`.
- [ ] Run the production build: `npm run build`.
- [ ] Run the headed tour flow using `HEARTHVIEW_E2E_API_PORT=50177 HEARTHVIEW_E2E_WEB_PORT=50178 UV_CACHE_DIR=/private/tmp/hearthview-uv-cache npm run test:e2e -- tests/e2e/tour-spike.spec.ts`.
- [ ] Open `/tour-spike` in the browser and inspect desktop and compact layouts. Capture orbit, walk, and north-up overhead screenshots.
- [ ] Compare the overhead screenshot directly with PDF A-1 page 2: east `window → 60-inch TV solid → mudroom opening`, south `37 → 60 opening → 37`, island 103 × 51 with 42/42/72 clearances, living width 177, and adjacent context.
- [ ] Measure generated GLB plus texture payload and usable load time on the target Mac; require ≤45 MB and ≤10 seconds.
- [ ] Update the acceptance record, explicitly preserving navigation/performance results but replacing the superseded geometry result with fresh evidence and a human-review-needed marker if visual approval is not yet supplied.
- [ ] Run `git diff --check`, `git status --short`, and inspect all generated-file diffs.
- [ ] Invoke `superpowers:verification-before-completion`, rerun every completion command fresh, and report exact pass counts, artifact size, load time, and any remaining human approval gate.
- [ ] Commit with `git commit -m "Reverify canonical HearthView tour"`.

