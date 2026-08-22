# A-1 Full-Plan Trace Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a full proposed-first-floor A-1 trace that the homeowner can compare directly with the PDF before any 3D work resumes.

**Architecture:** A versioned Python data module stores the proposed-view trace in original PDF-page coordinates and gives each record explicit provenance. FastAPI serves the trace and a crop rendered from the same coordinates; React draws source, trace, or overlay in a single coordinate system. No later 3D projection may consume the trace until user approval.

**Tech Stack:** Python 3.12, FastAPI, Pydantic, PyMuPDF, React, TypeScript, SVG, pytest, Vitest, Playwright.

**Spec:** `docs/superpowers/specs/2026-08-21-a1-full-plan-trace-design.md`

## Global Constraints

- Trace only page 2, view 2, “Proposed - First Floor”; exclude page 2’s existing-plan view.
- Every record uses exactly one provenance value: `dimension_verified`, `linework_traced`, or `ambiguous`.
- Do not add furniture, 3D, Blender, navigation, or visual staging.
- A dimension-verified record links to one or more printed A-1 labels; linework-traced records never display as measured facts.
- An ambiguity blocks approval and cannot be silently replaced by plausible geometry.
- The existing tour remains an unapproved prototype.

---

## File Structure

- Create `services/hearthview/a1_trace.py`: immutable source metadata, trace records, and topology/provenance validation.
- Modify `services/hearthview/ingest.py`: PDF-coordinate rectangular crop rendering.
- Modify `apps/api/hearthview_api/api_models.py` and `apps/api/hearthview_api/routes/projects.py`: trace metadata and crop-preview endpoints.
- Modify `scripts/generate_contracts.py` and generated `apps/web/src/api/types.ts`: trace response contract.
- Create `apps/web/src/features/plans/a1Trace.ts`, `A1TraceCanvas.tsx`, and `A1TraceReviewPage.tsx`: client data helpers, SVG, and review page.
- Modify `apps/web/src/app/App.tsx`, `apps/web/src/features/plans/PlansPage.tsx`, `apps/web/src/features/tour/TourPage.tsx`, and `apps/web/src/styles.css`.
- Create the named backend, frontend, and browser tests below.

### Task 1: Create the immutable trace contract and source crop

**Files:**
- Create: `services/hearthview/a1_trace.py`
- Create: `tests/backend/test_a1_trace.py`

**Interfaces:**
- Produces `PdfRect`, `TraceRecord`, `A1Trace`, and `build_a1_trace() -> A1Trace`.
- `A1Trace` provides `page_number`, `page_width_points`, `page_height_points`, `proposed_crop`, `records`, and `validate()`.

- [ ] **Step 1: Write failing contract tests**

~~~python
from hearthview.a1_trace import build_a1_trace

def test_trace_is_bound_to_proposed_a1_view() -> None:
    trace = build_a1_trace()
    assert trace.page_number == 2
    assert trace.page_width_points == 2592.0
    assert trace.page_height_points == 1728.24
    assert trace.proposed_crop.contains(trace.records[0].geometry.bounds)

def test_every_record_has_one_explicit_provenance() -> None:
    records = build_a1_trace().records
    assert records
    assert {r.provenance for r in records} <= {
        "dimension_verified", "linework_traced", "ambiguous"
    }
    assert all(r.source_page == 2 for r in records)
~~~

- [ ] **Step 2: Run the test to verify it fails**

Run: `uv run pytest tests/backend/test_a1_trace.py -q`

Expected: FAIL because `hearthview.a1_trace` does not exist.

- [ ] **Step 3: Add the minimal pure-data contract**

~~~python
@dataclass(frozen=True)
class PdfRect:
    x0: float; y0: float; x1: float; y1: float
    def contains(self, other: "PdfRect") -> bool: ...

@dataclass(frozen=True)
class TraceRecord:
    id: str
    kind: Literal["wall", "opening", "room", "stair", "fixed", "dimension"]
    room: str
    provenance: Literal["dimension_verified", "linework_traced", "ambiguous"]
    geometry: TraceGeometry
    source_page: int
    dimension_labels: tuple[str, ...]

def build_a1_trace() -> A1Trace: ...
~~~

Use PDF points, never browser pixels. Set the crop to the actual right/lower proposed-plan viewport. Reject duplicate IDs, malformed geometry, items outside the crop, and verified records without dimension labels.

- [ ] **Step 4: Run the focused tests**

Run: `uv run pytest tests/backend/test_a1_trace.py -q`

Expected: PASS.

- [ ] **Step 5: Commit**

