# HearthView tour-quality spike acceptance

**Run date:** 2026-08-21
**Route:** `/tour-spike`
**Artifact label:** Quality spike · visual staging
**Canonical source alignment:** Yes; the display mesh remains visual staging

## Gate results

| Gate | Result | Evidence |
| --- | --- | --- |
| Geometry | Machine pass; homeowner review pending | The independent validator accepted the canonical model/geometry hashes, printed dimensions, actual GLB floor and island bounds, wall openings, walkable metadata, barriers, cameras, and payload. The north-up overhead view now includes the mudroom and existing-living context needed to compare the transitions with A-1. |
| Realism | Previous spike pass; homeowner review pending | The regenerated 1920 × 1080 poster and browser scene load without missing materials. The user must still approve the rebuilt spatial reading and visual balance. |
| Navigation | Pass | Orbit, Move here, person-height Walk, recovery, Overhead, and Reset pass the fresh Playwright homeowner journey in 13.8 seconds. |
| Performance | Payload pass | The 24,630,985-byte payload is below the 45 MB target. The prior scene became usable in 8,770 ms on the target Mac; a fresh subjective load check remains part of homeowner testing. |

## Artifact evidence

- Canonical model: SHA-256 `a7b695f5ba7099e07c0af714e9c98b18446e4918525521469c870a77193328f6`
- Derived geometry: SHA-256 `eafe8a0af126b56885a526597b15fe7c63184ff0790e9b9420204d6850e7395b`
- GLB: 22,995,428 bytes, SHA-256 `b5a343c87d9b6d1714ad7ec1e4f8e18c1de8f8b69115435ec1dc0c37f57eba78`
- Environment: 1,332,398 bytes, SHA-256 `3c5a3b5efba3de62a845bf21fe7cb88e9657845ea5cf2b90a0158717f19aedfd`
- Poster: 293,020 bytes, SHA-256 `0eb6f0fc962fb4e9657838f9b597e887357bbbfa596ff7426e909eb841fc2036`
- Scene: 111,792 triangles and 315 mesh objects

The final browser pass covered a desktop viewport and visually confirmed that the north-up map matches the overhead render. Three.js emits one upstream `THREE.Clock` deprecation warning through React Three Fiber; it does not affect interaction or output.

The Playwright acceptance passes in headless Chromium in 13.8 seconds. It is not used as the target-Mac performance measurement.

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

## Trust boundary and known staging

The envelope, openings, island placement, printed dimensions, walkable region, and barriers are derived from the canonical A-1 spatial model and are the measured spike claims. Cabinetry detail, hardware, finishes, furniture, decor, and undimensioned offsets remain provisional visual staging. The display GLB carries canonical source hashes for traceability but is not itself a permit, construction, or field-verification artifact.
