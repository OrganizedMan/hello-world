# PDF-to-3D — Stage 0

The tool described in [`docs/plan/pdf-to-3d-development-plan.md`](../docs/plan/pdf-to-3d-development-plan.md): PDF floor plans → a deterministic, validated 3D model. This directory is the implementation; it lives alongside an unrelated app (ZeroBudget, at the repo root) in the same repo.

**What's here today (Stage 0 / Sprint 2):** the family room from the Garrigan fixture, hand-traced, solved by a real constraint solver, built into validated solid geometry, hashed, and served to a browser UI that shows it next to the source PDF page. No PDF extraction yet (Stage 1) — the walls are typed in, exactly like a human would with the calibrate-and-trace UI this stands in for.

## Run it

```bash
# once
pip install -r requirements-dev.txt
for p in packages/*/; do pip install -e "$p"; done
cd packages/ui && npm install && cd ../..

# every time
./tools/run_dev.sh
```

Then open **http://127.0.0.1:5173/**. You should see the source PDF page, a live 3D model you can orbit with the mouse, a wall-by-wall opening inventory, and a validation report — all built from the same locked geometry hash shown in the header.

## Layout

| Package | What |
|---|---|
| `units` | Exact int64-nanometre feet-inches/fraction parsing |
| `core_schema` | The canonical entities (plan §5) — the topology invariant that makes the reported render failure unrepresentable lives here |
| `ingest` | PDF open/rasterize + capability-tier detection (Tier A/B/C, plan §1) |
| `store` | The project `.g3d` SQLite file |
| `constraints` | The linear solver + well/under/over/contradictory diagnosis (plan §8) |
| `geometry` | manifold3d solid construction + the deterministic geometry hash |
| `validate` | The blocking validation report (plan §12) |
| `fixtures_garrigan` | The hand-traced family room fixture — the Sprint 2 proof |
| `server` | FastAPI, exposes all of the above to the browser |
| `ui` | React + Three.js + pdf.js viewer |

## Test

```bash
python3 -m pytest          # everything, including a live-browser smoke test
python3 tools/run_assertions.py   # the plan §16 assertion suite
```
