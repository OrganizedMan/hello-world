# Troubleshooting

Start with `amber doctor`. It reports what is installed, what each build
actually supports, and what is missing. It exits non-zero until the toolchain is
complete.

## The tools

**"X is not installed or not on PATH"** — install it and re-run `amber doctor`.
Amber does not substitute a different tool or a slower code path, because that
would make the run unattributable.

**COLMAP's `max_image_size` option shows as `null`** — the installed build
exposes neither `FeatureExtraction.max_image_size` nor the older
`SiftExtraction.max_image_size`. Amber will not guess a flag name. Check the
build with `colmap feature_extractor --help`.

**Brush reports `missing_required`** — this build does not expose a flag Amber
needs. Record the actual flags from `brush --help`; do not copy a command from a
tutorial, since a flag a build does not recognise is either an error or silently
ignored.

**A setting was "NOT applied"** — the installed build has no flag for it. Amber
warns rather than dropping it silently, because the recorded config must
describe what actually ran.

## Processing

**"not enough free disk space"** — the estimate is deliberately conservative
while it is marked `unmeasured`; M0 replaces it with a measured multiplier. Free
space, prune working data from an older scene (`amber prune <scene> --working`),
or pass `--skip-space-check` if you know better.

**A stage failed and you want to re-run it** — `amber retry <scene> --from
<stage>`. Everything downstream is invalidated too, since it derives from the
stage you are re-running. Completed upstream stages are not repeated.

**Processing was interrupted** — the archive is intact. A stage that was
mid-flight is reset to pending on the next run; nothing is left half-committed.

**"refusing to train against an unlocked split"** — the split must be locked
before training, or the resulting metrics would describe an experiment that
could still change. This indicates a pipeline bug, not a user error.

**"this scene's evaluation split is locked"** — you are trying to change the
split of a scene that already has training or metric artifacts. That is
forbidden by design. Process the video again as a new scene; the old metrics
stay valid for the old split.

## Pose failures

The pose gate is conjunctive, so `amber inspect <scene> --json` shows every
condition with its value and threshold. See the diagnostic table in
[`capture-guide.md`](capture-guide.md) for what each one means and what to
change when recording.

The most common real cause is the camera not moving enough. No amount of
processing recovers parallax that was never captured.

## Quality

**"no held-out renders were available"** — the evaluation cameras have not been
rendered, so the scene has not been evaluated. Amber refuses to report a quality
result it did not measure. Render the evaluation cameras into
`qa/evaluation-renders/` and `amber retry <scene> --from quality`.

**"the motion-artifact review has not passed"** — the capture may contain
moving subjects (a person, pet, foliage, water), so a human has to look at the
held-out renders and novel-view path before it can be called a success. Record
the verdict in `qa/motion-artifact-review.json` as `pass`, `fail`, or
`not_applicable` with a note and screenshots. Version 1 claims no automatic
motion detector, so this record is the only thing that can decide.

## The archive

**Checksums fail** — `amber inspect <scene> --verify` lists every mismatch or
missing file. Checksums cover the archival core only; working data is
regenerable and deliberately not checksummed.

**An interrupted prune** — `amber prune <scene> --repair` finishes it. The
manifest is always written before files are deleted, so the only possible
in-between state is "recorded as pruned but still on disk".

**What can I safely delete?** — `amber prune <scene> --dry-run` shows exactly
what would go, how many bytes it frees, and what it costs to regenerate. The
source, sparse camera model, trained master, current delivery derivative, QA
evidence, manifest, and checksums are never candidates.
