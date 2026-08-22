"""Derive the A-1 proposed-plan trace from the source PDF's own vectors.

Nothing here is hand-placed. Every coordinate is copied verbatim from a fill
path or stroke in the uploaded drawing, so a review overlay aligns with the
sheet by construction rather than by fitting.

Classification comes from the sheet's own WALL LEGEND. The legend swatches and
the plan use slightly different greys, so the plan's values are the ones
matched here:

    #4C4C4C  new 2x wood frame wall      #E6E6E6  counter / cabinet run
    #D9D9D9  existing wall               #EAEAEA  plumbing + appliance fixture

Excluded by never matching a class: dimension chains and their tick marks, red
demolition linework, furniture, the white boxes that back text labels, the
title block, the north arrow, and the whole existing-plan view.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
import re
from typing import Iterable, Literal, Sequence

import pymupdf as fitz

from hearthview.a1_trace import PdfRect

Point = tuple[float, float]
Polygon = tuple[Point, ...]
LayerName = Literal[
    "wall_new", "wall_existing", "counter", "fixture", "deck", "stair", "door"
]

# Sheet scale: 1/4" = 1'-0" on a 36x24 sheet at 72 dpi.
POINTS_PER_FOOT = 18.0
POINTS_PER_INCH = POINTS_PER_FOOT / 12.0

FILL_WALL_NEW = "#4C4C4C"
FILL_WALL_EXISTING = "#D9D9D9"
FILL_COUNTER = "#E6E6E6"
FILL_FIXTURE = "#EAEAEA"
FILL_PAPER = "#FFFFFF"

# A wall's poche is between a 3" partition and a 21" masonry pier. Anything
# thinner is trim or a stair tread; anything thicker is a counter or a room.
WALL_MIN_INCHES = 3.0
WALL_MAX_INCHES = 21.0
_SUBPATH_EPSILON = 0.05
# Inches are marked with a real double quote on A-1 (`8'  5"`) and with two
# apostrophes on A-0 and A-3 (`6'-9''`). Accepting only the first silently lost
# every ceiling height on those sheets, which read as the drawing not printing
# one at all.
_HEIGHT_TEXT = re.compile(r"""(\d+)'\s*-?\s*(\d+)?\s*(?:"|'')""")
# A bare 6'-3" only counts as a ceiling height when it sits beside a LOW
# CEILING note; on its own it is one of the sheet's many plan dimensions.
_LOW_ZONE_RADIUS = 45.0


class A1ExtractError(ValueError):
    """Raised when the A-1 proposed view cannot be located in a PDF."""


@dataclass(frozen=True)
class Shape:
    """One closed subpath lifted straight out of the PDF."""

    layer: LayerName
    points: Polygon

    @property
    def bounds(self) -> PdfRect:
        xs = [p[0] for p in self.points]
        ys = [p[1] for p in self.points]
        return PdfRect(min(xs), min(ys), max(xs), max(ys))


@dataclass(frozen=True)
class Opening:
    """A gap between two collinear wall segments: a door, window or cased opening."""

    axis: Literal["horizontal", "vertical"]
    bounds: PdfRect
    width_feet: float


@dataclass(frozen=True)
class Label:
    text: str
    bounds: PdfRect


@dataclass(frozen=True)
class StairNote:
    """The printed NEW STAIRS callout: riser and tread dimensions."""

    risers: int
    riser_height_inches: float
    treads: int
    tread_depth_inches: float


@dataclass(frozen=True)
class CeilingNote:
    """A printed ceiling height, in inches.

    ``kind`` separates a room's `CLG HT - 8' 5"` from the bare heights that
    annotate the LOW CEILING zone by the stair.
    """

    text: str
    inches: float
    bounds: PdfRect
    kind: Literal["room", "low_zone"]


@dataclass(frozen=True)
class A1Extraction:
    page_number: int
    page_width_points: float
    page_height_points: float
    footprint: PdfRect
    view: PdfRect
    shapes: tuple[Shape, ...]
    openings: tuple[Opening, ...]
    labels: tuple[Label, ...]
    ceiling_notes: tuple[CeilingNote, ...] = field(default=())
    stair_note: StairNote | None = field(default=None)
    stair_treads: tuple[tuple[Point, Point], ...] = field(default=())

    def layer(self, name: LayerName) -> tuple[Shape, ...]:
        return tuple(shape for shape in self.shapes if shape.layer == name)


