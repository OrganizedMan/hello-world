"""Blender-side renderer for a locked HearthView GLB.

Run only through ``hearthview.rendering.build_blender_command``.  This module is
intentionally dependency-free outside Blender's bundled Python.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

import bpy
from mathutils import Vector

sys.path.insert(0, str(Path(__file__).resolve().parent))
from scene_plan import Bounds, build_warm_scene_plan  # noqa: E402


def arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--geometry", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--camera", choices=["PLAN", "AXONOMETRIC", "KITCHEN", "LIVING_ROOM"], required=True)
    parser.add_argument(
        "--engine",
        choices=["DRAFT", "FINAL", "BLENDER_EEVEE_NEXT", "CYCLES"],
        required=True,
    )
    parser.add_argument("--width", type=int, required=True)
    parser.add_argument("--height", type=int, required=True)
    parser.add_argument("--style", choices=["WARM_BLANK_SLATE"], required=True)
    return parser.parse_args(sys.argv[sys.argv.index("--") + 1 :])


def material(
    name: str,
    color: tuple[float, float, float, float],
    roughness: float = 0.72,
    metallic: float = 0.0,
):
    value = bpy.data.materials.new(name)
    value.diffuse_color = color
    value.use_nodes = True
    principled = value.node_tree.nodes.get("Principled BSDF")
    principled.inputs["Base Color"].default_value = color
    principled.inputs["Roughness"].default_value = roughness
    principled.inputs["Metallic"].default_value = metallic
    return value


def textured_material(
    name,
    dark_color,
    light_color,
    roughness,
    texture_scale,
    bump_strength,
    mapping_scale,
):
    value = material(name, light_color, roughness)
    nodes = value.node_tree.nodes
    links = value.node_tree.links
    principled = nodes.get("Principled BSDF")
    coordinates = nodes.new("ShaderNodeTexCoord")
    mapping = nodes.new("ShaderNodeMapping")
    noise = nodes.new("ShaderNodeTexNoise")
    ramp = nodes.new("ShaderNodeValToRGB")
    bump = nodes.new("ShaderNodeBump")
    mapping.inputs["Scale"].default_value = mapping_scale
    noise.inputs["Scale"].default_value = texture_scale
    noise.inputs["Detail"].default_value = 4.0
    noise.inputs["Roughness"].default_value = 0.68
    ramp.color_ramp.elements[0].position = 0.28
    ramp.color_ramp.elements[0].color = dark_color
    ramp.color_ramp.elements[1].position = 0.74
    ramp.color_ramp.elements[1].color = light_color
    bump.inputs["Strength"].default_value = bump_strength
    bump.inputs["Distance"].default_value = 0.055
    links.new(coordinates.outputs["Generated"], mapping.inputs["Vector"])
    links.new(mapping.outputs["Vector"], noise.inputs["Vector"])
    links.new(noise.outputs["Fac"], ramp.inputs["Fac"])
    links.new(ramp.outputs["Color"], principled.inputs["Base Color"])
    links.new(noise.outputs["Fac"], bump.inputs["Height"])
    links.new(bump.outputs["Normal"], principled.inputs["Normal"])
    return value


def world_bounds(objects):
    points = [obj.matrix_world @ Vector(corner) for obj in objects for corner in obj.bound_box]
    return (
        Vector((min(point.x for point in points), min(point.y for point in points), min(point.z for point in points))),
        Vector((max(point.x for point in points), max(point.y for point in points), max(point.z for point in points))),
    )


def object_bounds(obj) -> Bounds:
    lower, upper = world_bounds((obj,))
    return Bounds(lower.x, lower.y, lower.z, upper.x, upper.y, upper.z)


def canonical_signature(objects):
    return [
        {
            "name": obj.name,
            "matrix": [round(value, 8) for row in obj.matrix_world for value in row],
            "bounds": [[round(value, 8) for value in corner] for corner in obj.bound_box],
        }
        for obj in sorted(objects, key=lambda item: item.name)
    ]


def link_only(obj, collection):
    for previous in list(obj.users_collection):
        previous.objects.unlink(obj)
    collection.objects.link(obj)


def add_box(collection, name, location, scale, surface, bevel=0.08):
    bpy.ops.mesh.primitive_cube_add(location=location)
    obj = bpy.context.object
    obj.name = name
    obj.scale = scale
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    link_only(obj, collection)
    obj.data.materials.append(surface)
    modifier = obj.modifiers.new("Soft edges", "BEVEL")
    modifier.width = bevel
    modifier.segments = 3
    return obj


def add_cylinder(collection, name, location, scale, surface, bevel=0.03):
    bpy.ops.mesh.primitive_cylinder_add(vertices=64, radius=1.0, depth=2.0, location=location)
    obj = bpy.context.object
    obj.name = name
    obj.scale = scale
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    link_only(obj, collection)
    obj.data.materials.append(surface)
    modifier = obj.modifiers.new("Soft edges", "BEVEL")
    modifier.width = bevel
    modifier.segments = 3
    for polygon in obj.data.polygons:
        polygon.use_smooth = True
    return obj


def add_sphere(collection, name, location, scale, surface):
    bpy.ops.mesh.primitive_uv_sphere_add(segments=48, ring_count=24, location=location)
    obj = bpy.context.object
    obj.name = name
    obj.scale = scale
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    link_only(obj, collection)
    obj.data.materials.append(surface)
    for polygon in obj.data.polygons:
        polygon.use_smooth = True
    return obj


def add_area_light(collection, name, location, target, energy, size, color):
    bpy.ops.object.light_add(type="AREA", location=location)
    value = bpy.context.object
    value.name = name
    value.data.energy = energy
    value.data.shape = "DISK"
    value.data.size = size
    value.data.color = color
    point_camera(value, location, target)
    link_only(value, collection)
    return value


def point_camera(camera, location, target):
    camera.location = location
    camera.rotation_euler = (Vector(target) - camera.location).to_track_quat("-Z", "Y").to_euler()


def main() -> None:
    args = arguments()
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.import_scene.gltf(filepath=str(args.geometry))
    canonical_objects = tuple(obj for obj in bpy.context.scene.objects if obj.type == "MESH")
    if not canonical_objects:
        raise RuntimeError("The approved GLB contains no mesh objects.")
    canonical = bpy.data.collections.new("HV_CANONICAL")
    bpy.context.scene.collection.children.link(canonical)
    for obj in canonical_objects:
        link_only(obj, canonical)
    signature_before = canonical_signature(canonical_objects)
    lower, upper = world_bounds(canonical_objects)
    center = (lower + upper) / 2
    span = upper - lower

    plaster = textured_material(
        "Warm ivory plaster",
        (0.66, 0.59, 0.50, 1.0),
        (0.80, 0.73, 0.64, 1.0),
        0.82,
        7.0,
        0.0025,
        (2.0, 2.0, 2.0),
    )
    oak = textured_material(
        "Natural white oak",
        (0.16, 0.075, 0.025, 1.0),
        (0.34, 0.18, 0.060, 1.0),
        0.48,
        5.0,
        0.006,
        (3.0, 22.0, 2.0),
    )
    floor_oak = textured_material(
        "Matte white oak floor",
        (0.11, 0.050, 0.018, 1.0),
        (0.27, 0.14, 0.045, 1.0),
        0.54,
        4.5,
        0.004,
        (2.0, 28.0, 2.0),
    )
    cabinetry = material("Warm putty cabinetry", (0.38, 0.31, 0.23, 1.0), 0.58)
    stone = textured_material(
        "Honed warm stone",
        (0.57, 0.52, 0.45, 1.0),
        (0.76, 0.70, 0.62, 1.0),
        0.38,
        4.5,
        0.002,
        (2.0, 2.0, 3.0),
    )
    charcoal = material("Soft charcoal", (0.012, 0.015, 0.014, 1.0), 0.28, 0.08)
    linen = textured_material(
        "Oatmeal linen",
        (0.39, 0.32, 0.24, 1.0),
        (0.55, 0.47, 0.37, 1.0),
        0.94,
        34.0,
        0.003,
        (2.0, 2.0, 2.0),
    )
    linen_light = material("Light oatmeal linen", (0.69, 0.59, 0.44, 1.0), 0.92)
    wool = textured_material(
        "Warm wool",
        (0.30, 0.23, 0.17, 1.0),
        (0.45, 0.36, 0.27, 1.0),
        1.0,
        42.0,
        0.004,
        (1.0, 1.0, 1.0),
    )
    sage = material("Muted sage", (0.085, 0.19, 0.08, 1.0), 0.86)
    ceramic = material("Warm ceramic", (0.36, 0.27, 0.18, 1.0), 0.62)
    surfaces = {
        "plaster": plaster,
        "oak": oak,
        "floor_oak": floor_oak,
        "cabinetry": cabinetry,
        "stone": stone,
        "charcoal": charcoal,
        "linen": linen,
        "linen_light": linen_light,
        "wool": wool,
        "sage": sage,
        "ceramic": ceramic,
    }
    for obj in canonical_objects:
        obj.data.materials.clear()
        name = obj.name.upper()
        obj.data.materials.append(
            charcoal
            if "TV" in name
            else floor_oak
            if "FLOOR" in name
            else cabinetry
            if "ISLAND" in name
            else plaster
        )
        obj.hide_select = True

    floor_object = next(obj for obj in canonical_objects if "FLOOR" in obj.name.upper())
    island_object = next(obj for obj in canonical_objects if "ISLAND" in obj.name.upper())
    tv_object = next(obj for obj in canonical_objects if "TV" in obj.name.upper())
    floor_bounds = object_bounds(floor_object)
    island_bounds = object_bounds(island_object)
    tv_bounds = object_bounds(tv_object)
    appearance = build_warm_scene_plan(floor=floor_bounds, island=island_bounds, tv=tv_bounds)

    styling = bpy.data.collections.new("HV_STYLING")
    bpy.context.scene.collection.children.link(styling)
    styled_objects = []
    for item in appearance.furnishings:
        surface = surfaces[item.material]
        if item.primitive == "BOX":
            obj = add_box(styling, item.name, item.location, item.scale, surface, item.bevel)
        elif item.primitive == "CYLINDER":
            obj = add_cylinder(styling, item.name, item.location, item.scale, surface, item.bevel)
        else:
            obj = add_sphere(styling, item.name, item.location, item.scale, surface)
        styled_objects.append(obj)

    lighting = bpy.data.collections.new("HV_LIGHTING")
    bpy.context.scene.collection.children.link(lighting)
    world = bpy.data.worlds.new("Warm daylight")
    bpy.context.scene.world = world
    world.use_nodes = True
    world.node_tree.nodes["Background"].inputs["Color"].default_value = (0.90, 0.78, 0.64, 1.0)
    world.node_tree.nodes["Background"].inputs["Strength"].default_value = 0.36
    add_area_light(
        lighting,
        "Large warm window light",
        (lower.x - span.x * 0.35, lower.y - span.y * 0.45, upper.z + span.z * 0.80),
        (center.x, center.y, floor_bounds.max_z + 0.8),
        980,
        max(span.x, span.y) * 0.72,
        (1.0, 0.86, 0.72),
    )
    add_area_light(
        lighting,
        "Soft ceiling bounce",
        (center.x, center.y, upper.z + 1.15),
        (center.x, center.y, floor_bounds.max_z),
        540,
        max(span.x, span.y) * 0.62,
        (1.0, 0.91, 0.80),
    )
    bpy.ops.object.light_add(type="SUN", location=(center.x, center.y, upper.z + 2))
    fill = bpy.context.object
    fill.name = "Soft daylight fill"
    fill.data.energy = 0.80
    fill.data.angle = math.radians(12)
    fill.data.color = (0.82, 0.90, 1.0)
    fill.rotation_euler = (math.radians(28), 0, math.radians(-32))
    link_only(fill, lighting)
    for pendant in (item for item in appearance.furnishings if item.name.startswith("Island pendant")):
        bpy.ops.object.light_add(
            type="POINT",
            location=(pendant.location[0], pendant.location[1], pendant.location[2] - 0.20),
        )
        glow = bpy.context.object
        glow.name = f"{pendant.name} warm glow"
        glow.data.energy = 45
        glow.data.color = (1.0, 0.58, 0.30)
        glow.data.shadow_soft_size = 0.32
        link_only(glow, lighting)
        cord_center_z = (pendant.location[2] + upper.z) / 2
        cord_half_height = max(0.03, (upper.z - pendant.location[2]) / 2)
        add_cylinder(
            styling,
            f"{pendant.name} cord",
            (pendant.location[0], pendant.location[1], cord_center_z),
            (0.009, 0.009, cord_half_height),
            charcoal,
            0.005,
        )

    camera_data = bpy.data.cameras.new("HearthView camera")
    camera = bpy.data.objects.new("HearthView camera", camera_data)
    lighting.objects.link(camera)
    bpy.context.scene.camera = camera
    camera_spec = next(value for value in appearance.cameras if value.name == args.camera)
    point_camera(camera, camera_spec.location, camera_spec.target)
    camera.data.lens = camera_spec.lens
    camera.data.sensor_width = 36
    camera.data.clip_start = 0.05
    camera.data.dof.use_dof = True
    camera.data.dof.focus_distance = (Vector(camera_spec.target) - camera.location).length
    camera.data.dof.aperture_fstop = 5.6
    if camera_spec.orthographic_scale is not None:
        camera.data.type = "ORTHO"
        camera.data.ortho_scale = camera_spec.orthographic_scale

    scene = bpy.context.scene
    if args.engine in {"FINAL", "CYCLES"}:
        scene.render.engine = "CYCLES"
    else:
        try:
            scene.render.engine = "BLENDER_EEVEE_NEXT"
        except TypeError:
            scene.render.engine = "BLENDER_EEVEE"
    scene.render.resolution_x = args.width
    scene.render.resolution_y = args.height
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = "PNG"
    scene.render.image_settings.color_mode = "RGB"
    scene.render.filepath = str(args.output)
    scene.render.film_transparent = False
    scene.view_settings.look = "AgX - Medium High Contrast"
    scene.view_settings.exposure = 0.15
    if args.engine in {"FINAL", "CYCLES"}:
        scene.cycles.samples = 160
        scene.cycles.use_denoising = True
        scene.cycles.use_adaptive_sampling = True
        scene.cycles.max_bounces = 8
        scene.cycles.diffuse_bounces = 4
        scene.cycles.glossy_bounces = 4

    if canonical_signature(canonical_objects) != signature_before:
        raise RuntimeError("Canonical geometry changed while styling the render.")
    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    manifest["canonical_signature"] = signature_before
    manifest["appearance"] = {
        "preset": "Warm Blank Slate",
        "version": "3",
        "procedural_materials": sorted(surfaces),
        "furnishings": [obj.name for obj in styled_objects],
    }
    manifest["camera_settings"] = {
        "name": camera_spec.name,
        "location": [round(value, 6) for value in camera_spec.location],
        "target": [round(value, 6) for value in camera_spec.target],
        "lens_mm": camera_spec.lens,
        "orthographic_scale": camera_spec.orthographic_scale,
    }
    manifest["lighting"] = {
        "rig": "Warm daylight v3",
        "procedural_only": True,
    }
    manifest["renderer"] = {
        "blender": bpy.app.version_string,
        "engine": scene.render.engine,
        "samples": scene.cycles.samples if scene.render.engine == "CYCLES" else None,
    }
    manifest["quality_checks"] = {
        "canonical_geometry_unchanged": True,
        "external_textures_missing": False,
    }
    args.manifest.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    bpy.ops.render.render(write_still=True)


if __name__ == "__main__":
    main()
