# Task 2A — Artifact validator partial handoff

Status: `DONE_WITH_CONCERNS`

This checkpoint contains the strict RED→GREEN validator implementation and its real GLB behavior tests. The Blender scene/build/artifact portion was explicitly split into a later Task 2B by the controller and is not claimed complete here.

## Staged implementation

- `spikes/tour_quality/validate_artifact.py`
  - Provides `validate_artifact(glb_path: Path, manifest_path: Path, *, public_dir: Path | None = None) -> tuple[str, ...]`.
  - Provides the required optional-argument CLI `main()` and repo/staging-relative browser defaults.
  - Decodes the real GLB JSON chunk and validates named nodes, embedded/local image behavior, embedded buffers, and visual-staging asset extras.
  - Uses `trimesh` world bounds for the real named `HV_FLOOR` and `HV_ISLAND_STRUCTURE` meshes rather than trusting manifest dimensions.
  - Validates schema, non-canonical label/boundary, all printed dimensions, runtime coordinate conversion, eye height, walkable bounds, barriers, cameras, artifact file hashes/byte counts, deterministic manifest size, actual total payload, and the 45,000,000-byte ceiling.
- `tests/backend/test_tour_artifact_validation.py`
  - Uses real temporary GLBs exported by `trimesh`, literal hand-built manifest contract values, and direct filesystem artifacts.
  - Initially contained 21 cases; Fix round 1 expands the focused suite to 27 cases.

## TDD evidence

RED command:

```sh
UV_CACHE_DIR=/private/tmp/hearthview-uv-cache \
PYTHONPATH=/Users/jackgarrigan/Documents/Codex/2026-08-18/bui/work/task-2-staging:/Users/jackgarrigan/Developer/hello-world/codex-pdf-to-bim \
uv run pytest -p no:cacheprovider /Users/jackgarrigan/Documents/Codex/2026-08-18/bui/work/task-2-staging/tests/backend/test_tour_artifact_validation.py -q
```

Observed RED: pytest collection exited 2 with `ModuleNotFoundError: No module named 'spikes.tour_quality.validate_artifact'`. This was the expected missing-production-module failure.

Fresh GREEN verification used the same command and exited 0:

```text
.....................                                                    [100%]
21 passed in 0.25s
```

`uv` also printed the non-fatal warning `Failed to acquire environment lock: Could not create temporary file` because the authorized source repository is read-only. Test execution still completed successfully.

## Blender checkpoint and concerns

- Blender was confirmed as `Blender 5.2.0 LTS` (`fbe6228777e7`).
- A background `--factory-startup` API probe crashed before Python execution in Blender's Metal device detection (`supports_barycentric_whitelist` / `MTLBackend::metal_is_supported`) while sandboxed.
- The required outside-sandbox retry awaited approval and was aborted. No builder, render, GLB, HDR copy, poster, manifest, provenance, or license file was produced.
- The combined backend suite and validator-on-real-output checks were not run because Task 2B artifacts do not yet exist.
- Artifact byte counts, SHA-256 values, export/render duration, triangle/material/image counts, poster inspection iterations, and visual warnings remain Task 2B work.
- No commits were made, no subagents were spawned, and no writes were made to the user-authorized source repository.

## Fix round 1

Three Important review findings were handled as separate RED→GREEN changes:

1. The real GLB fixture now uses Y-up artifact coordinates: X remains horizontal, Y is vertical, and source room depth is converted to negative Z. Validation checks `HV_FLOOR` at X `[0.0, 9.1694]`, Z `[-4.8514, 0.0]`, and `HV_ISLAND_STRUCTURE` at X `[1.7272, 4.3434]`, Z `[-3.0226, -1.7272]`. Eight literal drift cases independently prove each min/max X/Z edge. RED was 5 failed / 20 passed before the validator changed; the item reached 25 passed.
2. Every GLB image must now use an embedded `bufferView`. A real existing local sidecar image URI was accepted during RED (1 failed / 25 passed), then rejected after the validator change; the item reached 26 passed.
3. `artifact.sha256` keys must now be exactly `glb`, `poster`, and `environment`. A `sha256.manifest` mutation was accepted during RED (1 failed / 26 passed), then rejected after exact-key validation; the item reached 27 passed.

Fresh final verification command:

```sh
UV_CACHE_DIR=/private/tmp/hearthview-uv-cache \
PYTHONPATH=/Users/jackgarrigan/Documents/Codex/2026-08-18/bui/work/task-2-staging:/Users/jackgarrigan/Developer/hello-world/codex-pdf-to-bim \
uv run pytest -p no:cacheprovider /Users/jackgarrigan/Documents/Codex/2026-08-18/bui/work/task-2-staging/tests/backend/test_tour_artifact_validation.py -q
```

Fresh final output (exit 0):

```text
WARN Failed to acquire environment lock: Could not create temporary file
...........................                                              [100%]
27 passed in 0.25s
```

Blender was not invoked during this fix round. The Task 2B artifact/build concerns above remain unchanged.
