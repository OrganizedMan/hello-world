"""Path/text harvest with stable identity and text-mask suppression
(plan §6 steps 2, 5, 7).

This module only consumes `ingest.RawPath`/`RawTextSpan` — it never
imports pymupdf directly, preserving the AGPL isolation boundary (plan
§18 R5): a backend swap changes `ingest`, not `extract`.
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass, fields

from ingest import PdfHandle, RawPath, RawTextSpan

from .colors import TEXT_MASK_FILL, color_close

# Points are quantised to 1/100 pt before hashing so that a path_uid is
# stable across re-extraction of the same document even if a future
# backend reports coordinates with slightly different floating-point
# noise, while still changing whenever the actual geometry changes.
_QUANT = 100.0


def _path_uid(page_index: int, draw_index: int, points: tuple[tuple[float, float], ...]) -> str:
    quantised = tuple((round(x * _QUANT), round(y * _QUANT)) for x, y in points)
    payload = f"{page_index}:{draw_index}:{quantised}".encode()
    return hashlib.sha1(payload).hexdigest()


@dataclass(frozen=True, slots=True)
class HarvestedPath(RawPath):
    path_uid: str = ""

    @staticmethod
    def from_raw(raw: RawPath) -> "HarvestedPath":
        uid = _path_uid(raw.page_index, raw.draw_index, raw.points)
        return HarvestedPath(
            page_index=raw.page_index, draw_index=raw.draw_index, kind=raw.kind,
            fill_rgb=raw.fill_rgb, stroke_rgb=raw.stroke_rgb, width_pt=raw.width_pt,
            dashes=raw.dashes, closed=raw.closed, rect=raw.rect, points=raw.points,
            path_uid=uid,
        )


@dataclass(frozen=True, slots=True)
class HarvestedText(RawTextSpan):
    pass


def _is_text_mask(path: RawPath) -> bool:
    """Pure-white filled rectangles sit behind dimension strings as a
    background mask (plan §6 step 7). They must be dropped before poché
    detection or they read as walls; they carry no wall/dimension
    semantics of their own."""
    return (
        path.kind == "fill"
        and path.fill_rgb is not None
        and color_close(path.fill_rgb, TEXT_MASK_FILL)
    )


def harvest_paths(handle: PdfHandle, page_index: int, *, suppress_text_masks: bool = True) -> list[HarvestedPath]:
    """All vector paths on a page, with stable `path_uid`s. Text-mask
    rectangles are dropped by default (plan §6 step 7)."""
    raw = handle.raw_paths(page_index)
    if suppress_text_masks:
        raw = [p for p in raw if not _is_text_mask(p)]
    return [HarvestedPath.from_raw(p) for p in raw]


def harvest_text_lines(handle: PdfHandle, page_index: int) -> list[HarvestedText]:
    """All text spans on a page, unmodified beyond the backend-agnostic
    wrapper type. Line reassembly (joining split spans like
    "CLG HT - 8'" + " 5\"") is a classification concern — see
    `extract.classify.reassemble_lines`."""
    return [
        HarvestedText(**{f.name: getattr(s, f.name) for f in fields(RawTextSpan)})
        for s in handle.raw_text_spans(page_index)
    ]
