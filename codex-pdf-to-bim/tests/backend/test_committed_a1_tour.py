"""The committed whole-floor artifact must match the drawing it came from.

Same rule as `test_committed_tour_artifact.py`, applied to the other tour: the
GLB the browser is served gets opened and measured on every run, not just when
somebody remembers to build it by hand.

The check differs because the artifact does. The kitchen GLB exports a named
node per fixture, so it is measured landmark by landmark. This one merges
everything into a mesh per material, so there is nothing to look up -- instead
every primitive's eight corners must appear in the exported vertex cloud. That
is 212 boxes rather than 7 points, and a reflection fails it wholesale.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
GLB_PATH = REPO / "apps/web/public/tour-a1/a1-first-floor.glb"
MANIFEST_PATH = REPO / "apps/web/public/tour-a1/manifest.json"

sys.path.insert(0, str(REPO / "scripts"))

from hearthview.drawings import a1_source

pytestmark = pytest.mark.skipif(
    not (GLB_PATH.is_file() and MANIFEST_PATH.is_file() and a1_source() is not None),
    reason="whole-floor artifact or drawing set missing",
)


@pytest.fixture(scope="module")
def massing():
    from hearthview.a1_extract import extract_a1
    from hearthview.a1_massing import build_a1_massing

    return build_a1_massing(extract_a1(a1_source()))


@pytest.fixture(scope="module")
def vertices():
    trimesh = pytest.importorskip("trimesh")
    import numpy as np

    scene = trimesh.load(GLB_PATH, force="scene", process=False)
    return np.vstack([
        trimesh.transform_points(scene.geometry[scene.graph[node][1]].vertices,
                                 scene.graph[node][0])
        for node in scene.graph.nodes_geometry
    ])


def test_every_traced_corner_is_in_the_committed_export(vertices, massing) -> None:
    from measure_a1_tour import TOLERANCE, corner_offsets, expected_corners

    expected = expected_corners(massing.primitives)
    offsets = corner_offsets(vertices, expected)
    outside = int((offsets > TOLERANCE).sum())

    assert outside == 0, (
        f"{outside} of {len(expected)} traced corners are missing from the committed "
        f"GLB; worst offset {offsets.max():.3f} m (tolerance {TOLERANCE} m)"
    )


def test_a_mirrored_export_would_fail_this_check(vertices, massing) -> None:
    """Otherwise the check above could be satisfied by anything.

    Reflecting north-south is the exact failure that shipped the kitchen twice,
    so the guard has to reject it rather than merely accept the good case.
    """
    import numpy as np

    from measure_a1_tour import TOLERANCE, corner_offsets, expected_corners

    expected = expected_corners(massing.primitives)
    mirrored = vertices * np.array([1.0, 1.0, -1.0])
    offsets = corner_offsets(mirrored, expected)

    assert int((offsets > TOLERANCE).sum()) > len(expected) // 2


def test_the_committed_manifest_is_the_traced_schema() -> None:
    import json

    manifest = json.loads(MANIFEST_PATH.read_text())

    assert manifest["schema"] == "hearthview-tour/v2"
    assert manifest["canonical_geometry"] is True


def test_the_minimap_can_orient_itself(vertices) -> None:
    """north_vector must agree with the space the bounds are stated in.

    This manifest states its bounds in glTF ground coordinates, where north is
    -z, so north_vector is [0, -1]; the kitchen states plan coordinates and uses
    [0, 1]. The map reads the vector to pick its projection, so the pair has to
    be consistent or the compass points the wrong way.
    """
    import json

    orientation = json.loads(MANIFEST_PATH.read_text())["orientation"]
    bounds = orientation["bounds"]

    assert orientation["north_vector"] == [0, -1]
    assert bounds["min_y"] < 0 <= bounds["max_y"], "bounds are not in glTF ground space"
