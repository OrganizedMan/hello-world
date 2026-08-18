from constraints import (
    ConstraintStatus,
    anchor_region_datums,
    build_systems,
    diagnose,
)
from core_schema import DimensionConstraint, FeatureRef, ProvenanceBasis, SourceKind, SourceRef, user_confirmed
from units import NM_PER_FOOT


def ft(n):
    return n * NM_PER_FOOT


def dim(id_, a, b, value_nm):
    return DimensionConstraint(
        id=id_, region_id="R1", text=id_, value_nm=value_nm, axis="x",
        feature_a=a, feature_b=b,
        prov=user_confirmed(
            basis=ProvenanceBasis.EXPLICIT_DIMENSION, tolerance_nm=NM_PER_FOOT,
            created_by="user:jhmgarrigan",
            source_refs=(SourceRef(doc_id="d", page=1, kind=SourceKind.PATH, path_uids=("p",)),),
        ),
    )


def test_anchoring_a_datum_makes_a_relative_chain_well_constrained():
    datum = FeatureRef("R1", "datum")
    a = FeatureRef("WALL", "face:start")
    b = FeatureRef("WALL", "face:end")
    constraints = [dim("d0", datum, a, 0), dim("d1", a, b, ft(10))]

    systems = build_systems(constraints, [])
    d_before = diagnose(systems["x"])
    assert d_before.status == ConstraintStatus.UNDER_CONSTRAINED  # datum itself still floats

    anchor_region_datums(systems["x"])
    d_after = diagnose(systems["x"])
    assert d_after.status == ConstraintStatus.WELL_CONSTRAINED
    assert d_after.solution_nm[("R1", "datum")] == 0
    assert d_after.solution_nm[("WALL", "face:end")] == ft(10)


def test_anchor_region_datums_is_a_noop_without_a_datum_feature():
    a = FeatureRef("WALL", "face:start")
    b = FeatureRef("WALL", "face:end")
    constraints = [dim("d1", a, b, ft(10))]
    systems = build_systems(constraints, [])
    anchor_region_datums(systems["x"])  # no "datum" feature present
    d = diagnose(systems["x"])
    # still under-constrained: no datum to anchor, nothing invented
    assert d.status == ConstraintStatus.UNDER_CONSTRAINED


def test_multiple_datum_uses_all_anchor_to_the_same_zero():
    datum = FeatureRef("R1", "datum")
    a = FeatureRef("WALL_A", "face:start")
    b = FeatureRef("WALL_B", "face:start")
    constraints = [
        dim("d0a", datum, a, ft(5)),
        dim("d0b", datum, b, ft(-3)),
    ]
    systems = build_systems(constraints, [])
    anchor_region_datums(systems["x"])
    d = diagnose(systems["x"])
    assert d.status == ConstraintStatus.WELL_CONSTRAINED
    assert d.solution_nm[("WALL_A", "face:start")] == ft(5)
    assert d.solution_nm[("WALL_B", "face:start")] == ft(-3)
