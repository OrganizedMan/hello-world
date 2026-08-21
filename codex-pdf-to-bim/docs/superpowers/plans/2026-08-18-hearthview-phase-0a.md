# HearthView Phase 0A Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a polished local A-1 PDF-to-3D vertical slice with guided homeowner review, exact validation, deterministic geometry, interactive cameras, and a verified Blender render contract.

**Architecture:** A React/TypeScript browser client calls a local FastAPI service. The service stores immutable PDFs and append-only review events, validates an exact integer-tick model, and compiles a model-bound GLB consumed by both Three.js and Blender.

**Tech Stack:** Node 24, npm 11, React, TypeScript, Vite, Vitest, Testing Library, React Router, TanStack Query, PDF.js, Three.js/React Three Fiber, Python 3.12, uv, FastAPI, Pydantic v2, SQLAlchemy, pypdf, PyMuPDF, pytest, Hypothesis, trimesh, pygltflib, SQLite, optional Blender LTS.

**Spec:** `docs/superpowers/specs/2026-08-18-hearthview-phase-0a-design.md`

## Global Constraints

- Work only under `codex-pdf-to-bim/`; do not modify `amber/`, `client/`, `server/`, or repository-root application files.
- Do not switch branches or commit while the shared checkout remains on Claude's branch; use test results and `git diff -- codex-pdf-to-bim` as checkpoints.
- Core operation is local and must not require network access after dependencies are installed.
- Architectural coordinates use signed integer ticks at exactly 1/1024 inch.
- Persist canonical ticks as decimal strings in JSON; convert to JavaScript numbers only after safe-range validation.
- Imported source bytes are immutable and addressed by SHA-256.
- Interpretation emits candidates; only review events alter approved state.
- Structural edits invalidate validation tokens and compiled artifacts.
- Three.js and Blender consume the same compiled GLB.
- Every homeowner-facing input has a persistent label, units, help text or tooltip, and inline corrective error text.
- Product copy uses homeowner language and never claims permit, code, structural, or as-built certification.

## Planned file map

```text
codex-pdf-to-bim/
  package.json                       workspace commands
  pyproject.toml                     Python package and test configuration
  README.md                          local setup and homeowner workflow
  .gitignore                         generated/runtime exclusions
  apps/api/hearthview_api/
    main.py                          FastAPI composition root
    config.py                        application paths and settings
    errors.py                        typed domain-to-HTTP errors
    database.py                      SQLite engine/session/schema setup
    api_models.py                    request/response Pydantic models
    routes/projects.py               project/source/review endpoints
    routes/model.py                  validation/compile/report endpoints
    routes/render.py                 render job endpoints
  apps/web/
    package.json                     web dependencies and scripts
    vite.config.ts                   Vite/Vitest configuration
    src/main.tsx                     React entry
    src/app/App.tsx                  routes and providers
    src/app/AppShell.tsx             application shell/navigation
    src/api/client.ts                typed fetch boundary
    src/api/types.ts                 generated API types
    src/styles.css                   tokens, layout, responsive/accessibility styles
    src/components/HelpTooltip.tsx   accessible contextual help
    src/components/LengthField.tsx   labeled architectural input
    src/components/StatusBanner.tsx  homeowner status mapping
    src/features/home/HomePage.tsx   welcome/import entry
    src/features/plans/PlansPage.tsx PDF/source workflow
    src/features/review/ReviewPage.tsx guided confirmation queue
    src/features/model/ModelPage.tsx synchronized source/3D workspace
    src/features/model/ModelViewer.tsx GLB viewer and camera presets
    src/features/render/RenderPage.tsx render settings/jobs
    src/features/report/ReportPage.tsx validation/provenance report
  packages/contracts/schema.json     canonical boundary schema
  scripts/generate_contracts.py      Pydantic/JSON Schema to TS generator
  services/hearthview/
    units.py                          exact imperial parsing/formatting
    canonical.py                      sorted serialization and hashing
    models.py                         domain models and fixture payloads
    storage.py                        content-addressed artifact store
    events.py                         append/replay and revision checks
    ingest.py                         immutable PDF import and preview
    fixture.py                        A-1 Garrigan reviewed fixture
    validation.py                     issue codes, report, token
    geometry.py                       analytic primitive compiler and GLB
    rendering.py                      Blender detection/job orchestration
  services/blender/render_scene.py   locked-geometry Blender scene script
  tests/backend/                     Python unit/property/API/fixture tests
  tests/backend/conftest.py          shared isolated repositories and A-1 states
  apps/web/src/**/*.test.tsx         component and workflow tests
  tests/e2e/hearthview.spec.ts       browser happy path and invalid edit
```

