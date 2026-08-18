import pytest

from core_schema import (
    Point2,
    ProvenanceBasis,
    SourceKind,
    SourceRef,
    WallConstruction,
    WallSegment,
    user_authored,
    user_confirmed,
)
from geometry import build_wall_solid, compute_geometry_hash
from units import NM_PER_FOOT, NM_PER_INCH


def ft(n):
    return n * NM_PER_FOOT


def inch(n):
    return n * NM_PER_INCH


def src(page=2):
    return SourceRef(doc_id="doc1", page=page, kind=SourceKind.PATH, path_uids=("p1",))


def make_wall(id_, length_nm, prov=None, height_nm=ft(8)):
    return WallSegment(
        id=id_, level_id="L1", variant="proposed",
        baseline=(Point2(0, 0), Point2(length_nm, 0)),
        thickness_nm=inch(6),
        construction=WallConstruction.NEW_2X_16OC_GWB_BOTH,
        prov=prov or user_authored(created_by="user:jhmgarrigan"),
        base_z_nm=0, top_z_nm=height_nm,
    )


def build_solids(walls):
    return {w.id: build_wall_solid(w) for w in walls}


def test_hash_is_deterministic_across_repeated_builds():
    def make():
        walls = [make_wall("W1", ft(10)), make_wall("W2", ft(8))]
        return compute_geometry_hash(walls, build_solids(walls))

    hashes = [make() for _ in range(5)]
    assert len(set(hashes)) == 1


def test_hash_independent_of_python_dict_insertion_order():
    walls = [make_wall("W1", ft(10)), make_wall("W2", ft(8))]
    solids_ab = {"W1": build_wall_solid(walls[0]), "W2": build_wall_solid(walls[1])}
    solids_ba = {"W2": build_wall_solid(walls[1]), "W1": build_wall_solid(walls[0])}
    assert compute_geometry_hash(walls, solids_ab) == compute_geometry_hash(walls, solids_ba)


def test_hash_changes_when_a_wall_moves():
    walls_a = [make_wall("W1", ft(10))]
    walls_b = [make_wall("W1", ft(10) + inch(1))]  # 1 inch longer
    h_a = compute_geometry_hash(walls_a, build_solids(walls_a))
    h_b = compute_geometry_hash(walls_b, build_solids(walls_b))
    assert h_a != h_b


def test_hash_unaffected_by_provenance_only_change():
    # Re-confirming a wall (different created_by/source citation) must not
    # change the hash — only shape changes should. This is what lets the
    # review UI re-approve or re-cite an element without invalidating
    # every render that was locked against the old provenance.
    prov_a = user_authored(created_by="user:jhmgarrigan")
    prov_b = user_confirmed(
        basis=ProvenanceBasis.EXPLICIT_DIMENSION, tolerance_nm=NM_PER_INCH,
        created_by="extractor@0.2.0", source_refs=(src(page=3),),
    )
    walls_a = [make_wall("W1", ft(10), prov=prov_a)]
    walls_b = [make_wall("W1", ft(10), prov=prov_b)]
    h_a = compute_geometry_hash(walls_a, build_solids(walls_a))
    h_b = compute_geometry_hash(walls_b, build_solids(walls_b))
    assert h_a == h_b


def test_hash_is_a_64_char_hex_sha256():
    walls = [make_wall("W1", ft(10))]
    h = compute_geometry_hash(walls, build_solids(walls))
    assert len(h) == 64
    int(h, 16)  # raises if not valid hex
