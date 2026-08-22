from __future__ import annotations

import argparse
import hashlib
import json
import struct
from dataclasses import dataclass
from pathlib import Path

from hearthview.canonical import canonical_hash
from hearthview.fixture import build_a1_fixture
from hearthview.models import ProjectModel, ReviewDecision, ReviewState, Wall
from hearthview.units import TICKS_PER_INCH
from hearthview.validation import ValidationToken, assert_token, mint_token, validate


COMPILER_VERSION = "hearthview-analytic-0.1.0"
METERS_PER_TICK = 0.0254 / TICKS_PER_INCH


@dataclass(frozen=True)
class StationInterval:
    start_ticks: int
    end_ticks: int

    def overlaps(self, other: tuple[int, int] | "StationInterval") -> bool:
        other_start, other_end = (
            (other.start_ticks, other.end_ticks)
            if isinstance(other, StationInterval)
            else other
        )
        return self.start_ticks < other_end and other_start < self.end_ticks


@dataclass(frozen=True)
class Primitive:
    element_id: str
    part_kind: str
    x0_ticks: int
    y0_ticks: int
    z0_ticks: int
    x1_ticks: int
    y1_ticks: int
    z1_ticks: int
    station_interval: StationInterval

    def canonical_payload(self) -> dict[str, object]:
        return {
            "element_id": self.element_id,
            "part_kind": self.part_kind,
            "station": [self.station_interval.start_ticks, self.station_interval.end_ticks],
            "bounds": [
                self.x0_ticks,
                self.y0_ticks,
                self.z0_ticks,
                self.x1_ticks,
                self.y1_ticks,
                self.z1_ticks,
            ],
        }


@dataclass(frozen=True)
class GeometryArtifact:
    model_hash: str
    geometry_hash: str
    glb_file_hash: str
    primitive_count: int
    bounds_ticks: tuple[int, int, int, int, int, int]
    glb: bytes


def _wall_box(
    wall: Wall,
    start: int,
    end: int,
    z0: int,
    z1: int,
    part_kind: str,
) -> Primitive:
    if wall.axis == "X":
        bounds = (
            wall.origin_x_ticks + start,
            wall.origin_y_ticks,
            z0,
            wall.origin_x_ticks + end,
            wall.origin_y_ticks + wall.thickness_ticks,
            z1,
        )
    else:
        bounds = (
            wall.origin_x_ticks,
            wall.origin_y_ticks + start,
            z0,
            wall.origin_x_ticks + wall.thickness_ticks,
            wall.origin_y_ticks + end,
            z1,
        )
    return Primitive(
        element_id=wall.id,
        part_kind=part_kind,
        x0_ticks=min(bounds[0], bounds[3]),
        y0_ticks=min(bounds[1], bounds[4]),
        z0_ticks=min(bounds[2], bounds[5]),
        x1_ticks=max(bounds[0], bounds[3]),
        y1_ticks=max(bounds[1], bounds[4]),
        z1_ticks=max(bounds[2], bounds[5]),
        station_interval=StationInterval(start, end),
    )


def _wall_primitives(wall: Wall) -> list[Primitive]:
    openings = [
        child
        for child in wall.ordered_children
        if child.kind in {"WINDOW", "UNFRAMED_OPENING"}
    ]
    breakpoints = {0, wall.length_ticks}
    for opening in openings:
        breakpoints.update((opening.start_ticks, opening.end_ticks))
    primitives: list[Primitive] = []
    ordered_points = sorted(breakpoints)
    for start, end in zip(ordered_points, ordered_points[1:]):
        interval = StationInterval(start, end)
        if not any(interval.overlaps((opening.start_ticks, opening.end_ticks)) for opening in openings):
            primitives.append(_wall_box(wall, start, end, 0, wall.height_ticks, "WALL_SOLID"))
    for opening in openings:
        if opening.kind == "WINDOW":
            sill_height = 30 * TICKS_PER_INCH
            head_height = 78 * TICKS_PER_INCH
            primitives.append(
                _wall_box(
                    wall,
                    opening.start_ticks,
                    opening.end_ticks,
                    0,
                    min(sill_height, wall.height_ticks),
                    f"WINDOW_SILL:{opening.id}",
                )
            )
        else:
            head_height = 84 * TICKS_PER_INCH
        if wall.height_ticks > head_height:
            primitives.append(
                _wall_box(
                    wall,
                    opening.start_ticks,
                    opening.end_ticks,
                    head_height,
                    wall.height_ticks,
                    f"OPENING_HEAD:{opening.id}",
                )
            )
    return primitives


