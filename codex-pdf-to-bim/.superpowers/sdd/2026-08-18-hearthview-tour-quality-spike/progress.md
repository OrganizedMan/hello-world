# SDD ledger — plan: docs/superpowers/plans/2026-08-18-hearthview-tour-quality-spike.md

Baseline: 94 backend tests passed, 1 skipped; 23 frontend tests passed.

Ruling: Use the existing user-requested `codex-pdf-to-bim/` isolation and a local ledger instead of a second linked worktree — the app is an untracked dedicated subtree under Claude's active parent branch, and relocating it would disconnect the user's running local server — if wrong, the cost is manual copying to a formal branch/worktree before integration.

Ruling: Track task file lists and verification evidence instead of task commits — committing this untracked subtree would mix Codex-owned work into Claude's active parent branch — if wrong, the cost is coarser Git history for the spike, while every change remains isolated and reviewable by path.

## Preflight interface scan

| Tasks | Producer / consumer | Finding |
|---|---|---|
| 1 → 2 | `SceneContract`, meter constants, manifest primitives → Blender builder and validator | Clean; Task 2 is forbidden from re-deriving printed dimensions. |
| 2 → 3 | GLB, manifest, walkable/collider/camera names → browser loader and controller | Clean; names and schema are explicit. |
| 3 → 4 | `/tour-spike` controls and observable modes → Playwright acceptance | Clean; acceptance uses real controls and does not inspect implementation text. |
| 1 | Tests versus contract/validation implementation | Clean; expected values are hand-derived literals and mutation cases are named. |
| 2 | Validator tests versus generated artifact | Clean; authoring can change internally while artifact behavior stays fixed. |
| 3 | Pure navigation tests and real route shell | Clean; Canvas is isolated only at the browser boundary, not asserted as a mock. |
| 4 | E2E and evidence package | Clean; gate may truthfully fail without being rewritten as success. |

Plan self-review: all approved geometry, visual, navigation, trust, accessibility, isolation, performance, and evidence requirements map to Tasks 1–4; placeholder scan clean; shared schema/function names are consistent.

Task 1: Ruling: A-1's 15′-11″ north-wall-to-south-transition dimension is authoritative for the spike envelope and resolves the counter-face clearance chain as 2′-2″ counter + 3′-6″ clear + 4′-3″ island + 6′-0″ clear — the original brief omitted this visible chain — if wrong, the scene's depth and counter offset would require one localized contract/model rebuild.

Task 1: review findings — Important: missing envelope crashes instead of returning an error; Important: mutation coverage does not remove individual named openings/colliders/cameras; controller-confirmed Important: west/north clearances are measured from the walls rather than the counter faces.

Task 1: fix round 1/5 (3 addressed, 0 open — invalid envelope guard; per-name mutation coverage; counter-face clearance/depth chain; staged file set reviewed and transferred).

Task 1: complete (39 focused tests pass in the authorized repo; scoped re-review clean).

Task 2A: split from Task 2 after the validator reached green and sandboxed Blender Metal startup blocked the scene build; Task 2B retains all authoring/artifact requirements.

Task 2A: review findings — Important: actual GLB geometry uses source→glTF Y-up conversion but validator/tests check Blender X/Y floor plane; Important: local sidecar image URIs are accepted despite self-contained GLB requirement; Important: manifest self-hash key is not rejected; Minor deferred to final review: add direct coverage for GLB-only absent-node/extras/data-URI branches.

Task 2A: fix round 1/5 (3 addressed, 0 open — Y-up X/negative-Z geometry; embedded-only images; exact non-self-hashing SHA keys).

Task 2A: complete (27 focused tests pass in authorized repo; scoped re-review clean; one Minor deferred).
