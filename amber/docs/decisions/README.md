# Architecture decision records

One line per ADR: number, status, title.

| ADR | Status | Title |
| --- | --- | --- |
| [0001](0001-sfm-pipeline.md) | Proposed | SfM pipeline: COLMAP feature, matcher, mapper and resolution defaults |
| [0002](0002-backend-interfaces.md) | Accepted | Pose and trainer backends behind explicit interfaces |
| [0003](0003-archive-format.md) | Accepted | On-disk scene archive, regenerability invariant, and retention classes |

Status values: **Proposed** (written before evidence, decision deferred),
**Accepted**, **Superseded by NNNN**, **Rejected**.

ADR format: `# ADR NNNN: Title`, then **Status**, **Date**, **Context**,
**Decision**, **Alternatives**, **Consequences**, **Evidence**.

## Awaiting M0 execution

These ADRs are required by the plan but cannot be written honestly until the
M0 measurements exist on the target Mac:

- **0001 must move from Proposed to Accepted** once Gate B selects the feature,
  matcher, mapper, and pose-resolution defaults from measured evidence.
- **M0 outcome ADR (0004)** — proceed / re-scope / stop, written from the
  evidence at the effort bound.
- **Trainer ADR (0005)** — only if a Brush-versus-OpenSplat comparison was
  actually run to answer a concrete backend question.
