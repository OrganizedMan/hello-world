"""Casework/fixture footprints measured directly from poché geometry
(plan §2's "wall face coordinates and thickness directly from poché
polygons" finding, extended to casework), rather than from dimension-line
matching (`dimensions.py`). This is a second, independent extraction
technique verified against the fixture: Appendix A found the kitchen
island's poché rectangle (154.67 x 77.22 pt) measures within 0.1-0.9% of
its labelled 8'-7" x 4'-3" — so a footprint can be trusted once it is
corroborated by a nearby witness value, the same "propose, then require a
citation" discipline `dimensions.py` uses.
"""
from __future__ import annotations

from dataclasses import dataclass

from .classify import TextLine
from .colors import classify_fill
from .harvest import HarvestedPath

# A witness dimension label sits close to the edge it labels — generous
# enough for this fixture's island labels (a few points to ~15pt away)
# without pulling in an unrelated dimension elsewhere on the sheet.
LABEL_PROXIMITY_PT = 20.0
VALUE_TOLERANCE_IN = 3.0


@dataclass(frozen=True, slots=True)
class CaseworkFootprint:
    rect_pt: tuple[float, float, float, float]
    width_nm: int
    depth_nm: int
    width_text: str
    depth_text: str
    width_error_in: float
    depth_error_in: float


def _is_axis_aligned_rect(points: tuple[tuple[float, float], ...]) -> bool:
    """True if every point lies on the bounding box's own edges — i.e. the
    path traces (possibly with an extra collinear point, such as a sink
    centreline marker that happens to share this path) a plain axis-
    aligned rectangle. Requiring exactly 4 distinct coordinates is too
    strict: this fixture's island rectangle carries one spurious
    mid-edge point in its point list."""
    if len(points) < 4:
        return False
    xs = [x for x, y in points]
    ys = [y for x, y in points]
    x_lo, x_hi = min(xs), max(xs)
    y_lo, y_hi = min(ys), max(ys)
    if x_hi - x_lo < 1 or y_hi - y_lo < 1:
        return False
    tol = 0.5
    return all(
        abs(x - x_lo) < tol or abs(x - x_hi) < tol or abs(y - y_lo) < tol or abs(y - y_hi) < tol
        for x, y in points
    )


def _nearest_label(
    text_lines_and_values: list[tuple[TextLine, int]],
    edge_center: tuple[float, float],
    horizontal: bool,
    target_in: float,
) -> tuple[TextLine, int] | None:
    best = None
    best_dist = None
    for line, value_nm in text_lines_and_values:
        dx, dy = line.direction
        line_horizontal = abs(dx) >= abs(dy)
        if line_horizontal != horizontal:
            continue
        value_in = value_nm / 25_400_000
        if abs(value_in - target_in) > VALUE_TOLERANCE_IN:
            continue
        lx0, ly0, lx1, ly1 = line.bbox
        lcx, lcy = (lx0 + lx1) / 2, (ly0 + ly1) / 2
        dist = ((lcx - edge_center[0]) ** 2 + (lcy - edge_center[1]) ** 2) ** 0.5
        if dist > LABEL_PROXIMITY_PT * 6:  # coarse pre-filter before the real check below
            continue
        if best_dist is None or dist < best_dist:
            best_dist = dist
            best = (line, value_nm)
    return best


def find_casework_footprints(
    paths: list[HarvestedPath],
    text_lines_and_values: list[tuple[TextLine, int]],
    in_per_pt: float,
    page_index: int,
) -> list[CaseworkFootprint]:
    """Every casework-fill rectangle on the page whose measured width AND
    depth both agree with a nearby dimension-text witness — i.e. every
    footprint that is *corroborated*, not just present. An uncorroborated
    rectangle (no matching nearby labels) is silently skipped rather than
    guessed at; plenty of casework on this sheet has no individual
    dimension callout at all."""
    results = []
    for p in paths:
        if p.page_index != page_index or p.kind not in ("fill", "fill+stroke"):
            continue
        if classify_fill(p.fill_rgb) != "casework":
            continue
        if not _is_axis_aligned_rect(p.points):
            continue
        x0, y0, x1, y1 = p.rect
        width_pt, height_pt = x1 - x0, y1 - y0
        if width_pt < 10 or height_pt < 10:
            continue  # too small to be furniture/casework, likely a glyph fragment
        width_in, height_in = width_pt * in_per_pt, height_pt * in_per_pt

        width_label = _nearest_label(
            text_lines_and_values, ((x0 + x1) / 2, y0), horizontal=True, target_in=width_in,
        ) or _nearest_label(
            text_lines_and_values, ((x0 + x1) / 2, y1), horizontal=True, target_in=width_in,
        )
        depth_label = _nearest_label(
            text_lines_and_values, (x0, (y0 + y1) / 2), horizontal=False, target_in=height_in,
        ) or _nearest_label(
            text_lines_and_values, (x1, (y0 + y1) / 2), horizontal=False, target_in=height_in,
        )
        if width_label is None or depth_label is None:
            continue

        w_line, w_value_nm = width_label
        d_line, d_value_nm = depth_label
        results.append(CaseworkFootprint(
            rect_pt=(x0, y0, x1, y1),
            width_nm=w_value_nm,
            depth_nm=d_value_nm,
            width_text=w_line.text.strip(),
            depth_text=d_line.text.strip(),
            width_error_in=abs(width_in - w_value_nm / 25_400_000),
            depth_error_in=abs(height_in - d_value_nm / 25_400_000),
        ))
    return results
