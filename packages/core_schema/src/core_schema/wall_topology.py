"""The topology invariant that makes the family-room failure unrepresentable.

Plan §5.3:

    For every WallSegment W:
      openings sorted ascending by t_start
      forall i: 0 <= o[i].t_start < o[i].t_end <= |W.baseline|
      forall i: o[i].t_end <= o[i+1].t_start   # non-overlapping

An Opening cannot exist without a wall, and a "60\" TV" annotation binds to
a *solid wall interval*, never to an opening — so a TV can only ever be
placed on solid wall. This module is the one place that invariant is
checked; every path that constructs or edits a WallSegment's openings
(hand tracing, automatic extraction, review-UI edits) must go through it.
"""
from __future__ import annotations

from dataclasses import dataclass


class TopologyError(ValueError):
    """Raised when a wall's openings violate the ordering/non-overlap invariant."""


@dataclass(frozen=True, slots=True)
class OpeningInterval:
    """The minimal shape wall-topology validation needs from an Opening."""

    opening_id: str
    t_start_nm: int
    t_end_nm: int


def validate_wall_openings(
    wall_id: str, wall_length_nm: int, openings: tuple[OpeningInterval, ...]
) -> tuple[OpeningInterval, ...]:
    """Validate and return openings sorted ascending by t_start.

    Raises TopologyError, naming the wall and offending openings, on any
    violation: negative length, an opening outside the wall, a degenerate
    (zero/negative-length) opening, or two openings that overlap.
    """
    if wall_length_nm <= 0:
        raise TopologyError(f"wall {wall_id!r}: wall_length_nm must be positive, got {wall_length_nm}")

    ordered = tuple(sorted(openings, key=lambda o: o.t_start_nm))

    for o in ordered:
        if not (0 <= o.t_start_nm < o.t_end_nm <= wall_length_nm):
            raise TopologyError(
                f"wall {wall_id!r}: opening {o.opening_id!r} interval "
                f"[{o.t_start_nm}, {o.t_end_nm}) is not within [0, {wall_length_nm}]"
            )

    for a, b in zip(ordered, ordered[1:]):
        if a.t_end_nm > b.t_start_nm:
            raise TopologyError(
                f"wall {wall_id!r}: opening {a.opening_id!r} (ends {a.t_end_nm}) "
                f"overlaps opening {b.opening_id!r} (starts {b.t_start_nm})"
            )

    return ordered