~~~bash
git add services/hearthview/a1_trace.py tests/backend/test_a1_trace.py
git commit -m "Add A-1 trace contract"
~~~

### Task 2: Populate and validate the complete proposed-plan topology

**Files:**
- Modify: `services/hearthview/a1_trace.py`
- Modify: `tests/backend/test_a1_trace.py`

**Interfaces:**
- Consumes Task 1’s contract.
- Produces a full record collection plus `trace_summary(trace) -> TraceSummary`.

- [ ] **Step 1: Write failing topology tests**

~~~python
def test_trace_covers_required_proposed_plan_groups() -> None:
    rooms = {record.room for record in build_a1_trace().records}
    assert {
        "kitchen", "living_room", "mudroom", "study_room",
        "existing_living_room", "powder_room", "walk_in_pantry",
        "staircase", "entry", "dining_room", "deck",
    } <= rooms

def test_exterior_is_closed_and_openings_attach_to_walls() -> None:
    trace = build_a1_trace()
    assert trace.exterior_boundary.is_closed
    assert all(trace.attaches_to_wall(opening) for opening in trace.openings)

def test_verified_records_cite_printed_labels() -> None:
    verified = [r for r in build_a1_trace().records if r.provenance == "dimension_verified"]
    assert verified and all(record.dimension_labels for record in verified)
~~~

- [ ] **Step 2: Run the test to verify it fails**

Run: `uv run pytest tests/backend/test_a1_trace.py -q`

Expected: FAIL because the contract has no complete proposed-plan records.

- [ ] **Step 3: Trace in source drawing order**

Trace in this order: exterior boundary and deck; interior walls; window/door openings and door swings; stairs and low-ceiling boundary; fixed elements; then rooms and printed dimensions. Use stable IDs such as `wall.north.kitchen`, `opening.deck.north`, `room.existing_living`, and `fixed.fireplace.existing_living`.

Use `dimension_verified` only for visible printed dimensions (including kitchen/island, living, mudroom, deck, and opening chains). Use `linework_traced` for every visible but undimensioned alignment. Create bounded `ambiguous` records for illegible geometry.

- [ ] **Step 4: Add topology validators and summary**

~~~python
def trace_summary(trace: A1Trace) -> TraceSummary:
    return TraceSummary(
        verified=sum(r.provenance == "dimension_verified" for r in trace.records),
        traced=sum(r.provenance == "linework_traced" for r in trace.records),
        ambiguous=sum(r.provenance == "ambiguous" for r in trace.records),
    )
~~~

Validate a closed exterior boundary; attached openings; fixed-element containment; all named room groups; and no unclassified record.

- [ ] **Step 5: Verify and visually inspect an intermediate overlay**

Run: `uv run pytest tests/backend/test_a1_trace.py -q`

Expected: PASS.

Render a temporary SVG over the proposed crop at 100%. Inspect whole-plan alignment plus kitchen/living/mudroom, stair/pantry/powder, and entry/existing-living connections. Do not commit the temporary render.

- [ ] **Step 6: Commit**

~~~bash
git add services/hearthview/a1_trace.py tests/backend/test_a1_trace.py
git commit -m "Trace proposed A-1 first floor"
~~~

### Task 3: Serve a source-matched trace and crop

**Files:**
- Modify: `services/hearthview/ingest.py`
- Modify: `apps/api/hearthview_api/api_models.py`
- Modify: `apps/api/hearthview_api/routes/projects.py`
- Modify: `tests/backend/test_projects_api.py`
- Modify: `scripts/generate_contracts.py`
- Modify: `apps/web/src/api/types.ts`

**Interfaces:**
- Produces `GET /api/projects/{project_id}/sources/{source_id}/a1-trace`.
- Produces `GET /api/projects/{project_id}/sources/{source_id}/a1-trace/preview?max_width=...`.
- `A1TraceResponse` includes page/crop metadata, records, summary, and `approval_blocked`.

- [ ] **Step 1: Write failing source-bound API tests**

~~~python
def test_a1_trace_returns_source_matched_geometry(client, imported_garrigan_source):
    response = client.get(f"/api/projects/{project_id}/sources/{source_id}/a1-trace")
    assert response.status_code == 200
    assert response.json()["page_number"] == 2

def test_a1_trace_preview_is_png(client, imported_garrigan_source):
    response = client.get(f"/api/projects/{project_id}/sources/{source_id}/a1-trace/preview?max_width=1600")
    assert response.status_code == 200
    assert response.headers["content-type"] == "image/png"

