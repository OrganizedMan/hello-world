# Task 1 — Authoritative spike scene contract

## Context

This is the first task in an isolated proof-of-quality scene for HearthView. It establishes the only printed dimensions and spatial metadata that the Blender scene and browser tour may consume. Do not touch the existing canonical geometry or viewer.

## Binding global constraints

- Printed dimensions are authoritative: 30′-1″ span, 15′-11″ north-wall-to-south-transition depth, 8′-5″ ceiling, 8′-7″ × 4′-3″ island, 3′-6″ west- and north-counter-face clearances, 6′-0″ south transition, and 14′-9″ living clear width. The vertical chain leaves a 2′-2″ counter zone.
- The spike says “Quality spike · visual staging” and never presents its display GLB as canonical geometry.
- Cabinet fronts, hardware, finishes, furnishings, décor, and undimensioned offsets are provisional visual staging.
- External assets are out of scope for this task.
- Tests exercise observable behavior, use hand-derived literal expectations, and do not assert source text or mocks.

## Files

- Create `spikes/__init__.py` if package import requires it.
- Create `spikes/tour_quality/__init__.py`.
- Create `spikes/tour_quality/scene_contract.py`.
- Create `tests/backend/test_tour_scene_contract.py`.
- Create `spikes/tour_quality/README.md`.

## Required interfaces

- `build_scene_contract() -> SceneContract`
- `SceneContract.to_manifest() -> dict[str, object]`
- `validate_scene_contract(contract: SceneContract) -> tuple[str, ...]`
- Export named literal meter constants consumed later by Blender.

Use immutable dataclasses. Include envelope bounds, named wall openings, island footprint, cabinet/appliance order, a walkable rectangle or polygon, collision rectangles, camera presets, printed-dimension source labels, and provisional categories. Serialization must contain only JSON primitives and have stable list ordering.

The exact hand-derived meters are:

- span `9.1694`
- room depth `4.8514`
- counter zone depth `0.6604`
- ceiling `2.5654`
- island width `2.6162`
- island depth `1.2954`
- west clearance `1.0668`
- north clearance `1.0668`
- south transition `1.8288`
- living clear width `4.4958`
- eye height `1.65`

The provisional categories are exactly these values in stable order:

- `cabinetry_detail`
- `hardware`
- `finishes`
- `furniture`
- `decor`
- `undimensioned_offsets`

The A-1 kitchen order represented by the contract must cover north sink wall `tower, dishwasher, sink, trash, tower`; west wall `upper_cabinets, range, upper_cabinets, refrigerator`; north glazing `kitchen_window_group, deck_door_group`; east/south transitions `mudroom_opening, tv_wall, south_living_opening`.

## TDD sequence

1. Write tests first. Name the production break each catches.
2. Run `uv run pytest tests/backend/test_tour_scene_contract.py -q` and record the expected missing-module/import failure.
3. Implement the smallest complete contract and independent validation.
4. Mutate each required dimension/object/order/provisional category and verify validation returns actionable errors. Allow no dimension drift greater than `0.003` meters.
5. Run `uv run pytest tests/backend/test_tour_scene_contract.py -q` and `uv run pytest tests/backend -q`.
6. README must label the spike unproven until geometry, realism, and navigation pass; include the future Blender command and generated output locations without claiming they already exist.
7. Self-review for test tautologies, duplicated unit conversion logic, mutable defaults, unstable serialization, and accidental edits outside the listed files.

Do not commit: the controller has ruled that this dedicated subtree cannot safely be committed onto Claude's active parent branch. Do not spawn subagents.

## Report

Write `.superpowers/sdd/2026-08-18-hearthview-tour-quality-spike/task-1-report.md` with: status (`DONE`, `DONE_WITH_CONCERNS`, `NEEDS_CONTEXT`, or `BLOCKED`), files changed, RED command/output summary, GREEN command/output summary, full-suite summary, self-review, and concerns. Return only status, a one-line test summary, and concerns.
