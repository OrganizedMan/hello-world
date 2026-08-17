# ADR 0001: SfM pipeline — COLMAP feature, matcher, mapper and resolution defaults

**Status:** Proposed. The decision is deliberately **deferred** to M0 Gate B
evidence; this ADR records the candidate space and the rule for choosing.

**Date:** 2026-08-17

## Context

Amber needs camera poses from a single hand-held iPhone video before any
Gaussian training can happen. The pose stage is the plan's identified
high-risk stage: the trainer is cheap to replace, the pose pipeline is not.

Four choices interact and must not be conflated in a comparison:

1. feature extractor (SIFT vs. COLMAP-native ALIKED);
2. matcher (sequential + loop detection vs. LightGlue via ONNX);
3. mapper (incremental `mapper` vs. built-in `global_mapper`);
4. pose image resolution — and critically, the *effective* resolution, since
   COLMAP 4.x reports `FeatureExtraction.max_image_size=3200`, so a 4K input is
   silently reduced unless that limit is raised.

## Decision

**Deferred.** The implementation ships all four axes as configuration
(`PoseConfig`), defaults to the most robust documented path — SIFT +
sequential matcher with loop detection + incremental mapper — and records
requested versus effective image size on every run.

The production defaults will be set by the M0 Gate B matrix (P1–P5 in
`docs/m0-experiment-plan.md` §6), selected on:

1. pass/fail against the conjunctive pose gate (§7), then
2. registered-evaluation coverage, then
3. held-out PSNR/SSIM over the common registered-evaluation intersection, then
4. wall-clock cost on the 16 GB MacBook Air.

Criterion 1 is disqualifying, not weighted. Cost never outranks gate passage.

Interim defaults shipped in code, marked provisional:

| Axis | Provisional default | Why |
| --- | --- | --- |
| Feature | SIFT | COLMAP's most tested path; no ONNX runtime dependency |
| Matcher | `sequential_matcher` + loop detection | Correct prior for video; loop detection recovers revisits |
| Mapper | `mapper` (incremental) | COLMAP documents it as most robust and well-tested |
| Camera model | `OPENCV` | Permits radial distortion; a pinhole assumption is wrong for a phone lens |
| Pose long edge | source, with `max_image_size` raised to match | Prevents a silent internal downscale; benchmarked in P1–P3 |
| Training long edge | 1600 | Fits the 16 GB budget; independent of the pose tier |

## Alternatives

- **Global mapper as the default.** It absorbs GLOMAP and can be much faster,
  but it leans on good focal-length priors and is less outlier-robust. It is
  benchmarked (P4) on a *copy* of the same feature database so the comparison
  isolates the mapper. Rejected as default *for now* — and explicitly rejected
  as an automatic fallback when the incremental mapper fails, since failure
  there usually means a bad view graph, which the global mapper does not fix.
- **ALIKED + LightGlue as the default.** Learned features help on difficult
  texture and illumination, but they cannot create correspondence on a blank
  wall, and they add an ONNX runtime path whose Apple-silicon behavior is
  unmeasured. Conditioned on SIFT producing an inadequate view graph (P5).
- **hloc or another external matching stack.** Rejected for M0. It is a
  separately justified experiment only if the native options fail.
- **ARKit poses from a custom capture app.** Would remove much of this
  uncertainty and supply real metric scale, but it presupposes a capture app,
  which the plan places after proof that the result is worth preserving.

## Consequences

- The pose backend must expose feature/matcher/mapper/image-size as *separate*
  recorded fields, so a mapper comparison cannot masquerade as a different
  pipeline. Implemented in `PoseConfig`.
- Every run must record the option name, CLI-reported default, requested value,
  and effective dimensions. Implemented in `PoseResult.effective_image_size`.
- Until this ADR reaches Accepted, no document may describe these defaults as
  measured. They are provisional.

## Evidence

None yet. M0 has not been executed — see `docs/m0-experiment-plan.md` §1 for
the missing hardware and toolchain. `docs/feasibility-results.md` holds the
empty tables this ADR will be resolved from.
