# The traced tour pipeline

Read this first if you are picking the walkable-tour work up cold. It is the
contract the A-1 → Blender → browser path runs on, and the reasoning behind the
parts that look unusual.

Everything below concerns the **traced** path (`--spec`). The older hand-built
spike path still exists for comparison and is called out where it differs.

---

## 1. The coordinate frame is the contract

There is exactly one plan frame, established by `hearthview.a1_kitchen_scene`:

| axis | meaning | origin |
| --- | --- | --- |
| `+x` | metres **east** | interior face of the west wall |
| `+y` | metres **north** | interior face of the kitchen arm's south wall |
| `+z` | metres up | finished floor |

`(east, north, up)` is **right-handed**: east × north = up. Blender exports it
Y-up as `(x, y, z) → (x, z, -y)`, so in the glTF artifact **+x is east and −z is
north**. The spec carries this in its own `frame` block, and
`services/hearthview/chirality.py` is the single place that owns the conversion
and the handedness test.

**There is no mirror anywhere in this pipeline, and adding one is a bug.**

The reason this is written down so emphatically: the scene was authored
`(east, south, up)` for a long time. That triple is left-handed, so the exported
model came out as a reflection of the drawing — the sink on the wrong side of the
island, the range on the wrong wall. A mirror pass was added to undo it, then the
mirror only covered some of the geometry, and the scene shipped half-reflected
twice. Flipping `_my` to north-positive deleted the mirror pass and both classes
of bug with it.

### Consequences worth knowing

- `_my(pdf_y)` reverses the order of PDF coordinates, so anything derived from a
  PDF y-range must be `sorted()` before being treated as `(min, max)`.
- Wall runs on vertical boundaries run north-to-south in PDF order and
  south-to-north in plan order.
- The browser minimap reads `orientation.north_vector` and picks its projection
  from it, so a future frame change cannot silently mirror the map.

---

## 2. Walls are placed by rotation, never by reflection

Every cabinetry and appliance builder in `spikes/tour_quality/build_scene.py`
works in **one canonical local frame**:

> wall at local `y = 0`, room toward local `+y`, run along local `+x`

Each run in the spec emits a `station`: an `anchor` point and a `rotation_deg`
about the vertical axis. `_station()` creates an empty at the anchor with that
rotation, and the run's geometry is parented to it. Blender applies the
transform; the builder never sees world coordinates and never learns which wall
it is on.

```
north run: anchor [span, arm_north], rotation 180°   → run heads west
west  run: anchor [0.0,  arm_north], rotation -90°   → run heads south
```

Positions inside a run are given as `run_start` — distance from the anchor along
local `+x` — with `center_x` / `center_y` kept alongside for tests and collision.

**Every wall orientation on a plan is reachable from that canonical frame by a
rotation alone.** If a placement seems to need a reflection, the builder's local
frame disagrees with the canonical one; fix the builder, not the transform. That
is exactly what went wrong before: the north-run builders used "run along x" and
the west-run builders used "run along y", which are opposite handedness, so the
west wall genuinely could not be reached by rotation and a mirror was bolted on.

This generalises to the rest of the first floor and the other three levels
without change — a run on any wall is a station, and floors stack in `z`.

---

## 3. Measure the artifact, not the spec

The pipeline's three worst bugs all shipped green, because every check compared
the spec against itself inside one frame. The rule now:

**A check that never opens the exported GLB proves nothing about the model.**

Two things enforce it:

- `scripts/measure_glb.py <glb> --spec <spec.json>` loads the GLB with trimesh,
  reports every landmark's real world-space position, and diffs it against where
  the trace says it belongs. It also runs the handedness test. `--spec` is wired
  into the checkpoint script for traced builds.
- `tests/backend/test_traced_scene_build.py` stubs `bpy` and drives the real
  builders. Its `_world_boxes()` helper resolves each recorded box through its
  chain of parent empties, so assertions are about **world** position. Asserting
  local coordinates is what let a run land on the wrong wall while matching the
  spec exactly.

- `tests/backend/test_committed_tour_artifact.py` runs that same measurement
  against the GLB **committed under `apps/web/public/tour-spike/`**, so the
  artifact the browser is actually served is checked on every `pytest` run
  rather than only by hand after a build. Building a GLB needs Blender; reading
  one needs only trimesh, so this runs everywhere the rest of the suite does.

