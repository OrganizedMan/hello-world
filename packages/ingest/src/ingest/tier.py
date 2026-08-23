"""PDF capability-tier detection (plan §1).

A PDF is not one input format, it is three, and the product must say
which one it is looking at and what that costs the user *before* they
invest time tracing it:

  Tier A — native vector with structured semantics: minutes per floor.
  Tier B — native vector, flat semantics: tens of minutes per floor.
  Tier C — raster, no usable vector geometry: roughly an hour per floor.

These thresholds are a coarse, honest classifier, not a promise: a page
can be vector-rich but still poorly structured (Tier B in spirit) and this
module cannot see that yet — legend-driven colour semantics (Stage 1)
refines the A/B distinction. What this module guarantees is the one
distinction that matters most for setting expectations: is there vector
geometry to extract from at all (A or B) or not (C)?
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from .backend import PageSignals


class Tier(str, Enum):
    A = "A"  # native vector, structured semantics
    B = "B"  # native vector, flat semantics
    C = "C"  # raster — no usable vector geometry


EFFORT_ESTIMATE = {
    Tier.A: "minutes per floor — automatic extraction with review",
    Tier.B: "tens of minutes per floor — automatic geometry, manual semantics",
    Tier.C: "roughly an hour per floor — calibrate and trace by hand",
}

# A page dominated by one or more large raster images and with little to no
# vector content is a scan or a photograph of a drawing, regardless of how
# it got into the PDF.
_RASTER_IMAGE_AREA_FRACTION = 0.6
_RASTER_MAX_PATH_COUNT = 20

# Above this path count, a page carries enough vector detail that walls,
# openings and dimension lines are very likely present as real geometry
# (the Garrigan fixture sheets range from ~7,000 to ~22,000 paths).
_STRUCTURED_MIN_PATH_COUNT = 500
_STRUCTURED_MIN_TEXT_SPAN_COUNT = 20


@dataclass(frozen=True, slots=True)
class TierResult:
    tier: Tier
    effort_estimate: str
    signals: PageSignals

    def __str__(self) -> str:
        return f"Tier {self.tier.value} — {self.effort_estimate}"


def detect_tier(signals: PageSignals) -> TierResult:
    if (
        signals.image_area_fraction >= _RASTER_IMAGE_AREA_FRACTION
        and signals.vector_path_count < _RASTER_MAX_PATH_COUNT
    ):
        tier = Tier.C
    elif (
        signals.vector_path_count >= _STRUCTURED_MIN_PATH_COUNT
        and signals.text_span_count >= _STRUCTURED_MIN_TEXT_SPAN_COUNT
    ):
        tier = Tier.A
    else:
        tier = Tier.B

    return TierResult(tier=tier, effort_estimate=EFFORT_ESTIMATE[tier], signals=signals)
