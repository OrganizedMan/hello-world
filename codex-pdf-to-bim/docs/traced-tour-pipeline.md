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
| `services/hearthview/a1_massing.py` | Classified vectors → solids: walls, slabs, sills, lintels, stairs, counters. One storey. |
| `services/hearthview/a1_building.py` | Four sheets → one building on one datum. Owns the storey elevations. |
| `services/hearthview/a1_rooms.py` | Label-seeded flood fill. Which room is a point in, and how big is it. |
| `services/hearthview/a1_tour.py` | Building → GLB and `hearthview-tour/v2` manifest, a node per storey. No Blender. |
| `scripts/build_a1_building.py` | Every drawn storey: extract, build, measure. No Blender. |
| `spikes/tour_quality/building_look.py` | The look pass. Materials, casework, joinery, furniture, and the Cycles bake. Needs Blender. |
| `spikes/tour_quality/bakes/` | Baked lightmap atlases, kept so grading can be re-run without re-baking. |
| `scripts/check_export.py` | Opens the GLB and checks what fails silently: did a grade survive, is the atlas empty. |
| `scripts/tour_snapshot.mjs` | Photographs the tour in a real browser and fails on a console error or a dead control. |
| `apps/web/src/features/tour/` | Runtime. `tourManifest.ts` is a discriminated union on `schema`: v1 spike, v2 traced. |
| `apps/web/src/features/tour/tourFraming.ts` | Camera framing, storey and ceiling visibility, exposure metering, floor hit-testing. |

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

### The look pass

Those two write the *canvas*: correct geometry, no materials. `building_look.py`
turns it into the thing people look at, and needs Blender:

```bash
python spikes/tour_quality/building_look.py \
    --canvas apps/web/public/tour-building/a1-building.glb \
    --hdri apps/web/public/tour-building/environment.hdr \
    --rooms --casework --openings --tile 1.0 \
    --furniture spikes/tour_quality/assets/files \
    --sun 6.0 --sky 5.0 \
    --bake light --bake-size 2048 --bake-samples 64 \
    --atlas spikes/tour_quality/bakes/a1-building-2048-lightmap.png \
    --out apps/web/public/tour-building/a1-building-look.glb
```

**The bake is the long pole and everything after it is seconds.** About
twenty-six minutes on four cores at these settings. Anything downstream of it --
a paint colour, a tone curve, an export option -- reuses the atlas instead:

```bash
    --bake light --bake-size 2048 \
    --reuse-lightmap spikes/tour_quality/bakes/a1-building-2048-lightmap.png \
    --reuse-scale 2.9503
```

Forty seconds. Reuse assumes the geometry has not changed, because the unwrap
is deterministic only for a given build. Change the massing and you owe a bake.

**`--out` rewrites the manifest, and it does it last.** `build_a1_building.py`
points the manifest back at the plain canvas, and the look pass points it at the
finished model when it finishes. Committing between the two ships untextured,
unlit massing that loads perfectly and looks like nothing. Check before you
commit:

