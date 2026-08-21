# HearthView tour-quality spike

**Quality spike · visual staging**

This is an isolated, throwaway proof of quality. It remains unproven until the
geometry, realism, and navigation gates all pass. Its display GLB is not
canonical HearthView geometry.

`scene_contract.py` is the only source for the A-1 printed dimensions and
spatial metadata consumed by later spike work. Cabinet fronts, hardware,
finishes, furnishings, decor, and undimensioned offsets are provisional visual
staging rather than measured claims.

Future authoring will run:

```sh
blender --background --python spikes/tour_quality/build_scene.py
```

That future command is intended to generate (not yet present):

- `apps/web/public/tour-spike/hearthview-kitchen-family.glb`
- `apps/web/public/tour-spike/manifest.json`
- `apps/web/public/tour-spike/poster.webp`

External assets are outside Task 1's scope.
