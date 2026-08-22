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
from hearthview.a1_building import ASSUMED_FLOOR_ASSEMBLY_INCHES, DATUM_SHEET
from hearthview.geometry import Primitive
from hearthview.units import TICKS_PER_INCH

METERS_PER_TICK = 0.0254 / TICKS_PER_INCH
# Eye height for a 5'6" person: eyes sit roughly 4.5" below the top of the
# head, so 61.5" rather than the 65" this used to stand at -- which was a
# 5'9" viewer and made every room read slightly low.
EYE_HEIGHT_METERS = 1.562

# baseColorFactor, metallic, roughness
_MATERIALS: dict[str, tuple[tuple[float, float, float], float, float]] = {
    "wall": ((0.898, 0.882, 0.851), 0.0, 0.92),
    "floor": ((0.541, 0.404, 0.278), 0.0, 0.78),
    "ceiling": ((0.925, 0.918, 0.902), 0.0, 0.94),
    "counter": ((0.855, 0.839, 0.808), 0.0, 0.42),
    "fixture": ((0.937, 0.937, 0.929), 0.0, 0.35),
    "deck": ((0.478, 0.435, 0.376), 0.0, 0.88),
    "stair": ((0.616, 0.498, 0.361), 0.0, 0.72),
}
_FALLBACK = "wall"

# Normals live in the same frame as the corners, and `_corners` rewrites tick
# space (z up) into glTF (y up) as (x, y, z) -> (x, z, -y). These were left in
# tick space, so four of the six pointed the wrong way: floor and ceiling faces
# carried horizontal normals and the north and south walls carried vertical
# ones. Nothing failed -- the geometry was exactly right and every corner
# measured true -- the model simply could not catch light, which is most of why
# the massing read as flat grey paper.
def _to_gltf_normal(tick_normal: tuple[float, float, float]) -> tuple[float, float, float]:
    x, y, z = tick_normal
    return (x, z, -y)


