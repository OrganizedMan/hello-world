"""Package the A-1 massing as a walkable tour artifact.

The prototype tour shipped one hand-built room. This builds the whole traced
first floor instead, and writes a manifest that records what the geometry rests
on so the page can say so plainly rather than claiming accuracy it lacks.

The GLB is written here rather than through ``geometry._build_glb`` because the
tour needs a material per part; the compiler deliberately emits a single one.
"""

from __future__ import annotations

import json
import struct
from dataclasses import dataclass

from hearthview.a1_extract import POINTS_PER_FOOT, A1Extraction
from hearthview.a1_massing import (
    ASSUMED_DOOR_HEAD_INCHES,
    ASSUMED_WINDOW_SILL_INCHES,
    A1Massing,
)
from hearthview.geometry import Primitive
from hearthview.units import TICKS_PER_INCH

METERS_PER_TICK = 0.0254 / TICKS_PER_INCH
EYE_HEIGHT_METERS = 1.65

# baseColorFactor, metallic, roughness
_MATERIALS: dict[str, tuple[tuple[float, float, float], float, float]] = {
    "wall": ((0.898, 0.882, 0.851), 0.0, 0.92),
    "floor": ((0.541, 0.404, 0.278), 0.0, 0.78),
    "counter": ((0.855, 0.839, 0.808), 0.0, 0.42),
    "fixture": ((0.937, 0.937, 0.929), 0.0, 0.35),
    "deck": ((0.478, 0.435, 0.376), 0.0, 0.88),
    "stair": ((0.616, 0.498, 0.361), 0.0, 0.72),
}
_FALLBACK = "wall"

_FACES = (
    ((0, 1, 2, 3), (0.0, 0.0, -1.0)),
    ((5, 4, 7, 6), (0.0, 0.0, 1.0)),
    ((4, 5, 1, 0), (0.0, -1.0, 0.0)),
    ((3, 2, 6, 7), (0.0, 1.0, 0.0)),
    ((4, 0, 3, 7), (-1.0, 0.0, 0.0)),
    ((1, 5, 6, 2), (1.0, 0.0, 0.0)),
)


@dataclass(frozen=True)
class TourArtifact:
    glb: bytes
    manifest: dict


def _corners(item: Primitive) -> list[tuple[float, float, float]]:
    """Tick-space box to glTF metres, Y-up, plan north towards -Z."""
    x0, x1 = item.x0_ticks * METERS_PER_TICK, item.x1_ticks * METERS_PER_TICK
    y0, y1 = item.y0_ticks * METERS_PER_TICK, item.y1_ticks * METERS_PER_TICK
    z0, z1 = item.z0_ticks * METERS_PER_TICK, item.z1_ticks * METERS_PER_TICK
    return [
        (x0, z0, -y0), (x1, z0, -y0), (x1, z0, -y1), (x0, z0, -y1),
        (x0, z1, -y0), (x1, z1, -y0), (x1, z1, -y1), (x0, z1, -y1),
    ]


def build_glb(primitives: tuple[Primitive, ...]) -> bytes:
    by_material: dict[str, list[Primitive]] = {}
    for item in primitives:
        by_material.setdefault(
            item.part_kind if item.part_kind in _MATERIALS else _FALLBACK, []
        ).append(item)

    binary = bytearray()
    views: list[dict] = []
    accessors: list[dict] = []
    mesh_primitives: list[dict] = []
    materials: list[dict] = []

    def view(payload: bytes, target: int) -> int:
        while len(binary) % 4:
            binary.append(0)
        offset = len(binary)
        binary.extend(payload)
        views.append(
            {"buffer": 0, "byteLength": len(payload), "byteOffset": offset, "target": target}
        )
        return len(views) - 1

    for name, items in sorted(by_material.items()):
        positions: list[tuple[float, float, float]] = []
        normals: list[tuple[float, float, float]] = []
        indices: list[int] = []
        for item in items:
            corners = _corners(item)
            for face, normal in _FACES:
                base = len(positions)
                for corner_index in face:
                    positions.append(corners[corner_index])
                    normals.append(normal)
                indices.extend((base, base + 1, base + 2, base, base + 2, base + 3))
        if not positions:
            continue

        position_view = view(
            struct.pack("<" + "f" * (len(positions) * 3), *(c for p in positions for c in p)),
            34962,
        )
        normal_view = view(
            struct.pack("<" + "f" * (len(normals) * 3), *(c for n in normals for c in n)),
            34962,
        )
        index_view = view(struct.pack("<" + "I" * len(indices), *indices), 34963)

        position_accessor = len(accessors)
        accessors.append({
            "bufferView": position_view, "componentType": 5126, "count": len(positions),
            "type": "VEC3",
            "min": [min(p[i] for p in positions) for i in range(3)],
            "max": [max(p[i] for p in positions) for i in range(3)],
        })
        normal_accessor = len(accessors)
        accessors.append({
            "bufferView": normal_view, "componentType": 5126, "count": len(normals),
            "type": "VEC3",
        })
        index_accessor = len(accessors)
        accessors.append({
            "bufferView": index_view, "componentType": 5125, "count": len(indices),
            "type": "SCALAR",
        })

        colour, metallic, roughness = _MATERIALS[name]
        material_index = len(materials)
        materials.append({
            "name": name,
            "pbrMetallicRoughness": {
                "baseColorFactor": [*colour, 1.0],
                "metallicFactor": metallic,
                "roughnessFactor": roughness,
            },
            "doubleSided": True,
        })
        mesh_primitives.append({
            "attributes": {"POSITION": position_accessor, "NORMAL": normal_accessor},
            "indices": index_accessor,
            "material": material_index,
        })

    gltf = {
        "asset": {"version": "2.0", "generator": "hearthview-a1-tour"},
        "scene": 0,
        "scenes": [{"nodes": [0]}],
        "nodes": [{"mesh": 0, "name": "a1_first_floor"}],
        "meshes": [{"name": "a1_first_floor", "primitives": mesh_primitives}],
        "materials": materials,
        "accessors": accessors,
        "bufferViews": views,
        "buffers": [{"byteLength": len(binary)}],
    }

    json_bytes = json.dumps(gltf, separators=(",", ":")).encode("utf-8")
    json_bytes += b" " * (-len(json_bytes) % 4)
    binary += b"\x00" * (-len(binary) % 4)
    header = struct.pack("<III", 0x46546C67, 2, 12 + 8 + len(json_bytes) + 8 + len(binary))
    return (
        header
        + struct.pack("<II", len(json_bytes), 0x4E4F534A)
        + json_bytes
        + struct.pack("<II", len(binary), 0x004E4942)
        + bytes(binary)
    )


