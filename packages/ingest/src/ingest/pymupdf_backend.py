"""PyMuPDF implementation of the PdfBackend interface.

⚠️ PyMuPDF is AGPL-3.0 (or a commercial Artifex license). This module is
the *only* place `pymupdf` is imported anywhere in the pipeline — see
plan §18 R5. Swapping backends means writing a new module that satisfies
`ingest.backend.PdfBackend`/`PdfHandle`, not touching callers.
"""
from __future__ import annotations

import pymupdf

from .backend import PageSignals, PdfBackend, PdfHandle, RawPath, RawTextSpan


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

    def raw_paths(self, page_index: int) -> list[RawPath]:
        page = self._doc[page_index]
        out: list[RawPath] = []
        for draw_index, d in enumerate(page.get_drawings()):
            points = _flatten_path_items(d["items"])
            rect = d["rect"]
            out.append(RawPath(
                page_index=page_index,
                draw_index=draw_index,
                kind={"f": "fill", "s": "stroke", "fs": "fill+stroke"}[d["type"]],
                fill_rgb=d["fill"],
                stroke_rgb=d["color"],
                width_pt=d["width"],
                dashes=d["dashes"],
                closed=bool(d["closePath"]),
                rect=(rect.x0, rect.y0, rect.x1, rect.y1),
                points=points,
            ))
        return out

    def raw_text_spans(self, page_index: int) -> list[RawTextSpan]:
        page = self._doc[page_index]
        out: list[RawTextSpan] = []
        for block in page.get_text("dict")["blocks"]:
            if block["type"] != 0:
                continue
            for line in block["lines"]:
                for span in line["spans"]:
                    out.append(RawTextSpan(
                        page_index=page_index,
                        text=span["text"],
                        bbox=tuple(span["bbox"]),
                        size_pt=span["size"],
                        color_rgb=_int_to_rgb(span["color"]),
                        font=span["font"],
                        direction=tuple(line["dir"]),
                    ))
        return out

    def close(self) -> None:
        self._doc.close()


def _int_to_rgb(color: int) -> tuple[float, float, float]:
    """PyMuPDF packs text-span colour as a single 0xRRGGBB int, unlike
    drawing fill/stroke colour which is already an (r, g, b) float tuple."""
    r = ((color >> 16) & 0xFF) / 255.0
    g = ((color >> 8) & 0xFF) / 255.0
    b = (color & 0xFF) / 255.0
    return (r, g, b)


def _flatten_path_items(items: list) -> tuple[tuple[float, float], ...]:
    """Reduce a drawing's item list to an ordered polyline/polygon of
    vertices. This fixture's paths are entirely straight segments
    (Appendix A: "no beziers survive"); curves and rects are still handled
    so the extractor does not silently drop geometry on a different
    document set."""
    points: list[tuple[float, float]] = []

    def add(pt) -> None:
        p = (pt.x, pt.y)
        if not points or points[-1] != p:
            points.append(p)

    for item in items:
        op = item[0]
        if op == "l":
            add(item[1])
            add(item[2])
        elif op == "re":
            rect = item[1]
            add(pymupdf.Point(rect.x0, rect.y0))
            add(pymupdf.Point(rect.x1, rect.y0))
            add(pymupdf.Point(rect.x1, rect.y1))
            add(pymupdf.Point(rect.x0, rect.y1))
            add(pymupdf.Point(rect.x0, rect.y0))
        elif op == "qu":
            quad = item[1]
            for pt in (quad.ul, quad.ur, quad.lr, quad.ll):
                add(pt)
        elif op == "c":
            # Bezier: keep the anchor points, drop the control points —
            # good enough for wall/dimension-line geometry, which never
            # uses curves in this fixture.
            add(item[1])
            add(item[4])
    return tuple(points)


class PyMuPdfBackend(PdfBackend):
    def open(self, path: str) -> PyMuPdfHandle:
        return PyMuPdfHandle(pymupdf.open(path))