---

### Task 1: Runnable workspace and health boundary

**Files:**
- Create: `package.json`, `pyproject.toml`, `.gitignore`, `README.md`
- Create: `apps/api/hearthview_api/__init__.py`, `apps/api/hearthview_api/main.py`, `apps/api/hearthview_api/config.py`
- Create: `apps/web/package.json`, `apps/web/index.html`, `apps/web/tsconfig.json`, `apps/web/vite.config.ts`, `apps/web/src/main.tsx`, `apps/web/src/app/App.tsx`
- Test: `tests/backend/test_health.py`, `apps/web/src/app/App.test.tsx`

**Interfaces:**
- Produces: `create_app() -> FastAPI`, `GET /health -> {"status":"ok","service":"hearthview-api"}` and a Vite application displaying “HearthView”.

- [ ] **Step 1: Write failing backend and frontend health tests**

```python
from fastapi.testclient import TestClient
from hearthview_api.main import create_app

def test_health_reports_local_service() -> None:
    response = TestClient(create_app()).get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "service": "hearthview-api"}
```

```tsx
import { render, screen } from "@testing-library/react";
import { App } from "./App";

it("introduces the homeowner workflow", () => {
  render(<App />);
  expect(screen.getByRole("heading", { name: "See your plans come to life" })).toBeVisible();
  expect(screen.getByText("Your plans stay on this Mac")).toBeVisible();
});
```

- [ ] **Step 2: Run tests and verify missing modules fail**

Run: `uv run pytest tests/backend/test_health.py -q && npm --workspace apps/web test -- --run`  
Expected: import/module failures because the workspace is not created.

- [ ] **Step 3: Add minimal workspace, app factories, and scripts**

```python
from fastapi import FastAPI

def create_app() -> FastAPI:
    app = FastAPI(title="HearthView Local API", version="0.1.0")

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok", "service": "hearthview-api"}

    return app
```

Root scripts must provide `npm run dev`, `npm run test`, `npm run test:web`, `npm run test:api`, and `npm run build` without altering the repository-root package.

- [ ] **Step 4: Run health tests and production builds**

Run: `uv run pytest tests/backend/test_health.py -q`  
Expected: 1 passed.  
Run: `npm --workspace apps/web test -- --run && npm --workspace apps/web run build`  
Expected: frontend test passes and Vite emits `dist/`.

- [ ] **Step 5: Record checkpoint**

Run: `git status --short -- codex-pdf-to-bim`  
Expected: only Task 1 files and previously approved docs appear.

---

### Task 2: Exact units and canonical hashing

**Files:**
- Create: `services/hearthview/__init__.py`, `services/hearthview/units.py`, `services/hearthview/canonical.py`
- Test: `tests/backend/test_units.py`, `tests/backend/test_canonical.py`

**Interfaces:**
- Produces: `parse_length(text: str) -> int`, `format_length(ticks: int) -> str`, `canonical_bytes(value: object) -> bytes`, `canonical_hash(value: object) -> str`.

- [ ] **Step 1: Write failing examples and properties**

```python
import pytest
from hypothesis import given, strategies as st
from services.hearthview.units import TICKS_PER_INCH, format_length, parse_length

@pytest.mark.parametrize(("text", "inches"), [("5' 0\"", 60), ("60 in", 60), ("8'-7\"", 103)])
def test_parse_exact_imperial_lengths(text: str, inches: int) -> None:
    assert parse_length(text) == inches * TICKS_PER_INCH

@given(st.integers(min_value=0, max_value=1000 * 12 * 1024))
def test_format_parse_round_trip_on_whole_inches(ticks: int) -> None:
    ticks -= ticks % TICKS_PER_INCH
    assert parse_length(format_length(ticks)) == ticks
```

- [ ] **Step 2: Verify failures**

Run: `uv run pytest tests/backend/test_units.py tests/backend/test_canonical.py -q`  
Expected: import failures for both modules.

- [ ] **Step 3: Implement strict parsing and sorted canonical JSON**

