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
| `/tour` | `apps/web/public/tour-building/` | The house. This is the live path. |
| `/tour-spike` | `apps/web/public/tour-spike/` | The old kitchen spike, kept only for comparison. |
| `/tour/first-floor` | `apps/web/public/tour-a1/` | The whole traced first floor, plain massing. |
| `/tour/building` | `apps/web/public/tour-building/` | All four drawn storeys, one node each, with a floor switcher. |

The whole floor needs no Blender -- `a1_tour` writes the GLB itself -- so one
command builds and measures it anywhere the drawings are:

```bash
uv run python scripts/build_a1_tour.py      # first floor
uv run python scripts/build_a1_building.py  # every drawn storey
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
- **Stair extraction does not survive the other sheets.** Treads are found per
  sheet with no check that they stack, and they do not:

  | sheet | stair east position | treads | printed rise |
  | --- | --- | --- | --- |
  | A-0 | — | 0 | note present |
  | A-1 | 16.9 – 19.8 ft | 6 | yes |
  | A-2 | — | 0 | no |
  | A-3 | 27.3 – 32.8 ft | 10 | no |

  A-3's run sits about ten feet east of A-1's and extends a foot past its own
  footprint, and A-2 has no stair at all, so the model offers no way between
  storeys. Flights in a house stack; nothing checks that, which is why this
  shipped looking fine. Whatever A-3's treads are, they are probably not its
  stair.
- ~~**Multi-floor vertical alignment is untested.**~~ Checked. On one datum the
  basement's east and west walls land on the first floor's to 0.02 ft, A-2's
  north edge to 0.01 ft, and A-3's east and west edges match A-2's exactly.
  What remains assumed is *vertical*: the floor assembly between one ceiling and
  the next floor is in no sheet, so `ASSUMED_FLOOR_ASSEMBLY_INCHES` is a
  convention and every storey above the first inherits its error.
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

1. ~~**The rest of the house.**~~ Done: `/tour/building` serves all four drawn
   storeys, 528 primitives, every one of 4,224 traced corners present in the
   export.
2. ~~**Overhead view must drop the ceiling.**~~ Done. Ceilings are their own
   glTF nodes now, because a material cannot be hidden per-face in three.js, and
   they are switched off overhead and whenever a single floor is chosen. Walking
   keeps them.
3. ~~**A floor switcher in the browser UI.**~~ Done, alongside the storeys it
   switches between — and the camera reframes onto the floor you pick, which is
   what made the switcher feel broken even once it worked.
4. **Photorealism**, deliberately after the layout is right — materials,
   lighting and finishes on geometry that is already known to match the drawing.
   In progress; see §10.

---

## 9. The kitchen is not a special case

It was one for a long time: `a1_kitchen_scene.py` scoped a region with six
hand-picked PDF coordinates and `build_scene.py` built it with named stations
for the sink, the range and the island. Nothing else in the house had any of
that, so the kitchen looked finished and every other room looked like massing.

The unified path has no room-specific geometry in it at all. The trace already
places counters and fixtures wherever the drawing draws them -- six runs in the
kitchen, four in the two bathrooms, three in circulation, two in the mudroom --
so `building_look.py` builds carcass, doors and worktop from *any* run, and the
room only decides the worktop material. A kitchen is a room with more counter
in it.

Facing is derived rather than named: the vector from a run to its room's
centroid points into the room, so the wall is the other way. That works on any
wall of any storey without a station convention.

`spikes/tour_quality/build_scene.py` still exists and still builds the old
kitchen. It is the comparison, not the product.

Still deferred: the stock-furniture placement UI, and the levels above the
first.

---

## 10. Photorealism has to survive glTF

Two hard limits shape the whole look pass.

**Procedural materials do not export.** glTF has no node graphs, so a Blender
material built from noise and gradients arrives in the browser as 0 images and
0 textures — a flat colour. Photographed maps do arrive. That inverts the
usual advice: the texture library is the *easy* path here and the procedural
one is impossible, not the other way round.

**A real-time renderer has no bounce light.** Cycles knows an inside corner is
darker than an open wall; three.js applies the environment evenly to every
surface, so an interior lit only by an environment map reads as flat paper
whatever the materials are. This is most of the gap between the Cycles stills
and the browser, and no amount of material work closes it.

What does close it is `occlusionTexture`, the one place in the glTF core where
baked lighting has somewhere to go: it dims the ambient term only, which is
exactly the term that is wrong. `bake_occlusion()` in `building_look.py` bakes
Cycles ambient occlusion into a single shared atlas for the whole house and
wires it through the exporter's `glTF Material Output` group, which is the only
node setup the exporter recognises for occlusion.

Two things about that bake are load-bearing:

- **The bake needs its own UV set.** The render UVs are a cube projection
  scaled by real size, so oak keeps the same plank width in a cupboard as in a
  living room; they tile, and a tiling UV folds an atlas over itself.
- **Islands, not faces.** `uv.lightmap_pack` gives every face its own island.
  The floors are subdivided into thousands of faces to carry per-room finishes,
  so that produced a fourteen-thousand-island atlas and the walls came back as
  triangular smears. `uv.smart_project` merges connected coplanar faces, which
  is one island per wall face and one per floor.

The browser side matters too, and had been fighting it: the environment was
loaded at 0.3 strength and hidden behind a flat page colour, so the sky was
neither the outdoor view through the windows nor the light in the room.

### What fills the openings

The trace cuts every door, window and cased opening as a void: the wall run is
split around it and a sill and a lintel are built back in. Nothing stands *in*
the void, and an empty rectangle never reads as a window however well it is
lit. So the void travels with the artifact -- `manifest["openings"]`, recovered
from the sill and lintel solids rather than re-read from the sheet, because
reading the sheet twice is how two frames drift apart -- and the look pass
lines it with a head, two jambs and, for a window, a sill board and glass.

Glass is a blended surface, not transmission. Real transmission exports as
`KHR_materials_transmission` and forces the browser into a separate render pass
for each of the thirty-six windows; a nearly transparent, very smooth surface
picks the sky up out of the environment map and costs nothing. It is also
hidden from the occlusion bake, which would otherwise treat a pane of glass as
a wall and darken the room the window was cut to light.

Door leaves are deliberately absent. A walkable tour whose doors are shut is a
tour of one room.

### Baked lighting, not baked occlusion

Occlusion was the timid version. It dims the ambient term, which fixes flat
corners and leaves the room lit by a uniform sky -- so it reads as a good
model, not as a photograph. `--bake light` bakes the diffuse irradiance
itself: sun, sky, and every bounce between them, which is the Cycles solution
for this house at this time of day.

Three details make it work at all.

**It travels as `emissiveTexture`.** glTF core has no lightmap slot. Occlusion
looks like the obvious carrier and is not: the exporter packs it into the red
channel of an ORM texture alongside roughness and metallic, which shreds a
colour lightmap. Emissive is the one RGB texture in the core spec that keeps a
UV set of its own. The browser promotes it back to a three.js `lightMap` on
load; left as emissive it would glow flatly instead of lighting the surface.

**Direct and indirect, but not colour.** `use_pass_color` stays off. The albedo
is already in the base colour map, and multiplying it in twice turns oak into
mud.

**Sunlight is not bounded by one.** The bake is linear and goes well past 1.0
in a sunlit patch, so the atlas is normalised to fit an 8-bit image and the
divisor rides in the manifest as `artifact.lightmap.scale`. The browser
multiplies it back through `lightMapIntensity`. Clamping instead would flatten
every lit surface to the same white, which is exactly the look the bake exists
to replace.

A baked model also has to stop being lit twice: the directional sun is not
rendered at all, and the environment drops to a fraction of its strength --
just enough for the specular reflection in a worktop or a pane of glass. What
it is *not* is a substitute for a real-time renderer that could do this itself.
Nothing in the bake moves. The sun is at the hour it was baked at, forever.
