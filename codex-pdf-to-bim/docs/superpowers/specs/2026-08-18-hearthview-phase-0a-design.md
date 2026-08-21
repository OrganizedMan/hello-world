# HearthView Phase 0A: First-Floor Vertical Slice

**Status:** Approved through delegated technical judgment  
**Date:** 2026-08-18  
**Parent design:** `2026-08-18-hearthview-design.md`  

## Goal

Deliver a polished local application that proves HearthView's complete safety and visualization path on the proposed first-floor A-1 drawing:

```text
PDF import -> guided confirmation -> exact model -> validation
  -> deterministic GLB -> interactive 3D -> local Blender render
```

This phase establishes the architecture used by every later phase. It does not attempt general automatic reconstruction.

## User journey

### Welcome and import

The home screen explains the workflow in three short steps: add plans, confirm uncertain details, explore in 3D. The primary action accepts PDF files by picker or drag-and-drop. The application displays a local-processing badge and a tooltip explaining that plans remain on the Mac.

For the initial fixture, a “Load Garrigan example” action copies the supplied sources into an isolated project store through the same ingest API as ordinary imports. No UI code depends on the absolute Downloads paths.

### Sheet selection

Imported pages appear as labeled thumbnails. HearthView proposes the A-1 first-floor page and the proposed-plan region, while allowing the homeowner to correct the page or draw a new region. The source viewer always exposes zoom, pan, page number, and current source-resolution status.

### Guided review

The review queue begins with a preloaded fixture interpretation of the A-1 proposed design and later accepts generated candidates through the same contract. Review cards cover:

1. Confirm the proposed first-floor region.
2. Confirm the 8-foot-7-inch by 4-foot-3-inch kitchen island.
3. Confirm the east living-room wall order: window, solid TV zone, mudroom opening.
4. Confirm the south living-room wall's 5-foot opening and two 3-foot-1-inch returns.
5. Confirm that the wall-mounted TV belongs on the solid east-wall interval.

Each card shows a source highlight, plain-language explanation, proposed value, visible label, units, tooltip, confirm/edit action, and “Why am I being asked?” details. Values edited in feet-and-inches are parsed into integer ticks.

### Validation and correction

The project status bar reports how many required decisions remain. Invalid edits are rejected at the point of entry with a concrete explanation. The detailed validation panel groups issues as “Needs your input,” “Conflicting information,” or “Preview warning.”

Rendering remains locked until all blocking A-1 assertions pass. The application may show a watermarked provisional 3D preview while decisions remain.

### Explore in 3D

Once ready, the model workspace opens a synchronized Three.js scene with orbit, pan, zoom, reset, plan, axonometric, kitchen, and living-room camera presets. Clicking geometry selects the matching model element and offers source clickback.

The viewer uses warm neutral model materials, distinct phase/status overlays, soft shadows, a ground plane, and accessible camera controls. It loads a GLB from the geometry-artifact API rather than recreating walls from UI state.

### Render preview

The Render page offers a Warm Blank Slate preset, camera selection, draft/final quality, image size, and visible estimated resource guidance. Phase 0A must prove the job contract and produce at least one local Blender render when Blender is installed. If it is not installed, the page provides a checked prerequisite message and retains the runnable browser path.

## Web application

The initial web app uses React, TypeScript, Vite, React Router, TanStack Query, PDF.js, Three.js, React Three Fiber, Zod, and Vitest. Styling uses application-owned CSS variables and components rather than a heavy generic component framework.

Routes:

- `/` - welcome and recent projects;
- `/projects/:projectId/plans` - source and region setup;
- `/projects/:projectId/review` - prioritized confirmation queue;
- `/projects/:projectId/model` - synchronized source/model viewer;
- `/projects/:projectId/render` - camera and render jobs;
- `/projects/:projectId/report` - validation, provenance, and hashes.

Core UI components:

- AppShell and ProjectProgress;
- LocalOnlyBadge and HelpTooltip;
- PdfSourceViewer and SourceHighlight;
- ReviewQueue and ReviewCard;
- ArchitecturalLengthField;
- ProjectStatusBanner and ValidationIssueList;
- ModelViewer and CameraPresets;
- ElementInspector and SourceClickback;
- RenderSettings and RenderJobCard.

Every interactive component has a visible label, accessible name, keyboard behavior, focus style, tooltip or help text where domain meaning is non-obvious, and automated accessibility coverage.

## API and persistence

The FastAPI service uses Pydantic v2, SQLAlchemy/SQLite, pypdf for safe metadata and text inspection, and a pinned PDF rendering backend selected during implementation. Runtime project data lives outside the source tree in an application data directory overridable for tests.

Phase 0A endpoints:

```text
GET    /health
POST   /projects
GET    /projects/{id}
POST   /projects/{id}/sources
GET    /projects/{id}/sources/{sourceId}/pages/{page}/preview
GET    /projects/{id}/review-queue
POST   /projects/{id}/review-events
GET    /projects/{id}/model
POST   /projects/{id}/validate
POST   /projects/{id}/compile
GET    /projects/{id}/geometry/{artifactId}.glb
POST   /projects/{id}/render-jobs
GET    /projects/{id}/render-jobs/{jobId}
GET    /projects/{id}/validation-report
```