def _hex(colour: Sequence[float] | None) -> str | None:
    if colour is None:
        return None
    return "#%02X%02X%02X" % tuple(int(round(channel * 255)) for channel in colour)


def _subpaths(drawing: dict) -> list[Polygon]:
    """Split a drawing into disjoint closed subpaths.

    A single PDF fill often holds a whole wall run: one subpath per solid
    stretch, with the door and window gaps simply absent. Splitting on path
    discontinuity is what makes those openings recoverable.
    """
    out: list[list[Point]] = []
    current: list[Point] = []
    for item in drawing["items"]:
        if item[0] == "l":
            start = (item[1].x, item[1].y)
            end = (item[2].x, item[2].y)
            if current and (
                abs(current[-1][0] - start[0]) > _SUBPATH_EPSILON
                or abs(current[-1][1] - start[1]) > _SUBPATH_EPSILON
            ):
                out.append(current)
                current = [start, end]
            else:
                if not current:
                    current = [start]
                current.append(end)
        elif item[0] == "re":
            if current:
                out.append(current)
                current = []
            rect = item[1]
            out.append(
                [
                    (rect.x0, rect.y0),
                    (rect.x1, rect.y0),
                    (rect.x1, rect.y1),
                    (rect.x0, rect.y1),
                    (rect.x0, rect.y0),
                ]
            )
    if current:
        out.append(current)
    return [tuple(path) for path in out if len(path) >= 3]


def _rect_of(points: Iterable[Point]) -> fitz.Rect:
    pts = list(points)
    xs = [p[0] for p in pts]
    ys = [p[1] for p in pts]
    return fitz.Rect(min(xs), min(ys), max(xs), max(ys))


def _is_wall_sized(rect: fitz.Rect, *, min_feet: float) -> bool:
    thickness = min(rect.width, rect.height) / POINTS_PER_INCH
    length = max(rect.width, rect.height) / POINTS_PER_FOOT
    return WALL_MIN_INCHES <= thickness <= WALL_MAX_INCHES and length >= min_feet


VIEW_GAP_FEET = 3.0   # blank space this wide separates one drawn view from another


def _largest_poche_cluster(seeds: list[fitz.Rect]) -> list[fitz.Rect]:
    """The single body of wall poche carrying the most drawn wall.

    A-1 has one plan on the right half of the sheet, so bounding everything
    right of the midline found it. Other sheets do not: A-2 carries the OP#B
    option as a second plan, and A-3 a wide shallow strip that is not a plan at
    all. Bounding both together produced a footprint spanning the gap between
    them -- a second floor apparently deeper than the first.

    Clustering by proximity and keeping the largest is stable across all four
    sheets, and degenerates to the old behaviour when a sheet holds one view.
    """
    gap = VIEW_GAP_FEET * POINTS_PER_FOOT
    remaining = sorted(seeds, key=lambda r: (r.y0, r.x0))
    clusters: list[list[fitz.Rect]] = []
    while remaining:
        cluster = [remaining.pop(0)]
        grew = True
        while grew:
            grew = False
            for candidate in list(remaining):
                if any(_within(candidate, member, gap) for member in cluster):
                    cluster.append(candidate)
                    remaining.remove(candidate)
                    grew = True
        clusters.append(cluster)
    # Total poche area, not rectangle count: one plan drawn with fewer, longer
    # wall runs should still beat a dense cluster of short marks.
    return max(clusters, key=lambda group: sum(r.width * r.height for r in group))


def _within(a: fitz.Rect, b: fitz.Rect, gap: float) -> bool:
    """True when two rectangles are closer than `gap` on both axes."""
    return (
        a.x0 - gap <= b.x1 and b.x0 - gap <= a.x1
        and a.y0 - gap <= b.y1 and b.y0 - gap <= a.y1
    )


