# ADR 0004: Held-out rendering, and how the evaluation split is enforced

**Status:** Accepted, on measured evidence from the M0 Gate A probe.

**Date:** 2026-08-17

## Context

Amber must render every held-out evaluation view and compare it with its source
frame (plan §8.5). Doing so requires two things that turn out to be in tension
with how the trainer works.

`brush --help`, from the installed v0.3.0 build on the target Mac, offers:

```
--eval-split-every <N>    Create an eval dataset by selecting every nth image
--eval-save-to-disk       Save the rendered eval images to disk. Uses export-path
--eval-every <N>          Eval every this many steps
```

There is **no standalone render command**. Brush can only render an evaluation
split that it selected itself, by stride, during a training run.

ADR 0002 and `AGENTS.md` rule 10 are currently satisfied structurally: the
dataset view handed to the trainer contains neither the evaluation images nor
their cameras, so evaluation frames *cannot* supervise optimisation even if the
trainer wanted them to. That is the strongest available guarantee.

It is also, as written, a dead end. With the evaluation frames absent, Brush has
nothing to render, so `stage_quality` fails with
`no held-out renders were available` and the pipeline can never complete. A
guarantee that blocks the pipeline is not a usable guarantee.

## Decision

Hand Brush the full registered dataset and have `--eval-split-every` hold out
precisely the frames Amber locked, then verify the outcome rather than trusting
it.

The probe (see **Evidence**) showed this needs no filename-rewriting scheme at
all, which is simpler and stronger than first proposed:

1. `--eval-split-every N` selects sorted-filename indices **0, N, 2N, …**.
2. Amber's frame IDs are zero-padded and sequential, so filename order in the
   dataset view *is* temporal order.
3. Amber's production split was therefore changed to hold out indices
   0, N, 2N, … rather than N−1, 2N−1, … Both are "every Nth frame by temporal
   order"; only the phase differs, and the original phase was an arbitrary
   choice on Amber's side.

With those aligned, Brush's selection equals Amber's locked split **by
construction**. Two checks make that a guarantee rather than a hope:

- **Before training:** `stride_for_split` derives N from the locked split and
  refuses unless `range(0, total, N)` reproduces the split's positions exactly.
  An unexpressible split fails before a single step runs.
- **After training:** `collect_evaluation_renders` compares the set Brush
  actually rendered against the locked evaluation IDs and **fails on any
  difference**, reporting what was missing and what was unexpected. A missing
  held-out render is evidence about the run, never permission to score a smaller
  test set.

Brush names each render after its source image's stem, so renders come back
already keyed to Amber's frame IDs; they are copied into `qa/evaluation-renders/`
because trainer output is regenerable while QA evidence is archival.

This remains a deliberate weakening of ADR 0002's structural guarantee, and it
should be named as such: enforcement moves from "structurally impossible" to
"performed by the trainer, verified before and after by Amber".

Applicability is limited by what a stride can express:

- `registered_interval` is stride-expressible, so the production path is covered.
- `fixed_candidate_stratified` (32 temporally stratified frames) is **not**
  expressible as a stride, and `stride_for_split` rejects it with that
  explanation. Comparison groups need a renderer that accepts arbitrary cameras.
  Deferred until a comparison group is actually run; an inconclusive comparison
  is an allowed M0 outcome.

## Alternatives

- **Keep structural exclusion and add a separate renderer.** Strongest
  guarantee, and it preserves arbitrary splits. Rejected for now because it
  requires a new, unmeasured dependency capable of rendering a `.ply` from given
  COLMAP cameras. Worth revisiting if MetalSplatter or a SuperSplat headless
  path proves usable, and it is the better long-term answer.
- **Use Brush's own split and accept whatever it holds out.** Rejected
  outright. The split would then be chosen by the trainer rather than
  predeclared and locked, which breaks rules 10 and 11 and makes every metric
  describe an experiment nobody specified.
- **Resume a trained checkpoint for a render-only pass.** No documented flag
  combination in this build supports it; `--start-iter` resumes training rather
  than rendering. Rejected as speculation.
- **Skip held-out metrics and rely on the human rubric.** Rejected: initial
  acceptance criteria require saved held-out renders and metrics, and §8.6
  requires measured fidelity loss for the mobile derivative.

## Consequences

- `BrushBackend.prepare_dataset_view` will include evaluation images, so the
  current leak assertion becomes a *verification of Brush's exclusion* rather
  than a guarantee of absence. The test suite must change to match, and the
  weaker guarantee must be stated in `AGENTS.md` rather than left implied.
- A mismatch between Brush's evaluated set and Amber's locked set is a hard
  failure. This is the check that makes the arrangement acceptable, so it must
  never be downgraded to a warning.
- Comparison groups may remain blocked on rendering until the stratified-split
  question above is settled. That is acceptable: M0 Gate B runs one comparison
  group at most, and an inconclusive comparison is an allowed outcome.
- `--max-splats` defaults to 10,000,000 in this build, well above the 2,000,000
  cap in `TrainConfig`. The cap is therefore doing real work on a 16 GB machine
  and must keep being passed explicitly.

## Evidence

Measured on the target Mac (2025 MacBook Air, 16 GB), Brush v0.3.0
(`brush-app-aarch64-apple-darwin`, cargo-dist release), against the M0 public
control (COLMAP South Building, 128 images, reference model in **text** format):

```bash
brush brush-dataset --export-path ~/amber-control/probe \
  --total-steps 200 --eval-split-every 8 --eval-save-to-disk --max-resolution 800
```

Output: `probe/eval_200/` containing 16 PNGs, plus `probe/export_200.ply`.
Training took **9 s**.

**Finding 1 — stride phase.** The 16 held-out frames were `P1180141, 149, 157,
165, 173, 181, 189, 197, 205, 213, 221`, then `P1180308, 316, 324, 332, 340`.
The dataset is `P1180141–P1180221` (81 files) plus `P1180301–P1180347`
(47 files) = 128. Sorted indices 0, 8, …, 80 give the first eleven; indices 88,
96, 104, 112, 120 give the last five. The discontinuity between 221 and 308 is a
gap in the source numbering, which is what makes this a proof rather than a
coincidence: only an index-based stride starting at **0** reproduces that exact
set. The originally hypothesised offset of N−1 is ruled out.

**Finding 2 — render naming.** Each render is named after its source image's
stem with a `.png` extension, inside `eval_<step>/` beneath `--export-path`. With
multiple evaluation passes there are multiple such directories, so the
highest-numbered one is the final result.

**Finding 3 — flags.** Amber's existing candidates for export path, total steps,
max resolution, SH degree, and splat cap all matched this build exactly. This
build's `--max-splats` default is 10,000,000, so `TrainConfig`'s 2,000,000 cap is
doing real work on a 16 GB machine.

**Finding 4 — headless operation.** Brush runs as a CLI with no window; an
invalid dataset path produced a typed `I/O error while constructing BrushVfs`
rather than launching a GUI. `--with-viewer` is opt-in.

Findings 1 and 2 are the two measurements this ADR was blocked on, so it moves to
Accepted. Record all four in `docs/feasibility-results.md` §A4.
