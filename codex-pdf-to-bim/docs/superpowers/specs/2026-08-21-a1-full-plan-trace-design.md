# A-1 Full-Plan Trace Review

**Status:** Proposed for user review before implementation

## Purpose

Replace the simplified tour-specific room model with a reviewable, whole-sheet
2D trace of the proposed first-floor plan on A-1. The immediate goal is to
prove that HearthView can represent the drawing's actual topology before any
3D generation resumes.

The source is page 2, view 2, "Proposed - First Floor," in the Garrigan A-1
PDF. The existing half of the sheet is reference material only; it is not part
of this proposed-plan trace.

## Scope

The trace covers every visible proposed first-floor architectural element in
view 2:

- exterior and interior wall runs;
- rooms, circulation, stairs, and the deck footprint;
- door and window openings, including swings where drawn;
- fixed architectural elements such as the fireplace, kitchen counters,
  island, powder-room fixtures, pantry, and low-ceiling boundary;
- printed room names, ceiling-height notes, and dimensions used for validation.

It excludes furniture, photorealistic materials, cabinet-front detail, 3D,
tour navigation, permits, construction output, and any claim that an
unprinted offset is field-verified.

## Trace data and provenance

The trace is a versioned, source-page-coordinate data file. It stores SVG-like
paths/polygons for walls, openings, fixtures, labels, and dimensions. Every
record has a stable identifier, semantic type, source page/view, and one of
these provenance states:

- `dimension_verified`: geometry or extent is supported by a printed A-1
  dimension. The record links to its dimension label and validates against it.
- `linework_traced`: geometry follows visible proposed-plan linework but has no
  printed dimension establishing that exact position. It must be visibly
  labeled as traced, not measured.
- `ambiguous`: the sheet does not make the intended topology legible enough to
  trace safely. Ambiguous records render in an attention color and block
  approval until resolved, removed from scope, or explicitly accepted by the
  user.

No geometry may be unclassified. A later spatial/3D projection may consume
only the approved trace plus its provenance; it may not introduce coordinates
of its own.

## Review experience

Add an A-1 trace-review route reached from the current Plans flow. It presents
the proposed-plan crop at source resolution with three modes: PDF, Trace, and
Overlay. Overlay keeps the source drawing visible beneath an adjustable-opacity
trace, so the user can identify even small offsets without trusting a separate
render.

The panel shows counts for verified, traced, and ambiguous records; a legend;
and an item list grouped by room. Selecting a record highlights it in the
overlay and reports its provenance plus any associated printed dimensions.
Room/topology groups include kitchen, living room, mudroom, study room,
existing living room, stair/pantry/powder sequence, entry/dining room, and
deck. The review view explicitly notes that the trace is not for permits,
construction, or field verification.

## Approval gate

The trace is not eligible to feed 3D until the user approves the full proposed
plan in overlay mode. Approval means:

1. Exterior outline, room adjacencies, openings, stairs, deck, and fixed
   elements visually coincide with the A-1 proposed view.
2. Every trace record is classified as dimension-verified, linework-traced, or
   deliberately resolved ambiguity.
3. Dimension-verified records meet the documented tolerance; linework-traced
   records never display as measured construction facts.
4. The user has accepted the whole-plan trace or explicitly narrowed the
   approved scope to a named subset, such as kitchen/family only.

Until that gate passes, the current tour remains an invalid prototype and must
not be described as A-1-accurate.

## Validation

Automated checks will verify that:

- the proposed-plan crop and trace share a deterministic coordinate transform;
- all trace records have stable IDs, source provenance, and valid geometry;
- every room/topology group above is represented or explicitly marked
  ambiguous;
- exterior walls form a closed proposed-plan boundary;
- doors/windows attach to a wall and fixed elements lie within a room or
  declared boundary;
- each dimension-verified record matches its linked A-1 measurement within a
  stated tolerance;
- the review UI can switch PDF/Trace/Overlay, filter provenance states, and
  reveal an item's source evidence.

Visual QA is mandatory: inspect the whole overlay at full size, then inspect
the kitchen/living/mudroom, stair/pantry/powder, and entry/existing-living
connections at a readable zoom. Automated consistency checks never replace
that comparison.

## Failure handling

If an entire region cannot be traced confidently from A-1, the UI marks the
region ambiguous rather than filling in a plausible shape. If the full-sheet
review becomes too ambiguous or unwieldy, the user may approve a named,
bounded subset; unapproved portions remain unavailable to 3D generation.