Parsing accepts feet/inches, inches, and millimeters; rejects negatives for element widths; reduces fractional inches to exact 1/1024-inch ticks or reports that precision is unsupported. Canonical JSON recursively sorts mapping keys, keeps list order, rejects floats, emits UTF-8 without whitespace, and hashes with SHA-256.

```python
def canonical_hash(value: object) -> str:
    return hashlib.sha256(canonical_bytes(value)).hexdigest()
```

- [ ] **Step 4: Run unit/property tests**

Run: `uv run pytest tests/backend/test_units.py tests/backend/test_canonical.py -q`  
Expected: all examples and generated cases pass.

- [ ] **Step 5: Record checkpoint**

Run: `git diff --stat -- codex-pdf-to-bim/services codex-pdf-to-bim/tests/backend`

---

### Task 3: Domain contracts and A-1 fixture

**Files:**
- Create: `packages/contracts/schema.json`, `scripts/generate_contracts.py`, `services/hearthview/models.py`, `services/hearthview/fixture.py`
- Generate: `apps/web/src/api/types.ts`
- Create: `tests/backend/conftest.py`
- Test: `tests/backend/test_models.py`, `tests/backend/test_fixture.py`

**Interfaces:**
- Produces: Pydantic `ProjectModel`, `Wall`, `Opening`, `FixedObject`, `Island`, `SourceReference`, `ReviewItem`; `build_a1_fixture() -> ProjectModel`; `build_a1_review_queue() -> tuple[ReviewItem, ...]`.

- [ ] **Step 1: Write failing fixture assertions**

```python
from services.hearthview.fixture import build_a1_fixture
from services.hearthview.units import TICKS_PER_INCH

def test_a1_fixture_contains_exact_homeowner_facts() -> None:
    model = build_a1_fixture()
    assert model.island.width_ticks == 103 * TICKS_PER_INCH
    assert model.island.depth_ticks == 51 * TICKS_PER_INCH
    assert [item.kind for item in model.wall("family_east").ordered_children] == [
        "WINDOW", "SOLID_MOUNT_ZONE", "UNFRAMED_OPENING"
    ]
```

- [ ] **Step 2: Verify fixture tests fail**

Run: `uv run pytest tests/backend/test_models.py tests/backend/test_fixture.py -q`  
Expected: missing model and fixture modules.

- [ ] **Step 3: Implement immutable typed contracts and fixture construction**

All canonical models use `ConfigDict(frozen=True)`. IDs are stable strings. Tick fields serialize as decimal strings through field serializers. The fixture creates one first-floor level, the two mandatory family-room walls, openings, TV anchor, island, source references, and five review items described by the Phase 0A spec. `scripts/generate_contracts.py` exports the Pydantic JSON Schema to `packages/contracts/schema.json`, maps string-encoded tick fields to branded TypeScript strings, and writes `apps/web/src/api/types.ts` with a generated-file header and no handwritten request/response duplicates. Its `--check` mode renders both outputs in memory and exits nonzero when either saved file differs. `tests/backend/conftest.py` supplies isolated artifact/repository fixtures, approved and invalid A-1 states, valid tokens, review events, and a minimal one-page PDF used by later tasks.

- [ ] **Step 4: Validate schema and fixture tests**

Run: `uv run python scripts/generate_contracts.py && uv run python scripts/generate_contracts.py --check`  
Expected: generated contracts are current.  
Run: `uv run pytest tests/backend/test_models.py tests/backend/test_fixture.py -q`  
Expected: all model serialization, schema generation, and fixture assertions pass.

- [ ] **Step 5: Record checkpoint**

Run: `git diff --check -- codex-pdf-to-bim`

---

### Task 4: Content-addressed storage, SQLite projects, and review events

**Files:**
- Create: `apps/api/hearthview_api/database.py`, `apps/api/hearthview_api/errors.py`
- Create: `services/hearthview/storage.py`, `services/hearthview/events.py`
- Test: `tests/backend/test_storage.py`, `tests/backend/test_events.py`

**Interfaces:**
- Produces: `ArtifactStore.install(stream: BinaryIO) -> ArtifactRef`, `ProjectRepository.create(name: str) -> ProjectRecord`, `append_event(project_id, base_revision, event) -> int`, `revert_event(project_id, base_revision, target_event_id) -> int`, `replay(project_id) -> ProjectModel`.

- [ ] **Step 1: Write failing immutability, traversal, and revision tests**

