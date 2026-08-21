from __future__ import annotations

from dataclasses import dataclass
from html import escape
from pathlib import Path

import pymupdf as fitz
from pypdf import PdfReader
from pypdf.errors import PdfReadError

from hearthview.a1_trace import PdfRect


class PdfIngestError(ValueError):
    """Raised when a source PDF cannot be safely inspected or rendered."""


@dataclass(frozen=True)
class PdfInspection:
    page_count: int
    encrypted: bool
    title: str | None


def inspect_pdf(path: Path) -> PdfInspection:
    try:
        with path.open("rb") as stream:
            if stream.read(5) != b"%PDF-":
                raise PdfIngestError("The file does not begin with a PDF header.")
            stream.seek(0)
            reader = PdfReader(stream)
            if reader.is_encrypted:
                raise PdfIngestError("Encrypted PDFs are not supported.")
            page_count = len(reader.pages)
            if page_count < 1:
                raise PdfIngestError("The PDF has no pages.")
            title = reader.metadata.title if reader.metadata else None
    except (OSError, PdfReadError, ValueError) as error:
        if isinstance(error, PdfIngestError):
            raise
        raise PdfIngestError("The PDF could not be parsed.") from error
    return PdfInspection(page_count=page_count, encrypted=False, title=title)


def render_page(path: Path, page_number: int, max_width: int) -> bytes:
    if not 320 <= max_width <= 2048:
        raise PdfIngestError("Preview width must be between 320 and 2048 pixels.")
    try:
        document = fitz.open(path)
    except (RuntimeError, ValueError) as error:
        raise PdfIngestError("The PDF could not be rendered.") from error
    try:
        if not 1 <= page_number <= document.page_count:
            raise PdfIngestError(
                f"Page {page_number} is not available in this {document.page_count}-page PDF."
            )
        page = document.load_page(page_number - 1)
        scale = max_width / page.rect.width
        pixmap = page.get_pixmap(matrix=fitz.Matrix(scale, scale), alpha=False)
        return pixmap.tobytes("png")
    except (RuntimeError, ValueError) as error:
        if isinstance(error, PdfIngestError):
            raise
        raise PdfIngestError("The PDF page could not be rendered.") from error
    finally:
        document.close()


def render_region(
    path: Path,
    page_number: int,
    pdf_polygon: tuple[tuple[int, int], ...],
    max_width: int,
) -> bytes:
    if not 320 <= max_width <= 2048:
        raise PdfIngestError("Preview width must be between 320 and 2048 pixels.")
    if len(pdf_polygon) < 3:
        raise PdfIngestError("The source region is not a valid polygon.")
    try:
        document = fitz.open(path)
    except (RuntimeError, ValueError) as error:
        raise PdfIngestError("The PDF could not be rendered.") from error
    try:
        if not 1 <= page_number <= document.page_count:
            raise PdfIngestError(
                f"Page {page_number} is not available in this {document.page_count}-page PDF."
            )
        page = document.load_page(page_number - 1)
        # Fixture evidence coordinates are recorded against the 4× PDF preview.
        xs = [point[0] / 4 for point in pdf_polygon]
        ys = [point[1] / 4 for point in pdf_polygon]
        padding = 18
        clip = fitz.Rect(
            max(page.rect.x0, min(xs) - padding),
            max(page.rect.y0, min(ys) - padding),
            min(page.rect.x1, max(xs) + padding),
            min(page.rect.y1, max(ys) + padding),
        )
        if clip.is_empty or clip.width <= 1 or clip.height <= 1:
            raise PdfIngestError("The source region falls outside the selected page.")
        scale = max_width / clip.width
        pixmap = page.get_pixmap(matrix=fitz.Matrix(scale, scale), clip=clip, alpha=False)
        return pixmap.tobytes("png")
    except (RuntimeError, ValueError) as error:
        if isinstance(error, PdfIngestError):
            raise
        raise PdfIngestError("The source region could not be rendered.") from error
    finally:
        document.close()


