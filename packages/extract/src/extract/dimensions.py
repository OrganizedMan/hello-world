"""Dimension-to-geometry matching (plan §6 step 12).

The key finding (verified directly against the Garrigan fixture, not
assumed): this office's CAD export draws each tick-to-tick span of a
dimension chain as its own separate straight stroke item, so a tick
position is simply the shared endpoint of two adjacent dimension-line
segments (plus the touch-point of a perpendicular witness/extension
line where the segment on one side doesn't itself reach the tick).
Separate diagonal tick glyphs also exist in this export but are
redundant with these endpoints and are not needed. This is why matching
to *line endpoints* the way Appendix A's first probe did — nearest single
segment to the text — fails: it is usually the wrong sub-span in a
compressed chain, not an overshoot problem (this export has none).

The algorithm, arrived at empirically by hand-checking specific
mismatches against the real PDF (see git history for the two prior,
less accurate versions):

1. Find every plausible dimension *row* near the text — clusters of
   same-orientation stroke segments at a shared perpendicular offset,
   within `PERP_MAX_PT` of the text. Do not commit to "the nearest row";
   a same-width wall or casework line can sit closer to the text by
   chance than the real dimension row does.
2. For each row, collect tick positions along it (segment endpoints,
   plus perpendicular witness-line touch-points at that row's exact
   offset) and consider every consecutive pair.
3. Score every (row, pair) by whether the pair actually brackets the
   text's own centre, then by how closely its length (in real units)
   matches the text's parsed value. Take the best-scoring pair across
   *all* rows, not just the geometrically nearest one — trying every row
   and letting the resulting match quality decide is what rejects a
   closer-but-wrong row.
"""
from __future__ import annotations

from dataclasses import dataclass

from .classify import TextLine
from .harvest import HarvestedPath

PERP_MAX_PT = 15.0
PARALLEL_PAD_PT = 150.0
CLUSTER_TOL_PT = 1.0
# A witness/extension line drops perpendicular to the dimension row and
# touches it near-exactly at the tick position — a much tighter tolerance
# than PERP_MAX_PT (which locates the row itself, not a touch point on it).
WITNESS_TOUCH_TOL_PT = 3.0


@dataclass(frozen=True, slots=True)
class DimensionMatch:
    text: str
    value_nm: int
    page_index: int
    axis: str  # "x" | "y"
    a_pt: float
    b_pt: float
    perp_pt: float
    error_in: float


def _row_candidates(line: TextLine, paths: list[HarvestedPath]) -> list[tuple[float, list[float]]]:
    """Every plausible dimension row near the text, each with its own tick
    positions — not just the nearest row by perpendicular distance. A
    same-width wall or casework line can sit closer to the text than the
    real dimension row does, so row *selection* is left to the caller,
    which can score each row's resulting match rather than committing to
    a row on proximity alone (the module's first fix, scoping candidates
    to one row at all, still wasn't enough on its own — see dimensions.py
    history / the module docstring)."""
    x0, y0, x1, y1 = line.bbox
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
    dx, dy = line.direction
    horizontal = abs(dx) >= abs(dy)
    text_perp = cy if horizontal else cx
    lo = (cx if horizontal else cy) - PARALLEL_PAD_PT
    hi = (cx if horizontal else cy) + PARALLEL_PAD_PT

    row_segments: list[tuple[float, float, float]] = []  # (perp, a, b)
    witness_touches: list[tuple[float, float]] = []  # (perp, along)
    for p in paths:
        if p.page_index != line.page_index or len(p.points) != 2:
            continue
        (sx0, sy0), (sx1, sy1) = p.points
        is_h = abs(sy1 - sy0) < 0.5 and abs(sx1 - sx0) > 0.5
        is_v = abs(sx1 - sx0) < 0.5 and abs(sy1 - sy0) > 0.5

        if (horizontal and is_h) or (not horizontal and is_v):
            perp = (sy0 + sy1) / 2 if horizontal else (sx0 + sx1) / 2
            if abs(perp - text_perp) > PERP_MAX_PT:
                continue
            a, b = (sx0, sx1) if horizontal else (sy0, sy1)
            seg_lo, seg_hi = min(a, b), max(a, b)
            if seg_hi < lo or seg_lo > hi:
                continue
            row_segments.append((perp, seg_lo, seg_hi))
        elif (horizontal and is_v) or (not horizontal and is_h):
            for (px, py) in ((sx0, sy0), (sx1, sy1)):
                touch_perp = py if horizontal else px
                if abs(touch_perp - text_perp) > PERP_MAX_PT:
                    continue
                along = px if horizontal else py
                if lo <= along <= hi:
                    witness_touches.append((touch_perp, along))

    row_perps = _cluster(sorted({s[0] for s in row_segments}))
    rows = []
    for row_perp in row_perps:
        positions: list[float] = []
        for perp, a, b in row_segments:
            if abs(perp - row_perp) <= CLUSTER_TOL_PT:
                positions.append(a)
                positions.append(b)
        for touch_perp, along in witness_touches:
            if abs(touch_perp - row_perp) <= WITNESS_TOUCH_TOL_PT:
                positions.append(along)
        rows.append((row_perp, _cluster(positions)))
    return rows


def _cluster(positions: list[float]) -> list[float]:
    if not positions:
        return []
    positions = sorted(positions)
    clustered = [positions[0]]
    for p in positions[1:]:
        if p - clustered[-1] > CLUSTER_TOL_PT:
            clustered.append(p)
    return clustered


def match_dimension_text(
    line: TextLine, value_nm: int, paths: list[HarvestedPath], in_per_pt: float,
) -> DimensionMatch | None:
    """Best consecutive-tick-pair match for one dimension text, tried
    across every plausible row near the text (not just the nearest one —
    see `_row_candidates`), or None if no row yields a candidate pair at
    all."""
    x0, y0, x1, y1 = line.bbox
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
    dx, dy = line.direction
    horizontal = abs(dx) >= abs(dy)
    text_center = cx if horizontal else cy

    value_in = value_nm / 25_400_000

    best: DimensionMatch | None = None
    best_score = None
    for row_perp, positions in _row_candidates(line, paths):
        if len(positions) < 2:
            continue
        for a, b in zip(positions, positions[1:]):
            length_in = (b - a) * in_per_pt
            error_in = abs(length_in - value_in)
            contains_center = a - 2.0 <= text_center <= b + 2.0
            # Prefer pairs that actually bracket the label; among those,
            # the closest length wins. A non-bracketing pair is only ever
            # used if nothing brackets the label at all, on any row.
            score = (0 if contains_center else 1, error_in)
            if best_score is None or score < best_score:
                best_score = score
                best = DimensionMatch(
                    text=line.text, value_nm=value_nm, page_index=line.page_index,
                    axis="x" if horizontal else "y", a_pt=a, b_pt=b,
                    perp_pt=row_perp, error_in=error_in,
                )
    return best


def match_dimensions_on_page(
    lines_and_values: list[tuple[TextLine, int]], paths: list[HarvestedPath], in_per_pt: float,
) -> list[DimensionMatch]:
    matches = []
    for line, value_nm in lines_and_values:
        m = match_dimension_text(line, value_nm, paths, in_per_pt)
        if m is not None:
            matches.append(m)
    return matches
