"""Measure a built tour GLB against the A-1 trace.

The point of this script: everything else in the pipeline checks the spec or a
stub, all inside one coordinate frame, so those checks can agree with each other
and still disagree with the drawing. This reads the exported artifact itself and
reports where things actually ended up, in glTF world space.

    uv run python scripts/measure_glb.py apps/web/public/tour-spike/hearthview-kitchen-family.glb
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import trimesh

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "services"))
from hearthview.chirality import matches_drawing, model_turn, plan_turn

FT = 0.3048
# glTF Y-up: +x, +z horizontal, +y up. A plan point (east, south) exports to
# (east, ., -south), so -z is south and +x is east *if* the scene is authored
# in Blender's own convention.
WANTED = (
    "HV_SINK_RIM", "HV_RANGE_BODY", "HV_REFRIGERATOR_BODY", "HV_DISHWASHER_BODY",
    "HV_ISLAND_STRUCTURE", "HV_TV_SCREEN", "HV_FLOOR",
)


def centres(scene: trimesh.Scene) -> dict[str, np.ndarray]:
    found: dict[str, np.ndarray] = {}
    for name, geometry in scene.geometry.items():
        for node in scene.graph.nodes_geometry:
            transform, geom_name = scene.graph[node]
            if geom_name != name:
                continue
            key = next((w for w in WANTED if w in node or w in name), None)
            if key is None:
                continue
            bounds = trimesh.transform_points(geometry.bounds, transform)
            found.setdefault(key, bounds.mean(axis=0))
    return found


def main() -> int:
    if len(sys.argv) != 2:
        print(__doc__.strip())
        return 2
    scene = trimesh.load(Path(sys.argv[1]), force="scene", process=False)
    found = centres(scene)

    lower, upper = scene.bounds
    print(f"world bounds  x {lower[0]:7.2f}..{upper[0]:7.2f}   "
          f"y {lower[1]:6.2f}..{upper[1]:6.2f}   z {lower[2]:7.2f}..{upper[2]:7.2f} (m)")
    print(f"footprint     {(upper[0]-lower[0])/FT:.2f} x {(upper[2]-lower[2])/FT:.2f} ft, "
          f"{(upper[1]-lower[1])/FT:.2f} ft tall\n")

    for key in WANTED:
        if key in found:
            x, y, z = found[key]
            print(f"  {key:<24} x={x:7.2f} z={z:7.2f}  (y={y:5.2f})")
        else:
            print(f"  {key:<24} NOT FOUND")

    needed = {"HV_SINK_RIM", "HV_RANGE_BODY", "HV_ISLAND_STRUCTURE"}
    if needed <= found.keys():
        print("\n--- chirality ---")
        sink, rng, island = (
            (float(found[k][0]), float(found[k][2]))
            for k in ("HV_SINK_RIM", "HV_RANGE_BODY", "HV_ISLAND_STRUCTURE")
        )
        sink, rng, island = tuple(sink), tuple(rng), tuple(island)
        same = matches_drawing(sink, rng, island)
        print(f"  drawing turn {plan_turn():+8.2f}   "
              f"model turn {model_turn(sink, rng, island):+8.2f}")
        print(f"  => {'MATCHES the drawing' if same else 'MIRRORED versus the drawing'}")

        if same and {"HV_TV_SCREEN"} <= found.keys():
            island_pt = found["HV_ISLAND_STRUCTURE"]
            viewer = found["HV_TV_SCREEN"].copy()
            viewer[1] = island_pt[1]
            facing = island_pt - viewer
            facing[1] = 0.0
            right = np.array([-facing[2], 0.0, facing[0]])
            offset = found["HV_SINK_RIM"] - viewer
            offset[1] = 0.0
            side = float(np.dot(offset, right))
            print(f"  from the TV wall across the island, the sink is on the "
                  f"{'RIGHT' if side > 0 else 'LEFT'} (A-1 says RIGHT)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