def render_rect(path: Path, *, page_number: int, rect: PdfRect, max_width: int) -> bytes:
    """Render an original-PDF-coordinate crop without evidence-preview scaling."""
    if not 320 <= max_width <= 2048:
        raise PdfIngestError("Preview width must be between 320 and 2048 pixels.")
    try:
        document = fitz.open(path)
    except (RuntimeError, ValueError) as error:
        raise PdfIngestError("The PDF could not be rendered.") from error
    try:
        if not 1 <= page_number <= document.page_count:
            raise PdfIngestError(
                f"Page {page_number} is not available in this {document.page_count}-page PDF."
            )
        page = document.load_page(page_number - 1)
        x_scale = page.rect.width / 2592.0
        y_scale = page.rect.height / 1728.24
        clip = fitz.Rect(
            rect.x0 * x_scale,
            rect.y0 * y_scale,
            rect.x1 * x_scale,
            rect.y1 * y_scale,
        )
        if clip.is_empty or clip.width <= 1 or clip.height <= 1:
            raise PdfIngestError("The A-1 proposed-plan crop is not available.")
        scale = max_width / clip.width
        pixmap = page.get_pixmap(
            matrix=fitz.Matrix(scale, scale), clip=clip, alpha=False
        )
        return pixmap.tobytes("png")
    except (RuntimeError, ValueError) as error:
        if isinstance(error, PdfIngestError):
            raise
        raise PdfIngestError("The A-1 proposed-plan crop could not be rendered.") from error
    finally:
        document.close()


def render_vector_rect(path: Path, *, page_number: int, rect: PdfRect) -> bytes:
    """Extract drawing paths directly from a PDF crop as a source-bound SVG.

    This deliberately does not infer rooms or simplify geometry. Every rendered
    path originates in the uploaded PDF's vector drawing commands.
    """
    try:
        document = fitz.open(path)
    except (RuntimeError, ValueError) as error:
        raise PdfIngestError("The PDF could not be read for vector tracing.") from error
    try:
        if not 1 <= page_number <= document.page_count:
            raise PdfIngestError("The requested plan page is not available.")
        page = document.load_page(page_number - 1)
        x_scale = page.rect.width / 2592.0
        y_scale = page.rect.height / 1728.24
        clip = fitz.Rect(
            rect.x0 * x_scale,
            rect.y0 * y_scale,
            rect.x1 * x_scale,
            rect.y1 * y_scale,
        )

        def point(point: fitz.Point) -> tuple[float, float]:
            return (point.x / x_scale, point.y / y_scale)

        paths: list[str] = []
        drawing_count = 0
        for drawing in page.get_drawings():
            if not drawing["rect"].intersects(clip):
                continue
            commands: list[str] = []
            for item in drawing["items"]:
                if item[0] == "l":
                    start_x, start_y = point(item[1])
                    end_x, end_y = point(item[2])
                    commands.append(f"M {start_x:.2f} {start_y:.2f} L {end_x:.2f} {end_y:.2f}")
                elif item[0] == "re":
                    bounds = item[1]
                    x0, y0 = point(bounds.top_left)
                    x1, y1 = point(bounds.bottom_right)
                    commands.append(f"M {x0:.2f} {y0:.2f} H {x1:.2f} V {y1:.2f} H {x0:.2f} Z")
                elif item[0] == "qu":
                    quad = item[1]
                    points = [point(quad.ul), point(quad.ur), point(quad.lr), point(quad.ll)]
                    commands.append("M " + " L ".join(f"{x:.2f} {y:.2f}" for x, y in points) + " Z")
            if not commands:
                continue
            drawing_count += 1
            fill = "#1e2822" if drawing["type"] in {"f", "fs"} else "none"
            paths.append(
                f'<path d="{escape(" ".join(commands), quote=True)}" fill="{fill}" '
                'stroke="#1e2822" stroke-width="0.7" vector-effect="non-scaling-stroke"/>'
            )
        svg = (
            f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="{rect.x0} {rect.y0} '
            f'{rect.x1 - rect.x0} {rect.y1 - rect.y0}" role="img" '
            'aria-label="Vector linework extracted directly from the source PDF">'
            f'<metadata>source-drawing-count={drawing_count}</metadata>{"".join(paths)}</svg>'
        )
        return svg.encode("utf-8")
    except (RuntimeError, ValueError, KeyError) as error:
        raise PdfIngestError("The PDF vector trace could not be extracted.") from error
    finally:
        document.close()
