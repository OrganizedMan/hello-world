# HearthView tour-quality spike acceptance

**Run date:** 2026-08-21
**Route:** `/tour-spike`
**Artifact label:** Quality spike · visual staging
**Canonical geometry:** No

## Gate results

| Gate | Result | Evidence |
| --- | --- | --- |
| Geometry | Pass | The independent artifact validator accepted the printed dimensions, required scene nodes, walkable metadata, barriers, camera presets, hashes, and payload. |
| Realism | Pass for the spike | The 1920 × 1080 poster and browser scene were inspected at desktop size. Materials load, the layout and openings read clearly, the browser lighting is balanced, and the overhead view removes the ceiling instead of clipping through it. |
| Navigation | Pass | Orbit, a clearance-safe Move here landing, person-height Walk, Escape and Exit walk recovery, Overhead, and Reset were exercised in the real browser. The focused navigation suite and Playwright acceptance also pass. |
| Performance | Pass on the target local Mac | The 24,604,690-byte payload became usable in 8,770 ms in the in-app hardware browser at 1280 × 720, below the 45 MB and 10-second targets. |

## Artifact evidence

- GLB: 22,967,336 bytes, SHA-256 `2294ec797f90ece51e92e46625d1954468b447f691b831ca2e2e464eb42c3b18`
- Environment: 1,332,398 bytes, SHA-256 `3c5a3b5efba3de62a845bf21fe7cb88e9657845ea5cf2b90a0158717f19aedfd`
- Poster: 297,876 bytes, SHA-256 `30adb65a5acd2dfdde9e31e0206a866e80b82c14950ba71bf17cd192de818d8f`
- Scene: 110,264 triangles, 305 mesh objects, 30 materials, 26 images

The final browser pass covered a 1280 × 720 desktop viewport and a 390 × 844 compact viewport. No application console errors occurred. Three.js emits one upstream `THREE.Clock` deprecation warning through React Three Fiber; it does not affect interaction or output.

The Playwright acceptance passes in headless Chromium. Its software WebGL run takes about 1.2 minutes and is not used as the target-Mac performance measurement.

## Reproduction

```sh
uv run python -m spikes.tour_quality.validate_artifact \
  --glb apps/web/public/tour-spike/hearthview-kitchen-family.glb \
  --manifest apps/web/public/tour-spike/manifest.json \
  --public-dir apps/web/public/tour-spike

npm test
npm run build
HEARTHVIEW_E2E_API_PORT=50177 \
HEARTHVIEW_E2E_WEB_PORT=50178 \
npm run test:e2e -- tests/e2e/tour-spike.spec.ts
```

The approved overview image is delivered outside the repository as `outputs/hearthview-tour-spike-overview.png`.

## Trust boundary and known staging

The envelope, openings, island placement, printed dimensions, walkable region, and barriers are the measured spike claims. Cabinetry detail, hardware, finishes, furniture, decor, and undimensioned offsets remain provisional visual staging. The display GLB is not a canonical HearthView geometry artifact and is not suitable for permits, construction, or field verification.
