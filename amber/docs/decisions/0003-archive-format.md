# ADR 0003: Scene archive layout, regenerability invariant, and retention classes

**Status:** Accepted

**Date:** 2026-08-17

## Context

A capture produces far more bytes than it keeps: candidate frames, two derived
image tiers, evaluation frames, a COLMAP database and mapper intermediates,
trainer checkpoints, a PLY master, and a compressed delivery file. On a 16 GB
MacBook Air with a modest SSD, this fills the disk quickly. But the plan is an
*archival* tool — deleting the wrong thing destroys the memory's provenance.

The archive must therefore answer two questions mechanically: what may be
deleted, and what does deleting it cost to undo.

## Decision

Adopt the §9 layout, and make the **regenerability invariant** the sole test
for whether something may live under `working/`:

> Everything under `working/` must be functionally reconstructable from
> `source/original.mov`, the complete `manifest.json` recipe, and the pinned
> toolchain. "Functionally reconstructable" does not require bit-identity,
> because some dependencies are nondeterministic. Anything failing this test
> belongs in the archival core.

Every artifact carries a **retention class**:

| Class | Meaning | Prunable |
| --- | --- | --- |
| `archival_core` | source, sparse camera model, trained master, current delivery, QA evidence, manifest, checksums | **never** |
| `regenerable` | candidate/pose/training/evaluation image tiers, COLMAP database and intermediates, trainer checkpoints | yes, by explicit action |
| `derived_cache` | thumbnails, contact-sheet intermediates | yes, freely |

Pruning **updates** an artifact entry — status `present` → `pruned`, retaining
path, role, hash, `prior_bytes`, and `regeneration_cost_seconds`. It never
removes the entry, because the entry *is* the recipe.

Two retention profiles, chosen from measured M0 storage data in M1:
**Complete** (retain everything) and **Compact** (prune `regenerable` after
successful finalization). Neither may touch `archival_core`.

Storage is measured, not estimated: every stage records input bytes, output
bytes, and peak temporary bytes into `qa/storage-report.json`. Preflight
free-space estimation uses the closest measured profile, and refuses to start
rather than dying mid-training.

## Alternatives

- **SQLite as the source of truth.** Rejected for now: a scene archive must
  survive without the app. `manifest.json` per scene is the source of truth;
  a gallery may index it later, and SQLite is added only when the gallery
  needs it.
- **Delete pruned artifacts' entries entirely.** Rejected: it erases the
  provenance that justifies the archive existing.
- **Keep everything always.** Rejected as the only option, kept as the
  *Complete* profile. The plan requires a measured default, not a maximal one.
- **Bit-identical regenerability.** Rejected as unachievable: COLMAP's mapper
  and a GPU trainer are not deterministic across runs.

## Consequences

- The prune path needs a genuine integration test proving that removed
  `working/` data regenerates while the archival core and artifact history stay
  intact. Required by M1 exit criteria.
- Pruning must be crash-safe: an interrupted prune leaves either the old or new
  manifest, never a half-written one. Implemented via atomic replace.
- Any new artifact type must declare a retention class at creation, and the
  writer refuses an unclassified artifact.

## Evidence

Layout follows the plan's §9. Retention *defaults* await the M0 storage
measurements — `qa/storage-report.json` for both Gate B captures — which have
not been taken. Prune safety and the atomic-manifest property are covered by
unit tests now.
