"""The swappable PDF backend interface (plan §18 R5).

PyMuPDF is AGPL-3.0 / commercial. The project's commercial-license posture
is undecided (§21 Q1), so every PyMuPDF call is isolated behind this
interface from the first commit — swapping to pypdfium2 or pdfminer.six
later is a backend implementation, not a rewrite of ingest, extract, or
anything downstream.

Only the signals Sprint 1 needs are here: page geometry, per-page
vector/text/image counts for tier detection (§1), and rasterisation for
display and hand-tracing. Extraction proper (paths with fill/stroke/width,
text spans with position/font/colour) is a Stage 1 concern and belongs in
the `extract` package, built on top of this same interface.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class PageSignals:
    """Cheap per-page counts used for capability-tier detection (plan §1)."""

    page_index: int
    width_pt: float
    height_pt: float
    vector_path_count: int
    text_span_count: int
    image_area_fraction: float  # sum of raster image areas / page area, in [0, 1+]


@dataclass(frozen=True, slots=True)
class RawPath:
    """One vector drawing, backend-agnostic (plan §6 step 2).

    `points` is the path flattened to its straight-line vertices in PDF
    user-space (SheetCS, y-down) — beziers are pre-flattened by the
    backend, matching what the Garrigan fixture already contains natively
    (Appendix A: "no beziers survive"). `kind` distinguishes a filled
    region (wall/casework poché) from a stroked line (walls drawn as
    outlines, dimension lines, leaders) from both at once.
    """

    page_index: int
    draw_index: int
    kind: str  # "fill" | "stroke" | "fill+stroke"
    fill_rgb: tuple[float, float, float] | None
    stroke_rgb: tuple[float, float, float] | None
    width_pt: float | None
    dashes: str | None
    closed: bool
    rect: tuple[float, float, float, float]
    points: tuple[tuple[float, float], ...]


@dataclass(frozen=True, slots=True)
class RawTextSpan:
    """One text span, backend-agnostic. `direction` is the reading-direction
    unit vector PyMuPDF reports — this fixture only ever uses (1,0) or
    (0,-1) (Appendix A), never an arbitrary rotation."""

    page_index: int
    text: str
    bbox: tuple[float, float, float, float]
    size_pt: float
    color_rgb: tuple[float, float, float]
    font: str
    direction: tuple[float, float]


class PdfBackend(ABC):
    """A minimal PDF-reading capability. Implementations must not leak their
    underlying library's types across this boundary."""

    @abstractmethod
    def open(self, path: str) -> "PdfHandle":
        ...


class PdfHandle(ABC):
    @property
    @abstractmethod
    def page_count(self) -> int:
        ...

    @abstractmethod
    def page_signals(self, page_index: int) -> PageSignals:
        ...

    @abstractmethod
    def rasterize_page(self, page_index: int, dpi: int) -> bytes:
        """Render a page to PNG bytes at the given DPI."""
        ...

    @abstractmethod
    def raw_paths(self, page_index: int) -> list[RawPath]:
        """Every vector drawing on the page, in draw order. This is the
        Stage 1 extraction entry point (plan §6 step 2) — the `extract`
        package consumes this and nothing else of the underlying library."""
        ...

    @abstractmethod
    def raw_text_spans(self, page_index: int) -> list[RawTextSpan]:
        """Every text span on the page, in the backend's block/line order
        (plan §6 step 5)."""
        ...

    @abstractmethod
    def close(self) -> None:
        ...

    def __enter__(self) -> "PdfHandle":
        return self

    def __exit__(self, *exc) -> None:
        self.close()
