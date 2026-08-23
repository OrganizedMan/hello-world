"""Tour packaging tests: valid GLB, and a manifest that states its provenance."""

from __future__ import annotations

import json
import os
import struct
from pathlib import Path

import pytest

from hearthview.a1_extract import extract_a1
from hearthview.a1_massing import build_a1_massing
from hearthview.a1_tour import build_tour
from hearthview.geometry import Primitive

from hearthview.drawings import a1_source

_SOURCE = a1_source()
pytestmark = pytest.mark.skipif(
    _SOURCE is None,
    reason="No drawing set: commit drawings/ or set HEARTHVIEW_A1_PDF.",
)


@pytest.fixture(scope="module")
def tour():
    extraction = extract_a1(Path(_SOURCE))
    return build_tour(extraction, build_a1_massing(extraction))


def test_glb_container_is_well_formed(tour) -> None:
    magic, version, length = struct.unpack("<III", tour.glb[:12])

    assert magic == 0x46546C67  # "glTF"
    assert version == 2
    assert length == len(tour.glb)


def test_glb_declares_a_material_per_part_kind(tour) -> None:
    json_length = struct.unpack("<I", tour.glb[12:16])[0]
    gltf = json.loads(tour.glb[20 : 20 + json_length].decode("utf-8"))
    names = {material["name"] for material in gltf["materials"]}

    assert {"wall", "floor", "counter", "stair"} <= names
    assert len(gltf["meshes"][0]["primitives"]) == len(gltf["materials"])


def test_manifest_declares_measured_and_assumed_separately(tour) -> None:
    provenance = tour.manifest["provenance"]

    assert tour.manifest["canonical_geometry"] is True
    assert provenance["measured"] and provenance["assumed"]
    assert 50 < provenance["verified_percent"] <= 100
    # The claim that matters: openings have no printed vertical dimension.
    assert "no elevation" in provenance["absent_from_drawing_set"]


def test_walk_start_stands_clear_of_every_wall(tour) -> None:
    """A spawn inside a wall renders as a blank screen, so assert real clearance."""
    preset = next(
        p for p in tour.manifest["runtime"]["camera_presets"] if p["name"] == "walk_start"
    )
    x, _, z = preset["position"]

    for barrier in tour.manifest["runtime"]["barriers"]:
        inside_x = barrier["min_x"] <= x <= barrier["max_x"]
        inside_z = barrier["min_z"] <= z <= barrier["max_z"]
        assert not (inside_x and inside_z), f"walk_start is inside {barrier['name']}"


def test_walk_start_is_inside_the_walkable_bounds(tour) -> None:
    walkable = tour.manifest["runtime"]["walkable"]
    preset = next(
        p for p in tour.manifest["runtime"]["camera_presets"] if p["name"] == "walk_start"
    )
    x, _, z = preset["position"]

    assert walkable["min_x"] <= x <= walkable["max_x"]
    assert walkable["min_z"] <= z <= walkable["max_z"]


def test_envelope_covers_the_deck_not_just_the_walls(tour) -> None:
    """The deck reaches north of the building line; the envelope must include it."""
    envelope = tour.manifest["envelope"]
    depth_feet = (envelope["max_z"] - envelope["min_z"]) / 0.3048

    assert depth_feet > 45.0


def test_face_normals_are_in_the_same_frame_as_the_corners() -> None:
    """Normals must be rewritten into glTF space like the positions are.

    They were not, so the top and bottom of every solid carried a horizontal
    normal and the north and south faces carried vertical ones. Geometry was
    exact and every corner measured true; the model just could not catch light,
    and floors came out black under a sun directly above them.
    """
    from hearthview.a1_tour import _FACES

    up = [normal for _face, normal in _FACES if normal[1] > 0.5]
    down = [normal for _face, normal in _FACES if normal[1] < -0.5]
    horizontal = [normal for _face, normal in _FACES if abs(normal[1]) < 0.5]

    # glTF is Y-up: exactly one face of a box points up and one points down.
    assert len(up) == 1, "a box has one upward face"
    assert len(down) == 1, "a box has one downward face"
    assert len(horizontal) == 4, "the remaining four faces are walls"

    # Every normal is a unit axis vector, not a diagonal left over from a
    # partial transform.
    for normal in (n for _f, n in _FACES):
        assert sum(abs(component) for component in normal) == pytest.approx(1.0)


def test_a_floor_slab_faces_the_sky() -> None:
    """The end-to-end version: the widest solid's top normal must point up."""
    from hearthview.a1_tour import _FACES, _corners

    massing = build_a1_massing(extract_a1(Path(_SOURCE)))
    slab = max(
        massing.primitives,
        key=lambda item: (item.x1_ticks - item.x0_ticks) * (item.y1_ticks - item.y0_ticks),
    )
    corners = _corners(slab)
    top_face, top_normal = next(
        (face, normal) for face, normal in _FACES if normal[1] > 0.5
    )

    heights = {round(corners[index][1], 6) for index in top_face}
    lowest = min(corner[1] for corner in corners)

    assert top_normal == (0.0, 1.0, -0.0)
    assert len(heights) == 1, "the top face is level"
    assert heights.pop() > lowest, "the upward face is the higher one"


def test_faces_are_wound_outward_so_the_supplied_normal_is_the_shaded_one() -> None:
    """Winding and normal must agree, or lighting uses the opposite of both.

    three.js flips the normal for a back-facing fragment on a DoubleSide
    material. Every box here was wound inside-out, so the flip applied
    everywhere and each surface shaded as though it faced into the solid. The
    positions were exact throughout -- all 4,224 traced corners measured true --
    which is why nothing caught it until the model was looked at under a sun.
    """
    import numpy as np

    from hearthview.a1_tour import _FACES, _corners
    from hearthview.geometry import StationInterval

    box = Primitive("probe", "wall", 0, 0, 0, 100, 200, 300, StationInterval(0, 100))
    corners = _corners(box)

    for face, normal in _FACES:
        a, b, c = (np.array(corners[index]) for index in face[:3])
        # Triangles are emitted as (0, 2, 1), so the winding normal is c x b.
        winding = np.cross(c - a, b - a)
        winding = winding / np.linalg.norm(winding)

        assert float(np.dot(winding, np.array(normal))) > 0.99, (
            f"face {face} is wound against its normal {normal}"
        )


def test_every_normal_points_away_from_the_centre_of_the_solid() -> None:
    """Outward, not merely consistent: an inside-out box is self-consistent too."""
    import numpy as np

    from hearthview.a1_tour import _FACES, _corners
    from hearthview.geometry import StationInterval

    box = Primitive("probe", "wall", 0, 0, 0, 100, 200, 300, StationInterval(0, 100))
    corners = _corners(box)
    centre = np.mean([np.array(c) for c in corners], axis=0)

    for face, normal in _FACES:
        face_centre = np.mean([np.array(corners[index]) for index in face], axis=0)
        assert float(np.dot(face_centre - centre, np.array(normal))) > 0, (
            f"face {face} normal {normal} points into the solid"
        )
