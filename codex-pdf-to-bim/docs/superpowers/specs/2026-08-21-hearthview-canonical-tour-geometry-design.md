# HearthView Canonical Tour Geometry

**Status:** Approved design
**Date:** 2026-08-21
**Source:** Garrigan residence A-1 proposed first floor
**Parent designs:** `2026-08-18-hearthview-phase-0a-design.md`, `2026-08-18-hearthview-tour-quality-spike.md`

## Goal

Keep the successful browser-native tour controls and visual treatment while replacing the tour spike's independent, hand-authored room layout with a geometry adapter derived from HearthView's canonical A-1 spatial model.

The corrected tour remains focused on the proposed kitchen and living room. It includes enough adjacent context to make every boundary and transition intelligible: the mudroom opening, pantry and stair transition, low-ceiling zone, and opening into the existing living room. It does not expand into a furnished whole-house tour.

## Problem statement

The first tour artifact encoded several printed A-1 dimensions correctly, but it maintained a second spatial contract. Its validator compared the GLB against that same contract rather than comparing the contract against canonical A-1 geometry. As a result, internally consistent but incorrect wall topology passed:

- the east living-room wall did not preserve the A-1 window, solid 60-inch TV zone, and mudroom-opening sequence;
- the south living-room wall did not preserve the 3-foot-1-inch return, 5-foot opening, and 3-foot-1-inch return;
- adjacent transitions were flattened into a generic rectangular room;
- the overhead view could present an orientation inconsistent with the north indicator;
- tests asserted hand-written tour literals instead of a shared source of truth.

The existing acceptance result for geometry is therefore superseded. Navigation and performance results remain useful, while geometry must be re-earned.

## Scope and trust boundary

### Measured and canonical

The following data belongs to one canonical A-1 spatial model and is represented in signed integer ticks at 1/1024 inch:

- the 30-foot-1-inch kitchen/living span;
- the 15-foot-11-inch north-wall-to-south-transition depth;
- the 8-foot-5-inch primary ceiling height;
- the 8-foot-7-inch by 4-foot-3-inch island;
- the island's 3-foot-6-inch west and north clearances and 6-foot south transition;
- the 14-foot-9-inch living-room clear width;
- the north kitchen window group and deck glazing topology;
- the west kitchen appliance-wall topology;
- the east living-room wall's window, solid TV zone, and mudroom opening;
- the south living-room wall's 3-foot-1-inch, 5-foot, 3-foot-1-inch chain;
- the 60-inch TV anchor on the east solid interval;
- the main pantry, stair, low-ceiling, mudroom, and existing-living-room boundary context needed to understand those transitions.

Every canonical element carries a source reference or an explicit reviewed interpretation. Printed measurements remain distinct from reviewed topology and from provisional offsets. The A-1 instruction not to scale the drawing remains binding.

### Provisional appearance

Cabinet fronts, hardware, exact cabinet widths not printed on A-1, furniture, decor, finishes, lighting, and undimensioned styling offsets remain provisional. They may be detailed and plausible, but they must:

- be anchored to canonical walls, openings, or regions;
- never move or cover a canonical opening;
- never change a measured clearance;
- be identified as visual staging in the manifest and UI;
- remain separable from the canonical geometry hash.

## Canonical coordinate system

The A-1 spatial model uses a single plan coordinate frame:

- origin: northwest inner face of the 30-foot-1-inch kitchen/living span;
- positive X: west to east;
- positive Y: north to south;
- positive Z: floor to ceiling;
- storage unit: integer ticks;
- display conversion: meters exactly once at the adapter or GLB boundary.

The main kitchen/living region spans X = 0 to 361 inches and Y = 0 to 191 inches. The island begins after the 26-inch counter zone and 42-inch clearance on each relevant axis, giving a measured 103-inch by 51-inch footprint and a 72-inch transition to the south boundary.

The focused context may extend beyond the 191-inch main-region depth where A-1 shows adjacent circulation. That context does not change the main-region depth claim.

## Architecture

### Canonical A-1 spatial model

A new pure-Python canonical spatial module owns the measured plan coordinates, boundaries, openings, regions, ceiling zones, fixed-object anchors, provenance, and provisional flags for the focused A-1 slice.

The existing Phase 0A fixture is derived from this module rather than maintaining its own independent wall coordinates. Validation, deterministic compilation, source clickback, and the tour adapter therefore consume the same structural facts.

The spatial module exposes immutable records and two explicit projections:

1. a `ProjectModel` projection for the existing validation, canonical hashing, API, and analytic GLB compiler;
2. a tour-scene projection containing canonical architectural primitives plus appearance anchors and navigation metadata.

Neither projection may introduce measured coordinates that are absent from the canonical spatial model.

### Tour geometry adapter

The tour adapter converts canonical tick geometry into Blender-space meters. It produces:

- canonical wall panels and opening frames;
- the island structural footprint;
- floor, threshold, and ceiling-zone geometry;
- named regions for kitchen, living room, mudroom context, pantry/stair context, and existing-living transition;
- fixed TV and cabinetry anchor intervals;
- a walkable polygon and barriers derived from canonical boundaries plus staging collision envelopes;
- north-up camera presets and orientation metadata.

The adapter is deterministic. Given the same canonical model and adapter version, it emits the same geometry payload and geometry hash.

### Blender appearance scene

