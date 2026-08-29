# Third-party dependencies

Per §18 of the development plan, a formal license inventory is deferred
distribution work, not an M0/M1 deliverable. This file records what Amber
depends on so that distribution stays possible later.

Nothing here has been reviewed for distribution. Before distributing Amber,
review each license against how the tool is actually built, linked, and shipped.

## External tools (invoked as subprocesses, not linked)

| Tool | Purpose | License (to verify before distribution) |
| --- | --- | --- |
| FFmpeg / FFprobe | video probing and frame decoding | LGPL or GPL depending on build flags — the effective obligation depends on how the binary was built |
| COLMAP | camera poses, sparse reconstruction | BSD |
| Brush | Gaussian-splat training | Apache-2.0 |
| SplatTransform | delivery-format conversion | MIT |
| SuperSplat / PlayCanvas (M2) | local viewer and cleanup editor | MIT |
| OpenSplat (not implemented) | alternative trainer | AGPL-3.0 — note the copyleft implication before enabling |

Exact versions are not pinned here yet. M0 Gate A records the versions it
proves, and those become the pins; inventing a pin before measuring would be a
fiction. `amber doctor --json` captures the installed versions of a given
machine, and every run records its tool versions in `manifest.json`.

## Python dependencies

| Package | Purpose | License |
| --- | --- | --- |
| numpy | frame scoring, PSNR/SSIM | BSD-3-Clause |
| pillow | image loading and resampling | MIT-CMU |
| pytest (dev only) | tests | MIT |

## Data

The M0 public control scene (COLMAP South Building, or the ETH3D fallback)
carries its own license, which must be recorded verbatim in
`docs/feasibility-results.md` at download time. Private captures are never
committed to this repository.
