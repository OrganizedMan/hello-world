"""Work out which room is which, and how far each one reaches.

The drawing names every room -- KITCHEN, BEDROOM 2, POWDER ROOM -- but a label
is a piece of text at a point, not an extent. Anything that varies by room
(a tiled bathroom floor, cabinets in the kitchen and nowhere else) needs to know
where each room actually stops.

Walls give that, without any need to guess. Rasterise the storey, block the
cells a wall sits on, drop a seed at each label and let them all grow at once:
every reachable cell joins whichever label reaches it first. Doorways are gaps
in the wall, so two rooms meet in the opening rather than bleeding into each
other, which is where the boundary belongs anyway.
"""

from __future__ import annotations

import re
from collections import deque
from dataclasses import dataclass
from typing import Literal

from hearthview.a1_extract import A1Extraction, Label, POINTS_PER_FOOT
from hearthview.a1_trace import PdfRect

RoomKind = Literal[
    "kitchen", "bathroom", "bedroom", "living", "dining", "office",
    "utility", "storage", "circulation", "exterior", "other",
]

# Grid step. Three inches resolves a door opening without making the flood fill
# expensive: the whole first floor is about 160 by 180 cells.
CELL_INCHES = 3.0
CELL_POINTS = CELL_INCHES / 12.0 * POINTS_PER_FOOT

# Text on the sheet that names something other than a room. FIREPLACE is here
# rather than among the kinds because it is a feature standing inside a room:
# seeded as its own room it grew to 170 sq ft and took half the living room
# with it.
_NOT_A_ROOM = re.compile(
    r"RISERS?|TREADS?|HEIGHT|DEPTH|SCALE|=\s*1'|^\d|REMODEL|^ABOVE$|^NEW$|^\(E\)$"
    r"|FIREPLACE",
    re.IGNORECASE,
)

# Longest match wins, so "DINING ROOM" is not read as a bare "ROOM" and
# "WALK-IN" is not read as a bedroom.
_KINDS: tuple[tuple[str, RoomKind], ...] = (
    ("HANG OUT", "living"),
    ("LIVING ROOM", "living"),
    ("DINING ROOM", "dining"),
    ("STUDY ROOM", "office"),
    ("POWDER ROOM", "bathroom"),
    ("POWDER", "bathroom"),
    ("BATHROOM", "bathroom"),
    ("KITCHEN", "kitchen"),
    ("PANTRY", "storage"),
    ("BEDROOM", "bedroom"),
    ("OFFICE", "office"),
    ("STUDY", "office"),
    ("LAUNDRY", "utility"),
    ("MUDROOM", "utility"),
    ("WALK-IN", "storage"),
    ("CLOSET", "storage"),
    ("STORAGE", "storage"),
    ("BASEMENT", "storage"),
    ("STAIRCASE", "circulation"),
    ("STAIRS", "circulation"),
    ("HALL", "circulation"),
    ("ENTRY", "circulation"),
    ("DECK", "exterior"),
)


@dataclass(frozen=True)
class RoomGrid:
    """Which room owns each cell, so a point can be asked rather than a box.

    Room bounding boxes overlap on an L-shaped plan -- the living room's box can
    cover part of the kitchen -- so choosing a finish by box gives the wrong
    room along the join. The fill itself does not overlap, so keep it.
    """

    rooms: tuple["Room", ...]
    owner: tuple[int, ...]
    columns: int
    rows: int
    origin_x: float
    origin_y: float

    def runs(self) -> list[list[int]]:
        """Cell ownership as [room, row, first_column, last_column] runs.

        The grid is 160 by 178 per storey, which is bulky as a list of cells and
        compact as runs, because rooms are mostly convex. This is what travels
        to Blender: it must not need the PDF toolchain to know where a room is.
        """
        out: list[list[int]] = []
        for row in range(self.rows):
            start = 0
            base = row * self.columns
            while start < self.columns:
                who = self.owner[base + start]
                end = start
                while end + 1 < self.columns and self.owner[base + end + 1] == who:
                    end += 1
                if who >= 0:
                    out.append([who, row, start, end])
                start = end + 1
        return out

    def at(self, pdf_x: float, pdf_y: float) -> "Room | None":
        cx = int((pdf_x - self.origin_x) / CELL_POINTS)
        cy = int((pdf_y - self.origin_y) / CELL_POINTS)
        if not (0 <= cx < self.columns and 0 <= cy < self.rows):
            return None
        index = self.owner[cy * self.columns + cx]
        return self.rooms[index] if index >= 0 else None


@dataclass(frozen=True)
class Room:
    name: str
    kind: RoomKind
    bounds: PdfRect
    area_square_feet: float
    cells: int
    existing: bool          # labelled "(E)", meaning unchanged by the proposal

    @property
    def slug(self) -> str:
        return re.sub(r"[^a-z0-9]+", "_", self.name.lower()).strip("_")


def classify(text: str) -> RoomKind | None:
    """Room kind from a label, or None when the text does not name a room."""
    cleaned = text.upper().strip()
    if _NOT_A_ROOM.search(cleaned):
        return None
    for needle, kind in _KINDS:
        if needle in cleaned:
            return kind
    return None


