"""Stack the four drawn storeys into one building.

Each sheet is a plan of one level: A-0 basement, A-1 first, A-2 second, A-3
third. Two things have to be right for them to become a building rather than
four unrelated models.

**Horizontally, they share one datum.** A storey built on its own footprint
starts at (0, 0), which is correct alone and wrong stacked -- it would pile
every south-west corner on top of each other regardless of where each storey
actually sits. The sheets support a common origin, and this is checked rather
than assumed: on A-1's datum, A-0's east and west walls agree with A-1's to
0.02 ft, A-2's north edge to 0.01 ft, and A-3's east and west edges match A-2's
exactly. See `test_a1_building.py`.

**Vertically, they do not.** Ceiling heights are printed per storey, but the
floor assembly between one ceiling and the next floor is nowhere in the set --
it holds four plans and no section through the house. That thickness is a
convention, declared `assumed` here and surfaced in the browser, exactly as the
opening heights are.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from hearthview.a1_extract import A1Extraction, extract_a1
from hearthview.a1_massing import A1Massing, build_a1_massing
from hearthview.a1_trace import PdfRect
from hearthview.drawings import SHEET_PAGES
from hearthview.geometry import Primitive
from hearthview.units import TICKS_PER_INCH

# Ceiling to the floor above: joists, subfloor and finish. Not printed anywhere
# in this set, so it is a residential convention rather than a measurement.
ASSUMED_FLOOR_ASSEMBLY_INCHES = 12.0

# The storey the datum comes from, and the one at elevation zero.
DATUM_SHEET = "A-1"

STOREY_NAMES = {
    "A-0": "Basement",
    "A-1": "First floor",
    "A-2": "Second floor",
    "A-3": "Third floor",
}

# Bottom to top. Anything absent from the drawing set is simply skipped.
STOREY_ORDER = ("A-0", "A-1", "A-2", "A-3")


class A1BuildingError(ValueError):
    """Raised when the sheets cannot be assembled into a building."""


@dataclass(frozen=True)
class Storey:
    sheet: str
    name: str
    base_inches: float
    extraction: A1Extraction
    massing: A1Massing

    @property
    def ceiling_inches(self) -> float:
        return self.massing.ceiling.inches

    @property
    def primitives(self) -> tuple[Primitive, ...]:
        return self.massing.primitives


@dataclass(frozen=True)
class Building:
    storeys: tuple[Storey, ...]
    datum: PdfRect

    @property
    def primitives(self) -> tuple[Primitive, ...]:
        return tuple(item for storey in self.storeys for item in storey.primitives)

    @property
    def verified_fraction(self) -> float:
        total = sum(len(s.primitives) for s in self.storeys)
        if not total:
            return 0.0
        assumed = sum(len(s.massing.assumed_primitive_ids) for s in self.storeys)
        return (total - assumed) / total

    def storey(self, sheet: str) -> Storey:
        for candidate in self.storeys:
            if candidate.sheet == sheet:
                return candidate
        raise KeyError(sheet)


def _elevations(ceilings: dict[str, float]) -> dict[str, float]:
    """Floor level of each storey in inches, with the datum storey at zero.

    Upwards, each floor sits one ceiling plus one floor assembly above the last.
    Downwards is the same in reverse: the basement floor is its own ceiling and
    one assembly *below* the datum, so a deeper basement drops further.
    """
    base = {DATUM_SHEET: 0.0}
    order = [sheet for sheet in STOREY_ORDER if sheet in ceilings]
    datum_index = order.index(DATUM_SHEET)

    running = 0.0
    for sheet in order[datum_index + 1:]:
        running += ceilings[order[order.index(sheet) - 1]] + ASSUMED_FLOOR_ASSEMBLY_INCHES
        base[sheet] = running

    running = 0.0
    for sheet in reversed(order[:datum_index]):
        running -= ceilings[sheet] + ASSUMED_FLOOR_ASSEMBLY_INCHES
        base[sheet] = running
    return base


def build_building(source: Path) -> Building:
    """Extract every drawn storey and stack it on the datum sheet's origin."""
    extractions: dict[str, A1Extraction] = {}
    for sheet, page in SHEET_PAGES.items():
        try:
            extractions[sheet] = extract_a1(source, page_number=page)
        except Exception:  # a sheet that carries no readable plan is not a storey
            continue
    if DATUM_SHEET not in extractions:
        raise A1BuildingError(f"{DATUM_SHEET} is the datum and could not be read.")

    datum = extractions[DATUM_SHEET].footprint

    # Ceilings first: the elevations depend on every storey's height, so no
    # storey can be placed until they are all known.
    provisional: dict[str, A1Massing] = {}
    for sheet, extraction in extractions.items():
        try:
            provisional[sheet] = build_a1_massing(extraction, datum=datum)
        except Exception:
            continue
    if DATUM_SHEET not in provisional:
        raise A1BuildingError(f"{DATUM_SHEET} could not be massed.")

    ceilings = {sheet: massing.ceiling.inches for sheet, massing in provisional.items()}
    base_inches = _elevations(ceilings)

    storeys = []
    for sheet in STOREY_ORDER:
        if sheet not in provisional:
            continue
        elevation = base_inches[sheet]
        storeys.append(Storey(
            sheet=sheet,
            name=STOREY_NAMES[sheet],
            base_inches=elevation,
            extraction=extractions[sheet],
            massing=build_a1_massing(
                extractions[sheet],
                datum=datum,
                base_elevation_ticks=int(round(elevation * TICKS_PER_INCH)),
            ),
        ))
    return Building(storeys=tuple(storeys), datum=datum)
