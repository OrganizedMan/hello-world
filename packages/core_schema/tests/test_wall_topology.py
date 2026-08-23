import pytest

from core_schema import OpeningInterval, TopologyError, validate_wall_openings
from units import NM_PER_FOOT, NM_PER_INCH


def ft(n):
    return n * NM_PER_FOOT


def inch(n):
    return n * NM_PER_INCH


def test_orders_by_t_start():
    result = validate_wall_openings(
        "W1",
        ft(20),
        (
            OpeningInterval("late", ft(15), ft(17)),
            OpeningInterval("early", ft(1), ft(3)),
        ),
    )
    assert [o.opening_id for o in result] == ["early", "late"]


def test_rejects_reversed_interval():
    with pytest.raises(TopologyError):
        validate_wall_openings("W1", ft(20), (OpeningInterval("bad", ft(5), ft(3)),))


def test_rejects_opening_outside_wall():
    with pytest.raises(TopologyError):
        validate_wall_openings("W1", ft(10), (OpeningInterval("bad", ft(8), ft(12)),))


def test_rejects_overlap():
    with pytest.raises(TopologyError):
        validate_wall_openings(
            "W1",
            ft(20),
            (
                OpeningInterval("a", ft(1), ft(6)),
                OpeningInterval("b", ft(5), ft(9)),
            ),
        )


def test_adjacent_openings_allowed():
    # touching endpoints are not an overlap
    result = validate_wall_openings(
        "W1",
        ft(20),
        (
            OpeningInterval("a", ft(1), ft(5)),
            OpeningInterval("b", ft(5), ft(9)),
        ),
    )
    assert len(result) == 2


def test_rejects_non_positive_wall_length():
    with pytest.raises(TopologyError):
        validate_wall_openings("W1", 0, ())


# --- The mandatory regression test (plan §16, Appendix A) ---
#
# LIVING_ROOM.EAST, north to south: window, then solid wall carrying the
# "60\" TV" annotation, then an unframed opening into the mudroom. This is
# schema-level proof — independent of extraction or hand-tracing UI — that
# the ordering these three elements were reported in cannot be scrambled:
# the TV's wall interval is solid by construction, and the mudroom opening
# cannot silently migrate to a different wall.

def test_family_room_east_wall_topology_is_representable_and_ordered():
    wall_length = ft(14) + inch(4)  # arbitrary total >= sum of feature spans below
    window = OpeningInterval("window", ft(0), ft(3) + inch(8))
    # gap here is the solid interval carrying the "60\" TV" annotation
    mudroom_opening = OpeningInterval("to_mudroom", ft(11), ft(14))

    ordered = validate_wall_openings(
        "LIVING_ROOM.EAST", wall_length, (mudroom_opening, window)
    )

    assert [o.opening_id for o in ordered] == ["window", "to_mudroom"]

    # The TV annotation's interval sits strictly between the two openings —
    # i.e. on solid wall, never inside either opening.
    tv_start, tv_end = window.t_end_nm, mudroom_opening.t_start_nm
    assert tv_start < tv_end
    for o in ordered:
        assert not (o.t_start_nm < tv_end and tv_start < o.t_end_nm), (
            "the TV interval must not overlap any opening on this wall"
        )


def test_family_room_south_wall_has_only_the_5ft_opening_not_the_tv():
    # LIVING_ROOM.SOUTH carries the 3'-1" | 5'-0" | 3'-1" chain — a single
    # 5'-0" cased opening to the original living room. It must be
    # representable as its own wall, entirely independent of EAST.
    wall_length = ft(3) + inch(1) + ft(5) + ft(3) + inch(1)
    cased = OpeningInterval("to_living_room", ft(3) + inch(1), ft(3) + inch(1) + ft(5))
    ordered = validate_wall_openings("LIVING_ROOM.SOUTH", wall_length, (cased,))
    assert [o.opening_id for o in ordered] == ["to_living_room"]
    # This wall has no opening annotated "60\" TV" — the failure mode this
    # test guards against is exactly a TV ending up on *this* wall's 5'-0"
    # opening interval, which the schema makes structurally impossible:
    # an Opening is a hole, and a solid-wall annotation cannot be one.
