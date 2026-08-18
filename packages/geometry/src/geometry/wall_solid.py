"""Deterministic solid construction for one wall (plan §8, §9).

Extrudes a WallSegment's baseline into a rectangular prism and subtracts
its openings, using manifold3d for exact boolean geometry. This module
trusts that everything it needs is already resolved — it never invents a
height. A wall or opening with an UNKNOWN vertical extent is a validation
failure (plan §12), not a modelling decision for the geometry layer to
make; catching that belongs to `validate`, upstream of Build.
"""
from __future__ import annotations

import math

import manifold3d

from core_schema import UNKNOWN, WallSegment
from .units_bridge import nm_to_m

#: How far a subtraction cutter overhangs the wall's thickness on each
#: side, in metres. Purely to guarantee a clean through-cut regardless of
#: `offset_nm` — it has no effect on the resulting solid's shape, since
#: subtraction only removes material that was already there.
_OPENING_Y_BLEED_M = 1.0


class UnresolvedGeometryError(ValueError):
    """Raised when a wall or opening lacks a resolved vertical extent.
    Geometry construction never guesses — see module docstring."""


def build_wall_solid(wall: WallSegment) -> manifold3d.Manifold:
    if wall.base_z_nm is UNKNOWN or wall.top_z_nm is UNKNOWN:
        raise UnresolvedGeometryError(
            f"wall {wall.id!r} has an unresolved base_z_nm/top_z_nm; the "
            "validation report must resolve or explicitly block on this "
            "before Build (plan §12) — geometry construction never "
            "invents a height."
        )
    base_z_nm = wall.base_z_nm
    top_z_nm = wall.top_z_nm
    height_nm = top_z_nm - base_z_nm
    if height_nm <= 0:
        raise ValueError(f"wall {wall.id!r}: top_z_nm must be above base_z_nm")

    length_m = nm_to_m(wall.length_nm)
    thickness_m = nm_to_m(wall.thickness_nm)
    offset_m = nm_to_m(wall.offset_nm)
    height_m = nm_to_m(height_nm)
    base_z_m = nm_to_m(base_z_nm)

    # Built entirely in wall-local coordinates first: t (0..length) along
    # the wall, y across its thickness, z absolute vertical (walls are
    # vertical, so z never needs the in-plane rotation applied below).
    solid = manifold3d.Manifold.cube([length_m, thickness_m, height_m], center=False)
    solid = solid.translate([0.0, -thickness_m / 2.0 + offset_m, base_z_m])

    for opening in sorted(wall.openings, key=lambda o: o.id):
        if opening.sill_nm is UNKNOWN or opening.head_nm is UNKNOWN:
            raise UnresolvedGeometryError(
                f"opening {opening.id!r} on wall {wall.id!r} has an unresolved "
                "sill_nm/head_nm; validation must resolve this before Build."
            )
        t0_m = nm_to_m(opening.t_start_nm)
        t1_m = nm_to_m(opening.t_end_nm)
        z0_m = nm_to_m(base_z_nm + opening.sill_nm)
        z1_m = nm_to_m(base_z_nm + opening.head_nm)
        if not (z1_m > z0_m):
            raise ValueError(f"opening {opening.id!r}: head_nm must be above sill_nm")

        cutter_thickness_m = thickness_m + _OPENING_Y_BLEED_M
        cutter = manifold3d.Manifold.cube([t1_m - t0_m, cutter_thickness_m, z1_m - z0_m], center=False)
        cutter = cutter.translate([t0_m, -cutter_thickness_m / 2.0 + offset_m, z0_m])
        solid = solid - cutter

    p0, p1 = wall.baseline
    angle_deg = math.degrees(math.atan2(p1.y_nm - p0.y_nm, p1.x_nm - p0.x_nm))
    solid = solid.rotate([0.0, 0.0, angle_deg])
    solid = solid.translate([nm_to_m(p0.x_nm), nm_to_m(p0.y_nm), 0.0])
    return solid
