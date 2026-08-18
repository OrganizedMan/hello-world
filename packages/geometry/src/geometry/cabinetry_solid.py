"""Deterministic solid construction for fixed cabinetry (plan §5.2's
FixedCabinetry, extended here beyond walls): extrudes a footprint polygon
straight up from the floor to `height_nm`. Simpler than `wall_solid.py`
because cabinetry has no openings to subtract and — per the schema — no
`base_z_nm` of its own; it always sits on the floor.
"""
from __future__ import annotations

import manifold3d

from core_schema import FixedCabinetry
from .units_bridge import nm_to_m


def build_cabinetry_solid(item: FixedCabinetry) -> manifold3d.Manifold:
    if item.height_nm <= 0:
        raise ValueError(f"cabinetry {item.id!r}: height_nm must be positive")
    if len(item.footprint) < 3:
        raise ValueError(f"cabinetry {item.id!r}: footprint needs at least 3 points")

    polygon = [[nm_to_m(p.x_nm), nm_to_m(p.y_nm)] for p in item.footprint]
    cross_section = manifold3d.CrossSection([polygon])
    return cross_section.extrude(nm_to_m(item.height_nm))
