# Architecture

## Boundary

| Layer | Responsibility |
| --- | --- |
| Python orchestrator (`amber/`) | project state, subprocesses, diagnostics, quality reports |
| External pinned tools | FFmpeg, COLMAP, Brush, SplatTransform |
| Viewer (M2, not built) | TypeScript with locally bundled PlayCanvas/SuperSplat |
| UI | CLI first; a small local web interface only after the golden path is proven |

`manifest.json` is the source of truth. There is no database — a scene archive
must survive without Amber installed. SQLite arrives only if the gallery needs
an index, and even then the manifests stay authoritative.

## Modules

```
amber/
  cli.py                     doctor, process, inspect, retry, prune, list
  config.py                  profiles + thresholds loaded from the frozen plan
  events.py                  structured events; plain-language stage names
  models.py                  manifest, artifacts, frames, splits, gate results
  tools.py                   tool discovery, subprocess execution, failure parsing
  pipeline/
    import_video.py          ffprobe metadata, footage health
    frames.py                decode, score, eligibility, splits, image tiers
    poses.py                 the conjunctive pose gate
    quality.py               PSNR/SSIM, comparison groups, motion review
    package.py               PLY master, delivery derivatives
    run.py                   stage orchestration
  backends/
    poses/{base,colmap,colmap_model}.py
    trainers/{base,brush,opensplat}.py
  services/
    projects.py              archive layout, atomic writes, checksums
    jobs.py                  stage state: atomic, resumable, crash-safe
    storage.py               byte accounting, preflight, safe pruning
```

Not built yet, by design (AGENTS.md rule 17): `services/lan_share.py`,
`web/api.py`, and `viewer/` are Milestone 2–3 scope and wait on the M0/M1 gates.

## The stage machine

`import → frames → poses → train → quality → package`

Each stage commits atomically to `working/state.json`. A stage found `running`
at load time is reset to `pending`, because a process that died mid-stage did
not finish. `amber retry --from <stage>` invalidates that stage *and everything
downstream*, since downstream results derive from it.

## Three invariants worth understanding

**Pose images and training images are separate tiers.** Pose estimation runs at
source resolution; training runs downsampled to fit 16 GB. Coupling them would
let the trainer's memory budget degrade the camera solution, which is the one
thing training cannot recover from.

**Evaluation frames are pose inputs but never training inputs.** They must be
registered so their cameras exist to render from, and they must never supervise
optimisation. This is enforced structurally rather than by trust: the trainer
receives a dataset view that physically contains neither the evaluation images
nor their cameras, while the canonical model on disk keeps every camera so the
held-out views stay renderable.

**A split, once locked, cannot move.** If it could change after training, a
metric would describe an experiment that no longer exists. A deliberate new
split creates a new run and invalidates the prior metrics rather than
overwriting them.

## The pose gate

Conjunctive: nine conditions, all of which must pass. There is no weighted
score, so eight excellent statistics cannot outvote one failure. Thresholds are
loaded from `docs/m0-thresholds.json`, which mirrors the frozen experiment plan
— a threshold is never recomputed from the run it judges. A unit test asserts
the JSON and the plan agree.

## Backends

`PoseBackend` and `TrainerBackend` share the same three-method shape:
`doctor()`, the work method, and `cancel()`. Four rules keep the abstraction
honest (ADR 0002): capabilities are discovered from the installed binary, config
axes are recorded independently so a single-axis comparison stays single-axis,
progress goes through an injected event sink, and a backend never silently falls
back to a slower path or silently drops a setting its build cannot honour.

`OpenSplatBackend` is registered but raises on use. Enabling it requires a
trainer ADR stating the concrete question it answers.

## Storage

Three retention classes: `archival_core` (never pruned), `regenerable` (pruned
by explicit action), `derived_cache` (freely pruned). Pruning updates an
artifact's status and keeps its hash, prior size, and regeneration cost — the
entry *is* the recipe, so erasing it would destroy provenance.

The manifest is written *before* files are deleted. An interrupted prune can
therefore only leave "recorded as pruned but still present" — wasted space that
`amber prune --repair` finishes — never the reverse, where the manifest claims a
deleted file exists.
