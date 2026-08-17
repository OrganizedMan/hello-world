# ADR 0004: Held-out rendering, and how the evaluation split is enforced

**Status:** Proposed. Resolved by a Gate A probe; see **Evidence**.

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

**Proposed:** hand Brush the full registered dataset and have
`--eval-split-every` hold out precisely the frames Amber locked, then verify the
outcome rather than trusting it.

Amber writes the dataset view itself and therefore controls the filenames in it.
It will name the view's images so that the locked evaluation frames fall exactly
on the stride positions Brush selects, retaining a view-filename → canonical
frame-ID mapping in the manifest. After training, Amber compares the set of
frames Brush actually evaluated against its locked evaluation IDs and **fails
the stage on any mismatch** — no substitution, no silent shrinking of the test
set.

This is a deliberate weakening, and it should be named as such: enforcement
moves from "structurally impossible" to "performed by the trainer, verified
afterwards by Amber". The verification is what keeps it honest.

Applicability is limited by what a stride can express:

- `registered_interval` with interval 8 is stride-expressible, so the production
  path is covered.
- `fixed_candidate_stratified` (32 temporally stratified frames) is **not**
  expressible as a stride. Comparison groups therefore need either a renderer
  that accepts arbitrary cameras, or a filename ordering trick that maps the
  stratified set onto stride positions. This ADR does not decide that; it is
  deferred until a comparison group is actually run.

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

The flag list above is from `brush --help` on the target Mac, Brush v0.3.0
(`brush-app-aarch64-apple-darwin`, cargo-dist release). Amber's existing flag
candidates for export path, total steps, max resolution, SH degree, and splat
cap all matched this build exactly.

Two measurements are **outstanding** and gate this ADR's move to Accepted. Both
are answered by one short Gate A run against the public control:

```bash
brush brush-dataset --export-path ~/amber-control/probe \
  --total-steps 200 --eval-split-every 8 --eval-save-to-disk --max-resolution 800
```

1. Does Brush order dataset images by filename, and does "every nth" select
   index n−1, 2n−1, …?
2. What filenames does `--eval-save-to-disk` write, and where beneath
   `--export-path`?

Record both in `docs/feasibility-results.md` §A4. Until they are recorded, this
ADR stays Proposed and the implementation is not written — guessing the
answers is what this document exists to prevent.
