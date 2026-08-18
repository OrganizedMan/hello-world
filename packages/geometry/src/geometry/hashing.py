"""The geometry hash (plan §8, §12 check 11, §16 Tier 4/5).

    geometry_hash = sha256(canonical_json(solved_entities) ‖ canonical_mesh_digest)

Two independent renderers (Three.js, headless Cycles) and eight cameras
must all be provably looking at the same model. That guarantee has to
survive manifold3d's own internal vertex/triangle ordering being an
implementation detail, not a contract — so before hashing, every mesh is
canonicalized: vertices rounded to nearest nanometre and sorted
lexicographically, triangles re-indexed to match and then sorted by their
(now-canonical) vertex indices. Only then is the result independent of
anything but the actual shape.
"""
from __future__ import annotations

import hashlib
import json

import numpy as np

from core_schema import UNKNOWN, WallSegment
from units import NM_PER_M


def _nm_or_null(v):
    return None if v is UNKNOWN else v


def wall_canonical_dict(wall: WallSegment) -> dict:
    """The subset of a WallSegment's data that determines its *geometry* —
    deliberately excludes provenance/confidence, so re-confirming or
    re-citing a wall never changes the hash, only changing its shape does.
    """
    p0, p1 = wall.baseline
    return {
        "id": wall.id,
        "level_id": wall.level_id,
        "baseline": [[p0.x_nm, p0.y_nm], [p1.x_nm, p1.y_nm]],
        "thickness_nm": wall.thickness_nm,
        "offset_nm": wall.offset_nm,
        "base_z_nm": _nm_or_null(wall.base_z_nm),
        "top_z_nm": _nm_or_null(wall.top_z_nm),
        "construction": wall.construction.value,
        "openings": [
            {
                "id": o.id,
                "kind": o.kind.value,
                "t_start_nm": o.t_start_nm,
                "t_end_nm": o.t_end_nm,
                "sill_nm": _nm_or_null(o.sill_nm),
                "head_nm": _nm_or_null(o.head_nm),
            }
            for o in sorted(wall.openings, key=lambda o: o.id)
        ],
    }


def canonical_entities_json(walls: list[WallSegment]) -> bytes:
    payload = [wall_canonical_dict(w) for w in sorted(walls, key=lambda w: w.id)]
    return json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")


def canonical_mesh_bytes(solids: dict) -> bytes:
    """`solids` maps entity_id -> manifold3d.Manifold. See module docstring
    for why canonicalization (not just concatenation) is required."""
    parts: list[bytes] = []
    for entity_id in sorted(solids):
        mesh = solids[entity_id].to_mesh()
        verts_nm = np.round(np.asarray(mesh.vert_properties, dtype=np.float64) * NM_PER_M).astype(np.int64)
        tris = np.asarray(mesh.tri_verts, dtype=np.int64)

        order = np.lexsort((verts_nm[:, 2], verts_nm[:, 1], verts_nm[:, 0]))
        rank = np.empty_like(order)
        rank[order] = np.arange(len(order))
        sorted_verts = verts_nm[order]
        remapped_tris = rank[tris]  # winding preserved: only row order changes below

        tri_order = sorted(range(len(remapped_tris)), key=lambda i: tuple(remapped_tris[i]))
        sorted_tris = remapped_tris[tri_order]

        parts.append(entity_id.encode("utf-8"))
        parts.append(sorted_verts.tobytes())
        parts.append(sorted_tris.astype(np.int64).tobytes())
    return b"\x00".join(parts)


def compute_geometry_hash(walls: list[WallSegment], solids: dict) -> str:
    mesh_digest = hashlib.sha256(canonical_mesh_bytes(solids)).digest()
    return hashlib.sha256(canonical_entities_json(walls) + mesh_digest).hexdigest()
