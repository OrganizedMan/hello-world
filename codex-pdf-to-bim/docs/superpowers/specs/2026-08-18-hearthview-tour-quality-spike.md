# HearthView Tour Quality Spike

**Status:** Approved proof of quality; deliberately isolated and not production architecture yet  
**Date:** 2026-08-18  
**Source:** Garrigan residence A-1 proposed first floor

## Outcome

Build one browser-native, person-scale tour of the proposed kitchen and family room that is good enough to judge three separate risks before expanding HearthView: geometric fidelity, warm residential realism, and comfortable real-time navigation.

The spike is successful only when the user can open a dedicated route, immediately orbit the room, click a valid floor location to move there, enter person-height walking/free-look, return to orbit or an overhead view without getting stuck, and inspect the full kitchen–living volume at interactive frame rates.

## Scope and trust

- The architectural envelope uses printed A-1 dimensions; the drawing explicitly says not to scale it.
- The modeled kitchen/living span is 30 feet 1 inch, north-wall-to-south-transition depth 15 feet 11 inches, ceiling height 8 feet 5 inches, island 8 feet 7 inches by 4 feet 3 inches, island-to-west-counter clearance 3 feet 6 inches, island-to-north-counter clearance 3 feet 6 inches, island-to-south transition 6 feet, and living-room clear width 14 feet 9 inches. The depth chain implies a 2-foot-2-inch counter zone before the north clearance.
- The north and west kitchen cabinet/appliance order, window group, deck doors, mudroom opening, south opening, TV location, and room transitions must agree with A-1.
- A-1 states final cabinetry will be designed by an interior designer and verified against cabinetmaker plans. Cabinet fronts, hardware, finishes, furniture, décor, and exact undimensioned offsets are therefore explicitly **visual staging**, never measured claims.
- This spike may use an authored high-detail display scene separate from the canonical Phase 0A GLB. It must say “quality spike · visual staging” and must not display the canonical geometry hash as proof of identity.
- Existing import, review, model, render, and report behavior must remain unchanged.

## Visual target

The scene should read as a plausible high-end residential visualization rather than a diagram: real-scale bevels and trim, detailed shaker cabinetry, appliances and fixtures, warm oak floor, honed pale stone, warm plaster, physically plausible glass and metal, a restrained warm-neutral furnishing layer, soft daylight, practical lights, contact shadows, AgX tone mapping, and no obvious primitive stand-ins in the hero kitchen view.

All bundled external assets must be CC0 and recorded in a provenance manifest. Poly Haven and ambientCG are acceptable sources. Source packages remain authoring inputs; the browser ships only optimized assets needed by the spike.

## Navigation target

- Orbit is the default and always available.
- “Move here” lets the user select only a walkable floor; walls and furniture cannot be teleport targets.
- Walk mode uses a 1.65 m eye height, WASD/arrow movement relative to view direction, pointer or drag look, and collision against the spike’s authored boundaries.
- Escape and a visible “Exit walk” control return to orbit.
- Overhead exits walk and frames the full scene.
- A reset control returns to a useful kitchen overview.
- Controls are visibly labeled, have explanatory tooltips, keyboard focus, and short plain-language instructions.
- Touch users can orbit and click-to-move even when pointer-lock walking is unavailable.

## Acceptance gates

1. **Geometry:** a machine-readable manifest contains the printed dimensions above in meters and names every provisional category; a Blender-side validation script rejects missing envelope, cabinet order, openings, walkable floor, or dimension drift over 3 mm.
2. **Realism:** a 1920 × 1080 Eevee/Cycles validation poster and the interactive scene show the same authored layout with no missing textures, black materials, visible light leaks, z-fighting, or clipped hero camera.
3. **Navigation:** unit tests cover floor-only placement, blocking, sliding, walkable-boundary rejection, and mode escape; a headed browser check demonstrates orbit, move-here, walk/look, overhead, and reset.
4. **Performance:** optimized browser payload target is 45 MB or less, initial scene becomes usable within 10 seconds on the homeowner’s local Mac, and the tour remains visibly interactive at desktop resolution.

Failure of any gate is a useful spike result. The work stays labeled experimental until all three gates pass and the user has seen the example output.