_FACES = tuple(
    (face, _to_gltf_normal(normal))
    for face, normal in (
        ((0, 1, 2, 3), (0.0, 0.0, -1.0)),   # underside
        ((5, 4, 7, 6), (0.0, 0.0, 1.0)),    # top
        ((4, 5, 1, 0), (0.0, -1.0, 0.0)),   # south
        ((3, 2, 6, 7), (0.0, 1.0, 0.0)),    # north
        ((4, 0, 3, 7), (-1.0, 0.0, 0.0)),   # west
        ((1, 5, 6, 2), (1.0, 0.0, 0.0)),    # east
    )
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


def build_glb(
    primitives: tuple[Primitive, ...],
    *,
    groups: dict[str, tuple[Primitive, ...]] | None = None,
) -> bytes:
    """Pack primitives into a GLB, one mesh per material.

    `groups` splits the model into a node each, so the browser can show and hide
    them independently -- one per storey, which is what a floor switcher needs.
    Without it everything lands in a single node, as before.
    """
    grouped = groups if groups is not None else {"a1_first_floor": tuple(primitives)}

    binary = bytearray()
    views: list[dict] = []
    accessors: list[dict] = []
    materials: list[dict] = []
    material_index_by_name: dict[str, int] = {}
    meshes: list[dict] = []
    nodes: list[dict] = []

    def view(payload: bytes, target: int) -> int:
        while len(binary) % 4:
            binary.append(0)
        offset = len(binary)
        binary.extend(payload)
        views.append(
            {"buffer": 0, "byteLength": len(payload), "byteOffset": offset, "target": target}
        )
        return len(views) - 1

    def material_for(name: str) -> int:
        """One material entry per kind, shared across every node that uses it."""
        if name not in material_index_by_name:
            colour, metallic, roughness = _MATERIALS[name]
            material_index_by_name[name] = len(materials)
            materials.append({
                "name": name,
                "pbrMetallicRoughness": {
                    "baseColorFactor": [*colour, 1.0],
                    "metallicFactor": metallic,
                    "roughnessFactor": roughness,
                },
                "doubleSided": True,
            })
        return material_index_by_name[name]

    for group_name, group_items in grouped.items():
      by_material: dict[str, list[Primitive]] = {}
      for item in group_items:
        by_material.setdefault(
            item.part_kind if item.part_kind in _MATERIALS else _FALLBACK, []
        ).append(item)
      mesh_primitives: list[dict] = []
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
                # Wound so the front face is the outward one, which is what
                # makes the supplied normal the one three.js actually shades
                # with: on a DoubleSide material it flips the normal for a
                # back-facing fragment, so an inside-out box lights as though
                # every surface pointed into the solid. Floors came out black
                # under a sun directly above them for exactly this reason.
                indices.extend((base, base + 2, base + 1, base, base + 3, base + 2))
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

        mesh_primitives.append({
            "attributes": {"POSITION": position_accessor, "NORMAL": normal_accessor},
            "indices": index_accessor,
            "material": material_for(name),
        })
      if mesh_primitives:
        meshes.append({"name": group_name, "primitives": mesh_primitives})
        nodes.append({"mesh": len(meshes) - 1, "name": group_name})

    gltf = {
        "asset": {"version": "2.0", "generator": "hearthview-a1-tour"},
        "scene": 0,
        "scenes": [{"nodes": list(range(len(nodes)))}],
        "nodes": nodes,
        "meshes": meshes,
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


def _casework_block(building) -> list[dict]:
    """Every counter and fixture, with the room it stands in and its facing.

    Cabinetry is not a kitchen feature. The trace puts counters in the mudroom,
    the powder room and two bathrooms as well, so the look pass builds casework
    from any run and lets the room decide what it should look like.

    Facing is derived rather than guessed: the vector from a run to its room's
    centroid points into the room, so the wall is the other way. That works on
    any wall of any storey without naming one.
    """
    from hearthview.a1_extract import POINTS_PER_FOOT
    from hearthview.a1_rooms import build_room_grid
    from hearthview.units import TICKS_PER_INCH

    FT = 0.3048
    datum = building.datum
    out: list[dict] = []

    for storey in building.storeys:
        grid = build_room_grid(storey.extraction)
        centroids: dict[str, list[float]] = {}
        for row in range(grid.rows):
            for column in range(grid.columns):
                who = grid.owner[row * grid.columns + column]
                if who < 0:
                    continue
                name = grid.rooms[who].name
                acc = centroids.setdefault(name, [0.0, 0.0, 0.0])
                acc[0] += column
                acc[1] += row
                acc[2] += 1

        for item in storey.primitives:
            if item.part_kind not in ("counter", "fixture"):
                continue
            east0, east1 = (item.x0_ticks / TICKS_PER_INCH / 12 * FT,
                            item.x1_ticks / TICKS_PER_INCH / 12 * FT)
            north0, north1 = (item.y0_ticks / TICKS_PER_INCH / 12 * FT,
                              item.y1_ticks / TICKS_PER_INCH / 12 * FT)
            z0, z1 = (item.z0_ticks / TICKS_PER_INCH / 12 * FT,
                      item.z1_ticks / TICKS_PER_INCH / 12 * FT)
            centre_e, centre_n = (east0 + east1) / 2, (north0 + north1) / 2

            pdf_x = datum.x0 + centre_e / FT * POINTS_PER_FOOT
            pdf_y = datum.y1 - centre_n / FT * POINTS_PER_FOOT
            room = grid.at(pdf_x, pdf_y)
            if room is None:
                continue

            total = centroids[room.name]
            room_e = (datum.x0 + (total[0] / total[2] + 0.5) * _cell_points()
                      - datum.x0) / POINTS_PER_FOOT * FT
            room_n = (datum.y1 - (grid.origin_y + (total[1] / total[2] + 0.5) * _cell_points())
                      ) / POINTS_PER_FOOT * FT
            room_e += (grid.origin_x - datum.x0) / POINTS_PER_FOOT * FT

            toward = (room_e - centre_e, room_n - centre_n)
            if abs(east1 - east0) >= abs(north1 - north0):
                run_axis, facing = "X", (90.0 if toward[1] >= 0 else 270.0)
            else:
                run_axis, facing = "Y", (0.0 if toward[0] >= 0 else 180.0)

            out.append({
                "id": item.element_id,
                "part": item.part_kind,
                "node": storey_node_name(storey.sheet),
                "room": room.name,
                "room_kind": room.kind,
                "centre": [round(centre_e, 4), round(centre_n, 4), round((z0 + z1) / 2, 4)],
                "size": [round(east1 - east0, 4), round(north1 - north0, 4), round(z1 - z0, 4)],
                "run_axis": run_axis,
                "facing_degrees": facing,
            })
    return out


def _opening_block(building) -> list[dict]:
    """Every door, window and cased opening, as a void in a wall.

    The trace already cuts these holes -- the wall run is split around them and
    a sill and a lintel are built back in. What the massing has no opinion
    about is what stands *in* the hole, and an empty rectangle never reads as a
    window however well it is lit. So the void itself travels with the
    artifact, and the look pass fills it with glazing and trim.

    The extent is recovered from the sill and lintel solids rather than from
    the sheet: they are already in the storey's frame, elevation included, and
    reading the sheet twice is how the two frames drift apart.
    """
    from hearthview.units import TICKS_PER_INCH

    FT = 0.3048
    out: list[dict] = []

    def metres(ticks: int) -> float:
        return ticks / TICKS_PER_INCH / 12 * FT

    for storey in building.storeys:
        node = storey_node_name(storey.sheet)
        by_id = {item.element_id: item for item in storey.primitives}
        base = metres(int(round(storey.base_inches * TICKS_PER_INCH)))
        ceiling = base + storey.ceiling_inches / 12 * FT

        for index, item in enumerate(storey.massing.openings):
            lintel = by_id.get(f"lintel.{index:03d}")
            sill = by_id.get(f"sill.{index:03d}")
            frame = lintel or sill
            if frame is None:
                # Head at or above the ceiling and no sill: nothing was built
                # back in, so there is no void to measure.
                continue

            east0, east1 = metres(frame.x0_ticks), metres(frame.x1_ticks)
            north0, north1 = metres(frame.y0_ticks), metres(frame.y1_ticks)
            head = metres(lintel.z0_ticks) if lintel else ceiling
            foot = metres(sill.z1_ticks) if sill else base
            if head <= foot:
                continue

            width, depth = east1 - east0, north1 - north0
            out.append({
                "id": f"opening.{storey.sheet}.{index:03d}",
                "node": node,
                "kind": item.kind,
                "on_exterior": bool(item.on_exterior),
                "centre": [
                    round((east0 + east1) / 2, 4),
                    round((north0 + north1) / 2, 4),
                    round((foot + head) / 2, 4),
                ],
                "size": [round(width, 4), round(depth, 4), round(head - foot, 4)],
                # Which way the hole runs through the wall: a run along X is a
                # hole in a wall that faces north or south.
                "run_axis": "X" if width >= depth else "Y",
                "sill_meters": round(foot, 4),
                "head_meters": round(head, 4),
            })
    return out


def _cell_points() -> float:
    from hearthview.a1_rooms import CELL_POINTS

    return CELL_POINTS


def _room_block(building) -> dict:
    """Per-storey room extents, in the grid the fill produced."""
    from hearthview.a1_rooms import CELL_POINTS, build_room_grid

    out: dict[str, object] = {"cell_points": CELL_POINTS, "storeys": []}
    for storey in building.storeys:
        grid = build_room_grid(storey.extraction)
        out["storeys"].append({
            "sheet": storey.sheet,
            "node": storey_node_name(storey.sheet),
            "origin_pdf": [grid.origin_x, grid.origin_y],
            "columns": grid.columns,
            "rows": grid.rows,
            "rooms": [
                {"name": r.name, "kind": r.kind, "area_square_feet": r.area_square_feet}
                for r in grid.rooms
            ],
            "runs": grid.runs(),
        })
    return out


def storey_node_name(sheet: str) -> str:
    """GLB node holding one storey. The browser shows and hides these by name."""
    return f"storey_{sheet.replace('-', '').lower()}"


def build_building_tour(building) -> TourArtifact:
    """Every drawn storey in one GLB, a node each so floors can be switched.

    The manifest stays `hearthview-tour/v2` and keeps the datum storey's own
    provenance, because that is what the browser already validates and what the
    page prints. It gains a `storeys` block: what exists, how high each floor
    sits, and which node to show.
    """
    # Ceilings go in their own node per storey. They have to be separable in the
    # browser: overhead mode looks down into the plan, and a ceiling is exactly
    # the thing in the way. A material cannot be hidden per-face in three.js, so
    # this is a node or it is nothing.
    groups: dict[str, tuple] = {}
    for storey in building.storeys:
        node = storey_node_name(storey.sheet)
        groups[node] = tuple(p for p in storey.primitives if p.part_kind != "ceiling")
        ceiling = tuple(p for p in storey.primitives if p.part_kind == "ceiling")
        if ceiling:
            groups[f"{node}_ceiling"] = ceiling
    glb = build_glb(building.primitives, groups=groups)

    datum = building.storey(DATUM_SHEET)
    manifest = build_manifest(datum.extraction, datum.massing, glb_bytes=len(glb))
    manifest["label"] = "Traced from A-1 · every drawn storey"
    manifest["artifact"]["glb"] = "a1-building.glb"

    lowest = min(p.z0_ticks for p in building.primitives) * METERS_PER_TICK
    highest = max(p.z1_ticks for p in building.primitives) * METERS_PER_TICK
    manifest["envelope"]["min_y"] = round(lowest, 4)
    manifest["envelope"]["max_y"] = round(highest, 4)

    manifest["storeys"] = [
        {
            "sheet": storey.sheet,
            "name": storey.name,
            "node": storey_node_name(storey.sheet),
            "base_meters": round(storey.base_inches * 0.0254, 4),
            "ceiling_meters": round(storey.ceiling_inches * 0.0254, 4),
            "primitives": len(storey.primitives),
            "verified_fraction": round(storey.massing.verified_fraction, 4),
        }
        for storey in building.storeys
    ]
    # A-1's presets frame one floor from inside it, which puts the camera in the
    # middle of a four-storey building. Reframe from the whole envelope instead.
    east = (manifest["envelope"]["min_x"] + manifest["envelope"]["max_x"]) / 2
    north = (manifest["envelope"]["min_z"] + manifest["envelope"]["max_z"]) / 2
    width = manifest["envelope"]["max_x"] - manifest["envelope"]["min_x"]
    depth = manifest["envelope"]["max_z"] - manifest["envelope"]["min_z"]
    reach = max(width, depth)
    for preset in manifest["runtime"]["camera_presets"]:
        if preset["name"] == "kitchen_overview":
            preset["position"] = [
                round(east + reach * 0.85, 4),
                round(highest + reach * 0.45, 4),
                round(north + reach * 0.85, 4),
            ]
            preset["target"] = [round(east, 4), round((lowest + highest) / 2, 4), round(north, 4)]
        elif preset["name"] == "overhead":
            preset["position"] = [round(east, 4), round(highest + reach * 1.1, 4), round(north, 4)]
            preset["target"] = [round(east, 4), round(lowest, 4), round(north, 4)]

    # Rooms travel with the artifact so the look pass can vary finishes without
    # needing the extractor -- Blender's Python has no PDF stack.
    manifest["rooms"] = _room_block(building)
    manifest["casework"] = _casework_block(building)
    manifest["openings"] = _opening_block(building)
    # Sheet coordinates of the datum the canvas was built on, so the look pass
    # can convert a point in the model back to a point on the drawing.
    manifest["datum_pdf_origin"] = [building.datum.x0, building.datum.y1]

    manifest["provenance"]["assumed"].append(
        f"floor assembly between storeys {ASSUMED_FLOOR_ASSEMBLY_INCHES:.0f}\" "
        "(no section in the drawing set)"
    )
    return TourArtifact(glb, manifest)
