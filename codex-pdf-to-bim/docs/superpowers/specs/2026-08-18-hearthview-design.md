# HearthView: Homeowner PDF-to-3D Design

**Status:** Approved through delegated product and technical judgment  
**Date:** 2026-08-18  
**Working directory:** `codex-pdf-to-bim/`  
**Initial fixture:** Garrigan residence (private homeowner fixture)  

## 1. Product intent

HearthView is a local-first browser application for a homeowner who wants to import architectural renovation PDFs, resolve only the ambiguities that matter, explore the proposed design in 3D, and create warm photorealistic renders.

The application must feel like a guided consumer product, not a CAD or BIM workstation. It will use plain language, clearly labeled controls, persistent units, contextual tooltips, safe defaults, previews, undo, and source-linked explanations. BIM terminology may exist internally but must not be required to complete the workflow.

The application is assisted rather than falsely automatic. It may propose walls, openings, dimensions, phases, rooms, levels, and alternatives, but it must visibly ask for confirmation when evidence is incomplete or contradictory. Confirmed facts compile deterministically into geometry. Renderers never edit architectural geometry.

## 2. End-user outcome

The happy path is:

1. The homeowner opens the local application in a browser.
2. They drag in one or more plan PDFs.
3. HearthView identifies sheets and proposed-plan regions.
4. A short guided checklist asks only understandable questions: which option is preferred, whether a highlighted wall/opening is correct, and which printed dimension controls.
5. The application shows progress toward a model that is ready to view.
6. Once blocking questions are resolved, HearthView builds a navigable 3D model.
7. The homeowner explores preset and custom camera views.
8. They select a warm, neutral material/furnishing preset and request a photoreal render.
9. The application saves the render and its provenance alongside the project.

The first release supports the supplied Garrigan vector PDFs. Later phases broaden extraction and geometry without replacing the confirmed-model foundation.

## 3. Product principles

- **Homeowner language:** say “wall opening,” not “hosted void”; say “needs your input,” not “underconstrained.” Technical detail remains available under “Why?”
- **Progressive disclosure:** show the next blocking decision first. Advanced geometry and evidence controls stay collapsed until needed.
- **Visible certainty:** distinguish documented, inferred, user-confirmed, and unresolved elements with color, pattern, text, and tooltip explanations.
- **No silent invention:** unknown height, thickness, option, or roof relation remains unknown until confirmed.
- **Source before assumption:** printed dimensions outrank graphic scaling. “Do not scale” warnings remain visible in project provenance.
- **One house, many views:** interactive and photoreal render paths consume the same validated geometry artifact.
- **Local by default:** source documents and models remain on the user’s Mac. Core features work without network access.
- **Reversible work:** every meaningful edit is undoable and replayable.

## 4. Architecture

HearthView uses a monorepo inside `codex-pdf-to-bim/`.

```text
codex-pdf-to-bim/
  apps/
    web/                 React, TypeScript, PDF.js, Three.js
    api/                 FastAPI composition root and generated OpenAPI
  packages/
    contracts/           JSON Schema and generated TypeScript/Python types
    ui/                  accessible homeowner-facing components
  services/
    ingest/              hashing, PDF metadata, previews, regions
    interpret/           vector/text/CV/OCR candidate production
    model/               events, snapshots, alternatives, provenance
    constraints/         exact units, topology rules, solve reports
    geometry/            deterministic analytic mesh compiler
    render/              Blender orchestration and manifests
    export/              GLB, OBJ, DXF, and IFC profiles
  fixtures/
    garrigan-261-grove/   source manifest and expected assertions
  tests/                 unit, contract, fixture, geometry, visual, e2e
  docs/                  design, decisions, accuracy, runbooks
```

The web application owns interaction, PDF overlays, guided review, exact edits, project status, the real-time viewer, camera composition, and render presentation.

The Python service owns source hashing, PDF analysis, candidate generation, constraint solving, validation, deterministic geometry, Blender jobs, exports, SQLite persistence, and content-addressed artifacts.

JSON Schema and OpenAPI define the boundary. Request and response types are generated rather than duplicated by hand.

## 5. Trust and data flow

```text
immutable source PDFs
  -> evidence bundle
  -> untrusted candidate suggestions
  -> explicit homeowner review events
  -> canonical model snapshot
  -> solve and validation report
  -> validation token
  -> immutable geometry artifact and GLB
  -> Three.js exploration and Blender rendering
```

Interpretation cannot directly mutate an approved model. It emits candidate patches with evidence references, confidence components, alternatives, and unknown fields. Accept, edit, or reject actions create append-only model events.

A passing validation report mints a token bound to the model, schema, solver, and report hashes. The geometry compiler accepts only a matching token. Any structural edit invalidates the token and previously compiled geometry.