def _locate_view(drawings: list[dict], page: fitz.Rect) -> tuple[PdfRect, fitz.Rect]:
    """Find the proposed view by clustering wall poche, never by fixed coordinates."""
    midline = page.width / 2
    seeds = [
        drawing["rect"]
        for drawing in drawings
        if drawing["type"] in ("f", "fs")
        and _hex(drawing.get("fill")) in (FILL_WALL_NEW, FILL_WALL_EXISTING)
        and drawing["rect"].x0 > midline
        and _is_wall_sized(drawing["rect"], min_feet=1.0)
    ]
    if not seeds:
        raise A1ExtractError("No proposed-plan wall poche was found on this page.")
    seeds = _largest_poche_cluster(seeds)
    footprint = PdfRect(
        min(r.x0 for r in seeds),
        min(r.y0 for r in seeds),
        max(r.x1 for r in seeds),
        max(r.y1 for r in seeds),
    )
    # The deck sits above the wall footprint and carries no poche of its own.
    view = fitz.Rect(
        footprint.x0 - 45, footprint.y0 - 150, footprint.x1 + 45, footprint.y1 + 45
    )
    return footprint, view


def _find_openings(walls: Sequence[Shape]) -> list[Opening]:
    horizontal: dict[tuple[float, float], list[PdfRect]] = defaultdict(list)
    vertical: dict[tuple[float, float], list[PdfRect]] = defaultdict(list)
    for shape in walls:
        b = shape.bounds
        if (b.x1 - b.x0) >= (b.y1 - b.y0):
            horizontal[(round(b.y0, 1), round(b.y1, 1))].append(b)
        else:
            vertical[(round(b.x0, 1), round(b.x1, 1))].append(b)

    out: list[Opening] = []
    for (y0, y1), rects in horizontal.items():
        rects.sort(key=lambda r: r.x0)
        for left, right in zip(rects, rects[1:]):
            gap = right.x0 - left.x1
            if 4.0 <= gap <= 200.0:
                out.append(
                    Opening("horizontal", PdfRect(left.x1, y0, right.x0, y1), gap / POINTS_PER_FOOT)
                )
    for (x0, x1), rects in vertical.items():
        rects.sort(key=lambda r: r.y0)
        for top, bottom in zip(rects, rects[1:]):
            gap = bottom.y0 - top.y1
            if 4.0 <= gap <= 200.0:
                out.append(
                    Opening("vertical", PdfRect(x0, top.y1, x1, bottom.y0), gap / POINTS_PER_FOOT)
                )
    return out


def _door_swings(drawings: list[dict], view: fitz.Rect) -> list[Shape]:
    """Door arcs are exported as flattened polylines with a near-square bounding box."""
    out: list[Shape] = []
    for drawing in drawings:
        rect = drawing["rect"]
        if drawing["type"] != "s" or not _contains(view, rect):
            continue
        if _hex(drawing.get("color")) not in ("#000000", "#7F7F7F"):
            continue
        if rect.width < 1 or rect.height < 1:
            continue
        aspect = max(rect.width, rect.height) / min(rect.width, rect.height)
        span = max(rect.width, rect.height) / POINTS_PER_FOOT
        segments = [item for item in drawing["items"] if item[0] == "l"]
        if 1.0 <= aspect <= 1.7 and 1.2 <= span <= 4.5 and len(segments) >= 6:
            points: list[Point] = [(segments[0][1].x, segments[0][1].y)]
            points.extend((item[2].x, item[2].y) for item in segments)
            out.append(Shape("door", tuple(points)))
    return out


def _contains(view: fitz.Rect, rect: fitz.Rect) -> bool:
    return (
        rect.x0 >= view.x0 and rect.x1 <= view.x1 and rect.y0 >= view.y0 and rect.y1 <= view.y1
    )


def _merge_spans(spans: list[tuple[float, float]]) -> list[list[float]]:
    ordered = sorted(spans)
    merged = [list(ordered[0])]
    for start, end in ordered[1:]:
        if start <= merged[-1][1] + 2.0:
            merged[-1][1] = max(merged[-1][1], end)
        else:
            merged.append([start, end])
    return merged