def _merge_labels(labels: tuple[Label, ...]) -> list[tuple[str, PdfRect]]:
    """Join label lines that are stacked into one name.

    Room names wrap: POWDER / ROOM and OFFICE / / BEDROOM 4 arrive as separate
    spans, and reading them apart gives a room called "ROOM".
    """
    remaining = sorted(labels, key=lambda item: (item.bounds.y0, item.bounds.x0))
    merged: list[tuple[str, PdfRect]] = []
    used: set[int] = set()

    for index, label in enumerate(remaining):
        if index in used:
            continue
        text = label.text.strip()
        bounds = label.bounds
        line_height = max(bounds.y1 - bounds.y0, 1.0)
        for other_index, other in enumerate(remaining):
            if other_index <= index or other_index in used:
                continue
            gap = other.bounds.y0 - bounds.y1
            overlaps = other.bounds.x0 < bounds.x1 and bounds.x0 < other.bounds.x1
            if overlaps and -line_height * 0.4 <= gap <= line_height * 1.2:
                text = f"{text} {other.text.strip()}".strip()
                bounds = PdfRect(
                    min(bounds.x0, other.bounds.x0), min(bounds.y0, other.bounds.y0),
                    max(bounds.x1, other.bounds.x1), max(bounds.y1, other.bounds.y1),
                )
                used.add(other_index)
        merged.append((text, bounds))
    return merged


def detect_rooms(extraction: A1Extraction) -> tuple[Room, ...]:
    """Grow every room label outwards until it meets a wall or another room."""
    return build_room_grid(extraction).rooms


def build_room_grid(extraction: A1Extraction) -> RoomGrid:
    """The rooms, plus the cell ownership the fill produced."""
    footprint = extraction.footprint
    columns = max(1, int((footprint.x1 - footprint.x0) / CELL_POINTS) + 1)
    rows = max(1, int((footprint.y1 - footprint.y0) / CELL_POINTS) + 1)

    def cell_of(x: float, y: float) -> tuple[int, int]:
        return (
            min(columns - 1, max(0, int((x - footprint.x0) / CELL_POINTS))),
            min(rows - 1, max(0, int((y - footprint.y0) / CELL_POINTS))),
        )

    blocked = bytearray(columns * rows)
    for shape in extraction.layer("wall_new") + extraction.layer("wall_existing"):
        b = shape.bounds
        x0, y0 = cell_of(b.x0, b.y0)
        x1, y1 = cell_of(b.x1, b.y1)
        for cy in range(y0, y1 + 1):
            row = cy * columns
            for cx in range(x0, x1 + 1):
                blocked[row + cx] = 1

    seeds: list[tuple[str, RoomKind, bool, tuple[int, int]]] = []
    for text, bounds in _merge_labels(extraction.labels):
        kind = classify(text)
        if kind is None:
            continue
        existing = text.upper().lstrip().startswith("(E)")
        name = re.sub(r"^\(E\)\s*", "", text).strip()
        seeds.append((name, kind, existing, cell_of(
            (bounds.x0 + bounds.x1) / 2, (bounds.y0 + bounds.y1) / 2)))

    owner = [-1] * (columns * rows)
    queue: deque[tuple[int, int, int]] = deque()
    for index, (_name, _kind, _existing, (cx, cy)) in enumerate(seeds):
        # A label often sits on a wall glyph; step off it so the room can grow.
        for radius in range(0, 6):
            found = False
            for dy in range(-radius, radius + 1):
                for dx in range(-radius, radius + 1):
                    nx, ny = cx + dx, cy + dy
                    if not (0 <= nx < columns and 0 <= ny < rows):
                        continue
                    at = ny * columns + nx
                    if blocked[at] or owner[at] != -1:
                        continue
                    owner[at] = index
                    queue.append((nx, ny, index))
                    found = True
                    break
                if found:
                    break
            if found:
                break

    while queue:
        cx, cy, index = queue.popleft()
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            nx, ny = cx + dx, cy + dy
            if not (0 <= nx < columns and 0 <= ny < rows):
                continue
            at = ny * columns + nx
            if blocked[at] or owner[at] != -1:
                continue
            owner[at] = index
            queue.append((nx, ny, index))

    cell_area = (CELL_INCHES / 12.0) ** 2
    rooms: list[Room] = []
    kept: list[int] = []
    for index, (name, kind, existing, _seed) in enumerate(seeds):
        members = [i for i, who in enumerate(owner) if who == index]
        if not members:
            continue
        kept.append(index)
        xs = [i % columns for i in members]
        ys = [i // columns for i in members]
        rooms.append(Room(
            name=name,
            kind=kind,
            bounds=PdfRect(
                footprint.x0 + min(xs) * CELL_POINTS,
                footprint.y0 + min(ys) * CELL_POINTS,
                footprint.x0 + (max(xs) + 1) * CELL_POINTS,
                footprint.y0 + (max(ys) + 1) * CELL_POINTS,
            ),
            area_square_feet=round(len(members) * cell_area, 1),
            cells=len(members),
            existing=existing,
        ))
    # `owner` indexes into the seed list, so reorder it alongside any sort of
    # the rooms themselves or the two stop agreeing.
    order = sorted(range(len(rooms)), key=lambda i: -rooms[i].area_square_feet)
    remap = {old: new for new, old in enumerate(order)}
    seed_to_room = {seed_index: room_index for room_index, seed_index in enumerate(kept)}
    return RoomGrid(
        rooms=tuple(rooms[i] for i in order),
        owner=tuple(
            remap[seed_to_room[value]] if value in seed_to_room else -1
            for value in owner
        ),
        columns=columns,
        rows=rows,
        origin_x=footprint.x0,
        origin_y=footprint.y0,
    )
