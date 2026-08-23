"""nm <-> metre conversion at the geometry-kernel boundary.

int64 nanometres is the storage/interchange unit everywhere else in the
pipeline (plan §5.1). manifold3d, like most mesh/CSG kernels, expects
real-world-scale float coordinates rather than raw nanometre integers —
feeding it values on the order of 1e8-1e9 would sit far outside the
coordinate magnitudes its robustness tolerances are tuned for. Metres put
a house at a very ordinary scale (a 4 m wall, not a 4,000,000,000 unit
one), so conversion happens once, right here, at the one boundary that
needs it.
"""
from __future__ import annotations

from units import NM_PER_M


def nm_to_m(nm: int) -> float:
    return nm / NM_PER_M


def m_to_nm(m: float) -> int:
    return round(m * NM_PER_M)
