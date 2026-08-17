# M0 feasibility results

**Status: in progress.** The environment is pinned and one Gate A probe has run.
Everything still marked _(pending)_ has not been executed; per `AGENTS.md` rule
19, an unrun stage is reported as not run, never as an estimate.

## 0. Environment

| Item | Value |
| --- | --- |
| Machine | 2025 MacBook Air, 16 GB unified memory, arm64 (`Jacks-Air`) |
| macOS version | Darwin 27.0.0 |
| Python | 3.11.7 |
| Free space at setup | 34.7 GB |
| Date of run | 2026-08-17 |

Machine-readable copy: `docs/doctor-report.json`.

### Pinned tool versions

All discovered from the installed binaries by `amber doctor`, not from
documentation.

| Tool | Required | Version | Build / commit | Acceleration reported |
| --- | --- | --- | --- | --- |
| FFmpeg | yes | 9.0.1 | Homebrew | n/a |
| FFprobe | yes | 9.0.1 | Homebrew | n/a |
| COLMAP | yes | 4.1.1 | Homebrew `4.1.1_3` | **GPU SIFT confirmed** for both extractor and matcher — measured from the §A1 run log, not assumed |
| Brush | yes | `brush-cli 0.3.0` | `brush-app-aarch64-apple-darwin`, cargo-dist release | **unverified** — WebGPU/Metal path not yet confirmed from a run |
| SplatTransform | yes | `@playcanvas/splat-transform` via npm (node v20.20.2) | _(version string pending — its `--help` opens with a banner)_ | n/a |
| SuperSplat viewer | yes | _(pending — not yet used)_ | _(pending)_ | n/a |

### COLMAP capabilities as reported by this build

| Item | Value |
| --- | --- |
| `global_mapper` present | **yes** — the P4 benchmark is available |
| `view_graph_calibrator` present | _(pending — confirm from `colmap help`)_ |
| Feature-extraction size option | `FeatureExtraction.max_image_size` |
| That option's CLI default | **`-1` (no limit)** |

The `-1` default **contradicts the development plan's §8.2 premise** that current
COLMAP defaults to 3200 and therefore silently downscales 4K input. See
experiment-plan amendment A1 and ADR 0001. The P1–P3 resolution sweep still runs;
its rationale changes from "defeat a silent downscale" to "measure whether
downscaling pose images helps or hurts."

## Gate A — public control

Control scene: COLMAP South Building (see experiment plan §2).

| Item | Value |
| --- | --- |
| Retrieval URL | `https://github.com/colmap/colmap/releases/download/3.11.1/south-building.zip` — published as an asset of **COLMAP release 3.11.1**. `demuc.de/colmap/datasets/` only links to it. |
| Retrieval date | 2026-08-17 |
| Archive size | 400 MB |
| Contents | `images/` (**128** files, confirmed by count) and `sparse/` containing `cameras.txt`, `images.txt`, `points3D.txt` — reference model is **text** format, which `colmap_model.py` reads natively |
| License (verbatim) | **No license statement is given** by the COLMAP documentation. The only attribution is: "128 images of the 'South' building at UNC Chapel Hill. The images are taken with the same camera, kindly provided by Christopher Zach." Recorded as an absence rather than assumed to be permissive. |
| Expected registered images | 128 (floor 126) |

### A1–A3 — pose from raw control images