def test_a1_trace_rejects_unsupported_source(client, unsupported_source):
    response = client.get(f"/api/projects/{project_id}/sources/{source_id}/a1-trace")
    assert response.status_code == 422
~~~

- [ ] **Step 2: Run the API tests to verify they fail**

Run: `uv run pytest tests/backend/test_projects_api.py -k a1_trace -q`

Expected: FAIL with 404 because the routes do not exist.

- [ ] **Step 3: Add a non-legacy crop renderer**

~~~python
def render_rect(path: Path, *, page_number: int, rect: PdfRect, max_width: int) -> bytes:
    page = document.load_page(page_number - 1)
    clip = fitz.Rect(rect.x0, rect.y0, rect.x1, rect.y1)
    scale = max_width / clip.width
    return page.get_pixmap(matrix=fitz.Matrix(scale, scale), clip=clip, alpha=False).tobytes("png")
~~~

Keep it separate from `render_region`, which uses legacy 4x evidence coordinates.

- [ ] **Step 4: Add strict models and routes**

Resolve the requested source; require the supported Garrigan A-1 profile/hash; serialize only `build_a1_trace()`; return `UNSUPPORTED_A1_TRACE_SOURCE` for any other file; and render exactly `trace.proposed_crop`. Generate, rather than hand-edit, `api/types.ts`.

- [ ] **Step 5: Verify the API and generated types**

Run: `uv run pytest tests/backend/test_projects_api.py -k a1_trace -q && npm --workspace apps/web test -- --run`

Expected: PASS.

- [ ] **Step 6: Commit**

~~~bash
git add services/hearthview/ingest.py apps/api/hearthview_api/api_models.py apps/api/hearthview_api/routes/projects.py tests/backend/test_projects_api.py scripts/generate_contracts.py apps/web/src/api/types.ts
git commit -m "Serve source-bound A-1 trace"
~~~

### Task 4: Build the PDF/Trace/Overlay review route

**Files:**
- Create: `apps/web/src/features/plans/a1Trace.ts`
- Create: `apps/web/src/features/plans/A1TraceCanvas.tsx`
- Create: `apps/web/src/features/plans/A1TraceCanvas.test.tsx`
- Create: `apps/web/src/features/plans/A1TraceReviewPage.tsx`
- Create: `apps/web/src/features/plans/A1TraceReviewPage.test.tsx`
- Modify: `apps/web/src/app/App.tsx`
- Modify: `apps/web/src/features/plans/PlansPage.tsx`
- Modify: `apps/web/src/styles.css`

**Interfaces:**
- `A1TraceCanvas({ trace, mode, provenanceFilter, selectedId, onSelect })` uses the API’s page-coordinate viewBox.
- Route: `/projects/:projectId/a1-trace?source=:sourceId`.

- [ ] **Step 1: Write failing component tests**

~~~tsx
it("keeps trace paths in the source-coordinate viewBox", () => {
  render(<A1TraceCanvas trace={fixture} mode="overlay" provenanceFilter="all" selectedId={null} onSelect={() => {}} />);
  expect(screen.getByLabelText("A-1 proposed-plan trace")).toHaveAttribute("viewBox", "0 0 2592 1728.24");
  expect(screen.getByTestId("trace-wall.north.kitchen")).toBeVisible();
});

it("distinguishes traced and ambiguous items", () => {
  render(<A1TraceCanvas trace={fixture} mode="trace" provenanceFilter="all" selectedId={null} onSelect={() => {}} />);
  expect(screen.getByTestId("trace-room.kitchen")).toHaveAttribute("data-provenance", "linework_traced");
  expect(screen.getByTestId("trace-ambiguous.example")).toHaveAttribute("data-provenance", "ambiguous");
});
~~~

- [ ] **Step 2: Run the component tests to verify they fail**

Run: `npm --workspace apps/web test -- --run src/features/plans/A1TraceCanvas.test.tsx`

Expected: FAIL because the component does not exist.

- [ ] **Step 3: Implement coordinate-safe SVG behavior**

Use one relatively positioned frame for the crop image and SVG. Preserve the page-coordinate viewBox and translate drawing coordinates by the crop origin; never align to browser pixel measurements. PDF hides SVG, Trace hides the image, Overlay shows both with a 20-80% opacity control. Make each record keyboard-focusable and expose room, kind, and provenance in its accessible name.

- [ ] **Step 4: Implement the page and plan entry point**

Load both endpoints only after project/source parameters exist. Provide three mode buttons; provenance filters; count cards; grouped record list; selected-record evidence; and the persistent copy “This trace is not approved for 3D.” Link from Plans only when page 2 is selected. Display structured 404/422/preview errors without substituting another PDF.

