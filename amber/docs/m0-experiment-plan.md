# Milestone 0 experiment plan

**Status: FROZEN for execution.** Predeclared 2026-08-17, before any run.

This document is the predeclaration required by §11 of the development plan.
Every threshold here is fixed *before* data is collected. No threshold in this
file may be recomputed from the output of a run it judges. Amendments are
appended to §10 with an explicit statement of which prior comparisons they
invalidate.

Machine-readable mirror: `amber/config.py` loads these thresholds from
`docs/m0-thresholds.json`, so code and plan cannot drift. A test asserts the
JSON matches the values quoted in this document.

---

## 1. Execution status

M0 has **not been executed**. It requires the target hardware:

| Requirement | Needed for | Status |
| --- | --- | --- |
| Apple-silicon Mac, 16 GB (2025 MacBook Air) | every stage | not available in the build container |
| FFmpeg / FFprobe | Gate A1, all decode | not installed |
| COLMAP 4.x | Gate A3, Gate B pose | not installed |
| Brush | Gate A4, Gate B training | not installed |
| SplatTransform | Gate A5, delivery | not installed |
| iPhone 16 Pro + Safari | Gate A5, Gate B viewer trial | not available |
| Two controlled iPhone captures | Gate B | not recorded |

The tooling in this repository is written and unit-tested; `amber doctor`
reports the above as missing rather than assuming them. Results tables in
`docs/feasibility-results.md` are empty and must be filled by real runs.

## 2. Public control (Gate A)

- **Scene:** COLMAP's own *South Building* demo dataset (128 images),
  chosen because it is small, distributed by the COLMAP project for exactly
  this purpose, and ships with a reference reconstruction.
- **Expected registered-image count:** 128 of 128. A control run registering
  fewer than **126** indicates an installation or build problem, not a scene
  problem, and blocks Gate B.
- **License:** to be recorded verbatim in `docs/feasibility-results.md` at
  download time, together with the retrieval URL and date. This plan does not
  assert a license it has not verified.
- **Fallback control** if the above is unavailable: ETH3D `courtyard`
  (undistorted subset). Selecting the fallback is an amendment under §10.

## 3. Capture classes (Gate B)

| Class | Scene | `min_registered_frames` | Rationale for the absolute floor |
| --- | --- | --- | --- |
| `object` | textured tabletop object, full orbit | **80** | Below ~80 views a full 360° orbit leaves angular gaps wider than the plan's overlap contract. Anchored to the control's density per unit of angular sweep. **Labeled assumption** — no directly comparable public control at this capture scale. |
| `room` | small room or outdoor sitting area | **120** | Room-scale captures cover more surface per view and need more views for loop closure. **Labeled assumption.** |

Both floors are provisional and are confirmed or revised by the M0 outcome ADR.

## 4. Candidate extraction recipe

Fixed for every configuration of a given capture:

- Decode rate: **4 fps** from the untouched source.
- Orientation normalized from container metadata; working images
  Rec.709 / SDR; the color transform is recorded in the manifest.
- Candidate images written at source resolution, sRGB PNG.
- Eligibility filter applied before any selection:
  - sharpness (variance of Laplacian) ≥ **0.15 × the capture's median**;
  - clipped-highlight fraction ≤ **0.35**;
  - clipped-shadow fraction ≤ **0.35**.
- Eligibility uses only per-frame statistics, so it is identical across
  configurations and cannot leak configuration choices into the split.

## 5. The fixed comparative split

Policy `fixed_candidate_stratified`, per §8.2 of the plan.

- **Algorithm:** temporal stratification over the eligible candidate pool.
  The pool is ordered by presentation timestamp and divided into
  `n_eval` contiguous strata of equal count; from each stratum the frame
  nearest the stratum midpoint is taken, ties broken by lower frame ID.
- **`split_algorithm_version`:** 1
- **`split_seed`:** 20260817 (recorded; the algorithm above is deterministic
  and does not consume the seed, but the seed is frozen so that any future
  randomized variant is distinguishable).
- **`n_eval`:** 32 reserved evaluation frames per capture.
- **Timing:** reserved after candidate scoring and eligibility, and **before**
  any small/medium/dense selection or any pose configuration run.
- **Freezing:** the ordered evaluation IDs, the algorithm version, the seed,
  and the SHA-256 of the eligible candidate pool are appended to §9 of this
  document and locked before the first configuration runs.
- **Use:** the same 32 frames are added to *every* configuration's
  feature-matching and reconstruction inputs, and to *no* configuration's
  Gaussian supervision.
- **`min_common_evaluation_views`:** **12.** If the intersection of evaluation
  frames registered by every configuration in a comparison group is smaller
  than 12, the comparison is reported **inconclusive**. It is not rescued by
  ranking on the surviving subset.

Training-frame counts below exclude these 32 frames.

## 6. Configuration matrix

Training selections (per capture): **60 / 120 / 240** — small, medium, dense.

Pose configurations, run on the union of (training selection ∪ 32 evaluation):

| ID | Feature | Matcher | Mapper | Pose long edge |
| --- | --- | --- | --- | --- |
| P1 | SIFT | sequential + loop detection | incremental | 1600 (COLMAP default-ish control) |
| P2 | SIFT | sequential + loop detection | incremental | 3200 (current CLI default) |
| P3 | SIFT | sequential + loop detection | incremental | source long edge (4K = 3840) |
| P4 | SIFT | sequential + loop detection | **global** | best of P1–P3 |
| P5 | **ALIKED** | **LightGlue** (ONNX) | incremental | best of P1–P3 |