def _stair_treads(path: Path, page_number: int, view: fitz.Rect) -> list[tuple[Point, Point]]:
    """Recover stair treads with pdfplumber.

    PyMuPDF's ``get_drawings`` silently omits these strokes on this sheet; a
    cross-check against pdfplumber recovers them. When pdfplumber is missing the
    stair is simply absent rather than guessed.
    """
    try:
        import pdfplumber
    except ImportError:  # pragma: no cover - optional at runtime
        return []

    with pdfplumber.open(path) as pdf:
        page = pdf.pages[page_number - 1]
        dx, dy = -page.bbox[0], -page.bbox[1]
        rows: dict[float, list[tuple[float, float]]] = defaultdict(list)
        for line in page.lines:
            x0, x1 = line["x0"] + dx, line["x1"] + dx
            top, bottom = line["top"] + dy, line["bottom"] + dy
            if not _contains(view, fitz.Rect(min(x0, x1), min(top, bottom), max(x0, x1), max(top, bottom))):
                continue
            if abs(bottom - top) < 0.6:
                rows[round(top, 1)].append((min(x0, x1), max(x0, x1)))

    spans = {}
    for y, intervals in rows.items():
        widest = max(_merge_spans(intervals), key=lambda s: s[1] - s[0])
        if 30 <= widest[1] - widest[0] <= 150:
            spans[y] = widest
    if len(spans) < 4:
        return []

    buckets: dict[int, list[float]] = defaultdict(list)
    for y, (a, b) in spans.items():
        buckets[round(((a + b) / 2) / 20)].append(y)

    treads: list[tuple[Point, Point]] = []
    for ys in buckets.values():
        ys.sort()
        if len(ys) < 4:
            continue
        i = 0
        while i < len(ys) - 1:
            j = i + 1
            step = ys[j] - ys[i]
            if step < 6 or step > 30:
                i += 1
                continue
            run = [ys[i], ys[j]]
            while j + 1 < len(ys) and abs((ys[j + 1] - ys[j]) - step) < 2.5:
                j += 1
                run.append(ys[j])
            if len(run) >= 4:
                treads.extend(((spans[y][0], y), (spans[y][1], y)) for y in run)
            i = j if j > i + 1 else i + 1
    return treads


def _stair_note(page) -> StairNote | None:
    """Read the NEW STAIRS callout.

    It sits above the plan view rather than inside it, so it is collected from
    the whole page. It is the only printed vertical dimension in this drawing
    set besides the ceiling notes.
    """
    text = page.get_text("text")
    risers = re.search(r"(\d+)\s+RISERS", text)
    riser_h = re.search(r"HEIGHT OF RISERS:\s*(\d+(?:\.\d+)?)\"", text)
    treads = re.search(r"(\d+)\s+TREADS", text)
    tread_d = re.search(r"DEPTH OF TREADS:\s*(\d+(?:\.\d+)?)\"", text)
    if not (risers and riser_h and treads and tread_d):
        return None
    return StairNote(
        int(risers.group(1)),
        float(riser_h.group(1)),
        int(treads.group(1)),
        float(tread_d.group(1)),
    )