SQLite stores projects, immutable source metadata, model events, snapshots, reports, tokens, geometry artifacts, render jobs, and manifests. Large bytes live in a content-addressed artifact tree. Database rows reference SHA-256 identities and relative artifact paths.

Source import streams to a temporary file, hashes while reading, validates the PDF, then atomically installs it into the artifact store. Filenames are display metadata only and cannot control paths.

## Contracts

The Phase 0A canonical model includes project, source reference, level, wall, opening, fixed object, island, constraint, evidence state, and review state contracts.

An imperial length is encoded as integer ticks plus a canonical display string at API boundaries. TypeScript may receive integers only within its safe range; the initial residential domain is safely inside that range, while persisted canonical serialization encodes ticks as decimal strings to avoid future JSON precision loss.

Model events are append-only and carry event ID, project ID, base revision, actor kind, operation, payload, source references, rationale, and timestamp. Revision conflicts return a typed conflict and the current revision.

## Exact validation rules

The validator must report stable issue codes and element IDs.

- Every structural element has at least one source or user reference.
- Openings reference an existing host wall.
- Opening intervals are inside their host and do not overlap.
- Ordered opening/solid intervals match station order.
- The east wall contains a window before a solid TV interval of at least 60 inches before the mudroom opening.
- The south wall contains a 37-inch solid return, 60-inch opening, and 37-inch solid return.
- The TV anchor is contained by the east-wall solid interval and intersects no opening.
- The island is exactly 103 by 51 inches.
- Required review cards are approved or edited-and-approved.

A passing report contains no blocking issues and mints a token from canonical model, report, schema, and validator hashes.

## Geometry compiler

The compiler consumes a validated model snapshot and creates an indexed primitive table before serialization. Phase 0A supports orthogonal wall panels, rectangular openings, floor slab, ceiling, island massing, simple fixed cabinetry, and fixed-object anchors.

For each wall, the compiler partitions its station range at opening endpoints and emits deterministic rectangular panels for solid spans plus jamb, sill, and head panels as appropriate. It never subtracts an unrestricted Boolean mesh.

Primitive records are sorted by canonical element ID, part kind, and station. Positions derive from integer ticks and convert once to meters at GLB output. The geometry hash covers compiler identity and canonical primitive records. The GLB embeds project ID, model hash, geometry hash, and canonical element IDs.

Ten independent compiles of the unchanged fixture must produce one canonical geometry hash. Byte identity is tested when the serializer permits stable output; the GLB file hash is tracked separately.

## Blender contract

The render worker starts Blender as a subprocess with an application-owned Python scene script. It imports the compiled GLB into a locked canonical collection, validates metadata and bounds, then adds a separate appearance collection, camera, and light rig.

The script may assign materials but may not apply transforms, modifiers, or mesh edits to canonical nodes. Pre- and post-render checks compare node IDs, transforms, primitive counts, bounds, and embedded geometry hash.

Phase 0A's Blender goal is contract proof and a polished warm-neutral still, not the full Phase 4 furnishing library. The render manifest records Blender version, engine, device, settings, input hashes, output hash, timing, and warnings.

## Error behavior

- Invalid PDF: preserve no partial project source; explain how to choose another file.
- Duplicate PDF: reuse source bytes and explain that the file is already in the project.
- Unreadable page preview: retain metadata and allow retry or manual external review.
- Stale review edit: reload the latest revision without discarding the user's entered value.
- Invalid architectural length: show examples such as `5' 0"`, `60 in`, and `1524 mm`.
- Blocking validation: keep the report navigable and link every issue to the responsible review card or model element.
- Compile mismatch: invalidate the token and require a fresh validation.
- Blender missing: keep interactive 3D available and provide a verified install check.
- Render failure: preserve settings and logs, then offer retry.

## Test and acceptance plan

Implementation follows red-green-refactor in small vertical units.

Backend unit and property tests cover units, canonical serialization, station partitioning, model events, revision conflicts, source paths, fixture validation, and geometry identity.

Frontend component tests cover labels, tooltips, unit examples, inline errors, review progression, blocking status, and accessible names. End-to-end browser tests cover import, confirmation, invalid TV placement, validation, model load, camera changes, source clickback, and render-job submission.

Phase 0A is accepted when:

1. The app starts locally with one documented command.
2. A real PDF can be imported and A-1 previewed.
3. The required review queue is clear to a homeowner and all domain inputs are labeled and explained.
4. Invalid topology and TV placement are blocked with plain-language errors.
5. Exact island and family-room assertions pass.
6. Every structural element has provenance.
7. Validation mints a model-bound token.
8. Ten compiles yield one geometry hash.
9. The GLB loads in the browser with at least four useful cameras.
10. All cameras display the same geometry hash.
11. The render contract produces a local still when Blender is installed and otherwise reports the prerequisite cleanly.
12. Automated unit, contract, fixture, accessibility, and end-to-end tests pass.

## Deferred to the next phase

Whole-house levels, stairs, attic options, roof planes, general vector detection, OCR, multimodal services, full photoreal asset curation, IFC/DXF, Tauri packaging, accounts, collaboration, and cloud deployment are outside Phase 0A. Their interfaces remain represented in the parent design and must not be prematurely simulated as completed features.