`tests/backend/test_measure_glb_expectations.py` pins that the expected
positions are derived from the spec rather than written down, so they follow the
drawing when it changes.

The gap that guard closes was real: `measure_glb.py` only ever ran by hand, on a
Mac, straight after a Blender build, so nothing compared the *committed*
artifacts to the *committed* spec. See §5.

None of the checks above runs Blender, so none of them exercises the build.
`spikes/tour_quality/validate_artifact.py` does, from inside it — and its
expectations can go stale like any others. A correct traced build was once
rejected outright because the `HV_FLOOR` check still assumed the single
rectangle of the old spike, while the traced plan is L-shaped and its MAIN slab
starts north of the origin. **When the validator rejects a build, establish
whether the geometry or the expectation is wrong before touching the builder**;
the shape of the failure usually says which. There, span and depth both passed
and only the north offset disagreed, which is a moved goalpost, not bad
geometry.

---

## 4. Where things live

| path | role |
| --- | --- |
| `services/hearthview/a1_extract.py` | PDF → classified vectors. Legend-driven colours, 18.0 pt per foot, openings recovered as gaps between wall subpaths. |
| `services/hearthview/a1_kitchen_scene.py` | Extraction → Blender build plan (`a1_kitchen_scene_spec.json`). Owns the frame. |
| `services/hearthview/chirality.py` | The one definition of "is this model a mirror of the drawing". |
| `spikes/tour_quality/build_scene.py` | Runs inside Blender. `--spec` selects the traced path; without it, the legacy spike. |
| `spikes/tour_quality/scene_contract.py` | Spec → `hearthview-tour/v2` browser manifest. |
| `spikes/tour_quality/validate_artifact.py` | Contract and payload gates on the built GLB. |
| `scripts/kitchen_family_checkpoint.py` | One command: build → validate → measure (→ optional stills). |
| `scripts/measure_glb.py` | Artifact-versus-trace diff for the kitchen GLB, landmark by landmark. |
| `scripts/build_a1_tour.py` | Whole first floor: extract, build, measure. No Blender. |
| `scripts/measure_a1_tour.py` | Artifact-versus-trace diff for the whole-floor GLB, every primitive corner. |
| `apps/web/src/features/tour/` | Runtime. `tourManifest.ts` is a discriminated union on `schema`: v1 spike, v2 traced. |

---

## 5. What is *not* in the repo

Two things a fresh session cannot get from a clone:

1. **The tour-quality asset directory** (32 hash-pinned files listed in
   `spikes/tour_quality/assets/provenance.json`). Only `provenance.json` and
   `LICENSES.md` are tracked; the HDR, models and textures are not.
2. **Blender.** Required to build the GLB, and nothing else in the pipeline.

The **drawing set is committed** under `drawings/`, so nothing needs supplying
out of band any more. `hearthview.drawings.a1_source()` resolves it, and
`HEARTHVIEW_A1_PDF` still overrides when you want a different revision.

The built artifacts under `apps/web/public/tour-spike/` **are** committed, and
they are current: the GLB matches the trace exactly, and `manifest.json` is
`hearthview-tour/v2` with `canonical_geometry: true`.

That is checked rather than remembered.
`tests/backend/test_committed_tour_artifact.py` measures the committed GLB
against the committed spec on every `pytest` run, and CI runs it on every push.
Reading a GLB needs only trimesh; only building one needs Blender.

```
$ uv run python scripts/measure_glb.py \
      apps/web/public/tour-spike/hearthview-kitchen-family.glb \
      --spec spikes/tour_quality/a1_kitchen_scene_spec.json

  drawing turn   +73.64   model turn    +5.10
  => MATCHES the drawing
  from the TV wall across the island, the sink is on the RIGHT (A-1 says RIGHT)
  => worst offset 0.00 m (within the 0.15 m tolerance)
```

The offsets are zero rather than merely small because the builder and the
measurement both derive from the same spec. Any nonzero number here is real
drift, not rounding.

They were not always current, which is why that guard exists. The artifacts once
sat nine commits behind the spec — still `hearthview-tour-spike/v1` from the
legacy hand-built spike, mirrored, worst landmark 5.90 m out — while every suite
stayed green, because nothing opened the GLB. **Rebuild (§6) after any change
that moves geometry, and commit the result**; the guard fails the suite if you
forget.