- [ ] **Step 5: Run web tests**

Run: `npm --workspace apps/web test -- --run src/features/plans/A1TraceCanvas.test.tsx src/features/plans/A1TraceReviewPage.test.tsx src/features/plans/PlansPage.test.tsx`

Expected: PASS.

- [ ] **Step 6: Commit**

~~~bash
git add apps/web/src/features/plans/a1Trace.ts apps/web/src/features/plans/A1TraceCanvas.tsx apps/web/src/features/plans/A1TraceCanvas.test.tsx apps/web/src/features/plans/A1TraceReviewPage.tsx apps/web/src/features/plans/A1TraceReviewPage.test.tsx apps/web/src/app/App.tsx apps/web/src/features/plans/PlansPage.tsx apps/web/src/styles.css
git commit -m "Add A-1 trace overlay review"
~~~

### Task 5: Enforce the approval boundary and verify the homeowner journey

**Files:**
- Modify: `apps/web/src/features/tour/TourPage.tsx`
- Modify: `apps/web/src/features/tour/TourPage.test.tsx`
- Modify: `apps/web/src/features/plans/A1TraceReviewPage.tsx`
- Modify: `apps/web/src/features/plans/A1TraceReviewPage.test.tsx`
- Create: `tests/e2e/a1-trace.spec.ts`
- Modify: `spikes/tour_quality/acceptance.md`

**Interfaces:**
- Review UI exposes `Trace approval: pending`.
- Tour UI labels itself `Unapproved prototype`; no A-1-accurate claim is permitted.

- [ ] **Step 1: Write failing approval and browser tests**

~~~tsx
it("does not describe the tour as A-1 accurate before approval", () => {
  render(<TourPage />);
  expect(screen.getByText(/unapproved prototype/i)).toBeVisible();
  expect(screen.queryByText(/A-1 accurate/i)).not.toBeInTheDocument();
});
~~~

~~~ts
test("homeowner can compare the complete proposed plan with its trace", async ({ page }) => {
  await openImportedA1Trace(page);
  await expect(page.getByText("Trace approval: pending")).toBeVisible();
  await page.getByRole("button", { name: "Overlay" }).click();
  await expect(page.getByLabel("A-1 proposed-plan trace")).toBeVisible();
  await page.getByRole("button", { name: "Linework traced" }).click();
  await page.getByRole("button", { name: /kitchen.*wall/i }).click();
  await expect(page.getByText(/linework-traced/i)).toBeVisible();
});
~~~

- [ ] **Step 2: Run the tests to verify they fail**

Run: `npm --workspace apps/web test -- --run src/features/tour/TourPage.test.tsx src/features/plans/A1TraceReviewPage.test.tsx`

Run: `HEARTHVIEW_E2E_API_PORT=50177 HEARTHVIEW_E2E_WEB_PORT=50178 npm run test:e2e -- tests/e2e/a1-trace.spec.ts`

Expected: FAIL because the trace approval boundary and route do not exist.

- [ ] **Step 3: Implement the explicit boundary**

Never add automatic approval. Disable any future-3D approval control while ambiguities remain. Otherwise, require explicit homeowner approval in the conversation. Add a persistent tour banner: “Unapproved prototype - compare the A-1 trace first.” Update acceptance documentation to say the old tour geometry is invalid pending trace review.

- [ ] **Step 4: Run all verification**

~~~bash
UV_CACHE_DIR=/private/tmp/hearthview-uv-cache npm test
npm run build
HEARTHVIEW_E2E_API_PORT=50177 HEARTHVIEW_E2E_WEB_PORT=50178 UV_CACHE_DIR=/private/tmp/hearthview-uv-cache npm run test:e2e -- tests/e2e/a1-trace.spec.ts
git diff --check
~~~

Expected: all tests and build pass; no whitespace errors.

- [ ] **Step 5: Perform mandatory visual QA**

At desktop resolution inspect PDF, Trace, and Overlay at full size, then inspect kitchen/living/mudroom, stair/pantry/powder, and entry/existing-living connections. Record only observed facts. Do not claim user approval.

- [ ] **Step 6: Commit**

~~~bash
git add apps/web/src/features/tour/TourPage.tsx apps/web/src/features/tour/TourPage.test.tsx apps/web/src/features/plans/A1TraceReviewPage.tsx apps/web/src/features/plans/A1TraceReviewPage.test.tsx tests/e2e/a1-trace.spec.ts spikes/tour_quality/acceptance.md
git commit -m "Verify A-1 trace review"
~~~
