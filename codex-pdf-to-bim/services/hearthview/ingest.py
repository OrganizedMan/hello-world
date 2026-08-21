from __future__ import annotations

from dataclasses import dataclass
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