The compiler is pure for a given model hash, compiler version, and target profile. Stable element ordering and integer architectural coordinates produce a canonical primitive table and geometry hash. The browser viewer and Blender receive the same GLB bytes.

## 6. Canonical model

Architectural coordinates use signed integer ticks at 1/1024 inch. Display values use friendly feet-and-inches input and formatting. Hard dimensions never rely on binary floating point.

The initial entity set includes:

- Project, source document, sheet, drawing region, level, and design option.
- Wall segment, junction, wall opening, door, window, and unframed opening.
- Floor slab, ceiling plane, room, stair, stair run, and landing.
- Roof plane, roof edge, dormer, and low-headroom zone.
- Fixed cabinetry, appliance, furniture, material, camera, and light rig.
- Dimension, alignment, topology, and clearance constraints.
- Evidence, candidate patch, review event, source reference, and confidence.
- Solve report, validation report/token, geometry artifact, render manifest, and export artifact.

Walls form graph edges and junctions form vertices. Every opening belongs to one wall and occupies a non-overlapping half-open station interval. Rooms derive from wall-face cycles. A wall-mounted object must be contained by a solid interval and may not overlap an opening.

Design alternatives remain separate. Required alternatives have no silent default; the homeowner selects one through a visual comparison before whole-project release.

## 7. Homeowner experience

The main navigation is organized by understandable tasks:

1. **Plans** - import files and confirm detected sheets.
2. **Review** - answer a prioritized queue of plain-language questions.
3. **Model** - inspect the proposed home in 2D and 3D.
4. **Style** - choose finishes, furnishings, daylight, and mood.
5. **Render** - frame cameras, preview, and create final images.
6. **Export** - download geometry, reports, and exchange formats.

The primary modeling workspace uses a source plan, contextual inspector, and synchronized 3D preview. On narrower screens, the inspector and preview become tabs instead of compressed panes.

Every input has:

- a visible persistent label;
- explicit units beside the field;
- example formatting where useful;
- a tooltip explaining what the value changes;
- current source/authority status;
- inline validation with a corrective action;
- keyboard and pointer access;
- a safe reset or undo path.

The review queue is ordered by blocking impact. A card shows the highlighted source area, the proposed interpretation, why the app is asking, and a small set of safe actions. Batch acceptance is limited to homogeneous non-blocking candidates and always shows a preflight summary.

## 8. Fixture-specific requirements

The Garrigan A-1 model is the first regression fixture. Release requires:

- east family/living-room wall order: window, at least 60 inches of solid TV-mount wall, then mudroom opening;
- south wall order: 3 feet 1 inch solid, 5 foot unframed opening to the existing living room, then 3 feet 1 inch solid;
- TV anchor hosted on the east wall and intersecting no opening;
- kitchen island exactly 8 feet 7 inches by 4 feet 3 inches;
- approved kitchen cabinet, appliance, and window ordering;
- every structural element linked to drawing evidence or a user-entered fact.

Whole-house phases additionally preserve separate basement ceiling zones, reconcile or visibly conflict the three-riser transition, align the north additions without rescaling floors, and keep the primary attic and OP#B attic schemes mutually exclusive.

## 9. Geometry and validation

Validation runs in layers: schema, references, topology, exact constraints, geometry, vertical relations, roof closure, phase/option consistency, evidence coverage, and release identity.

User-facing status maps technical results into:

- **Ready to view** - no blocking architectural issues.
- **Needs your input** - one or more understandable decisions remain.
- **Conflicting information** - two source facts disagree and are shown together.
- **Preview only** - 3D can be explored but final rendering/export remains watermarked.

Analytic geometry handles orthogonal walls, openings, slabs, ceilings, and stairs first. Walls are split into panels around openings rather than passed through unrestricted Boolean operations. A narrow fixed-precision kernel adapter is introduced only for later roof and dormer intersections.

The compiler embeds canonical element IDs in GLB nodes so selection in 3D can navigate back to the exact source crop and review history.

## 10. Rendering and appearance

Three.js supplies immediate interaction, model-style materials, plan/axonometric views, section visibility, and saved cameras.

Blender LTS supplies final still renders. Eevee is the quick draft path and Cycles is the photoreal quality path. Blender imports the immutable GLB, verifies its geometry hash, and may add only appearance-layer materials, lights, cameras, and non-structural asset instances. It may not remodel, transform, or modify canonical geometry.

The default style is **Warm Blank Slate**:

- natural oak or similarly restrained wood tones;
- warm off-white walls and millwork;
- stone in soft neutral colors;
- warm daylight with believable exposure;
- a small number of generic modern furnishings for scale;
- minimal neutral textiles and décor;
- no personal photos, bold artwork, branded objects, or heavily styled clutter.

