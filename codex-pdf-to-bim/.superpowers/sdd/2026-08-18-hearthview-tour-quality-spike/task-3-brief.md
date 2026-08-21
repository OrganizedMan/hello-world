# Task 3 — Homeowner hybrid tour controller

## Context

Task 2 supplies `/tour-spike/hearthview-kitchen-family.glb`, `/tour-spike/manifest.json`, `/tour-spike/poster.webp`, and `/tour-spike/environment.hdr`. This task adds a dedicated `/tour-spike` browser experience. It is intentionally separate from the existing `ModelViewer.tsx`, project workflow, backend, and canonical identity UI.

The worker cannot write the user-authorized repo directly. Stage all relative outputs under:

`/Users/jackgarrigan/Documents/Codex/2026-08-18/bui/work/task-3-staging`

Read existing app conventions and Task 2 public artifacts from:

`/Users/jackgarrigan/Developer/hello-world/codex-pdf-to-bim`

The controller will mechanically transfer reviewed staged files.

## Binding global constraints

- Route is exactly `/tour-spike`; existing routes and `apps/web/src/features/model/ModelViewer.tsx` remain unchanged.
- Display persistent text `Quality spike · visual staging` and plainly explain that cabinetry detail, hardware, finishes, furniture, décor, and undimensioned offsets are provisional; never display a canonical geometry hash for this scene.
- Orbit is the default and always recoverable.
- “Move here” accepts only the authored walkable floor and never a wall/furniture/barrier.
- Walk uses a `1.65 m` eye height, a `0.30 m` body radius, `1.8 m/s` speed, WASD and arrow keys relative to the view direction, pointer-lock look when supported, and drag-look fallback.
- Escape/unlock and a visible “Exit walk” return to Orbit. Overhead and Reset also exit walking; no camera state may trap the user.
- Touch users can orbit and use click-to-move even without pointer lock.
- Every control has a visible persistent label plus plain-language tooltip/help text, keyboard focus, disabled explanation where relevant, and mode changes announced via an ARIA live region.
- Browser reads runtime bounds/barriers/cameras from the Task 2 manifest; do not duplicate architectural measurements in TypeScript.
- Scene remains local/offline: GLB, HDR, poster, and manifest paths are relative local URLs; no remote decoder/environment/CDN.
- Use existing Three/Fiber/Drei dependencies only. Do not add Rapier, ecctrl, bvhecctrl, or a direct three-mesh-bvh dependency for this rectangular spike.
- Tests assert observable behavior with hand-derived literals and do not inspect source text or assert a mock exists.

## Files

Stage:

- `apps/web/src/features/tour/tourNavigation.ts` — pure placement/movement/coordinate functions.
- `apps/web/src/features/tour/tourNavigation.test.ts` — pure behavior tests.
- `apps/web/src/features/tour/TourViewer.tsx` — Canvas, GLB/environment, lighting, mode controller, placement/walk/orbit/overhead/reset, error/loading boundaries.
- `apps/web/src/features/tour/TourPage.tsx` — manifest fetch, polished labeled homeowner shell, help, trust/performance UI.
- `apps/web/src/features/tour/TourPage.test.tsx` — page/control/error/a11y tests, with WebGL isolated only at the `TourViewer` boundary.
- `apps/web/src/app/App.tsx` — lazy `/tour-spike` route only.
- `apps/web/src/styles.css` — all styles scoped under `.tour-page` / `.tour-*`.

Write report:

`/Users/jackgarrigan/Documents/Codex/2026-08-18/bui/work/task-3-staging/task-3-report.md`

Do not commit and do not spawn subagents.

## Manifest types

Define and validate the minimum runtime structure at the page boundary without introducing a package dependency:

