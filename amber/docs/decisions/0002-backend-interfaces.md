# ADR 0002: Pose and trainer backends behind explicit interfaces

**Status:** Accepted

**Date:** 2026-08-17

## Context

The plan commits to standard 3DGS via Brush for version 1, while keeping open
the possibility of OpenSplat, a future Gabor backend, or a different pose
engine. Research dependencies in this area change quickly. If the orchestrator
calls tool binaries inline, swapping one means rewriting the pipeline, and a
"backend comparison" silently becomes a comparison of two different pipelines.

## Decision

Define two protocols, each with the same three-method shape, and route all
external reconstruction work through them:

```python
class PoseBackend(Protocol):
    def doctor(self) -> PoseBackendHealth: ...
    def reconstruct(self, frames, masks, config, events) -> PoseResult: ...
    def cancel(self) -> None: ...

class TrainerBackend(Protocol):
    def doctor(self) -> BackendHealth: ...
    def train(self, dataset, config, events) -> TrainResult: ...
    def cancel(self) -> None: ...
```

Rules that make the abstraction meaningful rather than decorative:

1. `doctor()` reports the *discovered* version and capabilities of the
   installed binary. Backends never assume flags from documentation; a flag
   that `doctor()` did not observe is not used.
2. Configuration is a typed object with independently recorded axes, so a
   single-axis comparison stays single-axis.
3. Backends emit progress through an injected `EventSink`; they never print to
   stdout directly, so the CLI and a future local web UI consume identical
   events.
4. `cancel()` must leave the project uncorrupted — stage state is committed
   atomically, so a cancelled stage reverts to its previous committed state.
5. A backend never silently falls back to a slower path. If the expected
   Metal/WebGPU path is unavailable, it fails loudly.

`ColmapPoseBackend` and `BrushBackend` are implemented first.
`OpenSplatBackend` exists as a registered-but-unimplemented entry that raises a
descriptive error, so choosing it is a deliberate act requiring a trainer ADR.

## Alternatives

- **Call the binaries inline in the pipeline.** Less code today. Rejected: it
  makes trainer replacement a pipeline rewrite and makes honest comparison
  hard, which is precisely the risk the plan flags.
- **A plugin system with entry points.** Over-engineered for two backends and
  it weakens version pinning.
- **Wait to abstract until a second backend is genuinely needed.** Normally
  correct, but here the interface also enforces the doctor/record/no-fallback
  discipline, which is valuable with one backend.

## Consequences

- Slight indirection cost on every stage.
- The manifest records `trainer_backend` and `pose_config` separately from the
  resolved command line, so runs stay attributable.
- Adding Gabor later requires a new `TrainerBackend` plus an export/viewer
  path, without touching import, archive layout, or the CLI.

## Evidence

Structural decision; no measurement required. Enforced by unit tests covering
config recording and no-silent-fallback behavior.
