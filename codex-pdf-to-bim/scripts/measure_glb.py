"""Measure a built tour GLB against the A-1 trace.

The point of this script: everything else in the pipeline checks the spec or a
stub, all inside one coordinate frame, so those checks can agree with each other
and still disagree with the drawing. This reads the exported artifact itself and
reports where things actually ended up, in glTF world space.

    uv run python scripts/measure_glb.py <glb>
    uv run python scripts/measure_glb.py <glb> --spec spikes/tour_quality/a1_kitchen_scene_spec.json

With --spec it does the thing the pipeline was missing: for every landmark the
spec places, it reports where the exported artifact actually put it and how far
that is from the traced position. Checking the spec against itself is what let
three separate placement bugs ship looking green.
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import trimesh

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "services"))
from hearthview.chirality import matches_drawing, model_turn, plan_turn

FT = 0.3048
# The authoring frame is (x east, y north, z up) and Blender exports it Y-up as
# (x, z, -y). So in the artifact +x is east and -z is north.
WANTED = (
    "HV_SINK_RIM", "HV_RANGE_BODY", "HV_REFRIGERATOR_BODY", "HV_DISHWASHER_BODY",
    "HV_ISLAND_STRUCTURE", "HV_TV_SCREEN", "HV_FLOOR",
)
TOLERANCE = 0.15   # metres; below this a difference is builder detail, not drift


def to_gltf(point: tuple[float, float]) -> tuple[float, float]:
    """Authoring plan coords (east, north) to the glTF ground plane (x, z)."""
    return (point[0], -point[1])


def expected_from_spec(spec: dict) -> dict[str, tuple[float, float]]:
    """Where the trace says each landmark belongs, in glTF ground coordinates.

    Every entry is derived from the spec rather than written down here, so this
    keeps working for any region on any floor the extractor emits.
    """
    envelope = spec["envelope"]
    kitchen = spec["kitchen"]
    north, west = kitchen["north_run"], kitchen["west_run"]
    depth = kitchen["counter_depth"]
    arm_north = envelope["arm_north"]
    island = kitchen["island"]
    main = next(s["rect"] for s in spec["slabs"] if s["name"] == "MAIN")

    return {
        "HV_SINK_RIM": to_gltf((north["sink"]["center_x"], arm_north - 0.37)),
        "HV_DISHWASHER_BODY": to_gltf(
            (north["dishwasher"]["center_x"], arm_north - (depth - 0.04) / 2)),
        "HV_RANGE_BODY": to_gltf(((depth - 0.02) / 2, west["range"]["center_y"])),
        "HV_REFRIGERATOR_BODY": to_gltf(
            ((west["fridge"]["depth"] - 0.015) / 2, west["fridge"]["center_y"])),
        "HV_ISLAND_STRUCTURE": to_gltf(
            ((island[0] + island[2]) / 2, (island[1] + island[3]) / 2)),
        "HV_TV_SCREEN": to_gltf(
            (spec["living"]["tv"]["line"] - 0.055, spec["living"]["tv"]["center_y"])),
        "HV_FLOOR": to_gltf(((main[0] + main[2]) / 2, (main[1] + main[3]) / 2)),
    }


def report_against_spec(found: dict[str, "np.ndarray"], spec: dict) -> bool:
    """Print the artifact-versus-trace diff. True when everything is in place."""
    expected = expected_from_spec(spec)
    print("\n--- artifact vs trace (glTF ground plane, metres) ---")
    print(f"  {'landmark':<24} {'traced x,z':>18} {'built x,z':>18} {'off by':>8}")
    worst = 0.0
    missing: list[str] = []
    for name, (ex, ez) in sorted(expected.items()):
        if name not in found:
            missing.append(name)
            print(f"  {name:<24} {ex:8.2f},{ez:8.2f} {'NOT IN GLB':>18}")
            continue
        bx, bz = float(found[name][0]), float(found[name][2])
        offset = ((bx - ex) ** 2 + (bz - ez) ** 2) ** 0.5
        worst = max(worst, offset)
        flag = "  <-- off" if offset > TOLERANCE else ""
        print(f"  {name:<24} {ex:8.2f},{ez:8.2f} {bx:8.2f},{bz:8.2f} {offset:8.2f}{flag}")
    ok = not missing and worst <= TOLERANCE
    print(f"  => worst offset {worst:.2f} m "
          f"({'within' if worst <= TOLERANCE else 'OUTSIDE'} the {TOLERANCE:.2f} m tolerance)"
          + (f", {len(missing)} landmark(s) missing" if missing else ""))
    return ok


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
    args = sys.argv[1:]
    spec_path: Path | None = None
    if "--spec" in args:
        index = args.index("--spec")
        if index + 1 >= len(args):
            print(__doc__.strip())
            return 2
        spec_path = Path(args[index + 1])
        args = args[:index] + args[index + 2:]
    if len(args) != 1:
        print(__doc__.strip())
        return 2
    scene = trimesh.load(Path(args[0]), force="scene", process=False)
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

    if spec_path is not None:
        import json

        if not report_against_spec(found, json.loads(spec_path.read_text())):
            return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
