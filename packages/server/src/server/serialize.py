"""JSON serialization for the review UI. Deliberately separate from
geometry.hashing's canonical dict — that one is scoped tight to what
determines the hash; this one is scoped to what a human reading the UI
wants to see (readable ft-in strings alongside raw nm, enum names, etc).
"""
from __future__ import annotations

from core_schema import UNKNOWN, FixedCabinetry, Opening, WallSegment
from units import nm_to_ft_in


def _nm_field(v):
    if v is UNKNOWN:
        return {"nm": None, "display": "Unknown"}
    return {"nm": v, "display": nm_to_ft_in(v)}


def opening_to_dict(o: Opening) -> dict:
    return {
        "id": o.id,
        "kind": o.kind.value,
        "t_start": _nm_field(o.t_start_nm),
        "t_end": _nm_field(o.t_end_nm),
        "width": _nm_field(o.t_end_nm - o.t_start_nm),
        "sill": _nm_field(o.sill_nm),
        "head": _nm_field(o.head_nm),
        "connects": list(o.connects) if o.connects else None,
        "annotation": o.annotation,
        "provenance_state": o.prov.state.value,
    }


def cabinetry_to_dict(c: FixedCabinetry) -> dict:
    xs = [p.x_nm for p in c.footprint]
    ys = [p.y_nm for p in c.footprint]
    return {
        "id": c.id,
        "level_id": c.level_id,
        "kind": c.kind,
        "label": c.label,
        "width": _nm_field(max(xs) - min(xs)),
        "depth": _nm_field(max(ys) - min(ys)),
        "height": _nm_field(c.height_nm),
        "provenance_state": c.prov.state.value,
    }


def wall_to_dict(w: WallSegment) -> dict:
    p0, p1 = w.baseline
    return {
        "id": w.id,
        "level_id": w.level_id,
        "variant": w.variant,
        "construction": w.construction.value,
        "baseline": [
            {"x_nm": p0.x_nm, "y_nm": p0.y_nm},
            {"x_nm": p1.x_nm, "y_nm": p1.y_nm},
        ],
        "length": _nm_field(w.length_nm),
        "thickness": _nm_field(w.thickness_nm),
        "base_z": _nm_field(w.base_z_nm),
        "top_z": _nm_field(w.top_z_nm),
        "provenance_state": w.prov.state.value,
        "openings": [opening_to_dict(o) for o in w.openings],
        "solid_intervals": [
            {"t_start": _nm_field(a), "t_end": _nm_field(b)}
            for a, b in w.solid_intervals()
        ],
    }