def compile_primitives(model: ProjectModel, token: ValidationToken) -> tuple[Primitive, ...]:
    assert_token(token, model)
    primitives: list[Primitive] = []
    for wall in model.walls:
        primitives.extend(_wall_primitives(wall))
    if model.island is not None:
        island = model.island
        primitives.append(
            Primitive(
                element_id=island.id,
                part_kind="ISLAND",
                x0_ticks=island.x_ticks,
                y0_ticks=island.y_ticks,
                z0_ticks=0,
                x1_ticks=island.x_ticks + island.width_ticks,
                y1_ticks=island.y_ticks + island.depth_ticks,
                z1_ticks=36 * TICKS_PER_INCH,
                station_interval=StationInterval(0, island.width_ticks),
            )
        )
    for fixed_object in model.fixed_objects:
        wall = model.wall(fixed_object.host_wall_id)
        if wall.axis == "Y":
            x0 = wall.origin_x_ticks - 2 * TICKS_PER_INCH
            x1 = wall.origin_x_ticks
            y0 = wall.origin_y_ticks + fixed_object.start_ticks
            y1 = wall.origin_y_ticks + fixed_object.end_ticks
        else:
            x0 = wall.origin_x_ticks + fixed_object.start_ticks
            x1 = wall.origin_x_ticks + fixed_object.end_ticks
            y0 = wall.origin_y_ticks - 2 * TICKS_PER_INCH
            y1 = wall.origin_y_ticks
        primitives.append(
            Primitive(
                element_id=fixed_object.id,
                part_kind="FIXED_TV",
                x0_ticks=min(x0, x1),
                y0_ticks=min(y0, y1),
                z0_ticks=42 * TICKS_PER_INCH,
                x1_ticks=max(x0, x1),
                y1_ticks=max(y0, y1),
                z1_ticks=76 * TICKS_PER_INCH,
                station_interval=StationInterval(
                    fixed_object.start_ticks, fixed_object.end_ticks
                ),
            )
        )
    if primitives:
        min_x = min(item.x0_ticks for item in primitives) - 12 * TICKS_PER_INCH
        min_y = min(item.y0_ticks for item in primitives) - 12 * TICKS_PER_INCH
        max_x = max(item.x1_ticks for item in primitives) + 12 * TICKS_PER_INCH
        max_y = max(item.y1_ticks for item in primitives) + 12 * TICKS_PER_INCH
        primitives.append(
            Primitive(
                element_id="staging_floor_estimated",
                part_kind="ESTIMATED_STAGING_FLOOR",
                x0_ticks=min_x,
                y0_ticks=min_y,
                z0_ticks=-6 * TICKS_PER_INCH,
                x1_ticks=max_x,
                y1_ticks=max_y,
                z1_ticks=0,
                station_interval=StationInterval(0, max_x - min_x),
            )
        )
    return tuple(
        sorted(
            primitives,
            key=lambda item: (
                item.element_id,
                item.part_kind,
                item.station_interval.start_ticks,
                item.station_interval.end_ticks,
            ),
        )
    )


_BOX_INDICES = (
    0, 2, 1, 0, 3, 2,
    4, 5, 6, 4, 6, 7,
    0, 1, 5, 0, 5, 4,
    1, 2, 6, 1, 6, 5,
    2, 3, 7, 2, 7, 6,
    3, 0, 4, 3, 4, 7,
)


def _gltf_point(x: int, y: int, z: int) -> tuple[float, float, float]:
    return (x * METERS_PER_TICK, z * METERS_PER_TICK, -y * METERS_PER_TICK)


def _box_vertices(item: Primitive) -> tuple[tuple[float, float, float], ...]:
    source = (
        (item.x0_ticks, item.y0_ticks, item.z0_ticks),
        (item.x1_ticks, item.y0_ticks, item.z0_ticks),
        (item.x1_ticks, item.y1_ticks, item.z0_ticks),
        (item.x0_ticks, item.y1_ticks, item.z0_ticks),
        (item.x0_ticks, item.y0_ticks, item.z1_ticks),
        (item.x1_ticks, item.y0_ticks, item.z1_ticks),
        (item.x1_ticks, item.y1_ticks, item.z1_ticks),
        (item.x0_ticks, item.y1_ticks, item.z1_ticks),
    )
    return tuple(_gltf_point(*point) for point in source)


