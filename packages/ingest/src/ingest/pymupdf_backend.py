"""PyMuPDF implementation of the PdfBackend interface.

⚠️ PyMuPDF is AGPL-3.0 (or a commercial Artifex license). This module is
the *only* place `pymupdf` is imported anywhere in the pipeline — see
plan §18 R5. Swapping backends means writing a new module that satisfies
`ingest.backend.PdfBackend`/`PdfHandle`, not touching callers.
"""
from __future__ import annotations

import pymupdf

from .backend import PageSignals, PdfBackend, PdfHandle


class PyMuPdfHandle(PdfHandle):
    def __init__(self, doc: "pymupdf.Document") -> None:
        self._doc = doc

    @property
    def page_count(self) -> int:
        return self._doc.page_count

    def page_signals(self, page_index: int) -> PageSignals:
        page = self._doc[page_index]
        rect = page.rect
        page_area = max(rect.width * rect.height, 1.0)

        vector_path_count = len(page.get_drawings())

        text_span_count = 0
        for block in page.get_text("dict")["blocks"]:
            if block["type"] != 0:
                continue
            for line in block["lines"]:
                text_span_count += len(line["spans"])

        image_area = 0.0
        for info in page.get_image_info():
            bbox = info.get("bbox")
            if not bbox:
                continue
            x0, y0, x1, y1 = bbox
            # Clip to the page rect: some embedded images are declared
            # larger than their visible placement.
            ix0, iy0 = max(x0, rect.x0), max(y0, rect.y0)
            ix1, iy1 = min(x1, rect.x1), min(y1, rect.y1)
            if ix1 > ix0 and iy1 > iy0:
                image_area += (ix1 - ix0) * (iy1 - iy0)

        return PageSignals(
            page_index=page_index,
            width_pt=rect.width,
            height_pt=rect.height,
            vector_path_count=vector_path_count,
            text_span_count=text_span_count,
            image_area_fraction=image_area / page_area,
        )

    def rasterize_page(self, page_index: int, dpi: int) -> bytes:
        page = self._doc[page_index]
        pix = page.get_pixmap(dpi=dpi)
        return pix.tobytes("png")

    def close(self) -> None:
        self._doc.close()


class PyMuPdfBackend(PdfBackend):
    def open(self, path: str) -> PyMuPdfHandle:
        return PyMuPdfHandle(pymupdf.open(path))
