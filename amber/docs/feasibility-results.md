# M0 feasibility results

**Status: not executed.** Every table below is empty by design. Filling a cell
requires a real run on the target hardware; per `AGENTS.md` rule 19, an unrun
stage is reported as not run, never as an estimate.

Run `amber doctor --json > docs/doctor-report.json` on the target Mac to begin.

## 0. Environment

| Item | Value |
| --- | --- |
| Machine | _(pending — target: 2025 MacBook Air, 16 GB unified memory)_ |
| macOS version | _(pending)_ |
| Date of run | _(pending)_ |

### Pinned tool versions

| Tool | Required | Version | Build / commit | Acceleration reported |
| --- | --- | --- | --- | --- |
| FFmpeg / FFprobe | yes | _(pending)_ | _(pending)_ | n/a |
| COLMAP | yes | _(pending)_ | _(pending)_ | _(pending — do **not** assume GPU SIFT on Apple silicon)_ |
| Brush | yes | _(pending)_ | _(pending)_ | _(pending — WebGPU/Metal)_ |
| SplatTransform | yes | _(pending)_ | _(pending)_ | n/a |
| SuperSplat viewer | yes | _(pending)_ | _(pending)_ | n/a |

## Gate A — public control

Control scene: COLMAP South Building (see experiment plan §2).

| Item | Value |
| --- | --- |
| Retrieval URL | _(pending)_ |
| Retrieval date | _(pending)_ |
| License (verbatim) | _(pending — record before use)_ |
| Expected registered images | 128 (floor 126) |

### A1–A3 — pose from raw control images

| Stage | Mapper | Registered / total | Connected models | Mean reproj. err. (px) | Wall clock | Peak RSS |
| --- | --- | --- | --- | --- | --- | --- |
| Feature extraction | — | — | — | — | _(pending)_ | _(pending)_ |
| Matching | — | — | — | — | _(pending)_ | _(pending)_ |
| Mapping | incremental | _(pending)_ | _(pending)_ | _(pending)_ | _(pending)_ | _(pending)_ |
| Mapping | global | _(pending)_ | _(pending)_ | _(pending)_ | _(pending)_ | _(pending)_ |

Effective feature-extraction image size (requested vs. what COLMAP saw):
_(pending)_

### A4 — training from the reference COLMAP model

This bypasses Amber's pose stage and proves the trainer independently.

| Item | Value |
| --- | --- |
| Brush completed without exhausting 16 GB | _(pending)_ |
| Peak memory | _(pending)_ |
| Wall clock | _(pending)_ |
| Output PLY loads | _(pending)_ |
| Output PLY sha256 | _(pending)_ |

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
