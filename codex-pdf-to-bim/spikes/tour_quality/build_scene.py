"""Build the isolated HearthView kitchen-family-room tour quality spike in Blender.

Run with Blender 5.2 LTS in background mode.  This script validates every local
authoring input, consumes Task 1's scene contract, assembles the display scene,
renders the poster, exports a self-contained GLB, writes deterministic metadata,
and invokes the existing pure-Python artifact validator.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
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

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

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


@dataclass(frozen=True)
class _Rect:
    """Minimal stand-in for the contract Rectangle used by shared builders."""

    min_x: float
    min_y: float
    max_x: float
    max_y: float

    @property
    def width(self) -> float:
        return self.max_x - self.min_x

    @property
    def depth(self) -> float:
        return self.max_y - self.min_y


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
    parser.add_argument(
        "--spec",
        type=Path,
        default=None,
        help="A-1 traced scene spec; omit to build the original hand-built spike.",
    )
    arguments = sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else []
    return parser.parse_args(arguments)


def _load_contract(repo: Path, spec_path: Path | None) -> tuple[Any, Any, dict | None]:
    repo = repo.resolve()
    if not (repo / "spikes" / "tour_quality" / "scene_contract.py").is_file():
        raise BuildError(f"Task 1 scene contract is missing under repo: {repo}")
    sys.path.insert(0, str(repo))
    sys.path.insert(0, str(repo / "services"))
    from spikes.tour_quality.scene_contract import (
        build_scene_contract,
        build_scene_contract_from_spec,
        validate_scene_contract,
    )

    module = sys.modules["spikes.tour_quality.scene_contract"]
    if spec_path is not None:
        if not spec_path.is_file():
            raise BuildError(f"traced scene spec is missing: {spec_path}")
        spec = json.loads(spec_path.read_text(encoding="utf-8"))
        if spec.get("schema") != "hearthview-kitchen-scene/v1":
            raise BuildError(f"unexpected scene spec schema: {spec.get('schema')!r}")
        return build_scene_contract_from_spec(spec), module, spec

    contract = build_scene_contract()
    errors = validate_scene_contract(contract)
    if errors:
        raise BuildError("Task 1 contract is invalid:\n" + "\n".join(f"- {error}" for error in errors))
    return contract, module, None


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


def _set_eevee_engine(render: Any) -> None:
    """Pick the render engine for the poster.

    EEVEE is the right default: it is fast and the poster is only a loading
    placeholder. But EEVEE initialises a GPU context, and on a headless machine
    without libEGL that aborts the whole process -- not an exception that can be
    caught, the interpreter is gone. Setting HEARTHVIEW_RENDER_ENGINE=CYCLES
    renders on the CPU instead, which is what lets the scene be built somewhere
    without a display. The exported GLB is identical either way; only the poster
    image differs.
    """
    requested = os.environ.get("HEARTHVIEW_RENDER_ENGINE", "").strip().upper()
    if requested == "CYCLES":
        render.engine = "CYCLES"
        return
    try:
        render.engine = "BLENDER_EEVEE_NEXT"
    except TypeError:
        render.engine = "BLENDER_EEVEE"


def _configure_scene(environment_path: Path) -> bpy.types.Scene:
    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene = bpy.context.scene
    scene.name = "HearthView Tour Quality Spike"
    scene["label"] = "Quality spike · visual staging"
    scene["canonical_geometry"] = False
    scene.unit_settings.system = "METRIC"
    scene.unit_settings.length_unit = "METERS"
    _set_eevee_engine(scene.render)
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
    scene.view_settings.exposure = 0.35
    _set_if_present(scene.render, "use_high_quality_normals", True)
    if hasattr(scene, "eevee"):
        _set_if_present(scene.eevee, "taa_samples", 96)
        _set_if_present(scene.eevee, "taa_render_samples", 96)
        _set_if_present(scene.eevee, "use_gtao", True)
        _set_if_present(scene.eevee, "gtao_distance", 3.0)
        _set_if_present(scene.eevee, "gtao_factor", 1.15)
        _set_if_present(scene.eevee, "use_raytracing", True)
        _set_if_present(scene.eevee, "shadow_pool_size", "1024")

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


def _build_traced_architecture(
    spec: dict, materials: dict[str, bpy.types.Material], root: bpy.types.Object
) -> None:
    """Build walls, slabs and glazing straight from the A-1 scene spec.

    Every box here carries coordinates the extractor read off the drawing, so
    unlike the hand-built path there is no transcribed layout to drift from it.
    """
    ceiling = spec["ceiling"]

    for slab in spec["slabs"]:
        min_x, min_y, max_x, max_y = slab["rect"]
        width, depth = max_x - min_x, max_y - min_y
        centre = ((min_x + max_x) / 2, (min_y + max_y) / 2)
        name = "HV_FLOOR" if slab["name"] == "MAIN" else f"HV_FLOOR_{slab['name']}"
        floor = create_box(
            name, (width, depth, 0.045), (centre[0], centre[1], -0.0225),
            material=materials["floor"], parent=root, bevel=0.0,
        )
        floor["traced_from"] = "A-1"
        create_box(
            f"HV_CEILING_{slab['name']}", (width, depth, 0.055),
            (centre[0], centre[1], ceiling + 0.0275),
            material=materials["plaster"], parent=root, bevel=0.001,
        )

    for box in spec["wall_boxes"]:
        create_box(
            box["name"], tuple(box["size"]), tuple(box["loc"]),
            material=materials["plaster"], parent=root, bevel=0.002,
        )

    for window in spec["windows"]:
        _build_traced_glazing(window, materials, root, sill=window["sill"], head=window["head"])
    for door in spec["doors"]:
        _build_traced_glazing(door, materials, root, sill=0.02, head=door["head"])


def _build_traced_glazing(
    item: dict,
    materials: dict[str, bpy.types.Material],
    root: bpy.types.Object,
    *,
    sill: float,
    head: float,
) -> None:
    """Casing, glass and mullions inside one traced opening."""
    thickness = item["thickness"]
    face = item["line"] + item["outward"] * thickness / 2
    span = item["end"] - item["start"]
    centre = (item["start"] + item["end"]) / 2
    height = head - sill
    if span <= 0.02 or height <= 0.02:
        return
    group = create_root(f"HV_OPENING_{item['name']}", root)

    def place(name: str, along: float, length: float, z_centre: float, z_size: float,
              material: bpy.types.Material, depth: float) -> None:
        if item["axis"] == "h":
            create_box(name, (length, depth, z_size), (along, face, z_centre),
                       material=material, parent=group, bevel=0.004)
        else:
            create_box(name, (depth, length, z_size), (face, along, z_centre),
                       material=material, parent=group, bevel=0.004)

    place(f"HV_GLASS_{item['name']}", centre, span - 0.10, (sill + head) / 2,
          height - 0.10, materials["glass"], thickness * 0.35)
    place(f"HV_CASING_HEAD_{item['name']}", centre, span, head - 0.03,
          0.06, materials["trim"], thickness + 0.02)
    place(f"HV_CASING_SILL_{item['name']}", centre, span, sill + 0.03,
          0.06, materials["trim"], thickness + 0.02)
    for side, along in (("A", item["start"] + 0.03), ("B", item["end"] - 0.03)):
        place(f"HV_CASING_JAMB_{side}_{item['name']}", along, 0.06,
              (sill + head) / 2, height, materials["trim"], thickness + 0.02)
    mullions = max(0, int(span // 0.95) - 1)
    for index in range(1, mullions + 1):
        along = item["start"] + span * index / (mullions + 1)
        place(f"HV_MULLION_{index}_{item['name']}", along, 0.05,
              (sill + head) / 2, height - 0.10, materials["trim"], thickness + 0.01)


def _build_traced_living(
    spec: dict,
    assets: Path,
    materials: dict[str, bpy.types.Material],
    root: bpy.types.Object,
) -> None:
    """Stage the family room inside the traced clear area.

    Positions are proportional to that rectangle rather than absolute, so the
    furniture cannot land inside a wall the way fixed spike coordinates did.
    """
    min_x, min_y, max_x, max_y = spec["living"]["clear_area"]
    width, depth = max_x - min_x, max_y - min_y
    centre_x, centre_y = (min_x + max_x) / 2, (min_y + max_y) / 2
    tv = spec["living"]["tv"]

    create_box(
        "HV_LIVING_RUG", (min(2.72, width * 0.78), min(2.62, depth * 0.72), 0.018),
        (centre_x, centre_y, 0.018), material=materials["rug"], parent=root,
        bevel=0.012, bevel_segments=4,
    )
    create_sofa(
        "HV_LINEN_SOFA", location=(min_x + width * 0.22, centre_y + depth * 0.18, 0.0),
        upholstery=materials["linen"], wood=materials["oak"], parent=root,
    )
    import_gltf_asset(
        assets / "models" / "modern_arm_chair_01" / "modern_arm_chair_01_1k.gltf",
        name="HV_IMPORTED_MODERN_ARM_CHAIR_01", parent=root,
        floor_center=(min_x + width * 0.30, min_y + depth * 0.18, 0.0),
        target_max_extent=1.02, rotation_z=math.radians(28.0),
        material_overrides={"pillow": materials["linen"], "legs": materials["oak"]},
    )
    import_gltf_asset(
        assets / "models" / "modern_coffee_table_01" / "modern_coffee_table_01_1k.gltf",
        name="HV_IMPORTED_MODERN_COFFEE_TABLE_01", parent=root,
        floor_center=(centre_x, centre_y, 0.0),
        target_max_extent=1.20, rotation_z=math.radians(90.0),
        material_overrides={"table": materials["oak"], "wood": materials["oak"]},
    )
    # The 60" TV hangs on the east wall where A-1 marks it. `tv["line"]` is
    # that wall's interior face, so both boxes are offset inward (west of it)
    # rather than sitting at a hardcoded x the way the spike's did.
    face = tv["line"]
    create_box(
        "HV_MEDIA_CONSOLE", (0.42, 1.72, 0.44), (face - 0.21, tv["center_y"], 0.24),
        material=materials["oak"], parent=root, bevel=0.015, bevel_segments=4,
    )
    create_box(
        "HV_TV_SCREEN", (0.045, tv["width"], 0.80),
        (face - 0.055, tv["center_y"], 1.23),
        material=materials["screen"], parent=root, bevel=0.018, bevel_segments=5,
    )
    planter = (max_x - 0.35, min_y + 0.35)
    create_cylinder("HV_PLANTER", radius=0.22, depth=0.42, location=(planter[0], planter[1], 0.21), material=materials["ceramic"], parent=root, vertices=48, bevel=0.012)
    create_cylinder("HV_PLANT_TRUNK", radius=0.035, depth=1.15, location=(planter[0], planter[1], 0.90), material=materials["oak"], parent=root, vertices=24)
    for index, (dx, dy, dz, scale) in enumerate(
        ((-0.18, 0.02, 1.18, (1.0, 0.45, 0.32)), (0.18, -0.05, 1.32, (0.95, 0.42, 0.30)),
         (0.05, 0.18, 1.52, (1.05, 0.48, 0.34)), (-0.10, -0.15, 1.65, (0.82, 0.38, 0.28)))
    ):
        create_sphere(f"HV_PLANT_LEAF_{index + 1}", radius=0.30, location=(planter[0] + dx, planter[1] + dy, dz), scale=scale, material=materials["leaf"], parent=root, segments=32, rings=16)


# South end of the hand-built spike's west cabinet run, in spike coordinates.
_SPIKE_WEST_RUN = 2.75


def _station(name: str, anchor: list[float], rotation_deg: float,
             parent: bpy.types.Object) -> bpy.types.Object:
    """An empty at a wall point, rotated so the canonical local frame lands on it.

    Builders below work in one frame only — wall at local y=0, room toward +y,
    run along +x. Every wall on the plan is reachable from that by a rotation
    about the vertical axis, so nothing needs a mirror and no builder has to
    know which wall it sits on. Children are parented, so Blender applies the
    transform and the local coordinates never touch world space.
    """
    empty = create_root(name, parent)
    empty.location = (anchor[0], anchor[1], 0.0)
    empty.rotation_euler = (0.0, 0.0, math.radians(rotation_deg))
    return empty


def _build_traced_kitchen(
    spec: dict, materials: dict[str, bpy.types.Material], root: bpy.types.Object
) -> None:
    """Cabinetry and appliances at the stations printed on A-1."""
    kitchen = spec["kitchen"]
    depth = kitchen["counter_depth"]
    north = kitchen["north_run"]
    west = kitchen["west_run"]

    def base(name: str, start: float, width: float, run_axis: str, unit_depth: float = None,
             doors: int = 2, parent: bpy.types.Object = None) -> None:
        create_cabinet_unit(
            name, start=start, width=width, depth=unit_depth or depth,
            base_z=0.095, height=0.775, run_axis=run_axis,
            body_material=materials["cabinet_body"], front_material=materials["cabinet"],
            hardware_material=materials["bronze"], parent=parent or root, doors=doors,
        )

    # Every station below is built in the canonical local frame under its own
    # rotated empty, so the same code serves any wall on any floor.
    north_wall = _station("HV_STATION_NORTH", north["station"]["anchor"],
                          north["station"]["rotation_deg"], root)
    west_wall = _station("HV_STATION_WEST", west["station"]["anchor"],
                         west["station"]["rotation_deg"], root)

    run = north["counter"]
    create_box("HV_NORTH_COUNTER", (run["end"] - run["start"], depth, 0.04),
               ((run["start"] + run["end"]) / 2, depth / 2, 0.89),
               material=materials["stone"], parent=north_wall, bevel=0.006, bevel_segments=4)
    for index, tower in enumerate(north["towers"], start=1):
        create_cabinet_unit(
            f"HV_NORTH_TOWER_{index}", start=tower["run_start"],
            width=tower["width"], depth=tower["depth"], base_z=0.095, height=2.26,
            run_axis="X", body_material=materials["cabinet_body"],
            front_material=materials["cabinet"], hardware_material=materials["bronze"],
            parent=north_wall, doors=2,
        )
    dishwasher, sink, trash = north["dishwasher"], north["sink"], north["trash"]
    _create_dishwasher(dishwasher["run_start"], dishwasher["width"], depth, materials, north_wall)
    base("HV_NORTH_SINK_BASE", sink["run_start"], sink["width"], "X", parent=north_wall)
    _create_sink_and_faucet(sink["run_start"] + sink["width"] / 2, depth, materials, north_wall)
    base("HV_NORTH_TRASH", trash["run_start"], trash["width"], "X", doors=1, parent=north_wall)

    counter = west["counter"]
    create_box("HV_WEST_COUNTER", (counter["end"] - counter["start"], depth, 0.04),
               ((counter["start"] + counter["end"]) / 2, depth / 2, 0.89),
               material=materials["stone"], parent=west_wall, bevel=0.006, bevel_segments=4)
    for index, upper in enumerate(west["uppers"], start=1):
        create_cabinet_unit(
            f"HV_WEST_UPPER_{index}", start=upper["run_start"],
            width=upper["width"], depth=0.39, base_z=1.42, height=0.90, run_axis="X",
            body_material=materials["cabinet_body"], front_material=materials["cabinet"],
            hardware_material=materials["bronze"], parent=west_wall, doors=2, toe_kick=False,
        )
        base(f"HV_WEST_BASE_{index}", upper["run_start"], upper["width"], "X", parent=west_wall)
    _create_range_and_hood(west["range"]["run_start"], west["range"]["width"], depth,
                           materials, west_wall)
    _create_refrigerator(west["fridge"]["run_start"], west["fridge"]["width"],
                         west["fridge"]["depth"], materials, west_wall)

    # Island: printed 8'-7" x 4'-3", placed where the trace found it.
    min_x, min_y, max_x, max_y = kitchen["island"]
    island = _Rect(min_x, min_y, max_x, max_y)
    centre = ((min_x + max_x) / 2, (min_y + max_y) / 2)
    structure = create_box(
        "HV_ISLAND_STRUCTURE", (island.width, island.depth, 0.91),
        (centre[0], centre[1], 0.455), material=materials["cabinet_body"],
        parent=root, bevel=0.004, bevel_segments=4,
    )
    structure["footprint_min_x"] = min_x
    structure["footprint_max_x"] = max_x
    structure["footprint_min_y"] = min_y
    structure["footprint_max_y"] = max_y
    _panel_island(island, materials, root)
    create_box(
        "HV_ISLAND_COUNTER_SLAB",
        (island.width + 0.08, island.depth + 0.31, 0.042),
        (centre[0], centre[1] + 0.115, 0.931),
        material=materials["stone"], parent=root, bevel=0.009, bevel_segments=5,
    )
    stool_y = max_y + 0.34
    stool_count = 4
    for index in range(1, stool_count + 1):
        x = min_x + island.width * index / (stool_count + 1)
        create_stool(
            f"HV_ISLAND_STOOL_{index}", location=(x, stool_y, 0.0),
            upholstery=materials["linen"], metal=materials["bronze"], parent=root,
        )


def _build_architecture(contract: Any, materials: dict[str, bpy.types.Material], root: bpy.types.Object) -> None:
    envelope = contract.envelope
    span = envelope.max_x - envelope.min_x
    depth = envelope.max_y - envelope.min_y
    ceiling = envelope.max_z - envelope.min_z
    wall = contract.wall_thickness
    openings = {opening.name: opening.footprint for opening in contract.wall_openings}
    kitchen_window = openings["kitchen_window_group"]
    deck_door = openings["deck_door_group"]
    east_window = openings["family_east_window"]
    mudroom = openings["mudroom_opening"]
    south_living = openings["south_living_opening"]
    regions = {region.name: region for region in contract.orientation.regions}

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

    # West wall is the appliance wall. The east wall follows the canonical
    # window -> solid TV interval -> mudroom opening sequence from A-1.
    _wall_box("HV_WEST_WALL", (wall, depth, ceiling), (-wall / 2, depth / 2, ceiling / 2), materials, root)
    _wall_box("HV_EAST_WALL_NORTH_PIER", (wall, east_window.min_y, ceiling), (span + wall / 2, east_window.min_y / 2, ceiling / 2), materials, root)
    _wall_box(
        "HV_EAST_WINDOW_SILL_WALL",
        (wall, east_window.depth, window_sill),
        (span + wall / 2, (east_window.min_y + east_window.max_y) / 2, window_sill / 2),
        materials,
        root,
    )
    _wall_box(
        "HV_EAST_WINDOW_HEADER",
        (wall, east_window.depth, ceiling - window_head),
        (span + wall / 2, (east_window.min_y + east_window.max_y) / 2, (window_head + ceiling) / 2),
        materials,
        root,
    )
    _wall_box(
        "HV_EAST_TV_WALL",
        (wall, mudroom.min_y - east_window.max_y, ceiling),
        (span + wall / 2, (east_window.max_y + mudroom.min_y) / 2, ceiling / 2),
        materials,
        root,
    )
    _wall_box("HV_EAST_MUDROOM_HEADER", (wall, mudroom.depth, ceiling - 2.18), (span + wall / 2, (mudroom.min_y + mudroom.max_y) / 2, (2.18 + ceiling) / 2), materials, root)
    _build_east_window_group(
        "HV_OPENING_family_east_window",
        min_y=east_window.min_y,
        max_y=east_window.max_y,
        sill=window_sill,
        head=window_head,
        x=span + 0.002,
        materials=materials,
        parent=root,
        mullions=1,
    )

    # The south boundary is the printed 37-inch return, 60-inch opening,
    # 37-inch return chain, positioned globally from the canonical model.
    existing_living = regions["existing_living_context"]
    west_return_width = south_living.min_x - existing_living.min_x
    east_return_width = existing_living.max_x - south_living.max_x
    _wall_box(
        "HV_SOUTH_RETURN_WEST",
        (west_return_width, wall, ceiling),
        ((existing_living.min_x + south_living.min_x) / 2, depth + wall / 2, ceiling / 2),
        materials,
        root,
    )
    _wall_box(
        "HV_SOUTH_RETURN_EAST",
        (east_return_width, wall, ceiling),
        ((south_living.max_x + existing_living.max_x) / 2, depth + wall / 2, ceiling / 2),
        materials,
        root,
    )
    create_box(
        "HV_SOUTH_LIVING_THRESHOLD",
        (south_living.width, 0.12, 0.016),
        ((south_living.min_x + south_living.max_x) / 2, depth, 0.008),
        material=materials["stone"],
        parent=root,
        bevel=0.002,
    )

    # Focused adjacent context makes both canonical openings legible without
    # pretending to be a whole-floor reconstruction.
    mudroom_context = regions["mudroom_context"]
    create_box(
        "HV_MUDROOM_CONTEXT_FLOOR",
        (mudroom_context.width, mudroom_context.depth, 0.045),
        (
            (mudroom_context.min_x + mudroom_context.max_x) / 2,
            (mudroom_context.min_y + mudroom_context.max_y) / 2,
            -0.0225,
        ),
        material=materials["floor"],
        parent=root,
        bevel=0.0,
    )
    create_box(
        "HV_EXISTING_LIVING_CONTEXT_FLOOR",
        (existing_living.width, existing_living.depth, 0.045),
        (
            (existing_living.min_x + existing_living.max_x) / 2,
            (existing_living.min_y + existing_living.max_y) / 2,
            -0.0225,
        ),
        material=materials["floor"],
        parent=root,
        bevel=0.0,
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


def _build_east_window_group(
    name: str,
    *,
    min_y: float,
    max_y: float,
    sill: float,
    head: float,
    x: float,
    materials: dict[str, bpy.types.Material],
    parent: bpy.types.Object,
    mullions: int,
) -> None:
    root = create_root(name, parent)
    width = max_y - min_y
    height = head - sill
    create_box(
        f"{name}_GLASS",
        (0.014, width - 0.08, height - 0.08),
        (x, (min_y + max_y) / 2, (sill + head) / 2),
        material=materials["glass"],
        parent=root,
        bevel=0.001,
    )
    for suffix, y in (("N", min_y), ("S", max_y)):
        create_box(
            f"{name}_JAMB_{suffix}",
            (0.075, 0.065, height + 0.12),
            (x - 0.025, y, (sill + head) / 2),
            material=materials["trim"],
            parent=root,
            bevel=0.002,
        )
    for suffix, z in (("SILL", sill), ("HEAD", head)):
        create_box(
            f"{name}_{suffix}",
            (0.10, width + 0.13, 0.065),
            (x - 0.028, (min_y + max_y) / 2, z),
            material=materials["trim"],
            parent=root,
            bevel=0.002,
        )
    for index in range(1, mullions + 1):
        y = min_y + width * index / (mullions + 1)
        create_box(
            f"{name}_MULLION_{index}",
            (0.045, 0.035, height - 0.04),
            (x - 0.035, y, (sill + head) / 2),
            material=materials["trim"],
            parent=root,
            bevel=0.0015,
        )


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
    # The appliance builders work in one canonical run frame (wall at local
    # y=0, room toward +y, run along +x), so this west run gets a station empty
    # rotated onto the wall. Run coordinates are measured from the south end.
    west_station = _station("HV_SPIKE_STATION_WEST", [0.0, _SPIKE_WEST_RUN], -90.0, root)
    _create_range_and_hood(_SPIKE_WEST_RUN - 0.72 - 0.9144, 0.9144, counter_depth, materials, west_station)
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
    _create_refrigerator(_SPIKE_WEST_RUN - 2.00 - 0.75, 0.75, counter_depth, materials, west_station)

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


def _cut_opening(target: bpy.types.Object, size: tuple[float, float, float],
                 location: tuple[float, float, float]) -> None:
    """Boolean a rectangular hole through an object, then drop the cutter."""
    cutter = create_box("HV_CUTTER_TMP", size, location)
    modifier = target.modifiers.new("HV_OPENING", type="BOOLEAN")
    modifier.operation = "DIFFERENCE"
    modifier.object = cutter
    modifier.solver = "EXACT"   # Blender 5 dropped FAST
    bpy.context.view_layer.objects.active = target
    bpy.ops.object.modifier_apply(modifier=modifier.name)
    bpy.data.objects.remove(cutter, do_unlink=True)


def _create_sink_and_faucet(center_x: float, depth: float, materials: dict[str, bpy.types.Material], root: bpy.types.Object) -> None:
    rim = create_box("HV_SINK_RIM", (0.66, 0.43, 0.035), (center_x, 0.37, 0.94), material=materials["steel"], parent=root, bevel=0.02, bevel_segments=5)
    # Cut the bowl opening out of the rim, so it reads as a sink rather than a
    # steel plate lying on the counter. The carve leaves the outer dimensions
    # alone, which matters: HV_SINK_RIM is one of the landmarks measure_glb
    # checks against the trace, and it is measured from its bounding box.
    _cut_opening(rim, (0.57, 0.34, 0.30), (center_x, 0.37, 0.94))
    # The bowl is a recess, not a block. This sat at z 0.928..0.988 -- above the
    # 0.94 rim -- so the sink read as a dark slab standing on the counter.
    basin = create_box(
        "HV_SINK_BASIN", (0.59, 0.36, 0.185), (center_x, 0.37, 0.8525),
        material=materials["steel"], parent=root, bevel=0.012, bevel_segments=4,
    )
    # Hollow it from above, leaving a 12 mm shell. A solid block here shows only
    # its top face through the rim opening, which renders as a dark panel rather
    # than a bowl you can see the inside of.
    _cut_opening(basin, (0.566, 0.336, 0.20), (center_x, 0.37, 0.876))
    # A gooseneck rises directly behind the basin and arcs forward over it, all
    # in one vertical plane. The previous run started 0.22 m to the right of the
    # sink and ended at its centre, so the tube swept sideways across the bowl;
    # with AUTO bezier handles that sideways travel became a loop, and it read
    # as a cartoon rather than a tap.
    spout_x = center_x
    behind_basin = 0.15          # metres from the wall: clear of the rim, on the deck
    over_basin = 0.36            # the bowl's centre line, where water should land
    create_curve_tube(
        "HV_GOSENECK_FAUCET",
        [
            (spout_x, behind_basin, 0.95),          # base on the counter
            (spout_x, behind_basin, 1.20),          # straight rise
            (spout_x, behind_basin + 0.06, 1.29),   # into the bend
            (spout_x, over_basin - 0.04, 1.30),     # apex, flattened
            (spout_x, over_basin, 1.17),            # spout, pointing down
        ],
        radius=0.011,            # 22 mm, a plausible tube; 28 mm read as plumbing
        material=materials["steel"],
        parent=root,
    )
    # Lever beside the base rather than floating 0.29 m away over the counter.
    create_cylinder(
        "HV_FAUCET_HANDLE",
        radius=0.009,
        depth=0.11,
        location=(spout_x + 0.075, behind_basin + 0.01, 1.03),
        rotation=(math.radians(62.0), 0.0, 0.0),
        material=materials["steel"],
        parent=root,
        vertices=24,
    )
    create_cylinder(
        "HV_FAUCET_BASE",
        radius=0.024,
        depth=0.02,
        location=(spout_x, behind_basin, 0.95),
        material=materials["steel"],
        parent=root,
        vertices=32,
    )


def _create_range_and_hood(start: float, width: float, depth: float, materials: dict[str, bpy.types.Material], root: bpy.types.Object) -> None:
    """Range in the canonical run frame: wall at local y=0, room toward +y.

    Every cabinetry builder in this module works in that one frame, so a run on
    any wall is a rotated station empty (see ``_station``) and never a mirror.
    """
    center_x = start + width / 2
    create_box("HV_RANGE_BODY", (width - 0.02, depth - 0.02, 0.89), (center_x, (depth - 0.02) / 2, 0.445), material=materials["black"], parent=root, bevel=0.006)
    create_box("HV_RANGE_OVEN_GLASS", (width * 0.67, 0.025, 0.43), (center_x, depth + 0.006, 0.42), material=materials["screen"], parent=root, bevel=0.018)
    create_cylinder("HV_RANGE_HANDLE", radius=0.012, depth=width * 0.72, location=(center_x, depth + 0.032, 0.68), rotation=(0.0, math.pi / 2, 0.0), material=materials["steel"], parent=root, vertices=24)
    for row, y in enumerate((0.19, 0.46)):
        for col, x_offset in enumerate((-0.25, 0.25)):
            create_cylinder(f"HV_RANGE_BURNER_{row}_{col}", radius=0.105, depth=0.018, location=(center_x + x_offset, y, 0.908), material=materials["black"], parent=root, vertices=40, bevel=0.002)
    for index, offset in enumerate((-0.28, -0.14, 0.0, 0.14, 0.28)):
        create_cylinder(f"HV_RANGE_KNOB_{index + 1}", radius=0.027, depth=0.025, location=(center_x + offset, depth + 0.032, 0.79), rotation=(math.pi / 2, 0.0, 0.0), material=materials["bronze"], parent=root, vertices=28)
    create_box("HV_RANGE_HOOD", (width + 0.10, 0.58, 0.19), (center_x, 0.30, 1.73), material=materials["cabinet"], parent=root, bevel=0.025, bevel_segments=5)
    create_box("HV_RANGE_HOOD_CHIMNEY", (0.44, 0.35, 0.66), (center_x, 0.18, 2.12), material=materials["cabinet"], parent=root, bevel=0.008)


def _create_refrigerator(start: float, width: float, depth: float, materials: dict[str, bpy.types.Material], root: bpy.types.Object) -> None:
    """Refrigerator in the canonical run frame (wall at local y=0, room +y).

    Door leaves are named A/B along the run rather than by compass point: the
    builder is not told which wall its station sits on.
    """
    center_x = start + width / 2
    create_box("HV_REFRIGERATOR_BODY", (width - 0.015, depth - 0.015, 2.28), (center_x, (depth - 0.015) / 2, 1.14), material=materials["steel"], parent=root, bevel=0.015, bevel_segments=4)
    create_box("HV_REFRIGERATOR_DOOR_A", (width / 2 - 0.012, 0.026, 1.58), (start + width * 0.25, depth + 0.007, 1.43), material=materials["cabinet"], parent=root, bevel=0.006)
    create_box("HV_REFRIGERATOR_DOOR_B", (width / 2 - 0.012, 0.026, 1.58), (start + width * 0.75, depth + 0.007, 1.43), material=materials["cabinet"], parent=root, bevel=0.006)
    create_box("HV_REFRIGERATOR_FREEZER", (width - 0.025, 0.026, 0.50), (center_x, depth + 0.007, 0.36), material=materials["cabinet"], parent=root, bevel=0.006)
    for index, x in enumerate((start + width * 0.39, start + width * 0.61)):
        create_cylinder(f"HV_REFRIGERATOR_HANDLE_{index + 1}", radius=0.011, depth=0.74, location=(x, depth + 0.045, 1.46), material=materials["bronze"], parent=root, vertices=24)


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


def _build_living(
    assets: Path,
    materials: dict[str, bpy.types.Material],
    root: bpy.types.Object,
    spec: dict | None = None,
) -> None:
    if spec is not None:
        _build_traced_living(spec, assets, materials, root)
        return
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
    spec: dict | None = None,
) -> bpy.types.Object:
    # Pendants hang over the island; daylight enters at the traced north
    # openings. With no spec these keep the original hand-placed positions.
    if spec is None:
        pendant_xs = (2.05, 3.04, 4.03)
        pendant_y = 2.375
        north_light = ((4.62, -0.42, 1.52), (4.30, 2.00, 0.88))
        deck_light = ((7.42, -0.48, 1.38), (6.80, 2.70, 0.90))
        bounce = ((5.30, 2.75, 2.42), (5.30, 2.75, 0.0))
        hero_position = (0.72, 4.38, 1.68)
        hero_target = (5.00, 1.92, 1.02)
    else:
        min_x, min_y, max_x, max_y = spec["kitchen"]["island"]
        island_cy = (min_y + max_y) / 2
        pendant_xs = tuple(min_x + (max_x - min_x) * f for f in (0.22, 0.5, 0.78))
        pendant_y = island_cy
        windows = [w for w in spec["windows"] if w["name"].startswith("HV_NORTH")]
        doors = [d for d in spec["doors"] if d["name"].startswith("HV_NORTH")]
        widest = max(windows, key=lambda w: w["end"] - w["start"]) if windows else None
        span = spec["envelope"]["span"]
        depth_east = spec["envelope"]["depth_east"]
        wx = ((widest["start"] + widest["end"]) / 2) if widest else span * 0.3
        north_light = ((wx, -0.42, 1.52), (wx, 2.0, 0.88))
        dx = ((doors[0]["start"] + doors[0]["end"]) / 2) if doors else span * 0.65
        deck_light = ((dx, -0.48, 1.38), (dx, 2.7, 0.9))
        bounce = ((span / 2, depth_east / 2, 2.42), (span / 2, depth_east / 2, 0.0))
        kitchen_camera = next(c for c in spec["cameras"] if c["name"] == "KITCHEN")
        hero_position = tuple(kitchen_camera["location"])
        hero_target = tuple(kitchen_camera["target"])

    for index, x in enumerate(pendant_xs, start=1):
        import_gltf_asset(
            assets / "models" / "modern_ceiling_lamp_01" / "modern_ceiling_lamp_01_1k.gltf",
            name=f"HV_IMPORTED_MODERN_CEILING_LAMP_01_{index}",
            parent=lighting_root,
            floor_center=(x, pendant_y, 1.48),
            target_max_extent=0.90,
            rotation_z=math.radians(12.0 * (index - 2)),
        )
        create_sphere(f"HV_PENDANT_BULB_{index}", radius=0.055, location=(x, pendant_y, 1.56), scale=(1.0, 1.0, 1.18), material=materials["bulb"], parent=lighting_root, segments=32, rings=16)
        add_point_light(f"HV_PENDANT_LIGHT_{index}", location=(x, pendant_y, 1.55), energy=88.0, color=(1.0, 0.46, 0.20), parent=lighting_root, radius=0.20)

    add_area_light("HV_NORTH_WINDOW_DAYLIGHT", location=north_light[0], energy=720.0, size=1.30, color=(0.78, 0.88, 1.0), target=north_light[1], parent=lighting_root)
    add_area_light("HV_DECK_DOOR_DAYLIGHT", location=deck_light[0], energy=960.0, size=2.35, color=(0.82, 0.90, 1.0), target=deck_light[1], parent=lighting_root)
    add_area_light("HV_CEILING_BOUNCE", location=bounce[0], energy=430.0, size=4.20, color=(1.0, 0.70, 0.48), target=bounce[1], parent=lighting_root)

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
        position=hero_position,
        target=hero_target,
        lens_mm=34.0,
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


def _export_glb(glb_path: Path, contract: Any) -> float:
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
            "label": contract.label,
            "canonical_geometry": contract.canonical_geometry,
            "provisional_categories": list(contract.provisional_categories),
            "canonical_model_hash": contract.canonical_model_hash,
            "canonical_geometry_hash": contract.canonical_geometry_hash,
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
        ux, uy, uz = camera.up
        cameras.append(
            {
                "name": camera.name,
                "position": [px, pz, -py],
                "target": [tx, tz, -ty],
                "up": [ux, uz, -uy],
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


def _run_validator(repo: Path, output_dir: Path, spec_path: Path | None = None) -> str:
    uv = shutil.which("uv")
    if not uv:
        raise BuildError("uv is required to run the pure-Python artifact validator")
    env = os.environ.copy()
    env["UV_CACHE_DIR"] = "/private/tmp/hearthview-uv-cache"
    python_paths = [str(repo), str(repo / "services")]
    if env.get("PYTHONPATH"):
        python_paths.append(env["PYTHONPATH"])
    env["PYTHONPATH"] = os.pathsep.join(python_paths)
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
    if spec_path is not None:
        command += ["--spec", str(spec_path)]
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
    contract, contract_module, spec = _load_contract(repo, args.spec)
    provenance = _validate_authoring_inputs(assets)
    output_dir.mkdir(parents=True, exist_ok=True)
    output_paths = [output_dir / name for name in (GLB_NAME, POSTER_NAME, ENVIRONMENT_NAME, MANIFEST_NAME)]
    for path in output_paths:
        if path.exists():
            path.unlink()

    scene = _configure_scene(assets / "drackenstein_quarry_puresky_1k.hdr")
    if spec is None:
        span_meters = contract_module.SPAN_METERS
        depth_meters = contract_module.ROOM_DEPTH_METERS
    else:
        span_meters = spec["envelope"]["span"]
        depth_meters = spec["envelope"]["arm_north"]
    materials = _create_materials(assets, span_meters, depth_meters)
    canonical_root = create_root("HV_CANONICAL")
    staging_root = create_root("HV_STAGING")
    canonical_root["canonical_model_hash"] = contract.canonical_model_hash
    canonical_root["canonical_geometry_hash"] = contract.canonical_geometry_hash
    staging_root["provisional"] = True
    architecture = create_root("HV_ARCHITECTURE", canonical_root)
    navigation = create_root("HV_NAVIGATION", canonical_root)
    cabinetry = create_root("HV_CABINETRY", staging_root)
    furniture = create_root("HV_FURNITURE", staging_root)
    lighting = create_root("HV_LIGHTING", staging_root)
    for root in (canonical_root, architecture, navigation):
        tag_contract_boundary(
            root,
            label=contract.label,
            canonical_geometry=True,
            categories=(),
        )
        root["canonical_model_hash"] = contract.canonical_model_hash
        root["canonical_geometry_hash"] = contract.canonical_geometry_hash
    for root in (staging_root, cabinetry, furniture, lighting):
        tag_contract_boundary(
            root,
            label=contract.label,
            canonical_geometry=False,
            categories=contract.provisional_categories,
        )

    if spec is None:
        _build_architecture(contract, materials, architecture)
        _build_kitchen(contract, materials, cabinetry)
    else:
        _build_traced_architecture(spec, materials, architecture)
        _build_traced_kitchen(spec, materials, cabinetry)
    _build_navigation(contract, materials, navigation)
    _build_living(assets, materials, furniture, spec)
    hero_camera = _build_lighting_and_cameras(
        assets, materials, lighting, navigation, contract, spec
    )
    scene.camera = hero_camera
    _convert_curves_to_mesh()
    bpy.context.view_layer.update()

    environment_path = output_dir / ENVIRONMENT_NAME
    shutil.copyfile(assets / "drackenstein_quarry_puresky_1k.hdr", environment_path)
    render_seconds = _render_poster(scene, output_dir / POSTER_NAME)
    export_seconds = _export_glb(output_dir / GLB_NAME, contract)
    manifest = _write_manifest(contract, output_dir)
    validator_output = _run_validator(repo, output_dir, args.spec)
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