```bash
uv run python scripts/check_export.py \
    apps/web/public/tour-building/a1-building-look.glb \
    --min-coverage 0.30 --albedo "HV_LOOK_PLASTER_TEX=220,213,209"
node scripts/tour_snapshot.mjs http://localhost:5173/tour ./tour-snapshots
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
- ~~**Stair extraction does not survive the other sheets.**~~ Fixed; see §11.
  Every storey now has a flight, all four stack over each other in plan, and
  three tests hold that: one per storey, one that the footprints overlap, one
  that a flight climbs its own storey and stops at the ceiling. What is still
  assumed is how far each flight runs — a plan cuts the stair where the floor
  above crosses it, so the treads past the drawn ones are declared `assumed`.
- **The last riser is missing by design.** A flight stops at its own printed
  ceiling, which leaves roughly a foot to the floor above. That gap is the floor
  assembly, which no sheet in this set dimensions.
- **A stair has no stringer, soffit or handrail.** The flight is a stack of
  treads, so from the side it reads as a solid mass rather than as joinery.
- ~~**Multi-floor vertical alignment is untested.**~~ Checked. On one datum the
  basement's east and west walls land on the first floor's to 0.02 ft, A-2's
  north edge to 0.01 ft, and A-3's east and west edges match A-2's exactly.
  What remains assumed is *vertical*: the floor assembly between one ceiling and
  the next floor is in no sheet, so `ASSUMED_FLOOR_ASSEMBLY_INCHES` is a
  convention and every storey above the first inherits its error.
- ~~**Scope is the kitchen/family checkpoint region only.**~~ Superseded. All
  four drawn storeys are built: 565 primitives, every one of 4,496 traced
  corners present in the export.
- ~~**The whole-floor path is outside the contract that fixed the kitchen.**~~
  Superseded. `scripts/measure_a1_tour.py` opens the exported GLB and diffs
  every primitive corner against the trace, and a committed-artifact test fails
  the suite when the two drift apart. `chirality.mapping_preserves_handedness`
  tests the *mapping* rather than named kitchen furniture, so it applies to
  every storey.
- **Nothing in the bake moves.** The lighting is baked, so the sun is at the
  hour it was baked at, permanently, and reflections are environment-map
  approximations. A different time of day is a re-bake.
- **The top storey has no roof**, and the ceiling slabs overhang the walls they
  sit on, which is the flying-saucer edge in the exploded view.
- **Furniture is three stock models.** A bedroom gets a chair because a chair,
  a table and a lamp are the only pieces in the repo. The proxy refuses Poly
  Haven and AmbientCG, so sourcing more is blocked from inside a session.
- **The powder room's four traced "fixture" shapes all became cabinets.** What
  they actually are is an open question for whoever knows the building.

---

## 8. Agreed next, in order

1. ~~**The rest of the house.**~~ Done: `/tour/building` serves all four drawn
   storeys, 565 primitives, every one of 4,496 traced corners present in the
   export.
2. ~~**Overhead view must drop the ceiling.**~~ Done. Ceilings are their own
   glTF nodes now, because a material cannot be hidden per-face in three.js, and
   they are switched off overhead and whenever a single floor is chosen. Walking
   keeps them.
3. ~~**A floor switcher in the browser UI.**~~ Done, alongside the storeys it
   switches between — and the camera reframes onto the floor you pick, which is
   what made the switcher feel broken even once it worked.
4. ~~**Photorealism**, deliberately after the layout is right.~~ Done to the
   limit of a real-time renderer; see §10. Cycles' whole diffuse solution is
   baked in, the walls are painted, windows are glazed and lined, and the camera
   meters for the room it is standing in.
5. ~~**Stairs on every storey.**~~ Done; see §11.
6. **A roof, and ceiling slabs that stop at their walls.** The top storey reads
   as a flat white slab from outside and every ceiling overhangs.
7. **Stair joinery** — a stringer and a soffit, so a flight stops reading as a
   solid mass from the side.
8. **Furniture beyond three stock pieces**, which needs assets the session
   proxy will not fetch.

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

Furniture follows the same rule and is placed the same way: a clearance
transform finds the most open point in each traced room, whatever shape the
trace gave it, and the room's *kind* decides what stands there — exactly as it
already decides the floor finish and the worktop material. Bathrooms, cupboards
and circulation get a light and nothing else, because furnishing them would be
invention rather than staging.

Still deferred: a UI for moving that furniture around.

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

### The bake is not the loop

Baking is measured in hours; grading, denoising, tone mapping and export are
measured in seconds. Chaining them meant every downstream question cost another
bake, and it is the single most expensive mistake available in this pipeline.
The atlas is kept in `spikes/tour_quality/bakes/` and `--reuse-lightmap` loads
it back, which turns a hundred-minute round trip into forty seconds. Reuse
assumes unchanged geometry: the unwrap is deterministic, but only for that
build.

Three things about the bake itself, each of which cost a bake to learn:

**Cycles denoising is a render setting.** `scene.render.bake` has no
equivalent and the bake operator does not denoise, so an atlas comes back
exactly as noisy as its sample count leaves it. Blender 5's compositor could
run OpenImageDenoise over it and needs a GPU context. A median in numpy is the
right filter for what is actually there — undersampled path tracing leaves
salt and pepper, which a median removes and a mean only spreads.

**A filter cannot rescue undersampling.** 5×5, 7×7 and 9×9 medians all plateau
at the same residue, because what is left is low-frequency Monte Carlo
variance and no spatial filter can tell that from a real light gradient. The
fix was in the sampling: a tight adaptive threshold, no sample floor, clamped
indirect fireflies, and fast GI off — it approximates exactly the deep bounces
this bake exists to capture. Tightening the threshold made the bake *faster*,
not slower, because adaptive sampling only ever saves time on texels that have
converged.

**Packing decides resolution, not image size.** `smart_project`'s own packer
left the atlas ninety-six per cent empty at twelve texels to the metre.
Unwrapping with no margin, levelling texel density by real area, and repacking
with concave island shapes gives forty per cent coverage and thirty-eight
texels to the metre — three times the detail for one second of work, where
buying it with image size would have cost nine times the bake.

`scripts/check_export.py` guards all of this from the artifact side, because
every one of these failures exports cleanly and raises nothing.

### The camera meters for what it is looking at

A white wall came out brown, and neither the albedo nor the bake was at fault:
the albedo was 195,190,178 in the export and the light was clean. The exposure
was metering for the sunlit exterior.

Baked light is linear. The sunlit outside sets the top of the range, and the
median lit texel indoors is about a quarter of the atlas peak, so a 0.55
albedo lands at 0.15 linear -- sRGB 75, which the eye reads as dark brown. A
real interior photograph blows the windows out precisely so the room reads
correctly; a real exterior photograph does not. One exposure cannot do both,
and the sweep says so:

| exposure | interior wall | exterior clipped |
| --- | --- | --- |
| 1.5 | 88, 85, 81 | 0.03% |
| 3.0 | 134, 130, 125 | 0.03% |
| 4.5 | 165, 161, 155 | 0.20% |
| 6.0 | 190, 185, 179 | 3.53% |

`exposureFor()` picks the stop from whether the camera is inside the storey's
own bounds. Two stops apart, chosen by where the camera is standing, which is
what a camera operator does.

The wall paint is a separate matter and was also wrong: seventeen points of
saturation between channels reads as tan across a large flat surface. It is
graded nearly neutral now, and because the atlas holds irradiance with no
albedo in it, changing the paint costs a re-export and not a re-bake -- forty
seconds against twenty-six minutes.

---

## 11. Reading a stair off a plan

Two of the four storeys came back with no stairs at all, and the two that did
were in different places — so the tour looked like a house you could not walk
through. Every cause was in the reading, not the drawing.

**Some sheets draw a tread as two strokes.** A-0 and A-2 draw each tread as a
pair an inch and a half apart; A-1 and A-3 draw one line. The ladder search
wants a constant riser, so on the paired sheets it measured 10.5, then 1.5,
and gave up after two steps. Collapsing pairs closer than three points is safe
because at this sheet's scale that is under two inches, and no riser is that
shallow.

**A stair can be found twice.** Treads are grouped by where their midpoint
falls, so a flight whose treads vary by an inch in width straddles two groups.
The massing then stacked both copies into one climb. Runs covering the same
ground are the same stair; the better-sampled one wins.

**Hatching looks like a stair.** Two runs on A-3 were five and a half feet wide
with a four-inch going, and they built a flight that came out through the roof.
Both facts are physical: nobody climbs a four-inch going — code minimum tread
depth is nine to ten inches and the real flights here run six and three-quarters
to nine — and a dwelling stair is not five feet wide.

**A plan cuts the flight where the floor above crosses it.** What is drawn is
the bottom of the stair, not the whole of it: A-1 shows six treads for a storey
needing about fourteen. Everything the continuation needs is measured — where
it starts, how wide it is, which way it travels, its going — and only the fact
that it keeps going is assumed. Those treads are declared `assumed`, exactly
like a door head or a window sill, and the flight stops at the printed ceiling.

**A continuation carried in a straight line walks out of the building.** The
flood fill stops at walls, so "still in the same room" is "still inside the
enclosure" without needing to know what the enclosure is called — which matters,
because only A-1 labels its staircase. The first version of that test ran down
the tread's *centre line*, and a tread is the best part of three feet wide: the
first floor's flight kept its centre in the stairwell while both ends stood out
in the family room and the kitchen. It was caught by looking at the model, not
by the check. Both ends are asked now, and a flight stops at the wall rather
than inventing the landing or the turn that a real stair would have there —
this pipeline reads plans, and a plan does not say which.

None of the four faults above was in the drawing. Every one was in the reading,
and every one produced a model that loaded cleanly and passed its tests.

The invariant that caught the roof-piercing flight was already in the suite:
nothing but the ceiling slab may rise above the printed ceiling height. It is
worth more than the fix it caught.
