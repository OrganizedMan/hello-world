"""Measure the built whole-floor GLB against the drawing it claims to come from.

The kitchen artifact is checked landmark by landmark, because its GLB exports a
named node per fixture. The whole-floor tour merges everything into one mesh per
material, so there are no nodes to look up -- and a check that cannot open the
artifact proves nothing about it (docs/traced-tour-pipeline.md section 3).

So this compares geometry instead: every primitive the massing places has eight
corners in a known glTF position, and each one must appear in the exported
vertex cloud. That is a far stronger statement than the landmark diff -- 212
boxes rather than 7 points -- and it fails wholesale on a mirrored model, since
a reflection moves every corner that is not on the mirror plane.

    uv run python scripts/measure_a1_tour.py <glb>
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import trimesh

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "services"))
from hearthview.a1_extract import extract_a1
from hearthview.a1_massing import build_a1_massing
from hearthview.a1_tour import _corners
from hearthview.drawings import a1_source

FT = 0.3048
TOLERANCE = 0.002   # metres; below this is float32 storage noise, not drift


def expected_corners(primitives) -> np.ndarray:
    """Every primitive corner, in glTF metres, as the trace places them."""
    return np.array([corner for item in primitives for corner in _corners(item)])


def corner_offsets(glb_vertices: np.ndarray, expected: np.ndarray) -> np.ndarray:
    """Distance from each expected corner to the nearest exported vertex."""
    worst = np.empty(len(expected))
    # Chunked so the pairwise matrix stays small regardless of model size.
    for start in range(0, len(expected), 256):
        block = expected[start:start + 256]
        deltas = glb_vertices[None, :, :] - block[:, None, :]
        worst[start:start + 256] = np.sqrt((deltas ** 2).sum(axis=2)).min(axis=1)
    return worst


def main() -> int:
    if len(sys.argv) != 2:
        print(__doc__.strip())
        return 2
    glb_path = Path(sys.argv[1])
    if not glb_path.is_file():
        print(f"No such GLB: {glb_path}")
        return 1

    source = a1_source()
    if source is None:
        print("No drawing set available; cannot measure against the trace.")
        return 1

    massing = build_a1_massing(extract_a1(source))
    expected = expected_corners(massing.primitives)

    scene = trimesh.load(glb_path, force="scene", process=False)
    vertices = np.vstack([
        trimesh.transform_points(geometry.vertices, scene.graph[node][0])
        for node in scene.graph.nodes_geometry
        for geometry in [scene.geometry[scene.graph[node][1]]]
    ])

    lower, upper = vertices.min(axis=0), vertices.max(axis=0)
    print(f"exported   {len(vertices):,} vertices, {len(massing.primitives)} primitives traced")
    print(f"bounds     x {lower[0]:6.2f}..{upper[0]:6.2f}   "
          f"y {lower[1]:5.2f}..{upper[1]:5.2f}   z {lower[2]:7.2f}..{upper[2]:6.2f} (m)")
    print(f"footprint  {(upper[0]-lower[0])/FT:.1f} x {(upper[2]-lower[2])/FT:.1f} ft, "
          f"{(upper[1]-lower[1])/FT:.1f} ft tall")

    offsets = corner_offsets(vertices, expected)
    missing = int((offsets > TOLERANCE).sum())
    print("\n--- artifact vs trace (every primitive corner) ---")
    print(f"  corners checked   {len(expected):,}")
    print(f"  worst offset      {offsets.max():.4f} m")
    print(f"  outside {TOLERANCE:.3f} m   {missing:,}")

    if missing:
        # Name the worst offenders rather than only counting them.
        order = np.argsort(offsets)[::-1][:5]
        print("  worst corners:")
        for index in order:
            item = massing.primitives[index // 8]
            x, y, z = expected[index]
            print(f"    {item.element_id:<28} {item.part_kind:<10} "
                  f"({x:7.2f},{y:6.2f},{z:8.2f})  off by {offsets[index]:.3f} m")
        print("  => the exported model DISAGREES with the drawing")
        return 1

    print("  => every traced corner is present in the export")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
