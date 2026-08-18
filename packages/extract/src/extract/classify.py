"""Text classification (plan §6 step 6): reassemble split spans into
lines, then classify each line as a dimension string, a ceiling-height
tag, or something else.

The mandatory false-positive guard from Appendix A: `"CLG HT - 8' 5\""`
contains a syntactically valid feet-inches token ("8' 5\"") but is not a
dimension — it is a room's ceiling-height callout. Classification here is
by *exact* match against the dimension grammar (via `units.parse_feet_inches`,
which is anchored start-to-end), so a line carrying any letters — "CLG HT
-", "TV", "REF", a room name — can never be misread as a bare dimension,
without needing a denylist of known prefixes.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from units import ParseError, parse_feet_inches

from .harvest import HarvestedText


class TextClass(str, Enum):
    DIMENSION_STRING = "dimension_string"
    CEILING_HEIGHT_TAG = "ceiling_height_tag"
    OTHER = "other"


@dataclass(frozen=True, slots=True)
class TextLine:
    page_index: int
    text: str
    bbox: tuple[float, float, float, float]
    color_rgb: tuple[float, float, float]
    direction: tuple[float, float]
    spans: tuple[HarvestedText, ...]


# Spans on the same reading line (same direction, same-ish baseline) that
# are within this many points of each other horizontally (in the reading
# direction) are joined into one line — this is what reunites
# "CLG HT - 8'" and " 5\"" when they arrive as separate spans (plan §6
# step 5). A generous gap is safe: two genuinely unrelated dimension
# strings on the same drawing are always far apart relative to this.
_JOIN_GAP_PT = 6.0
_BASELINE_TOL_PT = 1.5


def reassemble_lines(spans: list[HarvestedText]) -> list[TextLine]:
    """Group spans into reading lines by direction + baseline proximity,
    then order and join each group's text left-to-right (or top-to-bottom
    for vertical text)."""
    remaining = list(spans)
    lines: list[TextLine] = []

    while remaining:
        seed = remaining.pop(0)
        group = [seed]
        rest = []
        for s in remaining:
            if s.page_index != seed.page_index or s.direction != seed.direction:
                rest.append(s)
                continue
            if _same_baseline(seed, s) and _within_gap(group, s):
                group.append(s)
            else:
                rest.append(s)
        remaining = rest
        group.sort(key=_reading_key(seed.direction))
        lines.append(_join(group))

    return lines


def _same_baseline(a: HarvestedText, b: HarvestedText) -> bool:
    dx, dy = a.direction
    if abs(dx) >= abs(dy):  # horizontal text: compare y
        return abs(a.bbox[1] - b.bbox[1]) <= _BASELINE_TOL_PT
    return abs(a.bbox[0] - b.bbox[0]) <= _BASELINE_TOL_PT  # vertical text: compare x


def _within_gap(group: list[HarvestedText], candidate: HarvestedText) -> bool:
    dx, dy = group[0].direction
    for member in group:
        if abs(dx) >= abs(dy):
            gap = candidate.bbox[0] - member.bbox[2]
            gap2 = member.bbox[0] - candidate.bbox[2]
        else:
            gap = member.bbox[1] - candidate.bbox[3]
            gap2 = candidate.bbox[1] - member.bbox[3]
        if min(abs(gap), abs(gap2)) <= _JOIN_GAP_PT:
            return True
    return False


def _reading_key(direction: tuple[float, float]):
    dx, dy = direction
    if abs(dx) >= abs(dy):
        return lambda s: s.bbox[0]
    return lambda s: -s.bbox[1] if dy < 0 else s.bbox[1]


def _join(group: list[HarvestedText]) -> TextLine:
    seed = group[0]
    x0 = min(s.bbox[0] for s in group)
    y0 = min(s.bbox[1] for s in group)
    x1 = max(s.bbox[2] for s in group)
    y1 = max(s.bbox[3] for s in group)
    text = "".join(s.text for s in group)
    return TextLine(
        page_index=seed.page_index, text=text, bbox=(x0, y0, x1, y1),
        color_rgb=seed.color_rgb, direction=seed.direction, spans=tuple(group),
    )


def classify_text_line(line: TextLine) -> TextClass:
    stripped = line.text.strip()
    try:
        parse_feet_inches(stripped)
        return TextClass.DIMENSION_STRING
    except ParseError:
        pass
    if "CLG HT" in stripped.upper() or "CEILING" in stripped.upper():
        return TextClass.CEILING_HEIGHT_TAG
    return TextClass.OTHER