Blender continues to author materials, bevels, fixtures, provisional cabinetry detail, furniture, decor, cameras, and lighting. Architecture creation no longer contains freehand wall or opening coordinates. Appearance builders receive named canonical anchors and may only add staging geometry relative to them.

The GLB keeps canonical and staging nodes in separate named roots. Canonical nodes embed element IDs, source-reference IDs, and the canonical geometry hash. Staging nodes embed a provisional category and anchor ID.

### Browser presentation

The existing Orbit, Move here, Walk, Overhead, Reset, and Exit walk behavior remains. Walkability and collision use the regenerated manifest.

Overhead mode uses an explicit camera up vector so north is always at the top. The room-orientation diagram is generated from canonical region bounds and opening positions rather than static decorative rectangles. Kitchen, living room, island, mudroom transition, and north direction must agree between the diagram and the rendered overhead view.

## Data flow

```text
A-1 source evidence + reviewed interpretation
  -> canonical A-1 spatial model in integer ticks
     -> Phase 0A ProjectModel / validation / canonical hash
     -> tour geometry adapter
        -> canonical Blender architecture + appearance anchors
        -> walkable/collision/camera/orientation manifest
           -> detailed GLB + browser tour
```

No tour-specific measured coordinate may bypass the canonical spatial model.

## Validation

### Canonical model validation

Validation rejects:

- missing source provenance for measured elements;
- non-orthogonal or disconnected boundary topology in this orthogonal slice;
- openings outside their host walls or overlapping another opening;
- an east-wall sequence other than window, solid TV zone, mudroom opening;
- a south-wall sequence other than 37-inch solid, 60-inch opening, 37-inch solid;
- a TV anchor outside the east solid interval;
- island size or measured clearance drift of even one tick;
- a north/west opening or appliance topology inconsistent with the approved A-1 interpretation;
- conflicting north orientation metadata.

### Adapter and artifact validation

The artifact validator receives both the canonical spatial payload and the generated manifest. It rejects:

- mismatched canonical model or geometry hashes;
- missing or transformed canonical nodes;
- actual GLB bounds that drift more than 3 mm after unit conversion;
- missing east window, TV zone, mudroom opening, south returns, or south opening;
- staging geometry that intersects a canonical opening or measured island clearance;
- walkable areas that cross a canonical wall or staging barrier;
- camera or orientation metadata that is not north-up;
- stale artifact hashes, missing textures, or payloads over 45 MB.

The validator must not accept a manifest merely because it agrees with constants owned by the tour package.

## Error behavior

- If canonical geometry cannot be validated, artifact generation stops before Blender appearance work begins.
- If a staging object intersects canonical architecture, generation reports the staging object and anchor rather than silently moving canonical geometry.
- If an A-1 offset is not printed or reviewed, it remains explicitly provisional and cannot be included in the canonical hash as a measured claim.
- If the detailed artifact and canonical payload disagree, the browser does not load the tour and displays a retryable integrity message.
- Existing Phase 0A review edits remain authoritative; a stale tour artifact must be regenerated from the current canonical model revision.

## Testing strategy

Implementation follows red-green-refactor.

Pure backend tests first establish the canonical coordinate frame, measured dimensions, east and south wall sequences, island placement, region bounds, source provenance, and deterministic hash. Existing fixture and compiler tests are updated to prove they derive from the shared spatial model.

Adapter tests then prove exact tick-to-meter conversion, named canonical nodes, north-up cameras, geometry-derived orientation metadata, collision boundaries, and staging-anchor constraints. A regression test must fail against the old hand-authored mudroom and south-opening coordinates.

Artifact tests inspect actual GLB bounds and metadata against the canonical payload. They must demonstrate that changing only the manifest cannot make incorrect GLB geometry pass.

Frontend tests prove the orientation diagram is generated from the manifest and agrees with north-up overhead mode. Existing navigation tests remain and are rerun against regenerated barriers.

Headed browser acceptance covers orbit, a valid move-here target, walk and Escape recovery, overhead orientation, reset, compact layout, and integrity-error behavior. Visual review compares the regenerated overhead view directly with the A-1 proposed first-floor plan.

## Acceptance gates

The corrected tour is accepted only when:

1. One canonical spatial model supplies both Phase 0A and tour geometry.
2. The east wall visibly and structurally follows window, TV zone, mudroom opening.
3. The south wall visibly and structurally follows 37-inch return, 60-inch opening, 37-inch return.
4. North/west kitchen topology, deck glazing, island dimensions, clearances, and living width agree with A-1 evidence.
5. Focused mudroom, pantry/stair, low-ceiling, and existing-living context makes the openings intelligible without expanding into a whole-house tour.
6. Overhead mode and the orientation diagram are north-up and mutually consistent.
7. Canonical and staging geometry remain separately identified and hashed.
8. The artifact validator cross-checks actual GLB geometry against the canonical payload.
9. Orbit, Move here, Walk, Escape, Exit walk, Overhead, and Reset still pass in a real browser.
10. The browser payload remains at or below 45 MB and becomes usable within 10 seconds on the target local Mac.
11. Backend, frontend, artifact, end-to-end, and production-build verification pass.
12. A human comparison against A-1 approves the layout before geometry is marked passed.

## Deferred

This correction does not add general arbitrary-PDF reconstruction, whole-house furnishing, construction-grade cabinetry, roof or upper-floor geometry, permit output, or cloud delivery. Those remain later HearthView phases.
