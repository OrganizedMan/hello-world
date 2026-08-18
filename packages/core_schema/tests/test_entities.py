import pytest

from core_schema import (
    UNKNOWN,
    Opening,
    OpeningKind,
    Point2,
    ProvenanceBasis,
    SourceKind,
    SourceRef,
    TopologyError,
    WallConstruction,
    WallSegment,
    user_authored,
    user_confirmed,
)
from units import NM_PER_FOOT, NM_PER_INCH


def ft(n):
    return n * NM_PER_FOOT


def inch(n):
    return n * NM_PER_INCH


def src():
    return SourceRef(doc_id="doc1", page=2, kind=SourceKind.PATH, path_uids=("p1",))


def make_opening(id_, t0, t1, kind=OpeningKind.WINDOW, **kw):
    return Opening(
        id=id_,
        kind=kind,
        t_start_nm=t0,
        t_end_nm=t1,
        prov=user_confirmed(
            basis=ProvenanceBasis.EXPLICIT_DIMENSION,
            tolerance_nm=25_400_000,
            created_by="user:jhmgarrigan",
            source_refs=(src(),),
        ),
        **kw,
    )


def make_wall(id_, length_nm, openings=()):
    return WallSegment(
        id=id_,
        level_id="L1",
        variant="proposed",
        baseline=(Point2(0, 0), Point2(length_nm, 0)),
        thickness_nm=inch(6),
        construction=WallConstruction.NEW_2X_16OC_GWB_BOTH,
        prov=user_authored(created_by="user:jhmgarrigan"),
        openings=openings,
    )


def test_opening_rejects_zero_length():
    with pytest.raises(TopologyError):
        make_opening("bad", ft(1), ft(1))


def test_wall_length_computed_from_baseline():
    w = make_wall("W1", ft(10))
    assert w.length_nm == ft(10)


def test_wall_rejects_overlapping_openings_via_constructor():
    a = make_opening("a", ft(1), ft(6))
    b = make_opening("b", ft(5), ft(9))
    with pytest.raises(TopologyError):
        make_wall("W1", ft(20), openings=(a, b))


def test_wall_reorders_openings_by_t_start_regardless_of_construction_order():
    late = make_opening("late", ft(15), ft(17))
    early = make_opening("early", ft(1), ft(3))
    w = make_wall("W1", ft(20), openings=(late, early))
    assert [o.id for o in w.openings] == ["early", "late"]


def test_wall_is_immutable_frozen():
    w = make_wall("W1", ft(10))
    with pytest.raises(Exception):
        w.thickness_nm = inch(4)  # frozen dataclass -> raises FrozenInstanceError


# --- Family-room regression at the full WallSegment level ---

def test_east_wall_window_then_solid_tv_interval_then_mudroom_opening():
    window = make_opening("window", ft(0), ft(3) + inch(8), kind=OpeningKind.WINDOW)
    to_mudroom = make_opening(
        "to_mudroom", ft(11), ft(14), kind=OpeningKind.UNFRAMED,
        connects=("LIVING_ROOM", "MUDROOM"),
    )
    wall = make_wall(
        "LIVING_ROOM.EAST", ft(14) + inch(4), openings=(to_mudroom, window)
    )

    assert [o.id for o in wall.openings] == ["window", "to_mudroom"]

    solids = wall.solid_intervals()
    # the TV interval must be one of the solid intervals, strictly between
    # the window and the mudroom opening
    tv_interval = (window.t_end_nm, to_mudroom.t_start_nm)
    assert tv_interval in solids


def test_south_wall_has_the_5ft_opening_and_no_other():
    cased = make_opening(
        "to_living_room", ft(3) + inch(1), ft(3) + inch(1) + ft(5),
        kind=OpeningKind.CASED, connects=("FAMILY_ROOM", "(E) LIVING ROOM"),
    )
    wall = make_wall(
        "LIVING_ROOM.SOUTH",
        ft(3) + inch(1) + ft(5) + ft(3) + inch(1),
        openings=(cased,),
    )
    assert len(wall.openings) == 1
    assert wall.openings[0].kind == OpeningKind.CASED


def test_wall_with_unknown_top_z_is_representable():
    w = make_wall("W1", ft(10))
    assert w.top_z_nm is UNKNOWN
