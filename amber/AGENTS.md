# AGENTS.md — Amber non-negotiables

Canonical rules for anyone (human or agent) working in this repository.
The long development plan is reference material; this file is standing context.

## Authenticity

1. Preserve the untouched source video and its SHA-256. Never modify or delete it.
2. Never apply generative completion. Any future inpainting must be opt-in,
   separately stored, and visibly labeled.
3. A user must always be able to distinguish captured evidence from
   reconstructed estimate.

## Locality

4. Keep all processing local. Never add cloud processing implicitly.
5. The pipeline must work with networking disabled.

## Reproducibility

6. Pin and record every external tool version and its reported capabilities.
   `amber doctor` is the source of truth for what is installed.
7. Record the full command line and normalized config of every subprocess stage
   in the manifest.

## Pose and training discipline

8. Gate training on a healthy, recorded pose solution. The gate in
   `docs/m0-experiment-plan.md` is **conjunctive** — every condition must pass.
   A gate threshold is predeclared, never recomputed from a run's own output.
9. Keep full-resolution **pose images** separate from downsampled
   **training images**. They are independent tiers.
10. Keep evaluation RGB frames out of Gaussian supervision. Evaluation frames
    may participate in pose estimation; they may never supervise training.
    Brush can only render an evaluation set it selected itself, so this is
    enforced by aligning its stride selection to the locked split and verifying
    the result both before and after training (ADR 0004) — not by hiding the
    frames. Never downgrade either check to a warning.
11. Never change the evaluation split of a scene that already has a training or
    metric artifact. A deliberate new split creates a new run/version and
    invalidates rather than overwrites prior metrics.
12. Keep **pose masks** and **training masks** separate. Pose masks say
    "distrust this region for camera solving". Training masks say
    "delete this from the scene".

## Archive integrity

13. Treat `working/` as regenerable from `source/original.mov`, the manifest
    recipe, and the pinned toolchain. Anything not regenerable under that
    contract belongs in the archival core.
14. The archival core — `source/`, `master/` incl. the sparse camera model,
    `delivery/`, `qa/`, `manifest.json`, `checksums.sha256` — is never pruned.
15. Pruning updates artifact status; it never erases an artifact's recipe, hash,
    prior byte count, or regeneration cost.

## Structure

16. Put swappable pose and trainer components behind explicit interfaces
    (`PoseBackend`, `TrainerBackend`).
17. Do not build later-milestone UI before the M0/M1 gates pass. No gallery,
    no native app, no capture app, no 4D, no Gabor backend.
18. Record architecture or dependency changes in `docs/decisions/` **before**
    implementing them. ADR format: `# ADR NNNN: Title`, then **Status**,
    **Date**, **Context**, **Decision**, **Alternatives**, **Consequences**,
    **Evidence**. Keep `docs/decisions/README.md` as a one-line index.

## Evidence

19. Do not record a measurement that was not taken. An unrun stage is reported
    as not run, never as an estimate.
20. Do not set runtime, file-size, or frame-rate promises until M0 and M2
    establish real measurements on the target devices.
