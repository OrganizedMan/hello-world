# Amber

Turn an iPhone video into a locally stored, explorable 3D memory.

Everything runs on your own machine. The original video is copied, hashed, and
never modified. Nothing is uploaded, and nothing is invented: Amber preserves
what the camera saw, and says so plainly when a capture cannot support a
faithful reconstruction.

## Status

**Milestone 1 codebase; Milestone 0 Gate A partially executed.**
Full detail, including what has never been run, is in
[`docs/status.md`](docs/status.md).

| Deliverable | State |
| --- | --- |
| Frozen M0 experiment plan | written — `docs/m0-experiment-plan.md` |
| Decision log | ADRs 0001–0004 — `docs/decisions/` |
| `amber doctor` | working |
| `amber process` golden path | implemented; needs the toolchain to run |
| Unit + integration tests | 212 passing |
| M0 Gate A pose (incremental mapper) | **PASSED** — 128/128 registered on the public control |
| M0 Gate A trainer eval-split behavior | proven on the public control; resolved ADR 0004 |
| M0 Gate A full training (memory) | **PASSED** — 5.31 GB peak of 16 GB, 30,000 steps |
| M0 Gate A mobile/viewer check | not yet run |
| M0 Gate B | **not started** — no iPhone captures yet |
| A completed scene archive | **not produced** — needs COLMAP and Brush |
| M0 outcome ADR (proceed/re-scope/stop) | blocked on those measurements |
| ADR 0001 defaults (feature/matcher/mapper) | **Proposed**, deferred to Gate B evidence |

Gate A and Gate B require an Apple-silicon Mac with FFmpeg, COLMAP, Brush, and
SplatTransform installed, plus two controlled iPhone captures. Until they run,
`docs/feasibility-results.md` stays empty on purpose — an unrun stage is
reported as not run, never estimated.

## Install

```bash
pip install -e .
amber doctor
```

`amber doctor` reports what is actually installed and what each build supports.
It exits non-zero until the toolchain is complete, and it never assumes a
capability it did not observe — including GPU acceleration.

External tools, installed separately and pinned:

| Tool | Used for |
| --- | --- |
| FFmpeg / FFprobe | probing the video, decoding candidate frames |
| COLMAP 4.x | camera poses and the sparse point cloud |
| Brush | Gaussian-splat training on Apple silicon |
| SplatTransform | compressed delivery derivatives |

## Use

```bash
amber process ~/Movies/IMG_1234.MOV --profile beautiful --title "Living room"
amber inspect ~/Pictures/Amber\ Memories/2026-08-17-living-room-a1b2c3d4 --verify
amber retry  <scene> --from poses
amber prune  <scene> --dry-run
amber prune  <scene> --working
```

Processing runs six stages, each atomic and resumable: preparing the video,
finding clear viewpoints, reconstructing the camera path, building the scene,
reviewing quality, cleaning and packaging. A failure names the stage
responsible and gives capture advice rather than a subprocess error.

## What version 1 does not promise

People, pets, water, or foliage in motion; recovery of old casual footage with
no camera movement; a native iPhone app; dynamic/4D playback; generative filling
of surfaces the camera never saw; or a mesh accurate enough to measure.

Amber is excellent for rooms, yards on a still day, objects, and a person who
can hold a pose while the camera moves around them.

## Capture

Read [`docs/capture-guide.md`](docs/capture-guide.md) before recording. Camera
movement matters more than camera quality: a pan from one spot cannot produce a
3D scene, and Amber will tell you so rather than producing a plausible-looking
lie.

## Contributing

[`AGENTS.md`](AGENTS.md) holds the non-negotiables. The short version: preserve
the source, keep processing local, gate training on a healthy pose solution,
keep evaluation frames out of training, never repurpose a locked split, and
record architecture decisions in `docs/decisions/` before implementing them.

```bash
python -m pytest tests -q
./scripts/integration_test.sh          # add a video path for a full run
```
