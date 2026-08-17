# Project status

**As of:** 2026-08-17
**Branch:** `claude/build-to-plan-z8y813`
**Milestone:** M1 code complete; M0 Gate A partially executed

This file is a snapshot for whoever picks the work up next — including a future
session with no memory of this one. It records what is proven, what is merely
written, and what is still unknown. Per `AGENTS.md` rule 19, nothing here is
reported as measured unless it was actually measured.

---

## One-paragraph summary

The Milestone 1 codebase is written and tested: a six-stage local pipeline
(`amber process`) with pose and trainer backends behind interfaces, a
conjunctive pose gate loaded from a frozen predeclaration, an archival scene
format with safe pruning, and 212 passing tests. Milestone 0 — the measurement
milestone — is underway on the target Mac. Gate A part 1 (pose from the raw
public control) is **complete and passed decisively**: 128 of 128 images
registered, one connected model, 0.61 px mean reprojection error. The trainer
half of Gate A is proven for its eval-split behavior (ADR 0004) but has not yet
run a full-length training pass. Gate B has not started, so no scene archive
exists yet and no quality claim has been made about a real capture.

---

## Deliverable status

Against the plan's twelve expected first deliverables:

| # | Deliverable | State |
| --- | --- | --- |
| 1 | `AGENTS.md` + non-divergent `CLAUDE.md` pointer | done |
| 2 | `docs/m0-experiment-plan.md`, frozen, with split and effort bound | done |
| 3 | `docs/feasibility-results.md` with pose coverage and storage tables | **partially filled** — §0 environment, control provenance, §A1–A3 incremental-mapper pose (128/128, PASSED), §A4a probe, and §A4b full training (5.3 GB peak, PASSED) all done; global-mapper benchmark, §A5 mobile, and all Gate B tables still pending |
| 4 | `docs/decisions/README.md` | done |
| 5 | `docs/decisions/0001-sfm-pipeline.md` | written, **Status: Proposed** by design |
| 6 | M0 outcome ADR (proceed / re-scope / stop) | **blocked** — needs Gate A+B evidence |
| 7 | Trainer ADR | not needed yet; Brush has raised no concrete question |
| 8 | Working `amber doctor` | done |
| 9 | Working `amber process` golden path | code complete, **never run end to end** |
| 10 | One conforming scene archive | **not produced** |
| 11 | Unit tests for manifest, stage state, split determinism/immutability, comparison intersections, subprocess parsing, prune safety, checksums | done — 177 unit tests |
| 12 | Integration script incl. prune/regenerate | done — 29 integration tests + `scripts/integration_test.sh` |

Code: ~6,000 lines under `amber/`, ~2,500 lines of tests. Commits accumulating on the branch as M0 evidence lands.

---

## Decisions on record

| ADR | Status | Substance |
| --- | --- | --- |
| 0001 SfM pipeline | **Proposed** | Feature/matcher/mapper/resolution defaults deliberately deferred to Gate B evidence. Ships SIFT + sequential + incremental + OPENCV as provisional. |
| 0002 Backend interfaces | Accepted | `PoseBackend` / `TrainerBackend`; capabilities discovered from installed binaries; no silent fallback; no silently dropped settings. |
| 0003 Archive format | Accepted | Regenerability invariant; three retention classes; manifest written before deletion so an interrupted prune is recoverable. |
| 0004 Held-out rendering | **Accepted on measurement** | Brush renders only a stride-selected set of its own choosing, so Amber aligns its split to that stride and verifies before and after. |

ADR 0004 weakened ADR 0002's structural guarantee. `AGENTS.md` rule 10 was
updated to state the weaker, accurate mechanism rather than leaving the old claim
standing.

---

## Toolchain on the target Mac

Target: 2025 MacBook Air, 16 GB unified memory (`Jacks-Air`).

| Tool | State | Evidence |
| --- | --- | --- |
| Brush | **installed and proven** v0.3.0 (`brush-app-aarch64-apple-darwin`, cargo-dist) | trained the public control; headless CLI confirmed |
| Control dataset | **downloaded** — COLMAP South Building, 400 MB, `images/` + `sparse/` in **text** format | extracted and used |
| FFmpeg / FFprobe | **installed** 9.0.1 | `amber doctor` |
| COLMAP | **installed** 4.1.1 (Homebrew `4.1.1_3`) | `amber doctor`; `global_mapper` present |
| SplatTransform | **installed** via npm (node v20.20.2) | `amber doctor` |

`amber doctor` reports **Ready to process**. Versions are pinned in
`docs/feasibility-results.md` §0 and `docs/doctor-report.json`.

Measured COLMAP detail worth carrying forward: this build reports
`FeatureExtraction.max_image_size` with a default of **`-1`** (no limit), *not*
the 3200 the development plan assumed. See experiment-plan amendment A1 and
ADR 0001. Free space after the installs: **34.7 GB**, worth watching against the
still-unmeasured storage multiplier.

---

## Gate A findings so far

### Pose from raw control images (§A1–A3) — PASSED

Incremental mapper, full 128-image set, single-camera:

| Metric | Value |
| --- | --- |
| Registered | **128 / 128 (100%)** |
| Connected models | **1** |
| Mean reprojection error | **0.613 px** |
| Sparse points | 84,907 |
| Mean track length | 5.92 |
| Feature extraction | 19.2 s (GPU SIFT) |
| Exhaustive matching | 16.6 min (GPU SIFT, CPU-bound verification, 145% CPU) |
| Incremental mapping | 2.1 min (487% CPU — bundle adjustment is heavily threaded) |

