import pytest

from constraints import ConstraintStatus, UnsupportedConstraintError, anchor, build_systems, diagnose
from core_schema import (
    AlignmentConstraint,
    DimensionConstraint,
    FeatureRef,
    ProvenanceBasis,
    SourceKind,
    SourceRef,
    user_confirmed,
)
from units import NM_PER_FOOT, NM_PER_INCH


def ft(n):
    return n * NM_PER_FOOT


def inch(n):
    return n * NM_PER_INCH


def src():
    return SourceRef(doc_id="doc1", page=2, kind=SourceKind.PATH, path_uids=("p1",))


def dim(id_, a, b, value_nm, axis="x", weight=1.0):
    return DimensionConstraint(
        id=id_,
        region_id="R1",
        text=f"{id_} text",
        value_nm=value_nm,
        axis=axis,
        feature_a=FeatureRef(a, "face"),
        feature_b=FeatureRef(b, "face"),
        prov=user_confirmed(
            basis=ProvenanceBasis.EXPLICIT_DIMENSION,
            tolerance_nm=NM_PER_INCH,
            created_by="user:jhmgarrigan",
            source_refs=(src(),),
        ),
        weight=weight,
    )


def test_south_wall_chain_is_well_constrained_and_matches_appendix_a():
    # LIVING_ROOM.SOUTH: 3'-1" | 5'-0" | 3'-1" chain from Appendix A —
    # four jambs (A, B, C, D) pinned by three explicit dimensions.
    constraints = [
        dim("d1", "A", "B", ft(3) + inch(1)),
        dim("d2", "B", "C", ft(5)),
        dim("d3", "C", "D", ft(3) + inch(1)),
    ]
    systems = build_systems(constraints, [])
    systems["x"].rows.append(anchor(FeatureRef("A", "face"), 0))
    d = diagnose(systems["x"])
    assert d.status == ConstraintStatus.WELL_CONSTRAINED
    assert not d.is_blocking

    span = d.solution_nm[("D", "face")] - d.solution_nm[("A", "face")]
    assert span == ft(11) + inch(2)  # 3'-1" + 5'-0" + 3'-1"


def test_overall_dimension_confirms_the_chain_when_consistent():
    constraints = [
        dim("d1", "A", "B", ft(3) + inch(1)),
        dim("d2", "B", "C", ft(5)),
        dim("d3", "C", "D", ft(3) + inch(1)),
        dim("overall", "A", "D", ft(11) + inch(2), weight=1.0),
    ]
    systems = build_systems(constraints, [])
    systems["x"].rows.append(anchor(FeatureRef("A", "face"), 0))
    d = diagnose(systems["x"])
    assert d.status == ConstraintStatus.OVER_CONSTRAINED_CONSISTENT
    assert not d.is_blocking


def test_wrong_overall_dimension_is_contradictory():
    constraints = [
        dim("d1", "A", "B", ft(3) + inch(1)),
        dim("d2", "B", "C", ft(5)),
        dim("d3", "C", "D", ft(3) + inch(1)),
        dim("overall", "A", "D", ft(20)),  # inconsistent with the chain
    ]
    systems = build_systems(constraints, [])
    systems["x"].rows.append(anchor(FeatureRef("A", "face"), 0))
    d = diagnose(systems["x"])
    assert d.status == ConstraintStatus.CONTRADICTORY
    assert d.is_blocking


def test_equal_alignment_constraint_encodes_eq_eq_tags():
    # The attic "EQ / EQ" tags (Appendix A): two zones are equal width,
    # with no numeric value at all.
    ac = AlignmentConstraint(
        id="eq1",
        kind="equal",
        members=(FeatureRef("A", "face"), FeatureRef("B", "face"), FeatureRef("C", "face")),
        prov=user_confirmed(
            basis=ProvenanceBasis.EXPLICIT_DIMENSION,
            tolerance_nm=NM_PER_INCH,
            created_by="user:jhmgarrigan",
            source_refs=(src(),),
        ),
        axis="x",
    )
    overall = dim("overall", "A", "C", ft(20))
    systems = build_systems([overall], [ac])
    systems["x"].rows.append(anchor(FeatureRef("A", "face"), 0))
    d = diagnose(systems["x"])
    assert not d.is_blocking
    left = d.solution_nm[("B", "face")] - d.solution_nm[("A", "face")]
    right = d.solution_nm[("C", "face")] - d.solution_nm[("B", "face")]
    assert left == right == ft(10)


def test_along_wall_axis_is_explicitly_unsupported_not_silently_dropped():
    bad = dim("d1", "A", "B", ft(5), axis="along:W1")
    with pytest.raises(UnsupportedConstraintError):
        build_systems([bad], [])


def test_perpendicular_alignment_is_explicitly_unsupported():
    ac = AlignmentConstraint(
        id="p1", kind="perpendicular",
        members=(FeatureRef("A", "face"), FeatureRef("B", "face")),
        prov=user_confirmed(
            basis=ProvenanceBasis.EXPLICIT_DIMENSION, tolerance_nm=NM_PER_INCH,
            created_by="user:jhmgarrigan", source_refs=(src(),),
        ),
        axis="x",
    )
    with pytest.raises(UnsupportedConstraintError):
        build_systems([], [ac])
