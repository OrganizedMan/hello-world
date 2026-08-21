import json
import struct

import pytest

from hearthview.fixture import build_a1_fixture
from hearthview.geometry import compile_glb, compile_primitives
from hearthview.models import ReviewDecision, ReviewState
from hearthview.units import TICKS_PER_INCH
from hearthview.validation import TokenModelMismatch, mint_token, validate


def approved_model():
    model = build_a1_fixture()
    return model.model_copy(
        update={
            "review_decisions": tuple(
                ReviewDecision(item_id=item.item_id, state=ReviewState.APPROVED)
                for item in model.review_decisions
            )
        }
    )


def glb_json(glb: bytes) -> dict:
    magic, version, total_length = struct.unpack_from("<4sII", glb, 0)
    assert magic == b"glTF"
    assert version == 2
    assert total_length == len(glb)
    json_length, chunk_type = struct.unpack_from("<I4s", glb, 12)
    assert chunk_type == b"JSON"
    return json.loads(glb[20 : 20 + json_length].decode("utf-8"))


def test_openings_split_walls_without_solid_panels_covering_them() -> None:
    model = approved_model()
    token = mint_token(model, validate(model))

    primitives = compile_primitives(model, token)
    east_solid = [
        item
        for item in primitives
        if item.element_id == "family_east" and item.part_kind == "WALL_SOLID"
    ]

    assert east_solid
    assert all(
        not interval.overlaps(opening)
        for interval in (item.station_interval for item in east_solid)
        for opening in (
            (12 * TICKS_PER_INCH, 60 * TICKS_PER_INCH),
            (132 * TICKS_PER_INCH, 228 * TICKS_PER_INCH),
        )
    )


def test_derived_viewing_surface_is_never_labeled_as_verified_floor() -> None:
    model = approved_model()
    token = mint_token(model, validate(model))

    primitives = compile_primitives(model, token)

    assert not any(item.element_id == "floor_first" for item in primitives)
    assert not any(item.part_kind == "FLOOR_SLAB" for item in primitives)
    assert any(
        item.element_id == "staging_floor_estimated"
        and item.part_kind == "ESTIMATED_STAGING_FLOOR"
        for item in primitives
    )


def test_ten_compiles_produce_one_geometry_and_file_hash() -> None:
    model = approved_model()
    token = mint_token(model, validate(model))

    artifacts = [compile_glb(model, token) for _ in range(10)]

    assert len({artifact.geometry_hash for artifact in artifacts}) == 1
    assert len({artifact.glb_file_hash for artifact in artifacts}) == 1
    assert len({artifact.glb for artifact in artifacts}) == 1


def test_glb_embeds_model_identity_and_element_clickback_ids() -> None:
    model = approved_model()
    token = mint_token(model, validate(model))

    artifact = compile_glb(model, token)
    document = glb_json(artifact.glb)

    assert document["asset"]["version"] == "2.0"
    assert document["asset"]["extras"]["modelHash"] == token.model_hash
    assert document["asset"]["extras"]["geometryHash"] == artifact.geometry_hash
    node_ids = {node["extras"]["canonicalElementId"] for node in document["nodes"]}
    assert {"family_east", "family_south", "kitchen_island", "family_tv"} <= node_ids


def test_compiler_rejects_token_after_model_change() -> None:
    model = approved_model()
    token = mint_token(model, validate(model))
    changed = model.model_copy(update={"level_height_ticks": model.level_height_ticks + 1024})

    with pytest.raises(TokenModelMismatch):
        compile_glb(changed, token)
