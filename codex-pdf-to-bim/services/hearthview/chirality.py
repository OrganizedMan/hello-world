"""Is a built scene a mirror image of the drawing?

Handedness is the one orientation property that needs no compass: three
landmarks whose arrangement on the sheet is known must make the same turn in
the model, however the axes happen to be labelled. A reflection reverses that
turn; a rotation does not.

This lives in one module on purpose. The same question was asked in two places
with opposite sign conventions, which produced a confident answer that was
exactly backwards. Both the artifact measurement and the tests import from here
so they cannot drift apart again.
"""

from __future__ import annotations

Point = tuple[float, float]

# Sink, range and island on A-1, in feet as (east, north). Read off the trace:
# the sink is on the north wall, the range on the west wall, the island between.
PLAN_SINK: Point = (7.17, 0.0)
PLAN_RANGE: Point = (0.0, -6.90)
PLAN_ISLAND: Point = (9.80, -7.74)


def _turn(a: Point, b: Point, c: Point) -> float:
    """Signed turn of a -> b -> c, positive anticlockwise seen from above."""
    first = (b[0] - a[0], b[1] - a[1])
    second = (c[0] - a[0], c[1] - a[1])
    return first[0] * second[1] - first[1] * second[0]


def plan_turn() -> float:
    return _turn(PLAN_SINK, PLAN_RANGE, PLAN_ISLAND)


def model_turn(sink: Point, range_: Point, island: Point) -> float:
    """Same turn for glTF landmarks given as (x, z).

    glTF is Y-up, so the component of the cross product along +y — the one that
    corresponds to "out of the page" in a plan — is ``a_z * b_x - a_x * b_z``.
    Passing (x, z) and reversing the operands here keeps that correct.
    """
    return -_turn(sink, range_, island)


def blender_to_gltf(x: float, y: float) -> Point:
    """Blender plan coords to glTF ground plane: (x, y) -> (x, -y)."""
    return (x, -y)


def matches_drawing(sink: Point, range_: Point, island: Point) -> bool:
    """True when the model has the same handedness as A-1."""
    return (model_turn(sink, range_, island) > 0) == (plan_turn() > 0)


# Testing a *mapping* rather than a built model. The landmarks above are kitchen
# fixtures, which is fine for the kitchen and useless for a bedroom; every floor
# of the house needs the same question asked without naming furniture.
#
# Three probe points in sheet coordinates: the origin, one due east of it, one
# due north. On the sheet +x is east and PDF y grows *downwards*, so north is
# -y. A mapping that preserves the drawing's handedness sends these to a
# positive turn, because east x north = up.
_PROBE_ORIGIN: Point = (0.0, 0.0)
_PROBE_EAST: Point = (100.0, 0.0)
_PROBE_NORTH: Point = (0.0, -100.0)


def mapping_preserves_handedness(to_plan) -> bool:
    """True when a PDF-to-plan mapping keeps the drawing's handedness.

    ``to_plan`` takes ``(pdf_x, pdf_y)`` and returns plan ``(east, north)`` in
    any consistent unit; only the sign of the result matters. Measuring south
    instead of north, or flipping x, reverses the turn and yields a mirrored
    world -- and no amount of correct tracing repairs that, because the
    coordinates going in were already right. That is how the kitchen shipped
    reflected while driven by the trace.
    """
    origin, east, north = (
        to_plan(*probe) for probe in (_PROBE_ORIGIN, _PROBE_EAST, _PROBE_NORTH)
    )
    return _turn(origin, east, north) > 0
