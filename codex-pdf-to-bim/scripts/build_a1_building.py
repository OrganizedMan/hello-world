"""Build every drawn storey into one model, and measure it against the sheets.

Writes into `apps/web/public/tour-building/`, served at `/tour/building`.
Each storey becomes its own GLB node so the browser can switch floors.

Needs no Blender. Usage:
    uv run python scripts/build_a1_building.py [path-to-drawing.pdf]
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "services"))

from hearthview.a1_building import build_building
from hearthview.a1_tour import build_building_tour
from hearthview.drawings import a1_source

OUTPUT = REPO / "apps/web/public/tour-building"
SHARED = REPO / "apps/web/public/tour-spike"
FT = 0.3048


def main() -> int:
    source = Path(sys.argv[1]) if len(sys.argv) > 1 else a1_source()
    if source is None or not source.is_file():
        print("No drawing set. Pass a PDF path or commit drawings/.")
        return 1

    building = build_building(source)
    tour = build_building_tour(building)

    OUTPUT.mkdir(parents=True, exist_ok=True)
    glb_name = tour.manifest["artifact"]["glb"]
    (OUTPUT / glb_name).write_bytes(tour.glb)
    (OUTPUT / "manifest.json").write_text(json.dumps(tour.manifest, indent=2) + "\n")
    for shared in (tour.manifest["artifact"]["environment"], tour.manifest["artifact"]["poster"]):
        if not (OUTPUT / shared).exists() and (SHARED / shared).exists():
            shutil.copy2(SHARED / shared, OUTPUT / shared)

    print(f"wrote {glb_name} ({len(tour.glb):,} bytes) -> {OUTPUT}")
    for storey in building.storeys:
        print(f"  {storey.sheet}  {storey.name:13s} floor {storey.base_inches / 12:6.2f} ft   "
              f"ceiling {storey.ceiling_inches / 12:4.2f} ft   "
              f"{len(storey.primitives):3d} primitives")
    print(f"  total       {len(building.primitives)} primitives, "
          f"{building.verified_fraction:.1%} on a measured dimension")

    print()
    return subprocess.call([
        sys.executable, str(REPO / "scripts/measure_a1_tour.py"),
        str(OUTPUT / glb_name), "--building",
    ])


if __name__ == "__main__":
    raise SystemExit(main())