## 6. Running it

The drawing set is committed, so the whole suite runs from a clean clone with
nothing exported. To work against a different revision of the drawings:

```bash
export HEARTHVIEW_A1_PDF=/absolute/path/to/other-set.pdf
```

Regenerate the spec after any extractor or frame change:

```bash
uv run python -m hearthview.a1_kitchen_scene "$HEARTHVIEW_A1_PDF" \
    spikes/tour_quality/a1_kitchen_scene_spec.json
```

Full suites:

```bash
uv run pytest tests/backend -q
npm --workspace apps/web test -- --run
npx tsc -p apps/web --noEmit
```

Build the walkable tour (needs Blender; Mac paths):

```bash
uv run python scripts/kitchen_family_checkpoint.py \
    --assets /Users/jackgarrigan/Documents/Codex/2026-08-18/bui/work/tour-quality-assets
```

That writes the GLB, manifest, poster and environment into
`apps/web/public/tour-spike/`, then validates and measures them. Add `--stills`
only when you specifically want the Cycles validation images — they render from
a separate camera path and are not the deliverable. Then:

```bash
npm --workspace apps/web run dev -- --port 5178 --host 0.0.0.0
```

`--host 0.0.0.0` is required to reach the tour from a phone on the same network.

Two tours are served, from separate folders so that neither can overwrite the
other's `manifest.json`:

| route | folder | what it is |
| --- | --- | --- |
| `/tour-spike` | `apps/web/public/tour-spike/` | Kitchen and family room, built in Blender against the quality assets. |
| `/tour/first-floor` | `apps/web/public/tour-a1/` | The whole traced first floor, plain massing. |

The whole floor needs no Blender -- `a1_tour` writes the GLB itself -- so one
command builds and measures it anywhere the drawings are:

```bash
uv run python scripts/build_a1_tour.py
```

---

## 7. What is still unverified

State these plainly rather than implying the model is finished:

- **Opening heights are still assumed, but the set is not section-free.** Every
  window sill, window head and door head height is a convention, declared as
  `assumed` in the spec's provenance and surfaced in the browser. The A-3 OP#B
  sheet in `drawings/Garrigan-261-Grove-Street-attic-idea.pdf` carries a
  **Building Section**, which nothing reads yet. Whether it yields real heights
  for the floors below is unknown and worth finding out before assuming more.
- **Opening classification is approximate.** Window-versus-door-versus-cased
  typing is inferred from drawn symbols and position; roughly 24 openings across
  the full floor are typed "cased" with low confidence.
- **~25 diagonal bay segments are approximated** as straight runs.
- **Multi-floor vertical alignment is untested.** Nothing has yet checked that
  floor 2's walls land over floor 1's. All four levels *are* drawn -- A-0
  basement, A-1 first, A-2 second, A-3 third/attic -- so this is now a question
  of doing the work, not of missing source data.
- **Scope is the kitchen/family checkpoint region only** — the main kitchen and
  living rectangle plus the west kitchen arm. The region was approved on
  2026-08-22, so whole-floor generalisation is now in scope; see §8.
- **The whole-floor path is outside the contract that fixed the kitchen.**
  `a1_massing.py` and `a1_tour.py` build the whole traced first floor, but were
  last touched at `ed8ec06`, before all three frame fixes. Nothing in them
  imports `chirality` and nothing measures the GLB they write. Their 14 tests
  now run everywhere, since the drawings are committed, but passing those tests
  says nothing about handedness: that is exactly what the kitchen's suite did
  while shipping a mirror.

---

## 8. Agreed next, in order

1. ~~**The rest of the first floor.**~~ Done: `/tour/first-floor` serves the
   whole traced floor, its mapping is verified right-handed, and all 1,696
   traced corners are present in the export. The levels above it are next --
   A-2 and A-3 are drawn and nothing reads them yet.
2. **Overhead view must drop the ceiling.** It currently reads as a solid shape
   the size of the footprint rather than an open dolls'-house view down onto the
   plan.
3. **A floor switcher in the browser UI**, needed before more than one level is
   worth building.
4. **Photorealism**, deliberately after the layout is right — materials,
   lighting and finishes on geometry that is already known to match the drawing.

Still deferred: the stock-furniture placement UI, and the levels above the
first.
