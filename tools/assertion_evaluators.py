"""Real evaluators for a handful of assertion kinds, run against the
hand-traced Garrigan family room (plan §16 Tier 3, §22).

This is deliberately not a general assertion-DSL interpreter — that
generality belongs to Stage 1+, once extraction produces a real Project/
model to evaluate against every assertion file uniformly. What exists
here evaluates exactly the assertion kinds the Stage 0 fixture can
actually answer, against exactly that fixture, and says so plainly for
everything else. A NotImplementedReason is a *specific* fact ("this
needs a KITCHEN.ISLAND entity, which no fixture builds yet"), not a
generic placeholder — that specificity is the point.
"""
from __future__ import annotations

from dataclasses import dataclass

from units import ParseError, nm_to_ft_in, parse_feet_inches


class NotImplementedReason(Exception):
    def __init__(self, reason: str):
        self.reason = reason
        super().__init__(reason)


@dataclass(frozen=True, slots=True)
class EvalResult:
    passed: bool
    message: str


def _find_wall(walls, wall_id):
    for w in walls:
        if w.id == wall_id:
            return w
    raise NotImplementedReason(f"no wall {wall_id!r} in this fixture's model")


def eval_assert_wall_openings_ordered(args: dict, ctx) -> EvalResult:
    wall = _find_wall(ctx.walls, args["wall"])
    expected = args["expected"]
    real_expected = [e for e in expected if e.get("kind") != "solid"]
    actual_kinds = [o.kind.value for o in wall.openings]
    expected_kinds = [e["kind"] for e in real_expected]
    if actual_kinds != expected_kinds:
        return EvalResult(False, f"expected opening kinds {expected_kinds}, got {actual_kinds}")

    for e, o in zip(real_expected, wall.openings):
        want_connects = e.get("connects_to")
        if want_connects and not (o.connects and want_connects in o.connects):
            return EvalResult(False, f"opening {o.id} expected to connect to {want_connects!r}, got {o.connects}")
        want_width = e.get("width")
        if want_width:
            width_nm = o.t_end_nm - o.t_start_nm
            want_nm = parse_feet_inches(want_width)
            if abs(width_nm - want_nm) > parse_feet_inches('1"'):
                return EvalResult(
                    False,
                    f"opening {o.id} width mismatch: expected {want_width}, got {nm_to_ft_in(width_nm)}",
                )

    # "solid" placeholders: the openings flanking each one must have a real
    # gap between them, and that gap must actually be solid wall.
    for i, e in enumerate(expected):
        if e.get("kind") != "solid":
            continue
        before = [x for x in expected[:i] if x.get("kind") != "solid"]
        after = [x for x in expected[i + 1:] if x.get("kind") != "solid"]
        if not (before and after):
            continue
        idx_before = real_expected.index(before[-1])
        idx_after = real_expected.index(after[0])
        o_before, o_after = wall.openings[idx_before], wall.openings[idx_after]
        interval = (o_before.t_end_nm, o_after.t_start_nm)
        if interval not in wall.solid_intervals():
            return EvalResult(
                False,
                f"expected solid interval {interval} between {o_before.id!r} and "
                f"{o_after.id!r} is not solid wall",
            )

    return EvalResult(True, f"{wall.id}: {len(wall.openings)} opening(s) in the expected order")


def eval_assert_no_opening_on_wall_interval(args: dict, ctx) -> EvalResult:
    wall = _find_wall(ctx.walls, args["wall"])
    interval = ctx.tv_wall_interval(wall)  # raises if not actually solid
    overlapping = [
        o for o in wall.openings
        if o.t_start_nm < interval[1] and interval[0] < o.t_end_nm
    ]
    if overlapping:
        return EvalResult(
            False,
            f"opening(s) {[o.id for o in overlapping]} overlap the interval meant to stay solid",
        )
    return EvalResult(True, f"{wall.id}: interval {interval} is solid, no opening overlaps it")


def eval_assert_opening_chain(args: dict, ctx) -> EvalResult:
    wall = _find_wall(ctx.walls, args["wall"])
    chain_texts = args["chain"]
    try:
        chain_nm = [parse_feet_inches(t) for t in chain_texts]
    except ParseError as e:
        raise NotImplementedReason(f"could not parse chain value: {e}")

    if not wall.openings:
        return EvalResult(False, f"{wall.id} has no openings to form a chain around")
    if len(chain_nm) != 3:
        raise NotImplementedReason("only a 3-segment (before | opening | after) chain is evaluated")

    opening = wall.openings[0]
    before = opening.t_start_nm - 0
    width = opening.t_end_nm - opening.t_start_nm
    after = wall.length_nm - opening.t_end_nm
    tol = parse_feet_inches('1"')
    actual = [before, width, after]
    for expect, got, label in zip(chain_nm, actual, ("before", "opening width", "after")):
        if abs(expect - got) > tol:
            return EvalResult(
                False,
                f"{label}: expected {nm_to_ft_in(expect)}, got {nm_to_ft_in(got)}",
            )
    return EvalResult(True, f"{wall.id}: chain {chain_texts} matches within 1\"")


def eval_assert_ceiling_height(args: dict, ctx) -> EvalResult:
    # No Room entity exists yet (Stage 2): approximated via the height of
    # every wall in this fixture, since they were all traced with the
    # same confirmed CLG HT figure. Documented simplification, not a
    # silent one.
    if not ctx.walls:
        raise NotImplementedReason("no walls in this fixture's model")
    want_nm = parse_feet_inches(args["value"])
    tol_nm = parse_feet_inches(args.get("tol", '1"'))
    for w in ctx.walls:
        height_nm = w.top_z_nm - w.base_z_nm
        if abs(height_nm - want_nm) > tol_nm:
            return EvalResult(False, f"{w.id}: height {nm_to_ft_in(height_nm)} != {args['value']}")
    return EvalResult(
        True,
        f"all {len(ctx.walls)} wall(s) in this fixture are {args['value']} tall "
        "(approximated via wall height — no Room entity yet)",
    )


EVALUATORS = {
    "assert_wall_openings_ordered": eval_assert_wall_openings_ordered,
    "assert_no_opening_on_wall_interval": eval_assert_no_opening_on_wall_interval,
    "assert_opening_chain": eval_assert_opening_chain,
    "assert_ceiling_height": eval_assert_ceiling_height,
}

NOT_IMPLEMENTED_REASONS = {
    "assert_dimension": "requires the entity's geometry (e.g. KITCHEN.ISLAND as FixedCabinetry), not built by any Stage 0 fixture",
    "assert_text_not_classified_as_dimension": "requires the text classifier (extract package), which is Stage 1 scope",
}