| Stage | Mapper | Registered / total | Connected models | Mean reproj. err. (px) | Wall clock | Peak RSS |
| --- | --- | --- | --- | --- | --- | --- |
| Feature extraction | — | — | — | — | **19.2 s** (0.304 min by COLMAP's timer) | _(not captured)_ |
| Matching (exhaustive) | — | — | — | — | **16.6 min** (996.6 s; COLMAP's own timer) | _(not captured)_ |
| Mapping | incremental | **128 / 128 (100%)** | **1** | **0.613** | **2.094 min** (125.4 s) | _(not captured)_ |
| Mapping | global | _(not run this session)_ | | | | |

**Gate A part 1: PASSED, decisively.** 128 of 128 images registered — not just
above the 126 floor, a perfect result. `model_analyzer` output:

```
Rigs: 1
Cameras: 1
Frames: 128
Registered frames: 128
Images: 128
Registered images: 128
Points: 84907
Observations: 503064
Mean track length: 5.924883
Mean observations per image: 3930.187500
Mean reprojection error: 0.612813px
```

Registered frames equal registered images exactly, so there is exactly **one**
connected model — no fragmentation, and nothing for the dominant-model-fraction
gate condition to penalize. The reprojection error (0.61 px) sits well inside
the 1.5 px gate threshold defined for Gate B captures, though that threshold is
not being applied to the control here — this run's purpose is proving the
toolchain, not passing Amber's own gate.

**Registration order was not sequential.** The incremental mapper picked its own
starting pair — images #71 and #74 — and grew outward via repeated
retriangulation/global bundle-adjustment rounds (about 16 of them across the
run), rather than registering image 1, 2, 3… in order. This is expected
behavior for `colmap mapper` and is why "sequential" in `sequential_matcher`
refers to the *matching* strategy for video, not an assumption about
registration order.

**CPU, not GPU, dominates wall clock here.** The `time` output shows
487% CPU utilization during mapping (289.58s user + 336.05s system against
128.34s wall) and 145% during matching — both are heavily multi-threaded CPU
work. SIFT extraction is GPU-accelerated, but bundle adjustment and matching
verification are not. Peak RSS was not captured this run; a follow-up should
wrap these commands with `/usr/bin/time -l` (macOS) to get it, which also
addresses AGENTS.md's storage/memory measurement rule.

Total elapsed for Gate A part 1: 19.2 s + 16.6 min + 2.1 min ≈ **19 minutes**,
dominated by exhaustive matching's O(n²) cost on an unordered photo set — see
the note below on why this figure does not transfer to Amber's video path.

**Acceleration — measured, not assumed.** COLMAP announced
`Creating SIFT GPU feature extractor` and `Creating SIFT GPU feature matcher`.
GPU SIFT **is** available on this Apple-silicon build, which the plan explicitly
told us not to assume either way. Amber now parses this from the run log and
records it per-run (`effective_image_size.extraction_acceleration`).

**Effective feature-extraction image size.** Requested: no limit
(`FeatureExtraction.max_image_size` default `-1`). Effective: **3072 × 2304**,
the full source resolution, confirmed from COLMAP's own per-image
`Dimensions:` lines. Requested and effective agree here — which is exactly the
check §8.2 demands and which amendment A1 predicted.

**Other observations from the extraction pass.** Camera model defaulted to
`SIMPLE_RADIAL` (Amber's provisional default is `OPENCV`); focal length came
from an EXIF prior at 2484.86 px; feature counts ranged roughly
8,200–15,000 per image; and this build reports a gravity prior per image
(`Gravity: X=0.000, Y=1.000, Z=0.000`), a capability Amber does not currently
use.

**Note on the matching cost.** Exhaustive matching ran 9 blocks at 40–140 s
each. This is the correct matcher for an unordered photo collection like the
control, but it is **O(n²) and does not transfer to Amber's video path**, which
uses `sequential_matcher` with loop detection. Do not derive a frame budget for
iPhone captures from this number; measure sequential matching separately in
Gate B.

### A4a — evaluation-split probe (ADR 0004)

A deliberately trivial run whose only purpose was to determine how Brush selects
and names its held-out renders. Imagery quality is irrelevant here.

```bash
brush brush-dataset --export-path ~/amber-control/probe \
  --total-steps 200 --eval-split-every 8 --eval-save-to-disk --max-resolution 800
```

| Item | Value |
| --- | --- |
| Wall clock | **9 s** (200 steps, 128 images, 800 px) |
| Output | `probe/eval_200/` with 16 PNGs, plus `probe/export_200.ply` |
| Held-out set | `P1180141, 149, 157, 165, 173, 181, 189, 197, 205, 213, 221`, then `P1180308, 316, 324, 332, 340` |

**Finding 1 — stride phase.** `--eval-split-every N` selects sorted-filename
indices **0, N, 2N, …**, not N−1. The dataset is `P1180141–P1180221` (81 files)
plus `P1180301–P1180347` (47 files) = 128. Indices 0, 8, …, 80 give the first
eleven; indices 88, 96, 104, 112, 120 give the last five. The discontinuity
between 221 and 308 is what makes this a proof rather than a coincidence — only a
stride starting at index 0 reproduces that exact set.

**Finding 2 — render naming.** Each render is named after its source image's stem
with a `.png` extension, inside `eval_<step>/` beneath `--export-path`. Multiple
evaluation passes produce multiple such directories; the highest step is final.

**Finding 3 — flags.** Amber's candidates for export path, total steps, max
resolution, SH degree, and splat cap all matched this build. Its `--max-splats`
default is 10,000,000, so `TrainConfig`'s 2,000,000 cap is doing real work on a
16 GB machine.

**Finding 4 — headless operation.** Brush runs as a CLI with no window; an
invalid dataset path produced a typed `I/O error while constructing BrushVfs`
rather than launching a GUI. `--with-viewer` is opt-in.

Findings 1 and 2 moved ADR 0004 from Proposed to Accepted and are implemented in
`stride_for_split` and `collect_evaluation_renders`.

### A4b — full training from the reference COLMAP model

This bypasses Amber's pose stage and proves the trainer independently. **Run,
wrapped in `/usr/bin/time -l`.**

| Item | Value |
| --- | --- |
| Brush completed without exhausting 16 GB | **yes — passed with margin** |
| Peak memory footprint (macOS `time -l`) | **5,702,945,720 B ≈ 5.31 GB** (~33% of 16 GB) |
| Maximum resident set size (`getrusage`) | 1,970,110,464 B ≈ 1.83 GB — undercounts vs. footprint above; macOS RSS does not fully capture Metal/GPU-mapped memory, so peak footprint is the trustworthy figure |
| Wall clock | **9965.76 s ≈ 166.1 min ≈ 2.77 h** |
| CPU time | 4708.12 s user + 281.36 s sys ≈ 4989.5 s total (≈50% average utilization of wall clock — plausibly GPU/Metal-bound rather than CPU-bound during much of the run) |
| Checkpoints exported | 6: steps 5000, 10000, 15000, 20000, 25000, 30000 |
| Evaluation renders produced | 480 = 30 eval passes × 16 held-out views — consistent with default `--eval-every 1000` over 30,000 steps and `--eval-split-every 8` on 128 images, confirming A4a's stride finding at full scale |
| Output directory size | 2.3 GB total (6 PLYs + 480 renders) |
| Output PLY loads | not yet independently verified — deferred to §A5 (open in SuperSplat) |
| Output PLY sha256 | _(pending — record `shasum -a 256 export_30000.ply`)_ |
| Exact command | _(pending — record verbatim per AGENTS.md rule 6; only the `time -l` report and file listing were captured for this entry)_ |

**Gate A memory criterion: PASSED, decisively.** 5.3 GB peak leaves roughly
10.7 GB of headroom on the 16 GB machine, even without yet trying the
"beautiful" profile's higher resolution/step counts. This is the exit
criterion "Brush produces a loadable PLY from the reference COLMAP model
without exhausting 16 GB unified memory" — memory is settled; "loadable" is
confirmed once §A5 opens the PLY in a real viewer.

**Low IPC / CPU utilization is the notable open question**, not a red flag by
itself: instructions retired (9.77 trillion) over cycles elapsed
(18.44 trillion) gives IPC ≈ 0.53, and CPU time covers only about half of wall
clock. Both are consistent with a GPU/Metal-bound workload where the CPU
spends time waiting rather than computing, but this should be confirmed rather
than assumed — Activity Monitor's GPU history during a future run would settle
it.

### A5 — conversion and stock-viewer check

| Item | Mac | iPhone 16 Pro |
| --- | --- | --- |
| Derivative size | _(pending)_ | _(pending)_ |
| Load succeeded | _(pending)_ | _(pending)_ |
| Load time | _(pending)_ | _(pending)_ |
| Observed frame-rate range | _(pending)_ | _(pending)_ |
| Safari version | n/a | _(pending)_ |

### Gate A storage by stage

| Stage | Input bytes | Output bytes | Peak temp bytes |
| --- | --- | --- | --- |
| _(pending)_ | | | |

**Gate A verdict:** _(pending)_ — if pose fails but reference-model training
succeeds, the pose pipeline is the blocker; if reference-model training fails,
diagnose the trainer/toolchain before touching capture parameters.

## Gate B — controlled iPhone captures

Not started. Requires Gate A to pass and the two controlled captures
(`object-01`, `room-01`) to be recorded per the §7 capture contract.

### Frozen split records

See `docs/m0-experiment-plan.md` §9. Both entries are pending; they must be
appended and locked *before* the first configuration of that capture runs.

### Pose configuration results

| Capture | Config | Feature | Matcher | Mapper | Requested / effective long edge | Reg. % | Reg. abs. | Dominant model % | Max gap (s) | Max consec. missing | Median tri. angle | Transl./depth | Reproj. (px) | Path review | **Gate** | Eval coverage |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| _(pending)_ | | | | | | | | | | | | | | | | |

Gate column is conjunctive — every condition in experiment plan §7 must pass.

### Held-out metrics

Common registered-evaluation intersection size: _(pending)_
(`min_common_evaluation_views` = 12; below that the comparison is
**inconclusive**, not ranked.)

| Capture | Config | Training views | PSNR (intersection) | SSIM (intersection) | PSNR (full coverage) | SSIM (full coverage) | Registered eval / 32 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| _(pending)_ | | | | | | | |

### Delivery profiles

| Capture | Profile | SH degree | Splat count | Bytes | iPhone load time | iPhone fps | ΔPSNR vs. master | ΔSSIM vs. master |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| _(pending)_ | | | | | | | | |

### Object Capture baseline (object scene)

| Item | Object Capture (mesh) | Brush (splat) |
| --- | --- | --- |
| Ran | _(pending)_ | _(pending)_ |
| Processing cost | _(pending)_ | _(pending)_ |
| Appearance notes | _(pending)_ | _(pending)_ |
| Geometry notes | _(pending)_ | _(pending)_ |
| Viewing experience | _(pending)_ | _(pending)_ |

Recorded as a product baseline. The two outputs are different representations
and are not scored as interchangeable.

### Human visual review

Per §8.5 rubric, including the explicit motion-artifact field
(`pass` / `fail` / `not_applicable`) and screenshots: _(pending)_

### Gate B storage by stage

| Capture | Stage | Input bytes | Output bytes | Peak temp bytes |
| --- | --- | --- | --- | --- |
| _(pending)_ | | | | |

Retained archive size, Complete profile: _(pending)_
Retained archive size, Compact profile: _(pending)_
Recommended M1 default: _(pending)_

## Failure attribution

Every failure observed must be attributable to exactly one of:
import/color, frame selection, pose, training, conversion, or viewing.

| # | Stage | Symptom | Diagnosis | Resolution |
| --- | --- | --- | --- | --- |
| _(none recorded)_ | | | | |

## Effort ledger

| Session | Gate | Active hours | Work done |
| --- | --- | --- | --- |
| _(none)_ | | | |

Bound: 6 sessions × 3 active hours (2 Gate A, 4 Gate B). At the bound, publish
and write the M0 outcome ADR (proceed / re-scope / stop).
