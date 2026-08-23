"""Legend-verified colour taxonomy (plan §6 step 3, Appendix A).

These constants are the values *measured* on the Garrigan fixture, kept
here as the harness's starting taxonomy — not hardcoded as a universal
truth. Plan §6 step 3 calls for parsing each new document set's own
legend and binding swatch colours to this taxonomy; that legend parser
is a Stage 1 follow-on and is not implemented here. What this module
gives that parser is the vocabulary to bind into, and gives everything
else in `extract` a working default for this fixture and any other sheet
that happens to share this office's convention.
"""
from __future__ import annotations

RGB = tuple[float, float, float]

EXISTING_WALL_FILL: RGB = (0.851, 0.851, 0.851)
NEW_WALL_FILL: RGB = (0.298, 0.298, 0.298)
TEXT_MASK_FILL: RGB = (1.0, 1.0, 1.0)
CASEWORK_FILLS: tuple[RGB, ...] = ((0.902, 0.902, 0.902), (0.918, 0.918, 0.918), (0.910, 0.910, 0.910))

DEMOLITION_STROKE: RGB = (1.0, 0.0, 0.0)
DIMENSION_STROKE: RGB = (0.0, 0.0, 1.0)
EXISTING_LABEL_STROKE: RGB = (0.502, 0.502, 0.502)

_TOL = 0.01


def color_close(a: RGB | None, b: RGB, tol: float = _TOL) -> bool:
    if a is None:
        return False
    return all(abs(x - y) <= tol for x, y in zip(a, b))


def classify_fill(fill: RGB | None) -> str | None:
    """Returns a taxonomy label for a fill colour, or None if it matches
    nothing in the known taxonomy (a genuinely unclassified fill — left
    to a human or a legend-parser to bind, never guessed)."""
    if fill is None:
        return None
    if color_close(fill, EXISTING_WALL_FILL):
        return "existing_wall"
    if color_close(fill, NEW_WALL_FILL):
        return "new_wall"
    if color_close(fill, TEXT_MASK_FILL):
        return "text_mask"
    if any(color_close(fill, c) for c in CASEWORK_FILLS):
        return "casework"
    return None


def classify_stroke(stroke: RGB | None) -> str | None:
    if stroke is None:
        return None
    if color_close(stroke, DEMOLITION_STROKE):
        return "demolition_or_leader"  # length alone cannot separate these (Appendix A)
    if color_close(stroke, DIMENSION_STROKE):
        return "dimension_or_clg_tag"  # blue also marks CLG HT tags — see classify.py
    if color_close(stroke, EXISTING_LABEL_STROKE):
        return "existing_label"
    return None
