# HearthView

HearthView is a local-first homeowner tool that turns the supplied Garrigan proposed first-floor PDF into a guided, exact 3D model and a Blender-ready photoreal rendering. It is designed to feel like a calm renovation companion rather than BIM software.

This implementation lives entirely in `codex-pdf-to-bim/`, separate from the other app and Claude's parallel work.

## Start HearthView

Requirements:

- Python 3.12 or newer
- Node.js 24 or newer
- `uv` and `npm`
- Blender LTS only when you want the final photoreal PNG

From this folder:

```bash
uv sync
npm install
npm run doctor
npm run dev
```

Open the local address printed by the launcher, normally `http://127.0.0.1:5178`. The launcher starts both the browser app and its private local API, chooses available ports when the defaults are busy, and shuts both down together with `Ctrl-C`.

## Homeowner workflow

1. Choose **Add plan PDFs** and select the four-page Garrigan architectural PDF.
2. Verify that sheet A-1 is the proposed first-floor layout.
3. Confirm five plain-language details: the proposed region, island size, east wall order, south opening, and TV location.
4. Open the verified 3D model and orbit, zoom, or choose plan, overview, kitchen, and living-room cameras.
5. Click model elements to see their A-1 source evidence.
6. Choose **Create a polished render** for the Warm Blank Slate look: lightly furnished, warm, neutral, and intentionally generic.
7. Open the report to see the PDF, reviewed-model, and geometry fingerprints used for every view.

All plan bytes, decisions, models, and images remain on this Mac. Runtime data defaults to `work/hearthview-data/`; set `HEARTHVIEW_DATA_DIR` to use another local folder.

## Photoreal rendering

Interactive 3D works without Blender. Final rendering uses the exact same compiled GLB in a locked `HV_CANONICAL` collection, while materials, generic furniture, cameras, and lighting live separately.

Install Blender LTS and make its `blender` executable available on `PATH`. Alternatively, set an explicit local executable before starting HearthView:

```bash
export HEARTHVIEW_BLENDER="/Applications/Blender.app/Contents/MacOS/Blender"
npm run doctor
npm run dev
```

Draft renders use Eevee. Final renders use Cycles with denoising. The app preserves settings and an actionable log if Blender times out or fails.

## Accuracy and scope

HearthView stores architectural dimensions as signed integer ticks at exactly 1/1024 inch. Validation blocks 3D compilation until the five required A-1 facts are confirmed and the island, wall intervals, openings, TV anchor, and provenance all pass exact checks. A model-bound validation token prevents stale or changed geometry from compiling.

The current complete vertical slice intentionally interprets the supplied Garrigan A-1 proposed first floor. It does not pretend to perform general automatic reconstruction of arbitrary plan sets, roofs, stairs, attic options, or permit drawings. Those larger phases are described in `docs/superpowers/specs/2026-08-18-hearthview-design.md`.

This is a homeowner visualization, not a permit set, construction document, structural review, field measurement, or as-built record.

## Verification

```bash
npm test
npm run build
npm run doctor
```

For the real PDF browser journey:

```bash
npx playwright install chromium
HEARTHVIEW_GARRIGAN_PDF="/absolute/path/to/Garrigan plans.pdf" npm run test:e2e
```

The backend suite covers exact-unit properties, immutable content storage, append-only review events, validation tokens, deterministic GLB compilation, source APIs, and the safe Blender command contract. The frontend suite covers labels, tooltips, corrective errors, import, plan choice, guided review, stable cameras, source clickback, render prerequisites, and the report.