```python
def test_artifact_install_is_content_addressed_and_deduplicated(tmp_path):
    store = ArtifactStore(tmp_path)
    first = store.install(io.BytesIO(b"same bytes"))
    second = store.install(io.BytesIO(b"same bytes"))
    assert first.sha256 == second.sha256
    assert first.path == second.path

def test_stale_event_revision_is_rejected(repository):
    project = repository.create("Garrigan")
    repository.append_event(project.id, 0, fixture_confirmation())
    with pytest.raises(RevisionConflict):
        repository.append_event(project.id, 0, fixture_confirmation())
```

- [ ] **Step 2: Verify tests fail**

Run: `uv run pytest tests/backend/test_storage.py tests/backend/test_events.py -q`

- [ ] **Step 3: Implement atomic storage and append-only events**

Artifacts stream to a `NamedTemporaryFile` inside the artifact root, hash during copy, and atomically rename to `<sha256[:2]>/<sha256>`. SQLite enables foreign keys and WAL. Event payloads store canonical JSON; `(project_id, revision)` is unique. Replay starts from the fixture seed and applies only explicit approved/edit/reject/revert operations. A revert event names one prior event and deterministically removes its effect during replay without deleting history.

- [ ] **Step 4: Run persistence tests**

Run: `uv run pytest tests/backend/test_storage.py tests/backend/test_events.py -q`  
Expected: deduplication, restart, traversal, replay, and conflict cases pass.

- [ ] **Step 5: Record checkpoint**

Run: `git diff --check -- codex-pdf-to-bim`

---

### Task 5: Real PDF ingest and A-1 preview

**Files:**
- Create: `services/hearthview/ingest.py`
- Create: `apps/api/hearthview_api/api_models.py`, `apps/api/hearthview_api/routes/__init__.py`, `apps/api/hearthview_api/routes/projects.py`
- Modify: `apps/api/hearthview_api/main.py`
- Test: `tests/backend/test_ingest.py`, `tests/backend/test_projects_api.py`

**Interfaces:**
- Consumes: `ArtifactStore`, `ProjectRepository`.
- Produces: `inspect_pdf(path) -> PdfInspection`, `render_page(path, page_number, max_width) -> bytes`; project/source/review HTTP endpoints, including safe inline retrieval of immutable source PDF bytes for PDF.js.

- [ ] **Step 1: Write failing API tests using an in-memory generated PDF**

```python
def test_import_returns_hash_and_page_count(client, one_page_pdf):
    project_id = client.post("/projects", json={"name": "My renovation"}).json()["id"]
    response = client.post(
        f"/projects/{project_id}/sources",
        files={"file": ("plans.pdf", one_page_pdf, "application/pdf")},
    )
    assert response.status_code == 201
    assert response.json()["page_count"] == 1
    assert len(response.json()["sha256"]) == 64
```

- [ ] **Step 2: Verify missing endpoints fail**

Run: `uv run pytest tests/backend/test_ingest.py tests/backend/test_projects_api.py -q`  
Expected: 404 or missing-import failures.

- [ ] **Step 3: Implement streamed import, PDF checks, and bounded PNG rendering**

Reject non-PDF headers, encrypted PDFs, zero-page PDFs, invalid page numbers, uploads larger than the configured maximum, and paths not returned by `ArtifactStore`. Render with PyMuPDF behind the ingest interface and cap pixel dimensions. `GET /projects/{projectId}/sources/{sourceId}/file` streams only the stored artifact selected by repository ID with `application/pdf` and inline disposition. API errors return `{code, message, action}`.

- [ ] **Step 4: Run generated and real-fixture tests**

Run: `HEARTHVIEW_GARRIGAN_PDF='/Users/jackgarrigan/Downloads/Garrigan - 261 Grove Street - 08-17-26 - to send 1.pdf' uv run pytest tests/backend/test_ingest.py tests/backend/test_projects_api.py -q`  
Expected: generated file and real four-page file pass; A-1 is page 2.

- [ ] **Step 5: Record checkpoint**

Run: `git status --short -- codex-pdf-to-bim`

---

### Task 6: Exact validation and model-bound token

**Files:**
- Create: `services/hearthview/validation.py`
- Create: `apps/api/hearthview_api/routes/model.py`
- Modify: `apps/api/hearthview_api/main.py`
- Test: `tests/backend/test_validation.py`, `tests/backend/test_model_api.py`

**Interfaces:**
- Produces: `validate(model: ProjectModel) -> ValidationReport`, `mint_token(model, report) -> ValidationToken`, `assert_token(token, model) -> None`.

