import os
from pathlib import Path

import pytest

import hearthview.ingest as ingest
from hearthview.ingest import PdfIngestError, inspect_pdf, render_page, render_region


def test_inspect_and_render_one_page_pdf(tmp_path: Path, one_page_pdf: bytes) -> None:
    path = tmp_path / "plan.pdf"
    path.write_bytes(one_page_pdf)

    inspection = inspect_pdf(path)
    preview = render_page(path, page_number=1, max_width=600)

    assert inspection.page_count == 1
    assert inspection.encrypted is False
    assert preview.startswith(b"\x89PNG\r\n\x1a\n")


def test_render_rejects_page_outside_document(tmp_path: Path, one_page_pdf: bytes) -> None:
    path = tmp_path / "plan.pdf"
    path.write_bytes(one_page_pdf)

    with pytest.raises(PdfIngestError, match="Page 2 is not available"):
        render_page(path, page_number=2, max_width=600)


def test_render_page_wraps_page_decode_failure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class BrokenDocument:
        page_count = 1

        def load_page(self, _index: int):
            raise RuntimeError("damaged page tree")

        def close(self) -> None:
            pass

    path = tmp_path / "plan.pdf"
    path.write_bytes(b"%PDF-broken")
    monkeypatch.setattr(ingest.fitz, "open", lambda _path: BrokenDocument())

    with pytest.raises(PdfIngestError, match="could not be rendered"):
        render_page(path, page_number=1, max_width=600)


def test_render_region_returns_bounded_png_crop(tmp_path: Path, one_page_pdf: bytes) -> None:
    path = tmp_path / "plan.pdf"
    path.write_bytes(one_page_pdf)

    crop = render_region(
        path,
        page_number=1,
        pdf_polygon=((100, 100), (500, 100), (500, 500), (100, 500)),
        max_width=600,
    )

    assert crop.startswith(b"\x89PNG\r\n\x1a\n")


@pytest.mark.skipif("HEARTHVIEW_GARRIGAN_PDF" not in os.environ, reason="real fixture path not provided")
def test_real_garrigan_pdf_has_four_pages_and_a1_preview() -> None:
    path = Path(os.environ["HEARTHVIEW_GARRIGAN_PDF"])

    assert inspect_pdf(path).page_count == 4
    assert render_page(path, page_number=2, max_width=1000).startswith(b"\x89PNG")
