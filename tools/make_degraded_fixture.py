#!/usr/bin/env python3
"""Regenerate the Tier C fixture: a deliberately degraded raster of sheet
A-1 (plan §14 Stage 0 gate, Appendix D).

Renders page index 1 (sheet A-1, "Proposed - First Floor") of the main
Garrigan PDF to a 150 DPI JPEG and re-embeds it as the sole content of a
new single-page PDF: zero vector paths, one full-bleed raster image. JPEG
(not PNG) is used deliberately — it is both far smaller and a more
realistic stand-in for an actual scanned/photographed sheet than a
lossless re-encode would be.

Usage: python3 tools/make_degraded_fixture.py
"""
from __future__ import annotations

from pathlib import Path

import pymupdf

FIXTURE_DIR = Path(__file__).resolve().parent.parent / "fixtures" / "garrigan-261-grove" / "source"
SOURCE_PDF = FIXTURE_DIR / "garrigan-main-set.pdf"
OUT_PDF = FIXTURE_DIR / "garrigan-a1-degraded-150dpi.pdf"
SOURCE_PAGE_INDEX = 1  # sheet A-1
DPI = 150
JPEG_QUALITY = 85


def main() -> None:
    src = pymupdf.open(str(SOURCE_PDF))
    page = src[SOURCE_PAGE_INDEX]
    rect = page.rect

    pix = page.get_pixmap(dpi=DPI)
    jpg_bytes = pix.tobytes("jpg", jpg_quality=JPEG_QUALITY)

    out = pymupdf.open()
    new_page = out.new_page(width=rect.width, height=rect.height)
    new_page.insert_image(new_page.rect, stream=jpg_bytes)
    out.save(str(OUT_PDF), deflate=True, garbage=4)
    out.close()
    src.close()

    check = pymupdf.open(str(OUT_PDF))
    p = check[0]
    print(
        f"wrote {OUT_PDF} ({OUT_PDF.stat().st_size / 1e6:.2f} MB): "
        f"{len(p.get_drawings())} vector paths, {len(p.get_images())} image(s)"
    )
    check.close()


if __name__ == "__main__":
    main()
