"""Localhost API for the review UI (plan §15 `server`).

Serves the Stage 0 pipeline's output for the family-room fixture: the
built model, its validation report, its geometry hash, per-wall mesh data
for the Three.js viewer, and the source PDF page images (both the native
Tier A sheet and the generated Tier C degraded raster) so the UI can show
"here is the page, here is what was built from it" side by side.

No external network access: CORS is restricted to the Vite dev server's
localhost origins, nothing here calls out, and every fixture PDF is read
from the local repo checkout only.
"""
from __future__ import annotations

import io

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response

from fixtures_garrigan import (
    build_family_room,
    build_family_room_from_extraction,
    build_kitchen_island_from_extraction,
    diagnose_extracted_family_room,
    diagnose_family_room,
    tv_wall_interval,
)
from geometry import build_cabinetry_solid, build_wall_solid, compute_geometry_hash, nm_to_m
from ingest import PyMuPdfBackend, detect_tier
from units import NM_PER_FOOT
from validate import run_validation

from .repo_paths import FIXTURE_SOURCE_DIR
from .serialize import cabinetry_to_dict, wall_to_dict

# The kitchen island isn't yet registered into the family room's
# coordinate frame (plan §5.1's SheetCS -> RegionCS -> ProjectCS chain
# isn't built in Sprint 1) — see fixtures_garrigan.kitchen_island's module
# docstring. This offset is a display-only placement, applied here at the
# API boundary so it renders beside rather than inside the room, without
# pretending the island's own local coordinates mean anything relative to
# the walls.
_ISLAND_DISPLAY_OFFSET_M = (nm_to_m(2 * NM_PER_FOOT), nm_to_m(-8 * NM_PER_FOOT), 0.0)

app = FastAPI(title="PDF-to-3D Stage 0 API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["GET"],
    allow_headers=["*"],
)

_SOURCES = ("hand_traced", "extracted")
_cache: dict = {}


def _room(source: str):
    if source not in _SOURCES:
        raise HTTPException(400, f"unknown source {source!r}; choose one of {list(_SOURCES)}")
    key = f"room:{source}"
    if key not in _cache:
        _cache[key] = build_family_room() if source == "hand_traced" else build_family_room_from_extraction()
    return _cache[key]


def _diagnoses(source: str, room):
    return diagnose_family_room(room) if source == "hand_traced" else diagnose_extracted_family_room(room)


def _solids(source: str, room):
    key = f"solids:{source}"
    if key not in _cache:
        _cache[key] = {w.id: build_wall_solid(w) for w in room.walls}
    return _cache[key]


def _island():
    if "island" not in _cache:
        _cache["island"] = build_kitchen_island_from_extraction()
    return _cache["island"]


@app.get("/api/health")
def health():
    return {"status": "ok"}


@app.get("/api/family-room")
def family_room(source: str = "hand_traced"):
    room = _room(source)
    diagnoses = _diagnoses(source, room)
    report = run_validation(list(room.walls), diagnoses=diagnoses)
    solids = _solids(source, room)
    geometry_hash = compute_geometry_hash(list(room.walls), solids)

    east = next(w for w in room.walls if w.id == "LIVING_ROOM.EAST")
    tv_interval = tv_wall_interval(east)

    result = {
        "source": source,
        "walls": [wall_to_dict(w) for w in room.walls],
        "tv_wall_interval": {
            "wall_id": east.id,
            "t_start_nm": tv_interval[0],
            "t_end_nm": tv_interval[1],
        },
        "validation": {
            "is_blocking": report.is_blocking,
            "has_warnings": report.has_warnings,
            "checks": [
                {
                    "check_id": c.check_id,
                    "status": c.status.value,
                    "message": c.message,
                    "details": list(c.details),
                }
                for c in report.checks
            ],
        },
        "geometry_hash": geometry_hash,
    }

    if source == "extracted":
        # Diagnostic-only: how well each real dimension text matched its
        # witness geometry (plan §17's dimensional-placement metric), so
        # the UI can show match quality alongside the "unreviewed
        # proposal" badge rather than just the final coordinates.
        result["dimension_matches"] = [
            {"text": m.text, "axis": m.axis, "error_in": round(m.error_in, 3)}
            for m in room.matches
        ]

        # The kitchen island: a second, independent extraction technique
        # (poché footprint measurement, not dimension-chain matching —
        # see fixtures_garrigan.kitchen_island). Not registered to the
        # room's coordinate frame yet (see module docstring), so it's
        # listed as its own fixture rather than folded into `walls`.
        island = _island()
        fixture_dict = cabinetry_to_dict(island.cabinetry)
        fixture_dict["match_quality"] = {
            "width_error_in": round(island.footprint_match.width_error_in, 3),
            "depth_error_in": round(island.footprint_match.depth_error_in, 3),
        }
        result["fixtures"] = [fixture_dict]

    return result


@app.get("/api/family-room/mesh")
def family_room_mesh(source: str = "hand_traced"):
    room = _room(source)
    solids = _solids(source, room)
    result = {}
    for wall_id, solid in solids.items():
        mesh = solid.to_mesh()
        result[wall_id] = {
            "vertices": mesh.vert_properties.tolist(),
            "triangles": mesh.tri_verts.tolist(),
        }

    if source == "extracted":
        island = _island()
        island_solid = build_cabinetry_solid(island.cabinetry).translate(_ISLAND_DISPLAY_OFFSET_M)
        island_mesh = island_solid.to_mesh()
        result[island.cabinetry.id] = {
            "vertices": island_mesh.vert_properties.tolist(),
            "triangles": island_mesh.tri_verts.tolist(),
        }

    return result


_TIER_SOURCES = {
    "a1": ("garrigan-main-set.pdf", 1),
    "attic": ("garrigan-attic-idea.pdf", 0),
    "degraded": ("garrigan-a1-degraded-150dpi.pdf", 0),
}


@app.get("/api/tiers")
def tiers():
    backend = PyMuPdfBackend()
    out = {}
    for key, (filename, page_index) in _TIER_SOURCES.items():
        path = FIXTURE_SOURCE_DIR / filename
        with backend.open(str(path)) as h:
            sig = h.page_signals(page_index)
            result = detect_tier(sig)
        out[key] = {
            "filename": filename,
            "tier": result.tier.value,
            "effort_estimate": result.effort_estimate,
            "vector_path_count": sig.vector_path_count,
            "text_span_count": sig.text_span_count,
            "image_area_fraction": sig.image_area_fraction,
        }
    return out


@app.get("/api/source-image/{key}")
def source_image(key: str, dpi: int = 100):
    if key not in _TIER_SOURCES:
        raise HTTPException(404, f"unknown source image key {key!r}; choose one of {list(_TIER_SOURCES)}")
    filename, page_index = _TIER_SOURCES[key]
    path = FIXTURE_SOURCE_DIR / filename
    backend = PyMuPdfBackend()
    with backend.open(str(path)) as h:
        png_bytes = h.rasterize_page(page_index, dpi)
    return Response(content=png_bytes, media_type="image/png")