def _build_glb(primitives: tuple[Primitive, ...], model_hash: str, geometry_hash: str) -> bytes:
    binary = bytearray()
    buffer_views: list[dict[str, object]] = []
    accessors: list[dict[str, object]] = []
    meshes: list[dict[str, object]] = []
    nodes: list[dict[str, object]] = []

    def append_view(payload: bytes, target: int) -> int:
        while len(binary) % 4:
            binary.append(0)
        offset = len(binary)
        binary.extend(payload)
        index = len(buffer_views)
        buffer_views.append(
            {"buffer": 0, "byteLength": len(payload), "byteOffset": offset, "target": target}
        )
        return index

    for item in primitives:
        vertices = _box_vertices(item)
        position_bytes = struct.pack(
            "<" + "f" * 24,
            *(coordinate for vertex in vertices for coordinate in vertex),
        )
        index_bytes = struct.pack("<" + "H" * len(_BOX_INDICES), *_BOX_INDICES)
        position_view = append_view(position_bytes, 34962)
        index_view = append_view(index_bytes, 34963)
        position_accessor = len(accessors)
        accessors.append(
            {
                "bufferView": position_view,
                "byteOffset": 0,
                "componentType": 5126,
                "count": 8,
                "type": "VEC3",
                "min": [min(vertex[index] for vertex in vertices) for index in range(3)],
                "max": [max(vertex[index] for vertex in vertices) for index in range(3)],
            }
        )
        index_accessor = len(accessors)
        accessors.append(
            {
                "bufferView": index_view,
                "byteOffset": 0,
                "componentType": 5123,
                "count": len(_BOX_INDICES),
                "type": "SCALAR",
                "min": [0],
                "max": [7],
            }
        )
        mesh_index = len(meshes)
        meshes.append(
            {
                "name": f"{item.element_id}:{item.part_kind}",
                "primitives": [
                    {
                        "attributes": {"POSITION": position_accessor},
                        "indices": index_accessor,
                        "material": 0,
                        "mode": 4,
                    }
                ],
            }
        )
        nodes.append(
            {
                "mesh": mesh_index,
                "name": f"{item.element_id}:{item.part_kind}",
                "extras": {
                    "canonicalElementId": item.element_id,
                    "partKind": item.part_kind,
                },
            }
        )
    while len(binary) % 4:
        binary.append(0)
    document = {
        "accessors": accessors,
        "asset": {
            "generator": COMPILER_VERSION,
            "version": "2.0",
            "extras": {"geometryHash": geometry_hash, "modelHash": model_hash},
        },
        "bufferViews": buffer_views,
        "buffers": [{"byteLength": len(binary)}],
        "materials": [
            {
                "name": "Warm neutral model",
                "pbrMetallicRoughness": {
                    "baseColorFactor": [0.82, 0.75, 0.65, 1.0],
                    "metallicFactor": 0.0,
                    "roughnessFactor": 0.8,
                },
            }
        ],
        "meshes": meshes,
        "nodes": nodes,
        "scene": 0,
        "scenes": [{"nodes": list(range(len(nodes)))}],
    }
    json_bytes = json.dumps(
        document,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    while len(json_bytes) % 4:
        json_bytes += b" "
    total_length = 12 + 8 + len(json_bytes) + 8 + len(binary)
    return b"".join(
        (
            struct.pack("<4sII", b"glTF", 2, total_length),
            struct.pack("<I4s", len(json_bytes), b"JSON"),
            json_bytes,
            struct.pack("<I4s", len(binary), b"BIN\x00"),
            bytes(binary),
        )
    )


def compile_glb(model: ProjectModel, token: ValidationToken) -> GeometryArtifact:
    primitives = compile_primitives(model, token)
    geometry_hash = canonical_hash(
        {
            "compiler_version": COMPILER_VERSION,
            "primitives": [item.canonical_payload() for item in primitives],
        }
    )
    glb = _build_glb(primitives, token.model_hash, geometry_hash)
    bounds = (
        min(item.x0_ticks for item in primitives),
        min(item.y0_ticks for item in primitives),
        min(item.z0_ticks for item in primitives),
        max(item.x1_ticks for item in primitives),
        max(item.y1_ticks for item in primitives),
        max(item.z1_ticks for item in primitives),
    )
    return GeometryArtifact(
        model_hash=token.model_hash,
        geometry_hash=geometry_hash,
        glb_file_hash=hashlib.sha256(glb).hexdigest(),
        primitive_count=len(primitives),
        bounds_ticks=bounds,
        glb=glb,
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Compile the approved A-1 fixture.")
    parser.add_argument("--fixture", choices=["a1"], required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    model = build_a1_fixture()
    model = model.model_copy(
        update={
            "review_decisions": tuple(
                ReviewDecision(item_id=item.item_id, state=ReviewState.APPROVED)
                for item in model.review_decisions
            )
        }
    )
    artifact = compile_glb(model, mint_token(model, validate(model)))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(artifact.glb)
    print(json.dumps({
        "model_hash": artifact.model_hash,
        "geometry_hash": artifact.geometry_hash,
        "glb_file_hash": artifact.glb_file_hash,
        "primitive_count": artifact.primitive_count,
        "bounds_ticks": artifact.bounds_ticks,
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