- [ ] **Step 1: Write failing valid and deliberately broken topology tests**

```python
def test_a1_fixture_is_ready_and_mints_bound_token():
    model = approved_a1_fixture()
    report = validate(model)
    assert report.status == "READY_TO_VIEW"
    assert report.blocking_count == 0
    assert mint_token(model, report).model_hash == report.model_hash

def test_tv_over_opening_is_plain_language_blocker():
    report = validate(a1_with_tv_on_south_opening())
    issue = next(i for i in report.issues if i.code == "TV_REQUIRES_SOLID_WALL")
    assert issue.message == "Move the TV to a solid part of the east living-room wall."
```

- [ ] **Step 2: Verify validation tests fail**

Run: `uv run pytest tests/backend/test_validation.py tests/backend/test_model_api.py -q`

- [ ] **Step 3: Implement stable issue codes and token invalidation**

Rules execute in deterministic code/element order. Reports include counts, issues, model hash, validator version, and evidence coverage. Tokens hash the model/report/schema/validator tuple. `assert_token` raises `TOKEN_MODEL_MISMATCH` after any structural event.

- [ ] **Step 4: Run all validator and API tests**

Run: `uv run pytest tests/backend/test_validation.py tests/backend/test_model_api.py -q`  
Expected: fixture readiness, each negative rule, stable ordering, and stale-token rejection pass.

- [ ] **Step 5: Record checkpoint**

Run: `git diff --check -- codex-pdf-to-bim`

---

### Task 7: Deterministic primitive table and GLB compiler

**Files:**
- Create: `services/hearthview/geometry.py`
- Modify: `apps/api/hearthview_api/routes/model.py`
- Test: `tests/backend/test_geometry.py`, `tests/backend/test_compile_api.py`

**Interfaces:**
- Produces: `compile_primitives(model, token) -> tuple[Primitive, ...]`, `compile_glb(model, token) -> GeometryArtifact`.

- [ ] **Step 1: Write failing panel and repeatability tests**

```python
def test_opening_splits_wall_without_covering_open_interval():
    primitives = compile_primitives(approved_a1_fixture(), valid_token())
    east_parts = [p for p in primitives if p.element_id == "family_east"]
    assert all(not p.station_interval.overlaps(WINDOW_INTERVAL) for p in solid_panels(east_parts))

def test_ten_compiles_have_one_geometry_hash():
    artifacts = [compile_glb(approved_a1_fixture(), valid_token()) for _ in range(10)]
    assert len({a.geometry_hash for a in artifacts}) == 1
```

- [ ] **Step 2: Verify geometry tests fail**

Run: `uv run pytest tests/backend/test_geometry.py tests/backend/test_compile_api.py -q`

- [ ] **Step 3: Implement analytic partitioning and stable GLB output**

Partition each host at `0`, `length`, and all opening endpoints. Emit solid spans only where no opening is active, plus opening jamb/head/sill parts. Sort primitive records by `(element_id, part_kind, station_start, station_end)`. Convert ticks to meters once. Serialize with stable node names and extras containing canonical IDs and hashes.

- [ ] **Step 4: Inspect generated geometry**

Run: `uv run pytest tests/backend/test_geometry.py tests/backend/test_compile_api.py -q`  
Expected: interval, bounds, metadata, and ten-compile checks pass.  
Run: `uv run python -m services.hearthview.geometry --fixture a1 --output work/a1.glb`  
Expected: prints model hash, geometry hash, GLB file hash, primitive count, and bounds.

- [ ] **Step 5: Record checkpoint**

Run: `git diff --stat -- codex-pdf-to-bim/services/hearthview/geometry.py codex-pdf-to-bim/tests/backend`

---

### Task 8: Accessible application shell and API client

**Files:**
- Create: `apps/web/src/api/client.ts`
- Modify: generated `apps/web/src/api/types.ts` only through `scripts/generate_contracts.py`
- Create: `apps/web/src/app/AppShell.tsx`, `apps/web/src/components/HelpTooltip.tsx`, `apps/web/src/components/StatusBanner.tsx`
- Create: `apps/web/src/features/home/HomePage.tsx`, `apps/web/src/styles.css`
- Modify: `apps/web/src/app/App.tsx`
- Test: `apps/web/src/components/HelpTooltip.test.tsx`, `apps/web/src/app/AppShell.test.tsx`