def extract_a1(path: Path, *, page_number: int = 2) -> A1Extraction:
    """Extract the proposed first-floor architectural layer from an A-1 sheet."""
    document = fitz.open(path)
    try:
        if not 1 <= page_number <= document.page_count:
            raise A1ExtractError(f"Page {page_number} is not present in this PDF.")
        page = document.load_page(page_number - 1)
        drawings = page.get_drawings()
        footprint, view = _locate_view(drawings, page.rect)

        shapes: list[Shape] = []
        deck: Shape | None = None
        for drawing in drawings:
            if drawing["type"] not in ("f", "fs") or not _contains(view, drawing["rect"]):
                continue
            fill = _hex(drawing.get("fill"))

            if fill == FILL_PAPER:
                # The deck has no poche; it is the one large paper-filled polygon
                # in the view. Label backing boxes are small and near-trivial.
                rect = drawing["rect"]
                if rect.width * rect.height > 20000 and len(drawing["items"]) > 8:
                    widest = max(_subpaths(drawing), key=lambda s: _rect_of(s).get_area())
                    if deck is None or _rect_of(widest).get_area() > _rect_of(deck.points).get_area():
                        deck = Shape("deck", widest)
                continue

            if fill not in (FILL_WALL_NEW, FILL_WALL_EXISTING, FILL_COUNTER, FILL_FIXTURE):
                continue

            # An angled wall (the dining-room bay) splits into short diagonal
            # subpaths whose individual bounds understate their thickness, so a
            # subpath is kept when its parent drawing reads as a wall.
            parent_is_wall = fill in (
                FILL_WALL_NEW,
                FILL_WALL_EXISTING,
            ) and _is_wall_sized(drawing["rect"], min_feet=0.6)

            for subpath in _subpaths(drawing):
                rect = _rect_of(subpath)
                if fill in (FILL_WALL_NEW, FILL_WALL_EXISTING):
                    if parent_is_wall or _is_wall_sized(rect, min_feet=0.3):
                        layer: LayerName = (
                            "wall_new" if fill == FILL_WALL_NEW else "wall_existing"
                        )
                        shapes.append(Shape(layer, subpath))
                elif min(rect.width, rect.height) >= 10.0:
                    shapes.append(
                        Shape("counter" if fill == FILL_COUNTER else "fixture", subpath)
                    )

        if deck is not None:
            shapes.append(deck)
        shapes.extend(_door_swings(drawings, view))

        walls = [s for s in shapes if s.layer in ("wall_new", "wall_existing")]
        openings = _find_openings(walls)

        labels: list[Label] = []
        ceiling_notes: list[CeilingNote] = []
        low_zones: list[fitz.Rect] = []
        candidates: list[tuple[str, fitz.Rect]] = []
        for block in page.get_text("dict")["blocks"]:
            if block["type"] != 0:
                continue
            for line in block["lines"]:
                for span in line["spans"]:
                    text = span["text"].strip()
                    bbox = fitz.Rect(span["bbox"])
                    if not _contains(view, bbox):
                        continue
                    upper = text.upper()
                    if "CLG" in upper or "CEILING" in upper:
                        match = _HEIGHT_TEXT.search(text)
                        if match:
                            feet = int(match.group(1))
                            inches = int(match.group(2) or 0)
                            ceiling_notes.append(
                                CeilingNote(
                                    text,
                                    feet * 12 + inches,
                                    PdfRect(bbox.x0, bbox.y0, bbox.x1, bbox.y1),
                                    "room",
                                )
                            )
                        if "LOW" in upper:
                            low_zones.append(bbox)
                        continue
                    if _HEIGHT_TEXT.fullmatch(text):
                        candidates.append((text, bbox))
                        continue
                    if (
                        span["font"] in ("Arial-BoldMT", "ArialMT")
                        and span["size"] >= 9.0
                        and text.upper() == text
                        and len(text) >= 4
                        and "CLG" not in text
                    ):
                        labels.append(
                            Label(text, PdfRect(bbox.x0, bbox.y0, bbox.x1, bbox.y1))
                        )

        # Bare heights next to a LOW CEILING note describe that zone.
        for text, bbox in candidates:
            for zone in low_zones:
                near = fitz.Rect(
                    zone.x0 - _LOW_ZONE_RADIUS,
                    zone.y0 - _LOW_ZONE_RADIUS,
                    zone.x1 + _LOW_ZONE_RADIUS,
                    zone.y1 + _LOW_ZONE_RADIUS,
                )
                if near.intersects(bbox):
                    match = _HEIGHT_TEXT.search(text)
                    feet = int(match.group(1))
                    inches = int(match.group(2) or 0)
                    if feet * 12 + inches < 60:
                        break  # a plan dimension that merely sits nearby
                    ceiling_notes.append(
                        CeilingNote(
                            text,
                            feet * 12 + inches,
                            PdfRect(bbox.x0, bbox.y0, bbox.x1, bbox.y1),
                            "low_zone",
                        )
                    )
                    break

        stair_note = _stair_note(page)
        treads = _stair_treads(Path(path), page_number, view)
        return A1Extraction(
            page_number=page_number,
            page_width_points=page.rect.width,
            page_height_points=page.rect.height,
            footprint=footprint,
            view=PdfRect(view.x0, view.y0, view.x1, view.y1),
            shapes=tuple(shapes),
            openings=tuple(openings),
            labels=tuple(labels),
            ceiling_notes=tuple(ceiling_notes),
            stair_note=stair_note,
            stair_treads=tuple(treads),
        )
    finally:
        document.close()
