"""Emit the A-1 first-floor tour artifact into the web app's public folder.

Usage:
    uv run python scripts/build_a1_tour.py <path-to-A-1.pdf>
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "services"))

from hearthview.a1_extract import extract_a1
from hearthview.a1_massing import build_a1_massing
from hearthview.a1_tour import build_tour

OUTPUT = Path(__file__).resolve().parents[1] / "apps/web/public/tour-spike"


def main() -> int:
    if len(sys.argv) != 2:
        print(__doc__.strip())
        return 2
    source = Path(sys.argv[1])
    if not source.is_file():
        print(f"No such PDF: {source}")
        return 1

    extraction = extract_a1(source)
    massing = build_a1_massing(extraction)
    tour = build_tour(extraction, massing)

    OUTPUT.mkdir(parents=True, exist_ok=True)
    (OUTPUT / tour.manifest["artifact"]["glb"]).write_bytes(tour.glb)
    (OUTPUT / "manifest.json").write_text(json.dumps(tour.manifest, indent=2) + "\n")

    envelope = tour.manifest["envelope"]
    print(f"wrote {tour.manifest['artifact']['glb']} ({len(tour.glb):,} bytes)")
    print(f"  primitives  {len(massing.primitives)}")
    print(f"  ceiling     {massing.ceiling.note}")
    print(f"  verified    {massing.verified_fraction:.1%} of solids on a measured dimension")
    print(
        "  envelope    "
        f"{(envelope['max_x'] - envelope['min_x']) / 0.3048:.1f} x "
        f"{(envelope['max_z'] - envelope['min_z']) / 0.3048:.1f} x "
        f"{(envelope['max_y'] - envelope['min_y']) / 0.3048:.1f} ft"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
