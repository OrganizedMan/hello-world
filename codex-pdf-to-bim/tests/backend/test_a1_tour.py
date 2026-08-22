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

_SOURCE = os.environ.get("HEARTHVIEW_A1_PDF")
pytestmark = pytest.mark.skipif(
    not (_SOURCE and Path(_SOURCE).is_file()),
    reason="Set HEARTHVIEW_A1_PDF to the Garrigan A-1 drawing to run tour tests.",
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