Registration order was not sequential — the mapper picked its own starting pair
(images #71, #74) and grew outward through ~16 rounds of retriangulation and
global bundle adjustment. Peak RSS was not captured; a follow-up run should wrap
the commands in `/usr/bin/time -l` to get it.

The **global-mapper benchmark** (on a copied feature database, per §8.3) has not
been run this session.

### Brush eval-split probe (§A4a)

Four measurements, all from a deliberately trivial 200-step run, recorded in
ADR 0004 and transcribed into `docs/feasibility-results.md` §A4a.

1. **Stride phase.** `--eval-split-every N` selects sorted-filename indices
   0, N, 2N, … The 128-image control proves it: the held-out set spans a
   discontinuity in the source numbering (`P1180221` → `P1180308`) that only an
   index-based stride starting at 0 reproduces.
2. **Render naming.** Renders go to `eval_<step>/` beneath `--export-path`, each
   named after its source image's stem with a `.png` extension. Multiple
   evaluation passes produce multiple directories; the highest step is final.
3. **Flags.** Amber's candidates for export path, total steps, max resolution,
   SH degree, and splat cap all matched this build. Its `--max-splats` default is
   10,000,000, so `TrainConfig`'s 2,000,000 cap is doing real work here.
4. **Headless.** Runs as a CLI with no window; an invalid dataset path produced a
   typed `I/O error while constructing BrushVfs`. `--with-viewer` is opt-in.

Timing data point: 200 steps, 128 images, 800 px → **9 s**. Not a budget; a
single point from a deliberately trivial run.

### Full training run (§A4b) — PASSED on memory

30,000-step training on the reference COLMAP model, wrapped in
`/usr/bin/time -l`:

| Metric | Value |
| --- | --- |
| Peak memory footprint | **5.31 GB** of 16 GB (~33%) |
| Wall clock | 2.77 h (9965.76 s) |
| CPU utilization | ~50% of wall clock — plausibly GPU/Metal-bound |
| Checkpoints | 6 (steps 5000–30000) |
| Evaluation renders | 480 = 30 eval passes × 16 held-out views, confirming the A4a stride finding at full scale |

The exact command (resolution, splat cap) used for this run is **not yet
recorded verbatim** — only the `time -l` report and output listing were
captured. AGENTS.md rule 6 requires the literal command; get it before this
entry is considered complete. PLY `sha256` and independent "does it load in a
viewer" confirmation are deferred to §A5.

---

## What has never been executed

Being explicit, because code that has never run is not evidence:

- **Gate A global-mapper benchmark** on a copied feature database — the
  incremental-mapper result (§A1–A3) is in; the comparison point is not.
- **Gate A conversion and mobile check** — no `.sog` produced, no iPhone load
  time or frame rate recorded. The full-training PLY (§A4b) exists and is
  waiting for this step.
- **Gate B in its entirety** — no iPhone captures recorded.
- **`amber process`** — the `import`, `poses`, `train`, `quality`, and `package`
  stages have never run against real tools. Only `frames` has real end-to-end
  coverage (via ffmpeg in CI-like conditions).
- **Storage measurement** — `estimate_required_space` still reports basis
  `unmeasured` and uses a provisional ×25 multiplier.

---

## Open questions and known risks

| Item | Status |
| --- | --- |
| Stratified comparison splits cannot be rendered | Known limitation. `stride_for_split` rejects them explicitly. Needs a renderer accepting arbitrary cameras; deferred (ADR 0004). An inconclusive comparison is an allowed M0 outcome. |
| `min_registered_frames` floors (object 80, room 120) | **Labeled assumptions.** No comparable public control at that capture scale. The M0 outcome ADR confirms or revises them. |
| COLMAP `max_image_size` option name and default | **Resolved.** `FeatureExtraction.max_image_size`, default `-1` (no limit) on COLMAP 4.1.1 — not the 3200 the plan assumed. Amendment A1; ADR 0001 updated. |
| GPU acceleration | **COLMAP resolved:** GPU SIFT confirmed for extractor and matcher, measured from the §A1 run log. **Brush still unverified** — no run has announced its backend. |
| SplatTransform splat-count limit flag | Unverified. SH flag confirmed as `-H/--filter-harmonics`; the code warns rather than guessing if a limit flag is absent. |
| Default retention profile (Complete vs Compact) | Cannot be chosen until Gate B storage numbers exist. |
| Archive size range | Unmeasured. No promise may be made yet. |

---

## Effort ledger

Bound: six sessions, three active hours each — two for Gate A, four for Gate B.

| Session | Gate | Work |
| --- | --- | --- |
| 1 | setup + A | Toolchain fully installed and verified (`amber doctor` → Ready); control dataset acquired; Brush eval-split probe run and ADR 0004 resolved; incremental-mapper pose run — **128/128 registered, PASSED**; full 30,000-step Brush training on the reference model — **5.31 GB peak memory, PASSED** |

Five sessions remain. At the bound, publish whatever exists and write the M0
outcome ADR regardless of how tempting another parameter looks.

---

## Immediate next steps

1. Record the exact command used for the §A4b full training run (resolution,
   splat cap) and `shasum -a 256` its output PLY — required by AGENTS.md rule 6
   before that entry counts as complete.
2. Global-mapper benchmark on a copied feature database, for the P4 comparison
   point against the incremental-mapper result already in §A1–A3.
3. Convert the §A4b PLY to `.sog`, open on Mac and iPhone, record §A5.
4. Confirm whether `view_graph_calibrator` is present in this COLMAP build.
5. Pin SplatTransform's version string (its `--help` opens with a banner).
6. Only then record the two Gate B captures per `docs/capture-guide.md`.

`docs/mac-runbook.md` has the copy-paste commands for every step above.
