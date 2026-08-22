"""The traced contract must carry the spec's measured geometry into the manifest."""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from spikes.tour_quality.scene_contract import (
    build_scene_contract,
    build_scene_contract_from_spec,
    validate_scene_contract,
)

_SPEC = Path(__file__).resolve().parents[2] / "spikes/tour_quality/a1_kitchen_scene_spec.json"
pytestmark = pytest.mark.skipif(not _SPEC.is_file(), reason="committed scene spec missing")

FT = 0.3048


@pytest.fixture(scope="module")
def contract():
    return build_scene_contract_from_spec(json.loads(_SPEC.read_text()))


def test_traced_contract_is_v2_and_canonical(contract) -> None:
    assert contract.schema == "hearthview-tour/v2"
    assert contract.canonical_geometry is True
    assert contract.source and contract.source["points_per_foot"] == 18.0
    assert "no elevation" in contract.provenance["absent_from_drawing_set"]


def test_envelope_carries_the_full_west_run(contract) -> None:
    assert contract.envelope.max_y / FT == pytest.approx(19.58, abs=0.15)
    assert contract.envelope.max_x / FT == pytest.approx(28.87, abs=0.1)


def test_walkable_polygon_is_the_l_shape(contract) -> None:
    assert len(contract.walkable_polygon) == 6
    xs = [p[0] for p in contract.walkable_polygon]
    ys = [p[1] for p in contract.walkable_polygon]
    assert max(ys) / FT > 18.0  # reaches into the west arm
    assert max(xs) / FT > 27.5  # span minus the 0.35 m walk margin


def test_camera_presets_have_required_names_outside_collision(contract) -> None:
    names = {p.name for p in contract.camera_presets}
    assert names == {"kitchen_overview", "walk_start", "overhead"}
    island = contract.island_footprint
    for preset in contract.camera_presets:
        x, y, z = preset.position
        if z < 2.2:
            assert not (island.min_x <= x <= island.max_x and island.min_y <= y <= island.max_y)


def test_manifest_from_traced_contract_passes_the_browser_schema_shape(contract) -> None:
    manifest = contract.to_manifest()

    assert manifest["schema"] == "hearthview-tour/v2"
    assert manifest["canonical_geometry"] is True
    assert manifest["provenance"]["measured"]
    assert manifest["orientation"]["north_up"] is True
    for required in ("cabinetry_detail", "hardware", "finishes", "furniture",
                     "decor", "undimensioned_offsets"):
        assert required in manifest["provisional_categories"]


def test_spike_contract_is_untouched() -> None:
    spike = build_scene_contract()
    assert spike.schema == "hearthview-tour-spike/v1"
    assert spike.canonical_geometry is False
    assert spike.source is None
    assert validate_scene_contract(spike) == ()