**Interfaces:**
- Produces: `api.get/create/upload/post` typed helpers; `HelpTooltip({label, children})`; routed shell with Plans, Review, Model, Render, Report.

- [ ] **Step 1: Write failing navigation and tooltip tests**

```tsx
it("explains local processing with keyboard-accessible help", async () => {
  render(<HomePage />);
  await userEvent.tab();
  await userEvent.keyboard("{Enter}");
  expect(screen.getByRole("tooltip")).toHaveTextContent("processed by the local service");
});
```

- [ ] **Step 2: Verify frontend tests fail**

Run: `npm --workspace apps/web test -- --run`  
Expected: missing shell/component imports.

- [ ] **Step 3: Build the responsive visual system and typed error mapping**

Use CSS variables for ink, parchment, sage, amber, error, spacing, radius, shadows, and motion. Support `prefers-reduced-motion`. Tooltips use a real button, `aria-describedby`, Escape dismissal, hover/focus/click behavior, and no icon-only mystery controls.

- [ ] **Step 4: Run frontend tests and axe checks**

Run: `npm --workspace apps/web test -- --run && npm --workspace apps/web run build`  
Expected: component tests pass with no accessibility violations and production build succeeds.

- [ ] **Step 5: Record checkpoint**

Run: `git diff --check -- codex-pdf-to-bim/apps/web`

---

### Task 9: Plans and guided review workflows

**Files:**
- Create: `apps/web/src/components/LengthField.tsx`
- Create: `apps/web/src/features/plans/PdfSourceViewer.tsx`, `apps/web/src/features/plans/PlansPage.tsx`, `apps/web/src/features/review/ReviewPage.tsx`
- Modify: `apps/web/src/app/App.tsx`, `apps/web/src/api/types.ts`
- Test: `apps/web/src/components/LengthField.test.tsx`, `apps/web/src/features/plans/PlansPage.test.tsx`, `apps/web/src/features/review/ReviewPage.test.tsx`

**Interfaces:**
- Consumes: project/source/review endpoints.
- Produces: file drop/import, PDF.js source viewing with zoom/pan/page controls, editable proposed-region rectangle, five-card A-1 queue, exact edit-and-confirm events, and undo of the last review event.

- [ ] **Step 1: Write failing label, units, error, and review-progress tests**

```tsx
it("labels the island width and explains accepted formats", async () => {
  render(<LengthField id="island-width" label="Island width" value="8'-7\"" onCommit={vi.fn()} />);
  expect(screen.getByLabelText("Island width")).toHaveAccessibleDescription("Enter feet and inches, for example 8'-7\".");
  await userEvent.clear(screen.getByLabelText("Island width"));
  await userEvent.type(screen.getByLabelText("Island width"), "banana{Enter}");
  expect(screen.getByRole("alert")).toHaveTextContent("Use a length such as");
});
```

- [ ] **Step 2: Verify workflow tests fail**

Run: `npm --workspace apps/web test -- --run LengthField PlansPage ReviewPage`

- [ ] **Step 3: Implement import, thumbnails, and prioritized review cards**

`PdfSourceViewer` loads the immutable source-file endpoint through `pdfjs-dist`, configures its bundled worker, renders a bounded canvas for the selected page, and maintains a separate SVG highlight layer in PDF viewport coordinates. It exposes labeled zoom, pan, and page controls. The proposed-plan region appears as a draggable/resizable rectangle whose numeric page coordinates are also available through labeled fields; saving it creates a review event. Cards have a source-image region, documented/inferred badge, plain-language question, “Why?” disclosure, labeled editable value, confirm/edit/reject actions, undo-last-review action, and progress text. Successful actions invalidate model/report queries and focus the next card.

- [ ] **Step 4: Run component and integration tests**

Run: `npm --workspace apps/web test -- --run`  
Expected: file state, exact inputs, accessible errors, keyboard flow, and review progress pass.

- [ ] **Step 5: Record checkpoint**

Run: `git diff --check -- codex-pdf-to-bim/apps/web`

---

### Task 10: Interactive GLB viewer and source clickback

**Files:**
- Create: `apps/web/src/features/model/ModelViewer.tsx`, `apps/web/src/features/model/ModelPage.tsx`
- Modify: `apps/web/src/app/App.tsx`, `apps/web/src/api/types.ts`
- Test: `apps/web/src/features/model/ModelViewer.test.tsx`, `apps/web/src/features/model/ModelPage.test.tsx`