```ts
export type TourPoint = { x: number; z: number };
export type TourBounds = { min_x: number; max_x: number; min_z: number; max_z: number };
export type TourBarrier = TourBounds & { name: string };
export type TourCameraPreset = {
  name: "kitchen_overview" | "walk_start" | "overhead";
  position: [number, number, number];
  target: [number, number, number];
};
export type TourManifest = {
  schema: "hearthview-tour-spike/v1";
  label: "Quality spike · visual staging";
  canonical_geometry: false;
  provisional_categories: string[];
  runtime: {
    coordinate_rule: "three_x=source_x;three_y=source_z;three_z=-source_y";
    eye_height_meters: number;
    walkable: TourBounds;
    barriers: TourBarrier[];
    camera_presets: TourCameraPreset[];
  };
  artifact: {
    glb: string;
    poster: string;
    environment: string;
    total_browser_bytes: number;
  };
};
```

`parseTourManifest(value: unknown): TourManifest` must reject malformed/missing schema, wrong label, canonical true, missing runtime, non-finite numbers, eye height other than `1.65 ± 0.003`, missing camera presets, remote/root-escaping artifact paths, or payload over `45_000_000`. Its errors are caught by `TourPage` and shown with Retry and poster fallback; no blank canvas.

## Pure navigation interfaces

```ts
export const WALK_EYE_HEIGHT_METERS = 1.65;
export const WALK_RADIUS_METERS = 0.30;
export const WALK_SPEED_METERS_PER_SECOND = 1.8;

export function isWalkablePlacement(
  point: TourPoint,
  walkable: TourBounds,
  barriers: readonly TourBarrier[],
  radius?: number,
): boolean;

export function resolveMovement(
  position: TourPoint,
  delta: TourPoint,
  walkable: TourBounds,
  barriers: readonly TourBarrier[],
  radius?: number,
): TourPoint;

export function movementFromKeys(
  forward: TourPoint,
  pressed: ReadonlySet<string>,
  elapsedSeconds: number,
  speed?: number,
): TourPoint;
```

`isWalkablePlacement` keeps the complete radius inside bounds and outside each rectangle expanded by radius. Boundary contact is blocked. `resolveMovement` first tries both axes, then X only, then Z only, producing tangential sliding rather than tunneling. Reject a delta whose magnitude exceeds `speed * elapsed` only at the caller; pure resolver accepts a supplied delta. `movementFromKeys` projects/normalizes forward in XZ, derives a perpendicular right vector, combines W/ArrowUp, S/ArrowDown, A/ArrowLeft, D/ArrowRight, normalizes diagonals, clamps elapsed to `0.05`, and returns a literal zero for no/contradictory keys.

## RED tests

Write tests before implementation. At minimum:

- placement accepts a center point and rejects each edge at 0.30 m, expanded island/barrier contact, inside-barrier, and NaN;
- movement passes through open space;
- movement cannot cross a barrier or walkable boundary;
- diagonal collision slides on X when Z is blocked and on Z when X is blocked;
- movement cannot tunnel through a barrier with one large delta;
- forward and strafe vectors are view-relative; diagonal is normalized; opposite keys cancel; elapsed is clamped; output at 1 second/clamped 0.05 and 1.8 m/s is hand-derived `0.09 m`;
- parser accepts one complete literal manifest and rejects every malformed/trust/remote/oversize branch named above.

Run from the existing frontend workspace with the staged files temporarily copied or with a temporary staged tsconfig only if necessary. Record a real missing-module/function failure. Do not weaken Vitest discovery or tests to make staging convenient.

For `TourPage.test.tsx`, mock only `./TourViewer` because jsdom has no WebGL. Do not assert on the mock. Assert the real page's persistent labels/help/trust/status/fallback/retry behavior and that manifest validation occurs before the viewer boundary. Mock `fetch` with a complete real-shape response.

Required observable copy/roles:

- Heading: `Walk through your proposed kitchen`
- Badge: `Quality spike · visual staging`
- Buttons with accessible names: `Orbit`, `Move here`, `Walk`, `Overhead`, `Reset view`, and conditional `Exit walk`
- Plain control help includes `Drag to look`, `WASD or arrow keys`, `Click a clear floor spot`, and `Escape exits walking`
- Trust panel visible label `What is measured` naming room/island/clearance facts from manifest display fields where present, and `What is staged` naming the six provisional categories in homeowner language.
- Local note: `Runs locally after this tour is prepared.`
- Loading status and recoverable `Tour could not be opened` alert with `Try again`.