Users can change material and furnishing presets without changing the geometry hash. Final renders record model, geometry, appearance, camera, light rig, renderer, settings, and output hashes.

Photoreal release criteria include correct silhouettes and openings, stable geometry identity, adequate sampling, no missing textures, no clipped camera geometry, and a recorded provenance manifest.

## 11. Error handling and safety

All service failures use typed machine-readable errors and a plain-language UI mapping. A failed worker never silently produces a successful artifact.

- Malformed or oversized PDFs are rejected in an isolated ingest job with recovery guidance.
- Parsing failures preserve the source and offer manual sheet/region selection.
- Missing vertical information produces a preview with visibly provisional height, not an invented final model.
- Conflicting dimensions show both source snippets and allow the homeowner to choose, edit, or leave unresolved.
- Geometry failures identify the affected elements and preserve the last valid model.
- Render failures retain the geometry and settings so the job can be retried.
- Interrupted jobs are resumable or safely restartable by input hash.

No core job uses the network. Optional future cloud interpretation is opt-in per job, describes exactly which crop will leave the device, and is not required for the complete local workflow.

## 12. Phased delivery

### Phase 0A - First-floor vertical slice

Deliver the runnable shell, PDF import/viewing, A-1 region workflow, exact units, wall/opening model, guided review, fixture validation, deterministic GLB, Three.js viewer, saved cameras, and a Blender render smoke path.

### Phase 0B - Whole-house manual model

Add levels, floor alignment, ceilings, stairs, alternatives, full event history, manually confirmed roof planes, whole-house validation, and project packaging.

### Phase 1 - Vector-PDF assistance

Add native text/path extraction, view-region proposals, scale evidence, dimension chains, wall bands, openings, phase features, symbols, and review-time measurement. Suggestions remain untrusted until confirmed.

### Phase 2 - Raster/OCR and advanced assistance

Add deskewing, OCR, classical CV, symbol classifiers, bounded multimodal candidate adapters, confidence calibration, and privacy controls. Manual tracing remains a complete fallback.

### Phase 3 - Sections, multistory, and roofs

Add robust floor anchors, stair/headroom solving, section/elevation association, roof plane graphs, dormers, low-headroom contours, and a narrow solid-kernel adapter.

### Phase 4 - Photoreal visualization

Add curated PBR materials, Warm Blank Slate presets, generic furnishing assets, material assignment assistance, lighting rigs, camera composition, Eevee drafts, Cycles finals, render queue, and quality checks.

### Phase 5 - Exchange and packaging

Complete GLB/OBJ/DXF exports, a defined IFC subset, interoperability fixtures, Tauri packaging, signed local releases, backup/restore, and production diagnostics.

Each phase must leave a usable application and retain the prior phase's deterministic contracts.

## 13. Testing strategy

Development follows test-driven implementation. Primary assertions are graph, dimension, hash, and provenance checks; screenshots are secondary diagnostics.

- Unit tests cover feet/inches parsing, tick arithmetic, station intervals, transforms, phase logic, and friendly error mapping.
- Property tests cover serialization, coordinate round trips, opening non-overlap, event replay, and deterministic compilation.
- Contract tests compare generated TypeScript/Python models and typed API errors.
- Fixture tests enforce all Garrigan graph, dimension, level, option, and evidence requirements.
- Geometry tests cover bounds, normals, degeneracy, opening panels, stable IDs, and repeated hashes.
- Visual tests compare PDF overlays and pinned model-view silhouette, depth, normal, and object-ID passes.
- End-to-end tests cover import, review, validation, compilation, multi-camera viewing, rendering, and export.
- Accessibility tests cover labels, tooltips, focus order, keyboard operation, contrast, reduced motion, and screen-reader descriptions.
- Privacy tests run the core application with network access denied.

At least ten clean compiles of the same validated A-1 model must yield one geometry hash. Multiple interactive and Blender cameras must cite that hash.

## 14. Initial non-goals

The product will not certify building codes, permits, structural design, zoning, accessibility, or as-built conditions. It will not infer concealed construction, generate native RVT/DWG/SKP files, model MEP, or claim fully automatic conversion of arbitrary drawings.

These boundaries must be disclosed in friendly language without obstructing ordinary visualization use.

## 15. Completion definition

The entire solution is complete when a homeowner can import the supplied vector drawings, select the proposed options, resolve a small guided review queue, explore a source-linked and dimensionally validated whole-house 3D model, style it without altering architecture, and create warm furnished photoreal renders through the local application.

Completion also requires deterministic geometry identity, no silent unresolved structural facts, full structural provenance, repeatable project restore, tested exchange formats, and a documented local installation path.