**Interfaces:**
- Consumes: `GeometryArtifact` URL and GLB extras.
- Produces: plan, axonometric, kitchen, living-room cameras; selection callback by `canonicalElementId`; visible geometry hash.

- [ ] **Step 1: Write failing camera and selection tests with a mocked Canvas**

```tsx
it("keeps the geometry identity visible while cameras change", async () => {
  render(<ModelPage artifact={artifactWithHash("abc123")} />);
  expect(screen.getByText(/abc123/)).toBeVisible();
  await userEvent.click(screen.getByRole("button", { name: "Kitchen view" }));
  expect(screen.getByText(/abc123/)).toBeVisible();
});
```

- [ ] **Step 2: Verify model tests fail**

Run: `npm --workspace apps/web test -- --run ModelViewer ModelPage`

- [ ] **Step 3: Implement Three.js scene, presets, and selection boundary**

Use `GLTFLoader` through React Three Fiber. Traverse loaded nodes once to index `canonicalElementId`. Camera presets change only camera state. Add warm-neutral materials only where the GLB has no assigned display material; never change node geometry/transforms. Source clickback opens the matching A-1 highlight in a side panel.

- [ ] **Step 4: Run tests and browser smoke build**

Run: `npm --workspace apps/web test -- --run && npm --workspace apps/web run build`  
Expected: camera, identity, loading, error, selection, and responsive tests pass.

- [ ] **Step 5: Record checkpoint**

Run: `git diff --check -- codex-pdf-to-bim/apps/web`

---

### Task 11: Blender render contract and Warm Blank Slate preview

**Files:**
- Create: `services/hearthview/rendering.py`, `services/blender/render_scene.py`
- Create: `apps/api/hearthview_api/routes/render.py`
- Modify: `apps/api/hearthview_api/main.py`
- Test: `tests/backend/test_rendering.py`, `tests/backend/test_render_api.py`

**Interfaces:**
- Produces: `detect_blender() -> BlenderCapability`, `create_render_job(request) -> RenderJob`, `run_render(job) -> RenderArtifact`.

- [ ] **Step 1: Write failing missing-Blender and command-manifest tests**

```python
def test_missing_blender_is_actionable(monkeypatch):
    monkeypatch.setattr(shutil, "which", lambda _: None)
    capability = detect_blender()
    assert capability.available is False
    assert capability.action == "Install Blender LTS, then restart HearthView."

def test_render_command_uses_glb_without_model_edit_flags(fake_blender):
    job = create_render_job(fixture_render_request())
    command = build_blender_command(job, fake_blender)
    assert "render_scene.py" in " ".join(command)
    assert job.geometry_path in command
```

- [ ] **Step 2: Verify render tests fail**

Run: `uv run pytest tests/backend/test_rendering.py tests/backend/test_render_api.py -q`

- [ ] **Step 3: Implement capability endpoint, safe subprocess, and scene script**

The subprocess receives explicit argument-list paths, a scrubbed environment, output directory inside the artifact store, timeout, and captured log. The Blender script creates a locked `HV_CANONICAL` collection, imports GLB, records node transforms/bounds, applies Warm Blank Slate materials, adds a separate camera/light collection, renders, and rechecks canonical state.

- [ ] **Step 4: Run render contract tests and capability check**

Run: `uv run pytest tests/backend/test_rendering.py tests/backend/test_render_api.py -q`  
Expected: missing/install, safe path, manifest, timeout, and mutation-detection tests pass.  
Run: `uv run python -m services.hearthview.rendering --doctor`  
Expected on this Mac: reports Blender unavailable with the exact install action and exits successfully.

- [ ] **Step 5: Record checkpoint**

Run: `git diff --check -- codex-pdf-to-bim/services codex-pdf-to-bim/apps/api`

---

### Task 12: Render and report pages

**Files:**
- Create: `apps/web/src/features/render/RenderPage.tsx`, `apps/web/src/features/report/ReportPage.tsx`
- Modify: `apps/web/src/app/App.tsx`, `apps/web/src/api/types.ts`
- Test: `apps/web/src/features/render/RenderPage.test.tsx`, `apps/web/src/features/report/ReportPage.test.tsx`

**Interfaces:**
- Consumes: render capability/jobs and validation report.
- Produces: Warm Blank Slate settings, camera/quality/size inputs, missing-Blender guidance, retryable jobs, plain-language report/provenance view.

