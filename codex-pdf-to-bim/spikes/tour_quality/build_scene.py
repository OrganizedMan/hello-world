"""Build the isolated HearthView kitchen-family-room tour quality spike in Blender.

Run with Blender 5.2 LTS in background mode.  This script validates every local
authoring input, consumes Task 1's scene contract, assembles the display scene,
renders the poster, exports a self-contained GLB, writes deterministic metadata,
and invokes the existing pure-Python artifact validator.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import shutil
import struct
import subprocess
import sys
import time
from typing import Any

import bpy

from blender_builders import (
    add_area_light,
    add_camera,
    add_point_light,
    create_box,
    create_cabinet_unit,
    create_curve_tube,
    create_cylinder,
    create_mesh_plane,
    create_pbr_material,
    create_principled_material,
    create_root,
    create_shaker_front,
    create_sofa,
    create_sphere,
    create_stool,
    import_gltf_asset,
    tag_contract_boundary,
)


SCRIPT_DIR = Path(__file__).resolve().parent
STAGE_ROOT = SCRIPT_DIR.parents[1]
PROVENANCE_PATH = SCRIPT_DIR / "assets" / "provenance.json"
GLB_NAME = "hearthview-kitchen-family.glb"
POSTER_NAME = "poster.webp"
ENVIRONMENT_NAME = "environment.hdr"
MANIFEST_NAME = "manifest.json"
MAX_BROWSER_BYTES = 45_000_000
COORDINATE_RULE = "three_x=source_x;three_y=source_z;three_z=-source_y"
SCENE_NODES = [
    "HV_ARCHITECTURE",
    "HV_CABINETRY",
    "HV_FURNITURE",
    "HV_LIGHTING",
    "HV_NAVIGATION",
    "HV_FLOOR",
    "HV_ISLAND_STRUCTURE",
    "HV_WALKABLE",
]


class BuildError(RuntimeError):
    """A plain, actionable scene-build failure."""


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _md5(path: Path) -> str:
    digest = hashlib.md5(usedforsecurity=False)
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, required=True, help="Task 1 source repository")
    parser.add_argument("--assets", type=Path, required=True, help="Prepared local source assets")
    parser.add_argument("--output-dir", type=Path, required=True, help="Browser artifact directory")
    arguments = sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else []
    return parser.parse_args(arguments)


def _load_contract(repo: Path) -> tuple[Any, Any]:
    repo = repo.resolve()
    if not (repo / "spikes" / "tour_quality" / "scene_contract.py").is_file():
        raise BuildError(f"Task 1 scene contract is missing under repo: {repo}")
    sys.path.insert(0, str(repo))
    from spikes.tour_quality.scene_contract import build_scene_contract, validate_scene_contract

    contract = build_scene_contract()
    errors = validate_scene_contract(contract)
    if errors:
        raise BuildError("Task 1 contract is invalid:\n" + "\n".join(f"- {error}" for error in errors))
    return contract, sys.modules["spikes.tour_quality.scene_contract"]


def _validate_blender_version() -> None:
    if bpy.app.version < (5, 2, 0):
        raise BuildError(
            "Blender 5.2 or newer is required; found "
            + ".".join(str(component) for component in bpy.app.version)
        )


def _validate_authoring_inputs(assets_dir: Path) -> dict[str, Any]:
    if not assets_dir.is_dir():
        raise BuildError(f"authoring asset directory is missing: {assets_dir}")
    if not PROVENANCE_PATH.is_file():
        raise BuildError(f"provenance manifest is missing: {PROVENANCE_PATH}")
    try:
        provenance = json.loads(PROVENANCE_PATH.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise BuildError(f"provenance manifest is unreadable: {exc}") from exc
    if provenance.get("label") != "Quality spike · visual staging":
        raise BuildError("provenance label must be 'Quality spike · visual staging'")
    if provenance.get("canonical_geometry") is not False:
        raise BuildError("provenance canonical_geometry must be false")

    errors: list[str] = []
    files_seen: set[str] = set()
    for asset in provenance.get("assets", []):
        if not isinstance(asset, dict):
            errors.append("provenance asset entries must be objects")
            continue
        if not asset.get("source_page") or not asset.get("license_url") or not asset.get("authoring_role"):
            errors.append(f"provenance asset {asset.get('id')!r} lacks source/license/role metadata")
        for record in asset.get("files", []):
            if not isinstance(record, dict) or not isinstance(record.get("path"), str):
                errors.append(f"provenance asset {asset.get('id')!r} has an invalid file record")
                continue
            relative = record["path"]
            files_seen.add(relative)
            path = assets_dir / relative
            if not path.is_file():
                errors.append(f"missing authoring input: {path}")
                continue
            actual_sha = _sha256(path)
            if actual_sha != record.get("sha256"):
                errors.append(
                    f"wrong SHA-256 for {relative}: expected {record.get('sha256')}, got {actual_sha}"
                )
            upstream = record.get("upstream_digest")
            if isinstance(upstream, dict):
                algorithm = upstream.get("algorithm")
                expected = upstream.get("value")
                if algorithm == "md5":
                    actual = _md5(path)
                elif algorithm == "sha256":
                    actual = actual_sha
                else:
                    errors.append(f"unsupported upstream digest algorithm for {relative}: {algorithm!r}")
                    continue
                if actual != expected:
                    errors.append(
                        f"wrong upstream {algorithm} for {relative}: expected {expected}, got {actual}"
                    )

    required = {
        "drackenstein_quarry_puresky_1k.hdr",
        "wood_floor_diff_2k.jpg",
        "wood_floor_nor_gl_2k.jpg",
        "wood_floor_rough_2k.jpg",
        "beige_wall_001_diff_1k.jpg",
        "beige_wall_001_nor_gl_1k.jpg",
        "beige_wall_001_rough_1k.jpg",
        "Travertine009_2K-JPG.zip",
        "Travertine009/Travertine009_2K-JPG_Color.jpg",
        "Travertine009/Travertine009_2K-JPG_NormalGL.jpg",
        "Travertine009/Travertine009_2K-JPG_Roughness.jpg",
        "rough_linen_diff_1k.jpg",
        "rough_linen_nor_gl_1k.jpg",
        "rough_linen_rough_1k.jpg",
        "models/modern_arm_chair_01/modern_arm_chair_01_1k.gltf",
        "models/modern_arm_chair_01/modern_arm_chair_01.bin",
        "models/modern_coffee_table_01/modern_coffee_table_01_1k.gltf",
        "models/modern_coffee_table_01/modern_coffee_table_01.bin",
        "models/modern_ceiling_lamp_01/modern_ceiling_lamp_01_1k.gltf",
        "models/modern_ceiling_lamp_01/modern_ceiling_lamp_01.bin",
    }
    missing_from_provenance = sorted(required - files_seen)
    if missing_from_provenance:
        errors.append("provenance omits required inputs: " + ", ".join(missing_from_provenance))
    if errors:
        raise BuildError("authoring input validation failed:\n" + "\n".join(f"- {error}" for error in errors))
    return provenance


def _configure_scene(environment_path: Path) -> bpy.types.Scene:
    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene = bpy.context.scene
    scene.name = "HearthView Tour Quality Spike"
    scene["label"] = "Quality spike · visual staging"
    scene["canonical_geometry"] = False
    scene.unit_settings.system = "METRIC"
    scene.unit_settings.length_unit = "METERS"
    scene.render.engine = "BLENDER_EEVEE_NEXT"
    scene.render.resolution_x = 1920
    scene.render.resolution_y = 1080
    scene.render.resolution_percentage = 100
    scene.render.film_transparent = False
    scene.render.image_settings.file_format = "WEBP"
    scene.render.image_settings.color_mode = "RGB"
    scene.render.image_settings.quality = 95
    scene.render.use_file_extension = True
    scene.render.image_settings.color_depth = "8"
    scene.view_settings.look = _enum_preference(
        scene.view_settings,
        "look",
        ("AgX - Medium High Contrast", "AgX - Medium High Contrast (Punchy)", "Medium High Contrast"),
    )
    scene.view_settings.exposure = 1.0
    _set_if_present(scene.render, "use_high_quality_normals", True)
    if hasattr(scene, "eevee"):
        _set_if_present(scene.eevee, "taa_samples", 96)
        _set_if_present(scene.eevee, "taa_render_samples", 96)
        _set_if_present(scene.eevee, "use_gtao", True)
        _set_if_present(scene.eevee, "gtao_distance", 3.0)
        _set_if_present(scene.eevee, "gtao_factor", 1.15)
        _set_if_present(scene.eevee, "use_raytracing", True)

    world = bpy.data.worlds.new("HV_WORLD")
    world.use_nodes = True
    scene.world = world
    nodes = world.node_tree.nodes
    links = world.node_tree.links
    nodes.clear()
    output = nodes.new("ShaderNodeOutputWorld")
    background = nodes.new("ShaderNodeBackground")
    background.inputs["Strength"].default_value = 0.34
    environment = nodes.new("ShaderNodeTexEnvironment")
    environment.image = bpy.data.images.load(str(environment_path), check_existing=True)
    mapping = nodes.new("ShaderNodeMapping")
    mapping.inputs["Rotation"].default_value[2] = math.radians(18.0)
    texcoord = nodes.new("ShaderNodeTexCoord")
    links.new(texcoord.outputs["Generated"], mapping.inputs["Vector"])
    links.new(mapping.outputs["Vector"], environment.inputs["Vector"])
    links.new(environment.outputs["Color"], background.inputs["Color"])
    links.new(background.outputs["Background"], output.inputs["Surface"])
    return scene


def _set_if_present(target: Any, attribute: str, value: Any) -> None:
    if hasattr(target, attribute):
        try:
            setattr(target, attribute, value)
        except (AttributeError, TypeError, ValueError):
            pass


def _enum_preference(target: Any, attribute: str, preferences: tuple[str, ...]) -> str:
    current = getattr(target, attribute)
    try:
        values = {
            item.identifier
            for item in target.bl_rna.properties[attribute].enum_items
        }
    except (AttributeError, KeyError, TypeError):
        return current
    for preference in preferences:
        if preference in values:
            setattr(target, attribute, preference)
            return preference
    return current


def _create_materials(assets: Path, span: float, depth: float) -> dict[str, bpy.types.Material]:
    materials: dict[str, bpy.types.Material] = {}
    materials["floor"] = create_pbr_material(
        "HV_MAT_WOOD_FLOOR_PBR",
        base_color_path=assets / "wood_floor_diff_2k.jpg",
        normal_path=assets / "wood_floor_nor_gl_2k.jpg",
        roughness_path=assets / "wood_floor_rough_2k.jpg",
        uv_scale=(span / 1.7, depth / 1.7),
        tint=(0.82, 0.72, 0.58, 1.0),
        roughness_multiplier=0.92,
    )
    materials["plaster"] = create_pbr_material(
        "HV_MAT_BEIGE_PLASTER_PBR",
        base_color_path=assets / "beige_wall_001_diff_1k.jpg",
        normal_path=assets / "beige_wall_001_nor_gl_1k.jpg",
        roughness_path=assets / "beige_wall_001_rough_1k.jpg",
        uv_scale=(2.4, 2.4),
        tint=(0.90, 0.84, 0.74, 1.0),
        roughness_multiplier=1.05,
    )
    materials["stone"] = create_pbr_material(
        "HV_MAT_TRAVERTINE_HONED_PBR",
        base_color_path=assets / "Travertine009" / "Travertine009_2K-JPG_Color.jpg",
        normal_path=assets / "Travertine009" / "Travertine009_2K-JPG_NormalGL.jpg",
        roughness_path=assets / "Travertine009" / "Travertine009_2K-JPG_Roughness.jpg",
        uv_scale=(2.2, 2.2),
        tint=(1.0, 0.95, 0.87, 1.0),
        roughness_multiplier=0.78,
    )
    materials["linen"] = create_pbr_material(
        "HV_MAT_ROUGH_LINEN_PBR",
        base_color_path=assets / "rough_linen_diff_1k.jpg",
        normal_path=assets / "rough_linen_nor_gl_1k.jpg",
        roughness_path=assets / "rough_linen_rough_1k.jpg",
        uv_scale=(3.2, 3.2),
        tint=(0.79, 0.67, 0.53, 1.0),
        roughness_multiplier=1.05,
    )
    materials["cabinet"] = create_principled_material(
        "HV_MAT_PUTTY_CABINET", (0.68, 0.61, 0.49, 1.0), roughness=0.39
    )
    materials["cabinet_body"] = create_principled_material(
        "HV_MAT_CABINET_INTERIOR", (0.55, 0.49, 0.39, 1.0), roughness=0.48
    )
    materials["trim"] = create_principled_material(
        "HV_MAT_WARM_TRIM", (0.87, 0.82, 0.72, 1.0), roughness=0.40
    )
    materials["oak"] = create_principled_material(
        "HV_MAT_OAK", (0.39, 0.24, 0.12, 1.0), roughness=0.46
    )
    materials["bronze"] = create_principled_material(
        "HV_MAT_DARK_BRASS", (0.22, 0.13, 0.055, 1.0), roughness=0.27, metallic=0.82
    )
    materials["steel"] = create_principled_material(
        "HV_MAT_BRUSHED_STEEL", (0.48, 0.50, 0.50, 1.0), roughness=0.29, metallic=0.84
    )
    materials["black"] = create_principled_material(
        "HV_MAT_CHARCOAL", (0.018, 0.014, 0.011, 1.0), roughness=0.30, metallic=0.12
    )
    materials["glass"] = create_principled_material(
        "HV_MAT_CLEAR_GLASS", (0.69, 0.82, 0.86, 0.16), roughness=0.08, transmission=1.0, ior=1.45, alpha=0.22
    )
    materials["rug"] = create_principled_material(
        "HV_MAT_LOW_PILE_RUG", (0.33, 0.28, 0.22, 1.0), roughness=0.92
    )
    materials["ceramic"] = create_principled_material(
        "HV_MAT_CERAMIC", (0.66, 0.57, 0.45, 1.0), roughness=0.22
    )
    materials["leaf"] = create_principled_material(
        "HV_MAT_PLANT_LEAF", (0.08, 0.16, 0.07, 1.0), roughness=0.72
    )
    materials["screen"] = create_principled_material(
        "HV_MAT_TV_SCREEN", (0.004, 0.006, 0.008, 1.0), roughness=0.12, metallic=0.18
    )
    materials["navigation"] = create_principled_material(
        "HV_MAT_NAVIGATION", (0.07, 0.28, 0.42, 0.01), roughness=1.0, alpha=0.01
    )
    materials["bulb"] = create_principled_material(
        "HV_MAT_WARM_BULB",
        (1.0, 0.63, 0.27, 1.0),
        roughness=0.24,
        emission_color=(1.0, 0.42, 0.12, 1.0),
        emission_strength=7.5,
    )
    return materials


def _build_architecture(contract: Any, materials: dict[str, bpy.types.Material], root: bpy.types.Object) -> None:
    envelope = contract.envelope
    span = envelope.max_x - envelope.min_x
    depth = envelope.max_y - envelope.min_y
    ceiling = envelope.max_z - envelope.min_z
    wall = 0.14
    openings = {opening.name: opening.footprint for opening in contract.wall_openings}
    kitchen_window = openings["kitchen_window_group"]
    deck_door = openings["deck_door_group"]
    mudroom = openings["mudroom_opening"]
    south_living = openings["south_living_opening"]

    floor = create_box(
        "HV_FLOOR",
        (span, depth, 0.045),
        (span / 2, depth / 2, -0.0225),
        material=materials["floor"],
        parent=root,
        bevel=0.0,
    )
    floor["printed_span_meters"] = span
    floor["printed_depth_meters"] = depth
    create_box(
        "HV_CEILING",
        (span, depth, 0.055),
        (span / 2, depth / 2, ceiling + 0.0275),
        material=materials["plaster"],
        parent=root,
        bevel=0.001,
    )

    # North wall, segmented around the A-1 kitchen window and deck glazing.
    window_sill = 0.95
    window_head = 2.05
    door_sill = 0.05
    door_head = 2.35
    _wall_box("HV_NORTH_WALL_WEST", (kitchen_window.min_x, wall, ceiling), (kitchen_window.min_x / 2, -wall / 2, ceiling / 2), materials, root)
    _wall_box("HV_NORTH_WINDOW_SILL_WALL", (kitchen_window.width, wall, window_sill), ((kitchen_window.min_x + kitchen_window.max_x) / 2, -wall / 2, window_sill / 2), materials, root)
    _wall_box("HV_NORTH_WINDOW_HEADER", (kitchen_window.width, wall, ceiling - window_head), ((kitchen_window.min_x + kitchen_window.max_x) / 2, -wall / 2, (window_head + ceiling) / 2), materials, root)
    _wall_box("HV_NORTH_BETWEEN_OPENINGS", (deck_door.min_x - kitchen_window.max_x, wall, ceiling), ((kitchen_window.max_x + deck_door.min_x) / 2, -wall / 2, ceiling / 2), materials, root)
    _wall_box("HV_NORTH_DECK_HEADER", (deck_door.width, wall, ceiling - door_head), ((deck_door.min_x + deck_door.max_x) / 2, -wall / 2, (door_head + ceiling) / 2), materials, root)
    _wall_box("HV_NORTH_WALL_EAST", (span - deck_door.max_x, wall, ceiling), ((deck_door.max_x + span) / 2, -wall / 2, ceiling / 2), materials, root)

    # West wall is the appliance wall. East wall retains the mudroom transition and TV section.
    _wall_box("HV_WEST_WALL", (wall, depth, ceiling), (-wall / 2, depth / 2, ceiling / 2), materials, root)
    _wall_box("HV_EAST_WALL_NORTH_PIER", (wall, mudroom.min_y, ceiling), (span + wall / 2, mudroom.min_y / 2, ceiling / 2), materials, root)
    _wall_box("HV_EAST_MUDROOM_HEADER", (wall, mudroom.depth, ceiling - 2.18), (span + wall / 2, (mudroom.min_y + mudroom.max_y) / 2, (2.18 + ceiling) / 2), materials, root)
    _wall_box("HV_EAST_TV_WALL", (wall, depth - mudroom.max_y, ceiling), (span + wall / 2, (mudroom.max_y + depth) / 2, ceiling / 2), materials, root)

    # Only short south returns are modeled so the existing-living-room transition reads as open.
    _wall_box("HV_SOUTH_RETURN_WEST", (0.62, wall, ceiling), (0.31, depth + wall / 2, ceiling / 2), materials, root)
    _wall_box("HV_SOUTH_RETURN_EAST", (span - 8.62, wall, ceiling), ((8.62 + span) / 2, depth + wall / 2, ceiling / 2), materials, root)
    create_box(
        "HV_SOUTH_LIVING_THRESHOLD",
        (south_living.width, 0.12, 0.016),
        ((south_living.min_x + south_living.max_x) / 2, depth, 0.008),
        material=materials["stone"],
        parent=root,
        bevel=0.002,
    )

    # Window and deck-door groups carry trim, sills, mullions and local glazing.
    _build_window_group(
        "HV_OPENING_kitchen_window_group",
        min_x=kitchen_window.min_x,
        max_x=kitchen_window.max_x,
        sill=window_sill,
        head=window_head,
        y=-0.002,
        materials=materials,
        parent=root,
        mullions=2,
    )
    _build_window_group(
        "HV_OPENING_deck_door_group",
        min_x=deck_door.min_x,
        max_x=deck_door.max_x,
        sill=door_sill,
        head=door_head,
        y=-0.002,
        materials=materials,
        parent=root,
        mullions=3,
    )
    mudroom_root = create_root("HV_OPENING_mudroom_opening", root)
    for y in (mudroom.min_y, mudroom.max_y):
        create_box(
            f"HV_MUDROOM_CASING_{y:.2f}",
            (0.045, 0.08, 2.24),
            (span - 0.018, y, 1.12),
            material=materials["trim"],
            parent=mudroom_root,
            bevel=0.002,
        )
    create_box(
        "HV_MUDROOM_CASING_HEAD",
        (0.045, mudroom.depth + 0.08, 0.08),
        (span - 0.018, (mudroom.min_y + mudroom.max_y) / 2, 2.20),
        material=materials["trim"],
        parent=mudroom_root,
        bevel=0.002,
    )

    # Real-scale baseboard and restrained ceiling trim.
    create_box("HV_BASEBOARD_NORTH", (span, 0.025, 0.105), (span / 2, 0.0125, 0.0525), material=materials["trim"], parent=root, bevel=0.002)
    create_box("HV_BASEBOARD_WEST", (0.025, depth, 0.105), (0.0125, depth / 2, 0.0525), material=materials["trim"], parent=root, bevel=0.002)
    create_box("HV_CEILING_TRIM_NORTH", (span, 0.045, 0.06), (span / 2, 0.0225, ceiling - 0.03), material=materials["trim"], parent=root, bevel=0.002)
    create_box("HV_CEILING_TRIM_WEST", (0.045, depth, 0.06), (0.0225, depth / 2, ceiling - 0.03), material=materials["trim"], parent=root, bevel=0.002)


def _wall_box(name: str, size: tuple[float, float, float], location: tuple[float, float, float], materials: dict[str, bpy.types.Material], root: bpy.types.Object) -> None:
    create_box(name, size, location, material=materials["plaster"], parent=root, bevel=0.003)


def _build_window_group(
    name: str,
    *,
    min_x: float,
    max_x: float,
    sill: float,
    head: float,
    y: float,
    materials: dict[str, bpy.types.Material],
    parent: bpy.types.Object,
    mullions: int,
) -> None:
    root = create_root(name, parent)
    width = max_x - min_x
    height = head - sill
    create_box(f"{name}_GLASS", (width - 0.08, 0.014, height - 0.08), ((min_x + max_x) / 2, y, (sill + head) / 2), material=materials["glass"], parent=root, bevel=0.001)
    for suffix, x in (("L", min_x), ("R", max_x)):
        create_box(f"{name}_JAMB_{suffix}", (0.065, 0.075, height + 0.12), (x, y + 0.025, (sill + head) / 2), material=materials["trim"], parent=root, bevel=0.002)
    for suffix, z in (("SILL", sill), ("HEAD", head)):
        create_box(f"{name}_{suffix}", (width + 0.13, 0.10, 0.065), ((min_x + max_x) / 2, y + 0.028, z), material=materials["trim"], parent=root, bevel=0.002)
    for index in range(1, mullions + 1):
        x = min_x + width * index / (mullions + 1)
        create_box(f"{name}_MULLION_{index}", (0.035, 0.045, height - 0.04), (x, y + 0.035, (sill + head) / 2), material=materials["trim"], parent=root, bevel=0.0015)


def _build_navigation(contract: Any, materials: dict[str, bpy.types.Material], root: bpy.types.Object) -> None:
    polygon = contract.walkable_polygon
    min_x = min(point[0] for point in polygon)
    max_x = max(point[0] for point in polygon)
    min_y = min(point[1] for point in polygon)
    max_y = max(point[1] for point in polygon)
    walkable = create_mesh_plane(
        "HV_WALKABLE",
        min_x=min_x,
        max_x=max_x,
        min_y=min_y,
        max_y=max_y,
        z=0.004,
        material=materials["navigation"],
        parent=root,
    )
    walkable["raycastable"] = True
    walkable["min_x"] = min_x
    walkable["max_x"] = max_x
    walkable["min_y"] = min_y
    walkable["max_y"] = max_y

    for rectangle in contract.collision_rectangles:
        collider = create_box(
            f"HV_COLLIDER_{rectangle.name}",
            (rectangle.max_x - rectangle.min_x, rectangle.max_y - rectangle.min_y, 0.012),
            ((rectangle.min_x + rectangle.max_x) / 2, (rectangle.min_y + rectangle.max_y) / 2, 0.006),
            material=materials["navigation"],
            parent=root,
            bevel=0.0,
        )
        collider["collider_name"] = rectangle.name
        collider["min_x"] = rectangle.min_x
        collider["max_x"] = rectangle.max_x
        collider["min_y"] = rectangle.min_y
        collider["max_y"] = rectangle.max_y


def _build_kitchen(contract: Any, materials: dict[str, bpy.types.Material], root: bpy.types.Object) -> None:
    counter_depth = contract.counter_zone_depth
    island = contract.island_footprint
    kitchen_window = next(
        opening.footprint
        for opening in contract.wall_openings
        if opening.name == "kitchen_window_group"
    )
    sink_center = (kitchen_window.min_x + kitchen_window.max_x) / 2
    sink_start = sink_center - 0.495
    dishwasher_start = sink_start - 0.60
    left_tower_start = dishwasher_start - 0.50
    trash_start = sink_start + 0.99
    right_tower_start = trash_start + 0.36

    # North wall: tower, dishwasher, sink under the contract window, trash, tower.
    create_cabinet_unit(
        "HV_NORTH_FILLER_BASE",
        start=0.05,
        width=2.93,
        depth=counter_depth,
        base_z=0.095,
        height=0.775,
        run_axis="X",
        body_material=materials["cabinet_body"],
        front_material=materials["cabinet"],
        hardware_material=materials["bronze"],
        parent=root,
        doors=4,
    )
    create_box("HV_NORTH_FILLER_COUNTER", (2.98, counter_depth, 0.04), (1.49, counter_depth / 2, 0.89), material=materials["stone"], parent=root, bevel=0.006, bevel_segments=4)
    create_cabinet_unit(
        "HV_NORTH_TOWER_LEFT",
        start=left_tower_start,
        width=0.50,
        depth=0.64,
        base_z=0.095,
        height=2.26,
        run_axis="X",
        body_material=materials["cabinet_body"],
        front_material=materials["cabinet"],
        hardware_material=materials["bronze"],
        parent=root,
        doors=2,
    )
    _create_dishwasher(dishwasher_start, 0.60, counter_depth, materials, root)
    create_cabinet_unit(
        "HV_NORTH_SINK_BASE",
        start=sink_start,
        width=0.99,
        depth=counter_depth,
        base_z=0.095,
        height=0.775,
        run_axis="X",
        body_material=materials["cabinet_body"],
        front_material=materials["cabinet"],
        hardware_material=materials["bronze"],
        parent=root,
        doors=2,
    )
    create_cabinet_unit(
        "HV_NORTH_TRASH_PULLOUT",
        start=trash_start,
        width=0.36,
        depth=counter_depth,
        base_z=0.095,
        height=0.775,
        run_axis="X",
        body_material=materials["cabinet_body"],
        front_material=materials["cabinet"],
        hardware_material=materials["bronze"],
        parent=root,
        doors=1,
    )
    create_box("HV_NORTH_COUNTER_SINK_RUN", (right_tower_start - dishwasher_start, counter_depth, 0.04), ((dishwasher_start + right_tower_start) / 2, counter_depth / 2, 0.89), material=materials["stone"], parent=root, bevel=0.006, bevel_segments=4)
    create_cabinet_unit(
        "HV_NORTH_TOWER_RIGHT",
        start=right_tower_start,
        width=0.50,
        depth=0.64,
        base_z=0.095,
        height=2.26,
        run_axis="X",
        body_material=materials["cabinet_body"],
        front_material=materials["cabinet"],
        hardware_material=materials["bronze"],
        parent=root,
        doors=2,
    )
    _create_sink_and_faucet(sink_center, counter_depth, materials, root)
    create_cabinet_unit(
        "HV_NORTH_UPPER_LEFT_OF_WINDOW",
        start=left_tower_start + 0.52,
        width=0.35,
        depth=0.39,
        base_z=1.42,
        height=0.90,
        run_axis="X",
        body_material=materials["cabinet_body"],
        front_material=materials["cabinet"],
        hardware_material=materials["bronze"],
        parent=root,
        doors=1,
        toe_kick=False,
    )
    create_cabinet_unit(
        "HV_NORTH_UPPER_RIGHT_OF_WINDOW",
        start=kitchen_window.max_x + 0.04,
        width=0.13,
        depth=0.39,
        base_z=1.42,
        height=0.90,
        run_axis="X",
        body_material=materials["cabinet_body"],
        front_material=materials["cabinet"],
        hardware_material=materials["bronze"],
        parent=root,
        doors=1,
        toe_kick=False,
    )

    # West order north-to-south: uppers, range and hood, uppers, refrigerator.
    create_cabinet_unit(
        "HV_WEST_UPPER_NORTH",
        start=0.08,
        width=0.62,
        depth=0.39,
        base_z=1.42,
        height=0.90,
        run_axis="Y",
        body_material=materials["cabinet_body"],
        front_material=materials["cabinet"],
        hardware_material=materials["bronze"],
        parent=root,
        doors=1,
        toe_kick=False,
    )
    create_cabinet_unit(
        "HV_WEST_BASE_NORTH",
        start=0.08,
        width=0.62,
        depth=counter_depth,
        base_z=0.095,
        height=0.775,
        run_axis="Y",
        body_material=materials["cabinet_body"],
        front_material=materials["cabinet"],
        hardware_material=materials["bronze"],
        parent=root,
    )
    create_box("HV_WEST_COUNTER_NORTH", (counter_depth, 0.70, 0.04), (counter_depth / 2, 0.35, 0.89), material=materials["stone"], parent=root, bevel=0.006, bevel_segments=4)
    _create_range_and_hood(0.72, 0.9144, counter_depth, materials, root)
    create_cabinet_unit(
        "HV_WEST_UPPER_SOUTH",
        start=1.66,
        width=0.31,
        depth=0.39,
        base_z=1.42,
        height=0.90,
        run_axis="Y",
        body_material=materials["cabinet_body"],
        front_material=materials["cabinet"],
        hardware_material=materials["bronze"],
        parent=root,
        doors=1,
        toe_kick=False,
    )
    create_cabinet_unit(
        "HV_WEST_BASE_SOUTH",
        start=1.66,
        width=0.31,
        depth=counter_depth,
        base_z=0.095,
        height=0.775,
        run_axis="Y",
        body_material=materials["cabinet_body"],
        front_material=materials["cabinet"],
        hardware_material=materials["bronze"],
        parent=root,
    )
    create_box("HV_WEST_COUNTER_SOUTH", (counter_depth, 0.34, 0.04), (counter_depth / 2, 1.83, 0.89), material=materials["stone"], parent=root, bevel=0.006, bevel_segments=4)
    _create_refrigerator(2.00, 0.75, counter_depth, materials, root)

    # Crown/filler closes the cabinetry composition without implying measured BIM detail.
    create_box("HV_NORTH_CABINET_CROWN", (2.98, 0.075, 0.075), (4.49, 0.10, 2.39), material=materials["cabinet"], parent=root, bevel=0.003)
    create_box("HV_WEST_CABINET_CROWN", (0.075, 2.67, 0.075), (0.10, 1.375, 2.39), material=materials["cabinet"], parent=root, bevel=0.003)

    # Island structure is exact before its separate honed-stone overhang slab.
    island_center = ((island.min_x + island.max_x) / 2, (island.min_y + island.max_y) / 2)
    structure = create_box(
        "HV_ISLAND_STRUCTURE",
        (island.width, island.depth, 0.91),
        (island_center[0], island_center[1], 0.455),
        material=materials["cabinet_body"],
        parent=root,
        bevel=0.004,
        bevel_segments=4,
    )
    structure["footprint_min_x"] = island.min_x
    structure["footprint_max_x"] = island.max_x
    structure["footprint_min_y"] = island.min_y
    structure["footprint_max_y"] = island.max_y
    _panel_island(island, materials, root)
    create_box(
        "HV_ISLAND_COUNTER_SLAB",
        (island.width + 0.08, island.depth + 0.31, 0.042),
        (island_center[0], island_center[1] + 0.115, 0.931),
        material=materials["stone"],
        parent=root,
        bevel=0.009,
        bevel_segments=5,
    )

    # Four real-scale stools occupy the south overhang without closing the main walk route.
    stool_y = island.max_y + 0.34
    for index, x in enumerate((1.98, 2.66, 3.34, 4.02), start=1):
        create_stool(
            f"HV_ISLAND_STOOL_{index}",
            location=(x, stool_y, 0.0),
            upholstery=materials["linen"],
            metal=materials["bronze"],
            parent=root,
        )

    # Restricted counter styling: one bowl and two small vessels, no branded clutter.
    create_cylinder("HV_COUNTER_BOWL", radius=0.15, depth=0.07, location=(2.65, 2.35, 0.99), material=materials["ceramic"], parent=root, vertices=48, bevel=0.01)
    create_cylinder("HV_COUNTER_VESSEL", radius=0.045, depth=0.18, location=(0.38, 0.42, 1.00), material=materials["ceramic"], parent=root, vertices=32, bevel=0.006)


def _create_dishwasher(start: float, width: float, depth: float, materials: dict[str, bpy.types.Material], root: bpy.types.Object) -> None:
    center_x = start + width / 2
    create_box("HV_DISHWASHER_BODY", (width - 0.015, depth - 0.04, 0.79), (center_x, (depth - 0.04) / 2, 0.49), material=materials["steel"], parent=root, bevel=0.004)
    create_box("HV_DISHWASHER_FRONT", (width - 0.025, 0.022, 0.73), (center_x, depth + 0.007, 0.51), material=materials["cabinet"], parent=root, bevel=0.003)
    create_cylinder("HV_DISHWASHER_PULL", radius=0.008, depth=width * 0.62, location=(center_x, depth + 0.028, 0.78), rotation=(0.0, math.pi / 2, 0.0), material=materials["bronze"], parent=root, vertices=24)


def _create_sink_and_faucet(center_x: float, depth: float, materials: dict[str, bpy.types.Material], root: bpy.types.Object) -> None:
    create_box("HV_SINK_RIM", (0.66, 0.43, 0.035), (center_x, 0.37, 0.94), material=materials["steel"], parent=root, bevel=0.02, bevel_segments=5)
    create_box("HV_SINK_BASIN", (0.57, 0.34, 0.06), (center_x, 0.37, 0.958), material=materials["black"], parent=root, bevel=0.025, bevel_segments=5)
    create_curve_tube(
        "HV_GOSENECK_FAUCET",
        [(center_x + 0.22, 0.18, 0.96), (center_x + 0.22, 0.18, 1.34), (center_x, 0.26, 1.39), (center_x, 0.36, 1.20)],
        radius=0.014,
        material=materials["bronze"],
        parent=root,
    )
    create_cylinder("HV_FAUCET_HANDLE", radius=0.012, depth=0.14, location=(center_x + 0.29, 0.18, 1.08), material=materials["bronze"], parent=root, vertices=24)


def _create_range_and_hood(start: float, width: float, depth: float, materials: dict[str, bpy.types.Material], root: bpy.types.Object) -> None:
    center_y = start + width / 2
    create_box("HV_RANGE_BODY", (depth - 0.02, width - 0.02, 0.89), ((depth - 0.02) / 2, center_y, 0.445), material=materials["black"], parent=root, bevel=0.006)
    create_box("HV_RANGE_OVEN_GLASS", (0.025, width * 0.67, 0.43), (depth + 0.006, center_y, 0.42), material=materials["screen"], parent=root, bevel=0.018)
    create_cylinder("HV_RANGE_HANDLE", radius=0.012, depth=width * 0.72, location=(depth + 0.032, center_y, 0.68), rotation=(math.pi / 2, 0.0, 0.0), material=materials["steel"], parent=root, vertices=24)
    for row, x in enumerate((0.19, 0.46)):
        for col, y_offset in enumerate((-0.25, 0.25)):
            create_cylinder(f"HV_RANGE_BURNER_{row}_{col}", radius=0.105, depth=0.018, location=(x, center_y + y_offset, 0.908), material=materials["black"], parent=root, vertices=40, bevel=0.002)
    for index, offset in enumerate((-0.28, -0.14, 0.0, 0.14, 0.28)):
        create_cylinder(f"HV_RANGE_KNOB_{index + 1}", radius=0.027, depth=0.025, location=(depth + 0.032, center_y + offset, 0.79), rotation=(0.0, math.pi / 2, 0.0), material=materials["bronze"], parent=root, vertices=28)
    create_box("HV_RANGE_HOOD", (0.58, width + 0.10, 0.19), (0.30, center_y, 1.73), material=materials["cabinet"], parent=root, bevel=0.025, bevel_segments=5)
    create_box("HV_RANGE_HOOD_CHIMNEY", (0.35, 0.44, 0.66), (0.18, center_y, 2.12), material=materials["cabinet"], parent=root, bevel=0.008)


def _create_refrigerator(start: float, width: float, depth: float, materials: dict[str, bpy.types.Material], root: bpy.types.Object) -> None:
    center_y = start + width / 2
    create_box("HV_REFRIGERATOR_BODY", (depth - 0.015, width - 0.015, 2.28), ((depth - 0.015) / 2, center_y, 1.14), material=materials["steel"], parent=root, bevel=0.015, bevel_segments=4)
    create_box("HV_REFRIGERATOR_DOOR_N", (0.026, width / 2 - 0.012, 1.58), (depth + 0.007, start + width * 0.25, 1.43), material=materials["cabinet"], parent=root, bevel=0.006)
    create_box("HV_REFRIGERATOR_DOOR_S", (0.026, width / 2 - 0.012, 1.58), (depth + 0.007, start + width * 0.75, 1.43), material=materials["cabinet"], parent=root, bevel=0.006)
    create_box("HV_REFRIGERATOR_FREEZER", (0.026, width - 0.025, 0.50), (depth + 0.007, center_y, 0.36), material=materials["cabinet"], parent=root, bevel=0.006)
    for index, y in enumerate((start + width * 0.39, start + width * 0.61)):
        create_cylinder(f"HV_REFRIGERATOR_HANDLE_{index + 1}", radius=0.011, depth=0.74, location=(depth + 0.045, y, 1.46), material=materials["bronze"], parent=root, vertices=24)


def _panel_island(island: Any, materials: dict[str, bpy.types.Material], root: bpy.types.Object) -> None:
    center_x = (island.min_x + island.max_x) / 2
    center_y = (island.min_y + island.max_y) / 2
    panel_height = 0.72
    for side, y in (("N", island.min_y - 0.006), ("S", island.max_y + 0.006)):
        panel_width = island.width / 3
        for index in range(3):
            x = island.min_x + panel_width * (index + 0.5)
            create_shaker_front(
                f"HV_ISLAND_{side}_PANEL_{index + 1}",
                center=(x, y, 0.49),
                width=panel_width - 0.012,
                height=panel_height,
                thickness=0.018,
                face_axis="Y",
                material=materials["cabinet"],
                hardware_material=materials["bronze"],
                parent=root,
                pull_side=1.0 if side == "S" else -1.0,
            )
    for side, x in (("W", island.min_x - 0.006), ("E", island.max_x + 0.006)):
        create_shaker_front(
            f"HV_ISLAND_{side}_PANEL",
            center=(x, center_y, 0.49),
            width=island.depth - 0.025,
            height=panel_height,
            thickness=0.018,
            face_axis="X",
            material=materials["cabinet"],
            hardware_material=materials["bronze"],
            parent=root,
            pull_side=1.0 if side == "E" else -1.0,
        )
    create_box("HV_ISLAND_PLINTH", (island.width - 0.12, island.depth - 0.12, 0.095), (center_x, center_y, 0.0475), material=materials["cabinet_body"], parent=root, bevel=0.002)


def _build_living(assets: Path, materials: dict[str, bpy.types.Material], root: bpy.types.Object) -> None:
    create_box("HV_LIVING_RUG", (2.72, 2.62, 0.018), (7.32, 2.62, 0.018), material=materials["rug"], parent=root, bevel=0.012, bevel_segments=4)
    create_sofa("HV_LINEN_SOFA", location=(6.12, 3.55, 0.0), upholstery=materials["linen"], wood=materials["oak"], parent=root)
    import_gltf_asset(
        assets / "models" / "modern_arm_chair_01" / "modern_arm_chair_01_1k.gltf",
        name="HV_IMPORTED_MODERN_ARM_CHAIR_01",
        parent=root,
        floor_center=(6.95, 1.30, 0.0),
        target_max_extent=1.02,
        rotation_z=math.radians(28.0),
        material_overrides={"pillow": materials["linen"], "legs": materials["oak"]},
    )
    import_gltf_asset(
        assets / "models" / "modern_coffee_table_01" / "modern_coffee_table_01_1k.gltf",
        name="HV_IMPORTED_MODERN_COFFEE_TABLE_01",
        parent=root,
        floor_center=(7.50, 2.45, 0.0),
        target_max_extent=1.20,
        rotation_z=math.radians(90.0),
        material_overrides={"table": materials["oak"], "wood": materials["oak"]},
    )
    create_box("HV_MEDIA_CONSOLE", (0.42, 1.72, 0.44), (8.88, 2.06, 0.24), material=materials["oak"], parent=root, bevel=0.015, bevel_segments=4)
    create_box("HV_TV_SCREEN", (0.045, 1.42, 0.80), (9.115, 2.06, 1.23), material=materials["screen"], parent=root, bevel=0.018, bevel_segments=5)
    create_cylinder("HV_PLANTER", radius=0.22, depth=0.42, location=(8.35, 3.80, 0.21), material=materials["ceramic"], parent=root, vertices=48, bevel=0.012)
    create_cylinder("HV_PLANT_TRUNK", radius=0.035, depth=1.15, location=(8.35, 3.80, 0.90), material=materials["oak"], parent=root, vertices=24)
    for index, (dx, dy, dz, scale) in enumerate(
        ((-0.18, 0.02, 1.18, (1.0, 0.45, 0.32)), (0.18, -0.05, 1.32, (0.95, 0.42, 0.30)), (0.05, 0.18, 1.52, (1.05, 0.48, 0.34)), (-0.10, -0.15, 1.65, (0.82, 0.38, 0.28)))
    ):
        create_sphere(f"HV_PLANT_LEAF_{index + 1}", radius=0.30, location=(8.35 + dx, 3.80 + dy, dz), scale=scale, material=materials["leaf"], parent=root, segments=32, rings=16)
    create_cylinder("HV_COFFEE_CERAMIC", radius=0.075, depth=0.18, location=(7.48, 2.25, 0.49), material=materials["ceramic"], parent=root, vertices=32, bevel=0.008)
    create_box("HV_COFFEE_BOOK_1", (0.26, 0.19, 0.025), (7.57, 2.58, 0.425), material=materials["trim"], parent=root, bevel=0.004)
    create_box("HV_COFFEE_BOOK_2", (0.23, 0.17, 0.023), (7.56, 2.58, 0.45), material=materials["cabinet"], parent=root, bevel=0.004, rotation=(0.0, 0.0, math.radians(6.0)))


def _build_lighting_and_cameras(
    assets: Path,
    materials: dict[str, bpy.types.Material],
    lighting_root: bpy.types.Object,
    navigation_root: bpy.types.Object,
    contract: Any,
) -> bpy.types.Object:
    # Imported real-scale pendants plus emissive bulbs and corresponding warm lights.
    for index, x in enumerate((2.05, 3.04, 4.03), start=1):
        import_gltf_asset(
            assets / "models" / "modern_ceiling_lamp_01" / "modern_ceiling_lamp_01_1k.gltf",
            name=f"HV_IMPORTED_MODERN_CEILING_LAMP_01_{index}",
            parent=lighting_root,
            floor_center=(x, 2.375, 1.48),
            target_max_extent=0.90,
            rotation_z=math.radians(12.0 * (index - 2)),
        )
        create_sphere(f"HV_PENDANT_BULB_{index}", radius=0.055, location=(x, 2.375, 1.56), scale=(1.0, 1.0, 1.18), material=materials["bulb"], parent=lighting_root, segments=32, rings=16)
        add_point_light(f"HV_PENDANT_LIGHT_{index}", location=(x, 2.375, 1.55), energy=88.0, color=(1.0, 0.46, 0.20), parent=lighting_root, radius=0.20)

    add_area_light("HV_NORTH_WINDOW_DAYLIGHT", location=(4.62, -0.42, 1.52), energy=720.0, size=1.30, color=(0.78, 0.88, 1.0), target=(4.30, 2.00, 0.88), parent=lighting_root)
    add_area_light("HV_DECK_DOOR_DAYLIGHT", location=(7.42, -0.48, 1.38), energy=960.0, size=2.35, color=(0.82, 0.90, 1.0), target=(6.80, 2.70, 0.90), parent=lighting_root)
    add_area_light("HV_CEILING_BOUNCE", location=(5.30, 2.75, 2.42), energy=430.0, size=4.20, color=(1.0, 0.70, 0.48), target=(5.30, 2.75, 0.0), parent=lighting_root)

    sun_data = bpy.data.lights.new(name="HV_SUN_DATA", type="SUN")
    sun_data.energy = 1.55
    sun_data.angle = math.radians(4.0)
    sun_data.color = (1.0, 0.79, 0.59)
    sun = bpy.data.objects.new("HV_SUN", sun_data)
    bpy.context.collection.objects.link(sun)
    sun.rotation_euler = (math.radians(36.0), 0.0, math.radians(-24.0))
    sun.parent = lighting_root

    hero = add_camera(
        "HV_CAMERA_HERO",
        position=(0.76, 4.22, 1.66),
        target=(5.15, 1.92, 1.02),
        lens_mm=38.0,
        parent=navigation_root,
    )
    preset_lenses = {"kitchen_overview": 39.0, "walk_start": 40.0, "overhead": 42.0}
    for preset in contract.camera_presets:
        add_camera(
            f"HV_CAMERA_{preset.name.upper()}",
            position=preset.position,
            target=preset.target,
            lens_mm=preset_lenses[preset.name],
            parent=navigation_root,
        )
    return hero


def _convert_curves_to_mesh() -> None:
    for obj in list(bpy.data.objects):
        if obj.type != "CURVE":
            continue
        bpy.ops.object.select_all(action="DESELECT")
        obj.select_set(True)
        bpy.context.view_layer.objects.active = obj
        result = bpy.ops.object.convert(target="MESH")
        if "FINISHED" not in result:
            raise BuildError(f"failed to convert curve for glTF export: {obj.name}")


def _render_poster(scene: bpy.types.Scene, poster_path: Path) -> float:
    scene.render.filepath = str(poster_path)
    started = time.monotonic()
    result = bpy.ops.render.render(write_still=True)
    duration = time.monotonic() - started
    if "FINISHED" not in result or not poster_path.is_file():
        raise BuildError(f"poster render failed: {poster_path}")
    if poster_path.stat().st_size <= 0:
        raise BuildError("poster render is empty")
    return duration


def _export_glb(glb_path: Path) -> float:
    desired = {
        "filepath": str(glb_path),
        "export_format": "GLB",
        "use_selection": False,
        "export_texcoords": True,
        "export_normals": True,
        "export_tangents": True,
        "export_materials": "EXPORT",
        "export_cameras": True,
        "export_lights": True,
        "export_extras": True,
        "export_yup": True,
        "export_apply": False,
        "export_image_format": "AUTO",
        "export_keep_originals": False,
        "export_draco_mesh_compression_enable": False,
    }
    try:
        properties = set(bpy.ops.export_scene.gltf.get_rna_type().properties.keys())
    except (AttributeError, RuntimeError):
        properties = set(desired)
    arguments = {key: value for key, value in desired.items() if key in properties}
    started = time.monotonic()
    result = bpy.ops.export_scene.gltf(**arguments)
    duration = time.monotonic() - started
    if "FINISHED" not in result or not glb_path.is_file():
        raise BuildError(f"GLB export failed: {glb_path}")
    _inject_glb_asset_extras(
        glb_path,
        {
            "label": "Quality spike · visual staging",
            "canonical_geometry": False,
            "provisional_categories": [
                "cabinetry_detail",
                "hardware",
                "finishes",
                "furniture",
                "decor",
                "undimensioned_offsets",
            ],
        },
    )
    return duration


def _inject_glb_asset_extras(path: Path, extras: dict[str, Any]) -> None:
    data = path.read_bytes()
    if len(data) < 20:
        raise BuildError("exported GLB is too short")
    magic, version, declared_length = struct.unpack_from("<4sII", data, 0)
    if magic != b"glTF" or version != 2 or declared_length != len(data):
        raise BuildError("exported GLB header is invalid")
    chunks: list[tuple[bytes, bytes]] = []
    offset = 12
    while offset < len(data):
        if offset + 8 > len(data):
            raise BuildError("exported GLB has a truncated chunk header")
        length, kind = struct.unpack_from("<I4s", data, offset)
        start = offset + 8
        end = start + length
        if end > len(data):
            raise BuildError("exported GLB has a truncated chunk")
        chunks.append((kind, data[start:end]))
        offset = end
    if not chunks or chunks[0][0] != b"JSON":
        raise BuildError("exported GLB does not start with a JSON chunk")
    gltf = json.loads(chunks[0][1].rstrip(b" \x00").decode("utf-8"))
    gltf.setdefault("asset", {})["extras"] = extras
    json_bytes = json.dumps(gltf, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    json_bytes += b" " * ((4 - len(json_bytes) % 4) % 4)
    rebuilt_chunks = [(b"JSON", json_bytes), *chunks[1:]]
    body = b"".join(struct.pack("<I4s", len(chunk), kind) + chunk for kind, chunk in rebuilt_chunks)
    path.write_bytes(struct.pack("<4sII", b"glTF", 2, 12 + len(body)) + body)


def _runtime_metadata(contract: Any) -> dict[str, Any]:
    polygon = contract.walkable_polygon
    barriers = []
    for rectangle in contract.collision_rectangles:
        barriers.append(
            {
                "name": rectangle.name,
                "min_x": rectangle.min_x,
                "max_x": rectangle.max_x,
                "min_z": -rectangle.max_y,
                "max_z": -rectangle.min_y,
            }
        )
    cameras = []
    for camera in contract.camera_presets:
        px, py, pz = camera.position
        tx, ty, tz = camera.target
        cameras.append(
            {
                "name": camera.name,
                "position": [px, pz, -py],
                "target": [tx, tz, -ty],
            }
        )
    eye_height = next(
        item.meters for item in contract.printed_dimensions if item.name == "eye_height"
    )
    return {
        "coordinate_rule": COORDINATE_RULE,
        "eye_height_meters": eye_height,
        "walkable": {
            "min_x": min(point[0] for point in polygon),
            "max_x": max(point[0] for point in polygon),
            "min_z": -max(point[1] for point in polygon),
            "max_z": -min(point[1] for point in polygon),
        },
        "barriers": barriers,
        "camera_presets": cameras,
    }


def _write_manifest(contract: Any, output_dir: Path) -> dict[str, Any]:
    paths = {
        "glb": output_dir / GLB_NAME,
        "poster": output_dir / POSTER_NAME,
        "environment": output_dir / ENVIRONMENT_NAME,
    }
    for label, path in paths.items():
        if not path.is_file():
            raise BuildError(f"cannot write manifest; {label} output is missing: {path}")
    manifest = contract.to_manifest()
    manifest["artifact"] = {
        "glb": GLB_NAME,
        "poster": POSTER_NAME,
        "environment": ENVIRONMENT_NAME,
        "sha256": {name: _sha256(path) for name, path in paths.items()},
        "bytes": {name: path.stat().st_size for name, path in paths.items()} | {"manifest": 0},
        "total_browser_bytes": 0,
    }
    manifest["runtime"] = _runtime_metadata(contract)
    manifest["scene_nodes"] = SCENE_NODES
    manifest_path = output_dir / MANIFEST_NAME
    artifact_bytes = sum(path.stat().st_size for path in paths.values())
    for _iteration in range(12):
        encoded = (json.dumps(manifest, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
        manifest["artifact"]["bytes"]["manifest"] = len(encoded)
        manifest["artifact"]["total_browser_bytes"] = artifact_bytes + len(encoded)
        final = (json.dumps(manifest, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
        if len(final) == manifest["artifact"]["bytes"]["manifest"]:
            manifest_path.write_bytes(final)
            break
    else:
        raise BuildError("manifest byte count did not converge")
    total = manifest["artifact"]["total_browser_bytes"]
    if total > MAX_BROWSER_BYTES:
        raise BuildError(f"browser payload is {total} bytes, exceeding {MAX_BROWSER_BYTES}")
    return manifest


def _run_validator(repo: Path, output_dir: Path) -> str:
    uv = shutil.which("uv")
    if not uv:
        raise BuildError("uv is required to run the pure-Python artifact validator")
    env = os.environ.copy()
    env["UV_CACHE_DIR"] = "/private/tmp/hearthview-uv-cache"
    env["PYTHONPATH"] = os.pathsep.join((str(STAGE_ROOT), str(repo)))
    command = [
        uv,
        "run",
        "python",
        str(SCRIPT_DIR / "validate_artifact.py"),
        "--glb",
        str(output_dir / GLB_NAME),
        "--manifest",
        str(output_dir / MANIFEST_NAME),
        "--public-dir",
        str(output_dir),
    ]
    result = subprocess.run(command, cwd=repo, env=env, text=True, capture_output=True, check=False)
    combined = "\n".join(part.strip() for part in (result.stdout, result.stderr) if part.strip())
    if result.returncode != 0:
        raise BuildError("artifact validator rejected generated outputs:\n" + (combined or "no validator output"))
    return combined


def _scene_metrics() -> dict[str, int]:
    depsgraph = bpy.context.evaluated_depsgraph_get()
    triangles = 0
    mesh_objects = 0
    for obj in bpy.context.scene.objects:
        if obj.type != "MESH":
            continue
        mesh_objects += 1
        evaluated = obj.evaluated_get(depsgraph)
        mesh = evaluated.to_mesh()
        try:
            mesh.calc_loop_triangles()
            triangles += len(mesh.loop_triangles)
        finally:
            evaluated.to_mesh_clear()
    return {
        "objects": len(bpy.context.scene.objects),
        "mesh_objects": mesh_objects,
        "triangles": triangles,
        "materials": len(bpy.data.materials),
        "images": len(bpy.data.images),
        "lights": sum(1 for obj in bpy.context.scene.objects if obj.type == "LIGHT"),
        "cameras": sum(1 for obj in bpy.context.scene.objects if obj.type == "CAMERA"),
    }


def build(args: argparse.Namespace) -> dict[str, Any]:
    started = time.monotonic()
    repo = args.repo.resolve()
    assets = args.assets.resolve()
    output_dir = args.output_dir.resolve()
    _validate_blender_version()
    contract, contract_module = _load_contract(repo)
    provenance = _validate_authoring_inputs(assets)
    output_dir.mkdir(parents=True, exist_ok=True)
    output_paths = [output_dir / name for name in (GLB_NAME, POSTER_NAME, ENVIRONMENT_NAME, MANIFEST_NAME)]
    for path in output_paths:
        if path.exists():
            path.unlink()

    scene = _configure_scene(assets / "drackenstein_quarry_puresky_1k.hdr")
    materials = _create_materials(assets, contract_module.SPAN_METERS, contract_module.ROOM_DEPTH_METERS)
    architecture = create_root("HV_ARCHITECTURE")
    cabinetry = create_root("HV_CABINETRY")
    furniture = create_root("HV_FURNITURE")
    lighting = create_root("HV_LIGHTING")
    navigation = create_root("HV_NAVIGATION")
    for root in (architecture, cabinetry, furniture, lighting, navigation):
        tag_contract_boundary(
            root,
            label=contract.label,
            canonical_geometry=contract.canonical_geometry,
            categories=contract.provisional_categories,
        )

    _build_architecture(contract, materials, architecture)
    _build_navigation(contract, materials, navigation)
    _build_kitchen(contract, materials, cabinetry)
    _build_living(assets, materials, furniture)
    hero_camera = _build_lighting_and_cameras(assets, materials, lighting, navigation, contract)
    scene.camera = hero_camera
    _convert_curves_to_mesh()
    bpy.context.view_layer.update()

    environment_path = output_dir / ENVIRONMENT_NAME
    shutil.copyfile(assets / "drackenstein_quarry_puresky_1k.hdr", environment_path)
    render_seconds = _render_poster(scene, output_dir / POSTER_NAME)
    export_seconds = _export_glb(output_dir / GLB_NAME)
    manifest = _write_manifest(contract, output_dir)
    validator_output = _run_validator(repo, output_dir)
    metrics = _scene_metrics()
    metrics.update(
        {
            "blender_version": bpy.app.version_string,
            "render_seconds": round(render_seconds, 3),
            "export_seconds": round(export_seconds, 3),
            "build_seconds": round(time.monotonic() - started, 3),
            "artifact_bytes": manifest["artifact"]["bytes"],
            "artifact_sha256": manifest["artifact"]["sha256"],
            "total_browser_bytes": manifest["artifact"]["total_browser_bytes"],
            "validator_output": validator_output,
            "provenance_assets": len(provenance.get("assets", [])),
        }
    )
    return metrics


def main() -> int:
    try:
        args = _parse_args()
        metrics = build(args)
    except (BuildError, FileNotFoundError, OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"HEARTHVIEW BUILD ERROR: {exc}", file=sys.stderr, flush=True)
        return 1
    except Exception as exc:
        print(f"HEARTHVIEW BUILD ERROR: unexpected {type(exc).__name__}: {exc}", file=sys.stderr, flush=True)
        raise
    print("HEARTHVIEW_BUILD_METRICS=" + json.dumps(metrics, ensure_ascii=False, sort_keys=True), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