- P4 runs on a **copy of P1–P3's feature database**, with
  `view_graph_calibrator` run first where the installed COLMAP recommends it.
  The global mapper is a benchmarked alternative, not an automatic fallback.
- P5 runs **only if** the SIFT view graph is inadequate (fails the gate on
  view-graph grounds, not on capture grounds). External matchers such as hloc
  are out of scope for M0 and require an amendment.
- For every run, record the option name, the CLI-reported default, the
  requested value, and the **effective image dimensions the extractor saw**.
  "Near-source" is never assumed.

End-to-end training runs (Brush) are executed only for configurations that
pass the pose gate, and only for the predeclared set: the medium (120)
selection at each surviving pose configuration, plus small (60) and dense (240)
at the single best-scoring pose configuration.

## 7. The conjunctive pose gate

A pose run **passes only when every condition below passes**. There is no
weighted score and no partial pass.

| # | Condition | Threshold | Diagnostic on failure |
| --- | --- | --- | --- |
| 1 | registered / pose-input frames | ≥ **0.80** | `low_registration_ratio` |
| 2 | absolute registered frames | ≥ class floor (§3) | `insufficient_registered_frames` |
| 3 | registered frames in largest connected model | ≥ **0.95** | `fragmented_reconstruction` |
| 4 | longest temporal gap | ≤ **1.5 s** | `temporal_gap_exceeded` |
| 5 | longest run of consecutive missing selected frames | ≤ **5** | `consecutive_frames_missing` |
| 6 | median triangulation angle | ≥ **3.0°** | `insufficient_parallax` |
| 7 | camera-path extent ÷ median scene depth | ≥ **0.05** | `insufficient_translation` |
| 8 | mean reprojection error | ≤ **1.5 px** | `high_reprojection_error` |
| 9 | rendered camera-path review | human `pass` | `camera_path_review_failed` |

Condition 7 is the pure-pan detector required by the test matrix. A capture
that fails **only** condition 6 or 7 reports `insufficient_translation` as the
user-facing cause.

Additionally recorded for every run, and **not** gate conditions:

- reserved-evaluation registration coverage (count and exact IDs);
- sparse point count, median observations per point;
- separate extraction / matching / mapping timings;
- connected-model count.

A run that fails to register an evaluation frame **records the loss**. It never
substitutes a different frame and never shrinks the reserved set.

## 8. Metrics, storage, and review

- **Image metrics:** PSNR and SSIM over held-out evaluation renders, per-view
  and aggregate. LPIPS only if it runs locally without a network fetch.
- **Comparison aggregate:** computed over the common registered-evaluation
  intersection (§5). Each configuration additionally publishes its full
  registered-evaluation metrics and its coverage, so the intersection cannot
  hide a weak pose solution.
- **Storage:** input bytes, output bytes, and peak temporary bytes for every
  stage of both captures, written to `qa/storage-report.json`.
- **Human review:** the §8.5 rubric, with the explicit motion-artifact field
  recorded as `pass` / `fail` / `not_applicable` plus screenshots. Version 1
  claims no automatic motion detector.
- **Object Capture baseline:** on the object scene, run Apple RealityKit
  Object Capture from the same selected images when the API is available, and
  record the mesh-versus-splat comparison as a product baseline, not as an
  interchangeable trainer.

## 9. Frozen per-capture split records

*Appended and locked after each Gate B candidate pool is decoded, before any
configuration runs. Empty until M0 executes.*

### Capture `object-01`

- candidate pool SHA-256: _(pending)_
- eligible candidate count: _(pending)_
- reserved evaluation IDs (ordered, 32): _(pending)_
- locked at: _(pending)_

### Capture `room-01`

- candidate pool SHA-256: _(pending)_
- eligible candidate count: _(pending)_
- reserved evaluation IDs (ordered, 32): _(pending)_
- locked at: _(pending)_

## 10. Effort bound and amendments

**Bound:** six focused working sessions, each at most three hours of active
operator/engineering time — up to **two** for Gate A, **four** for Gate B.
Unattended processing does not count. At most **one** deliberate recapture per
scene.

At the bound, publish the evidence as it stands and write a numbered M0 outcome
ADR choosing **proceed**, **re-scope**, or **stop**. Extending M0 requires that
ADR to state a new hypothesis and a new finite bound first.

**Stopping rule:** stop and do not build app UI if no controlled iPhone capture
passes the conjunctive pose gate, or if a gate-passing capture cannot produce a
visually acceptable splat under the §8.5 rubric.

A configuration is **not** added because a preceding result was disappointing.
Amendments are appended below with date, rationale, and the list of existing
comparisons they invalidate.

### Amendment log

**A1 — 2026-08-17 — COLMAP's feature-extraction size default is not 3200.**

Measured on the target Mac: COLMAP **4.1.1** (Homebrew `4.1.1_3`) reports
`FeatureExtraction.max_image_size` with a CLI default of **`-1`**, meaning no
limit. §6's P2 row is therefore mislabeled: 3200 is *not* "current CLI default"
on this build, and the development plan's §8.2 premise — that a 4K input is
already reduced internally unless the limit is raised — does not hold here.

What changes: the *rationale* for the P1–P3 resolution sweep. It is no longer
"discover and defeat a silent downscale" but "measure whether downscaling pose
images helps or hurts, given that the default is full resolution."

What does not change: the three configurations themselves (1600 / 3200 / source
long edge) remain as predeclared, and every gate threshold is untouched.

**Comparisons invalidated: none.** No pose configuration had been run when this
was measured.

Amber still records the option name, the CLI-reported default, the requested
value, and the effective dimensions for every run, so this correction is visible
per-run rather than only here.