- [ ] **Step 1: Write failing end-user presentation tests**

```tsx
it("explains the warm furnished default without hiding controls", () => {
  render(<RenderPage capability={availableBlender} />);
  expect(screen.getByLabelText("Visual style")).toHaveValue("Warm Blank Slate");
  expect(screen.getByText("Lightly furnished with warm, neutral finishes")).toBeVisible();
  expect(screen.getByLabelText("Render quality")).toBeVisible();
});
```

- [ ] **Step 2: Verify page tests fail**

Run: `npm --workspace apps/web test -- --run RenderPage ReportPage`

- [ ] **Step 3: Implement labeled settings, job states, and provenance summary**

Draft maps to Eevee and final maps to Cycles. The page keeps labels visible, explains time/quality trade-offs, disables final rendering when validation is blocked, and shows Blender installation guidance without disabling interactive model exploration. The report shows source hash, model hash, geometry hash, evidence coverage, and linked issues.

- [ ] **Step 4: Run page tests and build**

Run: `npm --workspace apps/web test -- --run && npm --workspace apps/web run build`

- [ ] **Step 5: Record checkpoint**

Run: `git diff --check -- codex-pdf-to-bim/apps/web`

---

### Task 13: End-to-end workflow, local launcher, and acceptance evidence

**Files:**
- Create: `scripts/dev.py`, `scripts/doctor.py`, `tests/e2e/hearthview.spec.ts`, `playwright.config.ts`
- Modify: `package.json`, `README.md`
- Test: full backend/frontend/e2e suites

**Interfaces:**
- Produces: one-command local launch, environment doctor, and complete A-1 acceptance workflow.

- [ ] **Step 1: Write the browser acceptance path**

```ts
test("homeowner imports A-1, confirms facts, and explores one geometry", async ({ page }) => {
  await page.goto("/");
  await page.getByRole("button", { name: "Add plan PDFs" }).setInputFiles(process.env.HEARTHVIEW_GARRIGAN_PDF!);
  await page.getByRole("button", { name: "Use proposed first floor" }).click();
  for (const name of ["Confirm island size", "Confirm east wall", "Confirm south opening", "Confirm TV location"]) {
    await page.getByRole("button", { name }).click();
  }
  await expect(page.getByText("Ready to view")).toBeVisible();
  const hash = await page.getByTestId("geometry-hash").textContent();
  await page.getByRole("button", { name: "Kitchen view" }).click();
  await expect(page.getByTestId("geometry-hash")).toHaveText(hash!);
});
```

- [ ] **Step 2: Verify e2e fails before launcher wiring**

Run: `HEARTHVIEW_GARRIGAN_PDF='/Users/jackgarrigan/Downloads/Garrigan - 261 Grove Street - 08-17-26 - to send 1.pdf' npm run test:e2e`  
Expected: launcher/base URL failure.

- [ ] **Step 3: Implement launcher, doctor, seeded-example convenience, and README**

`scripts/dev.py` chooses free local ports, starts Uvicorn and Vite with explicit working directories, forwards termination, and prints the browser URL. `scripts/doctor.py` reports Python, Node, PDF backend, artifact directory, and Blender capabilities without claiming unmeasured performance. README documents installation, `npm run dev`, the homeowner workflow, privacy, limitations, test commands, and the optional Blender prerequisite.

- [ ] **Step 4: Run full verification**

Run: `uv run pytest tests/backend -q`  
Expected: all backend unit, property, API, fixture, geometry, and render-contract tests pass.  
Run: `npm --workspace apps/web test -- --run && npm --workspace apps/web run build`  
Expected: all web tests pass and production bundle builds.  
Run: `HEARTHVIEW_GARRIGAN_PDF='/Users/jackgarrigan/Downloads/Garrigan - 261 Grove Street - 08-17-26 - to send 1.pdf' npm run test:e2e`  
Expected: import-to-model workflow passes.  
Run: `uv run python scripts/doctor.py`  
Expected: local API/web/PDF requirements pass; Blender is clearly reported as optional and unavailable on this machine.

- [ ] **Step 5: Inspect the final shared-worktree boundary**

Run: `git status --short -- codex-pdf-to-bim && git status --short | rg -v '^.. codex-pdf-to-bim/' || true`  
Expected: all implementation changes are inside `codex-pdf-to-bim/`; no Claude or existing-app file was modified.