## Viewer implementation

### Canvas and scene

- Load GLB with `useGLTF('/tour-spike/' + manifest.artifact.glb)` and HDR using Drei `Environment` with the equivalent local path. Reject a path that did not pass `parseTourManifest`.
- Clone the scene once. Preserve exported normals/materials. Set cast/receive shadows; do not recompute existing normals or replace PBR materials.
- Hide `HV_COLLIDER_*` and any navigation helpers visually; keep `HV_WALKABLE` raycastable but render it fully transparent (`colorWrite=false`, `depthWrite=false`) without preventing pointer events.
- Toggle `HV_CEILING` invisible in orbit/placing/overhead and visible in walk so the room is readable from above but person-height lighting remains believable.
- Canvas: shadows, `dpr={[1, 1.75]}`, `gl` with antialias, high-performance, `AgXToneMapping`, `SRGBColorSpace`, physically correct modern defaults; use local Environment, one restrained hemisphere/ambient fill, window directional light and warm practical points only as needed to match the poster. Use `AdaptiveDpr` or `PerformanceMonitor` without visibly pixelating the settled view.
- Add a scene-level error boundary with poster fallback and `onError` callback. Suspense/`useProgress` yields a visible DOM loading overlay with percentage.

### Modes

Define `TourMode = "orbit" | "placing" | "walk" | "overhead"` and expose current mode to the page via callback.

- Orbit default: `OrbitControls`, useful authored kitchen preset, damping, sensible min/max distance, max polar angle below the floor, pan enabled so the camera can be freely repositioned.
- Move here: page sets `placing`; pointer becomes crosshair; controls pause; next click walks the event ancestry and accepts only object `HV_WALKABLE`; validate the Three X/Z hit against runtime bounds/barriers, position camera at `(x, 1.65, z)`, keep a level forward direction, announce success, and switch back to Orbit at that position. Wall/furniture clicks announce `Choose a clear spot on the floor` and remain in placing.
- Walk: if no prior placement, use `walk_start`; set exact eye height; request pointer lock only from the user button/canvas gesture when supported; register key state with cleanup; `useFrame` gets camera forward, calls `movementFromKeys`, then `resolveMovement`; never change eye height. Drag-look fallback updates yaw/pitch with pitch clamp when pointer lock is unavailable; touch keeps orbit/click-to-move available and shows a calm note instead of failing.
- Escape, pointer-lock unlock, and visible Exit walk call one idempotent return-to-orbit transition and clear pressed keys.
- Overhead: exit pointer lock/walk, apply authored overhead position/target, enable orbit, preserve scene load and selected position marker.
- Reset: exit pointer lock/walk, clear placement marker, apply authored kitchen overview and target.

### UI and homeowner ergonomics

- Tour route uses a large stage, compact responsive control dock, visible mode chip, short instructions, a small top-down orientation diagram using manifest bounds/barriers (SVG or DOM, not a decorative screenshot), and a placed-camera marker if available.
- Use existing `HelpTooltip` where it fits. Every button also has a concise `title`; the label itself stays visible.
- Walk button is disabled with visible reason while the scene is loading/error. Move-here remains the obvious touch-friendly alternative.
- Use no unexplained `orbit`, `pointer lock`, collider, glTF, or BIM jargon in explanatory copy. The button may be named Orbit because the user approved it, but tooltip says `Rotate around the room from the outside, then pan or zoom to reframe.`

## Verification

Run:

```sh
npm --workspace apps/web test -- --run
npm run build
```

The staging setup may require the controller to transfer files before the full build; if so, run focused pure tests in staging and state exactly what remains for controller verification. Report RED/GREEN evidence, exact frontend test counts, build result/warnings, manual code-level mutation check, and self-review for: existing viewer untouched, no remote resources, cleanup of listeners/pointer lock, exact eye height, collision slide/tunneling, ceiling mode, accessible labels/tooltips, load/error recovery, and responsive CSS.

Return only status (`DONE`, `DONE_WITH_CONCERNS`, `NEEDS_CONTEXT`, or `BLOCKED`), one-line test/build summary, and concerns.
