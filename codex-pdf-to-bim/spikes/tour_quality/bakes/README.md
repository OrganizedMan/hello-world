# Baked lightmap atlases

Cycles atlases kept so that grading, tone mapping and export can be re-run
without paying for the bake again — hours against seconds. Reuse one with:

    --bake light --reuse-lightmap <atlas.png> --reuse-scale <scale>

The scale is what the atlas was normalised by to fit an 8-bit image; it is
printed by the bake and stored in the manifest as `artifact.lightmap.scale`.
Reusing an atlas assumes the geometry is unchanged: the UV unwrap is
deterministic, but it is deterministic *for that build*.

| atlas | size | samples | scale | built from |
| --- | --- | --- | --- | --- |
| `a1-building-2048-lightmap.png` | 2048 | 64 | 2.9482 | four storeys, casework, joinery, furniture; sun 6.0, sky 5.0 |
