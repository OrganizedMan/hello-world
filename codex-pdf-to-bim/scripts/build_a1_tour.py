"""Build the whole traced first floor and measure it against the drawing.

Writes into `apps/web/public/tour-a1/`, served by the browser at
`/tour/first-floor`. That is deliberately *not* `tour-spike/`: both tours write
a file called `manifest.json`, and while they shared a folder whichever ran last
silently replaced the other's.

Unlike the kitchen checkpoint this needs no Blender -- `a1_tour` writes the GLB
itself -- so it runs anywhere the drawings do.

Usage:
    uv run python scripts/build_a1_tour.py [path-to-drawing.pdf]
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "services"))

from hearthview.a1_extract import extract_a1
from hearthview.a1_massing import build_a1_massing
from hearthview.a1_tour import build_tour
from hearthview.drawings import a1_source

OUTPUT = REPO / "apps/web/public/tour-a1"
SHARED = REPO / "apps/web/public/tour-spike"
FT = 0.3048


def main() -> int:
    source = Path(sys.argv[1]) if len(sys.argv) > 1 else a1_source()
    if source is None or not source.is_file():
        print("No drawing set. Pass a PDF path or commit drawings/.")
        return 1

    extraction = extract_a1(source)
    massing = build_a1_massing(extraction)
    tour = build_tour(extraction, massing)

    OUTPUT.mkdir(parents=True, exist_ok=True)
    glb_name = tour.manifest["artifact"]["glb"]
    (OUTPUT / glb_name).write_bytes(tour.glb)
    (OUTPUT / "manifest.json").write_text(json.dumps(tour.manifest, indent=2) + "\n")

    # The environment and poster are staging assets, not traced geometry, so
    # they are shared with the kitchen tour rather than rebuilt.
    for shared in (tour.manifest["artifact"]["environment"], tour.manifest["artifact"]["poster"]):
        if not (OUTPUT / shared).exists() and (SHARED / shared).exists():
            shutil.copy2(SHARED / shared, OUTPUT / shared)

    envelope = tour.manifest["envelope"]
    print(f"wrote {glb_name} ({len(tour.glb):,} bytes) -> {OUTPUT}")
    print(f"  primitives  {len(massing.primitives)}")
    print(f"  ceiling     {massing.ceiling.note}")
    print(f"  verified    {massing.verified_fraction:.1%} of solids on a measured dimension")
    print(
        "  envelope    "
        f"{(envelope['max_x'] - envelope['min_x']) / FT:.1f} x "
        f"{(envelope['max_z'] - envelope['min_z']) / FT:.1f} x "
        f"{(envelope['max_y'] - envelope['min_y']) / FT:.1f} ft"
    )

    # Measure the artifact, not the plan that produced it. A build that is not
    # checked against the drawing is not finished (docs section 3).
    print()
    return subprocess.call(
        [sys.executable, str(REPO / "scripts/measure_a1_tour.py"), str(OUTPUT / glb_name)]
    )


if __name__ == "__main__":
    raise SystemExit(main())