def _rect(name: str, x0: float, z0: float, x1: float, z1: float) -> dict:
    return {
        "name": name,
        "min_x": round(min(x0, x1), 4), "min_y": round(min(z0, z1), 4),
        "max_x": round(max(x0, x1), 4), "max_y": round(max(z0, z1), 4),
    }


def build_manifest(
    extraction: A1Extraction, massing: A1Massing, *, glb_bytes: int
) -> dict:
    """Describe the tour, including exactly what its heights rest on."""
    footprint = extraction.footprint
    width = (footprint.x1 - footprint.x0) / POINTS_PER_FOOT * 0.3048
    depth = (footprint.y1 - footprint.y0) / POINTS_PER_FOOT * 0.3048
    ceiling = massing.ceiling.inches * 0.0254
    span = max(width, depth)

    def to_x(px: float) -> float:
        return (px - footprint.x0) / POINTS_PER_FOOT * 0.3048

    def to_z(py: float) -> float:
        return -(footprint.y1 - py) / POINTS_PER_FOOT * 0.3048

    regions = []
    for label in extraction.labels:
        b = label.bounds
        cx, cz = to_x((b.x0 + b.x1) / 2), to_z((b.y0 + b.y1) / 2)
        regions.append(_rect(label.text.title(), cx - 0.9, cz - 0.9, cx + 0.9, cz + 0.9))

    barriers = []
    for item in massing.primitives:
        if item.part_kind != "wall":
            continue
        barriers.append({
            "name": item.element_id,
            "min_x": round(item.x0_ticks * METERS_PER_TICK, 4),
            "max_x": round(item.x1_ticks * METERS_PER_TICK, 4),
            "min_z": round(-item.y1_ticks * METERS_PER_TICK, 4),
            "max_z": round(-item.y0_ticks * METERS_PER_TICK, 4),
        })

    openings = []
    for index, item in enumerate(massing.openings):
        b = item.opening.bounds
        cx, cz = (b.x0 + b.x1) / 2, (b.y0 + b.y1) / 2
        distances = {
            "north": cz - footprint.y0, "south": footprint.y1 - cz,
            "west": cx - footprint.x0, "east": footprint.x1 - cx,
        }
        openings.append({
            "name": f"{item.kind}.{index:03d}",
            "kind": item.kind,
            "wall": min(distances, key=distances.get),
            "width_feet": round(item.width_feet, 2),
            "footprint": _rect(
                f"{item.kind}.{index:03d}",
                to_x(b.x0), to_z(b.y0), to_x(b.x1), to_z(b.y1),
            ),
        })

    # Walk has to start on open floor. Room labels are printed in clear space,
    # so the label with the most clearance from any wall is a safe spawn.
    def clearance(x: float, z: float) -> float:
        best = float("inf")
        for barrier in barriers:
            dx = max(barrier["min_x"] - x, 0.0, x - barrier["max_x"])
            dz = max(barrier["min_z"] - z, 0.0, z - barrier["max_z"])
            best = min(best, (dx * dx + dz * dz) ** 0.5)
        return best

    spawn_x, spawn_z, spawn_clear = width * 0.5, -depth * 0.5, -1.0
    for label in extraction.labels:
        b = label.bounds
        cx, cz = to_x((b.x0 + b.x1) / 2), to_z((b.y0 + b.y1) / 2)
        room = clearance(cx, cz)
        if room > spawn_clear:
            spawn_x, spawn_z, spawn_clear = cx, cz, room

    # Look across the plan rather than at whichever wall happens to be nearest.
    centres = [
        (to_x((l.bounds.x0 + l.bounds.x1) / 2), to_z((l.bounds.y0 + l.bounds.y1) / 2))
        for l in extraction.labels
    ] or [(width / 2, -depth / 2)]
    look_x = sum(c[0] for c in centres) / len(centres)
    look_z = sum(c[1] for c in centres) / len(centres)
    if abs(look_x - spawn_x) < 0.5 and abs(look_z - spawn_z) < 0.5:
        look_x, look_z = spawn_x, spawn_z - 3.0

    verified = round(massing.verified_fraction * 100, 1)
    return {
        "schema": "hearthview-tour/v2",
        "label": "Traced from A-1 · measured geometry",
        "canonical_geometry": True,
        "source": {
            "sheet": "A-1", "page": extraction.page_number, "view": "Proposed - First Floor",
            "points_per_foot": POINTS_PER_FOOT,
        },
        "provenance": {
            "verified_percent": verified,
            "measured": [
                "wall footprints and thicknesses (wall poche)",
                "opening positions and widths (gaps in the wall runs)",
                f"ceiling height ({massing.ceiling.note})",
            ],
            "assumed": [
                f"door head height {ASSUMED_DOOR_HEAD_INCHES / 12:.2f} ft",
                f"window sill height {ASSUMED_WINDOW_SILL_INCHES / 12:.2f} ft",
                "counter and fixture heights",
            ],
            "absent_from_drawing_set": (
                "A-1, A-2 and A-3 are all plans; the set contains no elevation "
                "or section, so no opening has a printed vertical dimension."
            ),
            "approximated_wall_segments": len(massing.approximated_wall_ids),
        },
        # Measured from the solids, not the wall footprint: the deck reaches
        # about seven feet north of the building line.
        "envelope": {
            "min_x": round(min(p.x0_ticks for p in massing.primitives) * METERS_PER_TICK, 4),
            "min_y": round(min(p.z0_ticks for p in massing.primitives) * METERS_PER_TICK, 4),
            "min_z": round(-max(p.y1_ticks for p in massing.primitives) * METERS_PER_TICK, 4),
            "max_x": round(max(p.x1_ticks for p in massing.primitives) * METERS_PER_TICK, 4),
            "max_y": round(max(p.z1_ticks for p in massing.primitives) * METERS_PER_TICK, 4),
            "max_z": round(-min(p.y0_ticks for p in massing.primitives) * METERS_PER_TICK, 4),
        },
        "orientation": {
            "bounds": _rect("first_floor", 0.0, -depth, width, 0.0),
            "north_vector": [0, -1],
            "north_up": True,
            "regions": regions,
            "openings": openings,
        },
        "provisional_categories": [
            "cabinetry_detail", "hardware", "finishes", "furniture", "decor",
            "undimensioned_offsets", "opening_heights",
        ],
        "artifact": {
            "glb": "a1-first-floor.glb",
            "poster": "poster.webp",
            "environment": "environment.hdr",
            "total_browser_bytes": glb_bytes,
        },
        "runtime": {
            "eye_height_meters": EYE_HEIGHT_METERS,
            "walkable": {
                "min_x": 0.3, "max_x": round(width - 0.3, 4),
                "min_z": round(-depth + 0.3, 4), "max_z": -0.3,
            },
            "barriers": barriers,
            "camera_presets": [
                # The floor has no ceiling plane, so a raised three-quarter
                # vantage reads as a dollhouse view of the whole plan.
                {
                    "name": "kitchen_overview",
                    "position": [round(width * 1.05, 3), round(span * 0.62, 3), round(span * 0.42, 3)],
                    "target": [round(width * 0.46, 3), 0.0, round(-depth * 0.52, 3)],
                    "up": [0, 1, 0],
                },
                {
                    "name": "walk_start",
                    "position": [round(spawn_x, 3), EYE_HEIGHT_METERS, round(spawn_z, 3)],
                    "target": [round(look_x, 3), EYE_HEIGHT_METERS, round(look_z, 3)],
                    "up": [0, 1, 0],
                },
                {
                    "name": "overhead",
                    "position": [round(width * 0.5, 3), round(span * 1.05, 3), round(-depth * 0.5, 3)],
                    "target": [round(width * 0.5, 3), 0.0, round(-depth * 0.5, 3)],
                    "up": [0, 0, -1],
                },
            ],
        },
    }


def build_tour(extraction: A1Extraction, massing: A1Massing) -> TourArtifact:
    glb = build_glb(massing.primitives)
    return TourArtifact(glb, build_manifest(extraction, massing, glb_bytes=len(glb)))
