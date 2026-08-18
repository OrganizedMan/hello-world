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
    def close(self) -> None:
        ...

    def __enter__(self) -> "PdfHandle":
        return self

    def __exit__(self, *exc) -> None:
        self.close()
