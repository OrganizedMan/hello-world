"""Focused Blender helpers for the HearthView tour-quality display scene.

The functions in this module deliberately operate in Blender authoring coordinates:
X is room width, Y runs north-to-south, and Z is up.  They are kept separate from
``build_scene.py`` so material/import mechanics and repeated millwork geometry stay
small enough to inspect independently.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from pathlib import Path
from typing import Any
import math

import bpy
from mathutils import Vector


Color = tuple[float, float, float, float]


def _set_principled_input(shader: Any, names: Sequence[str], value: Any) -> None:
    """Set a Principled input across Blender naming changes."""

    for name in names:
        socket = shader.inputs.get(name)
        if socket is not None:
            socket.default_value = value
            return


def _assign_material(obj: bpy.types.Object, material: bpy.types.Material | None) -> None:
    if material is None or not hasattr(obj.data, "materials"):
        return
    obj.data.materials.clear()
    obj.data.materials.append(material)


def parent_to(obj: bpy.types.Object, parent: bpy.types.Object | None) -> bpy.types.Object:
    if parent is not None:
        obj.parent = parent
    return obj


def create_root(name: str, parent: bpy.types.Object | None = None) -> bpy.types.Object:
    root = bpy.data.objects.new(name, None)
    bpy.context.collection.objects.link(root)
    root.empty_display_type = "PLAIN_AXES"
    root.empty_display_size = 0.22
    root["hearthview_role"] = name.removeprefix("HV_").lower()
    return parent_to(root, parent)


def create_principled_material(
    name: str,
    color: Color,
    *,
    roughness: float = 0.45,
    metallic: float = 0.0,
    transmission: float = 0.0,
    ior: float = 1.45,
    emission_color: Color | None = None,
    emission_strength: float = 0.0,
    alpha: float = 1.0,
) -> bpy.types.Material:
    material = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    material.use_nodes = True
    nodes = material.node_tree.nodes
    nodes.clear()
    output = nodes.new("ShaderNodeOutputMaterial")
    shader = nodes.new("ShaderNodeBsdfPrincipled")
    _set_principled_input(shader, ("Base Color",), color)
    _set_principled_input(shader, ("Roughness",), roughness)
    _set_principled_input(shader, ("Metallic",), metallic)
    _set_principled_input(shader, ("Transmission Weight", "Transmission"), transmission)
    _set_principled_input(shader, ("IOR",), ior)
    _set_principled_input(shader, ("Alpha",), alpha)
    if emission_color is not None:
        _set_principled_input(shader, ("Emission Color", "Emission"), emission_color)
        _set_principled_input(shader, ("Emission Strength",), emission_strength)
    material.node_tree.links.new(shader.outputs["BSDF"], output.inputs["Surface"])
    material.diffuse_color = color
    if alpha < 1.0:
        if hasattr(material, "surface_render_method"):
            try:
                material.surface_render_method = "DITHERED"
            except (TypeError, ValueError):
                material.surface_render_method = "BLENDED"
        elif hasattr(material, "blend_method"):
            material.blend_method = "BLEND"
        material.diffuse_color = (*color[:3], alpha)
    return material


def create_pbr_material(
    name: str,
    *,
    base_color_path: Path,
    normal_path: Path,
    roughness_path: Path,
    uv_scale: tuple[float, float] = (1.0, 1.0),
    tint: Color = (1.0, 1.0, 1.0, 1.0),
    roughness_multiplier: float = 1.0,
) -> bpy.types.Material:
    """Create a mapped PBR material using real color, OpenGL normal and roughness maps."""

    for path in (base_color_path, normal_path, roughness_path):
        if not Path(path).is_file():
            raise FileNotFoundError(f"PBR input is missing: {path}")

    material = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    material.use_nodes = True
    nodes = material.node_tree.nodes
    links = material.node_tree.links
    nodes.clear()

    output = nodes.new("ShaderNodeOutputMaterial")
    shader = nodes.new("ShaderNodeBsdfPrincipled")
    texcoord = nodes.new("ShaderNodeTexCoord")
    mapping = nodes.new("ShaderNodeMapping")
    mapping.inputs["Scale"].default_value = (uv_scale[0], uv_scale[1], 1.0)
    links.new(texcoord.outputs["UV"], mapping.inputs["Vector"])

    color_image = nodes.new("ShaderNodeTexImage")
    color_image.image = bpy.data.images.load(str(base_color_path), check_existing=True)
    color_image.interpolation = "Linear"
    links.new(mapping.outputs["Vector"], color_image.inputs["Vector"])
    if tint != (1.0, 1.0, 1.0, 1.0):
        multiply = nodes.new("ShaderNodeMixRGB")
        multiply.blend_type = "MULTIPLY"
        multiply.inputs[0].default_value = 1.0
        multiply.inputs[2].default_value = tint
        links.new(color_image.outputs["Color"], multiply.inputs[1])
        links.new(multiply.outputs["Color"], shader.inputs["Base Color"])
    else:
        links.new(color_image.outputs["Color"], shader.inputs["Base Color"])

    rough_image = nodes.new("ShaderNodeTexImage")
    rough_image.image = bpy.data.images.load(str(roughness_path), check_existing=True)
    rough_image.image.colorspace_settings.name = "Non-Color"
    rough_image.interpolation = "Linear"
    links.new(mapping.outputs["Vector"], rough_image.inputs["Vector"])
    if roughness_multiplier != 1.0:
        multiply_rough = nodes.new("ShaderNodeMath")
        multiply_rough.operation = "MULTIPLY"
        multiply_rough.inputs[1].default_value = roughness_multiplier
        links.new(rough_image.outputs["Color"], multiply_rough.inputs[0])
        links.new(multiply_rough.outputs[0], shader.inputs["Roughness"])
    else:
        links.new(rough_image.outputs["Color"], shader.inputs["Roughness"])

    normal_image = nodes.new("ShaderNodeTexImage")
    normal_image.image = bpy.data.images.load(str(normal_path), check_existing=True)
    normal_image.image.colorspace_settings.name = "Non-Color"
    normal_image.interpolation = "Linear"
    normal_map = nodes.new("ShaderNodeNormalMap")
    normal_map.space = "TANGENT"
    normal_map.inputs["Strength"].default_value = 0.55
    links.new(mapping.outputs["Vector"], normal_image.inputs["Vector"])
    links.new(normal_image.outputs["Color"], normal_map.inputs["Color"])
    links.new(normal_map.outputs["Normal"], shader.inputs["Normal"])
    links.new(shader.outputs["BSDF"], output.inputs["Surface"])
    material.diffuse_color = tint
    return material


def create_box(
    name: str,
    size: tuple[float, float, float],
    location: tuple[float, float, float],
    *,
    material: bpy.types.Material | None = None,
    parent: bpy.types.Object | None = None,
    bevel: float = 0.003,
    bevel_segments: int = 3,
    rotation: tuple[float, float, float] = (0.0, 0.0, 0.0),
) -> bpy.types.Object:
    if min(size) <= 0:
        raise ValueError(f"{name} box dimensions must be positive, got {size!r}")
    bpy.ops.mesh.primitive_cube_add(size=1.0, location=location, rotation=rotation)
    obj = bpy.context.object
    obj.name = name
    obj.dimensions = size
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    if bevel > 0.0:
        modifier = obj.modifiers.new("Softened visible edges", "BEVEL")
        modifier.width = min(bevel, min(size) * 0.24)
        modifier.segments = bevel_segments
        modifier.limit_method = "ANGLE"
    _assign_material(obj, material)
    parent_to(obj, parent)
    return obj


def create_cylinder(
    name: str,
    *,
    radius: float,
    depth: float,
    location: tuple[float, float, float],
    material: bpy.types.Material | None = None,
    parent: bpy.types.Object | None = None,
    rotation: tuple[float, float, float] = (0.0, 0.0, 0.0),
    vertices: int = 48,
    bevel: float = 0.0015,
) -> bpy.types.Object:
    bpy.ops.mesh.primitive_cylinder_add(
        vertices=vertices,
        radius=radius,
        depth=depth,
        location=location,
        rotation=rotation,
    )
    obj = bpy.context.object
    obj.name = name
    if bevel > 0:
        modifier = obj.modifiers.new("Edge easing", "BEVEL")
        modifier.width = min(bevel, radius * 0.25, depth * 0.2)
        modifier.segments = 2
    _assign_material(obj, material)
    parent_to(obj, parent)
    for polygon in obj.data.polygons:
        polygon.use_smooth = True
    return obj


def create_sphere(
    name: str,
    *,
    radius: float,
    location: tuple[float, float, float],
    scale: tuple[float, float, float] = (1.0, 1.0, 1.0),
    material: bpy.types.Material | None = None,
    parent: bpy.types.Object | None = None,
    segments: int = 48,
    rings: int = 24,
) -> bpy.types.Object:
    bpy.ops.mesh.primitive_uv_sphere_add(
        segments=segments,
        ring_count=rings,
        radius=radius,
        location=location,
    )
    obj = bpy.context.object
    obj.name = name
    obj.scale = scale
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    _assign_material(obj, material)
    parent_to(obj, parent)
    for polygon in obj.data.polygons:
        polygon.use_smooth = True
    return obj


def create_curve_tube(
    name: str,
    points: Sequence[tuple[float, float, float]],
    *,
    radius: float,
    material: bpy.types.Material | None = None,
    parent: bpy.types.Object | None = None,
) -> bpy.types.Object:
    curve_data = bpy.data.curves.new(name=f"{name}_CURVE", type="CURVE")
    curve_data.dimensions = "3D"
    curve_data.resolution_u = 16
    curve_data.bevel_depth = radius
    curve_data.bevel_resolution = 4
    spline = curve_data.splines.new("BEZIER")
    spline.bezier_points.add(len(points) - 1)
    for bezier_point, coordinate in zip(spline.bezier_points, points):
        bezier_point.co = coordinate
        bezier_point.handle_left_type = "AUTO"
        bezier_point.handle_right_type = "AUTO"
    obj = bpy.data.objects.new(name, curve_data)
    bpy.context.collection.objects.link(obj)
    _assign_material(obj, material)
    parent_to(obj, parent)
    return obj


def create_mesh_plane(
    name: str,
    *,
    min_x: float,
    max_x: float,
    min_y: float,
    max_y: float,
    z: float,
    material: bpy.types.Material | None = None,
    parent: bpy.types.Object | None = None,
) -> bpy.types.Object:
    mesh = bpy.data.meshes.new(f"{name}_MESH")
    mesh.from_pydata(
        [(min_x, min_y, z), (max_x, min_y, z), (max_x, max_y, z), (min_x, max_y, z)],
        [],
        [(0, 1, 2, 3)],
    )
    mesh.update()
    obj = bpy.data.objects.new(name, mesh)
    bpy.context.collection.objects.link(obj)
    _assign_material(obj, material)
    parent_to(obj, parent)
    return obj


def create_shaker_front(
    name: str,
    *,
    center: tuple[float, float, float],
    width: float,
    height: float,
    thickness: float,
    face_axis: str,
    material: bpy.types.Material,
    hardware_material: bpy.types.Material,
    parent: bpy.types.Object,
    pull_side: float = 1.0,
) -> list[bpy.types.Object]:
    """Build a five-piece Shaker front facing +X or +Y."""

    if face_axis not in {"X", "Y"}:
        raise ValueError("face_axis must be X or Y")
    rail = min(0.075, width * 0.19, height * 0.14)
    reveal = 0.0025
    width = max(width - reveal * 2.0, 0.10)
    height = max(height - reveal * 2.0, 0.12)
    cx, cy, cz = center

    if face_axis == "Y":
        dims_panel = (width - 2 * rail, thickness * 0.55, height - 2 * rail)
        panel_loc = (cx, cy - thickness * 0.23, cz)
        dims_vertical = (rail, thickness, height)
        dims_horizontal = (width - 2 * rail, thickness, rail)
        vertical_locs = ((cx - width / 2 + rail / 2, cy, cz), (cx + width / 2 - rail / 2, cy, cz))
        horizontal_locs = ((cx, cy, cz - height / 2 + rail / 2), (cx, cy, cz + height / 2 - rail / 2))
        pull_loc = (cx + pull_side * (width / 2 - rail * 0.60), cy + thickness * 0.75, cz)
    else:
        dims_panel = (thickness * 0.55, width - 2 * rail, height - 2 * rail)
        panel_loc = (cx - thickness * 0.23, cy, cz)
        dims_vertical = (thickness, rail, height)
        dims_horizontal = (thickness, width - 2 * rail, rail)
        vertical_locs = ((cx, cy - width / 2 + rail / 2, cz), (cx, cy + width / 2 - rail / 2, cz))
        horizontal_locs = ((cx, cy, cz - height / 2 + rail / 2), (cx, cy, cz + height / 2 - rail / 2))
        pull_loc = (cx + thickness * 0.75, cy + pull_side * (width / 2 - rail * 0.60), cz)

    pieces = [
        create_box(f"{name}_INSET", dims_panel, panel_loc, material=material, parent=parent, bevel=0.0015),
        create_box(f"{name}_STILE_L", dims_vertical, vertical_locs[0], material=material, parent=parent, bevel=0.0015),
        create_box(f"{name}_STILE_R", dims_vertical, vertical_locs[1], material=material, parent=parent, bevel=0.0015),
        create_box(f"{name}_RAIL_B", dims_horizontal, horizontal_locs[0], material=material, parent=parent, bevel=0.0015),
        create_box(f"{name}_RAIL_T", dims_horizontal, horizontal_locs[1], material=material, parent=parent, bevel=0.0015),
    ]
    pieces.append(
        create_cylinder(
            f"{name}_PULL",
            radius=0.006,
            depth=min(0.17, height * 0.28),
            location=pull_loc,
            material=hardware_material,
            parent=parent,
            vertices=24,
            bevel=0.001,
        )
    )
    return pieces


def create_cabinet_unit(
    name: str,
    *,
    start: float,
    width: float,
    depth: float,
    base_z: float,
    height: float,
    run_axis: str,
    body_material: bpy.types.Material,
    front_material: bpy.types.Material,
    hardware_material: bpy.types.Material,
    parent: bpy.types.Object,
    doors: int = 1,
    toe_kick: bool = True,
) -> bpy.types.Object:
    """Create a cabinet whose run follows X (north wall) or Y (west wall)."""

    if run_axis not in {"X", "Y"}:
        raise ValueError("run_axis must be X or Y")
    if run_axis == "X":
        center = (start + width / 2, depth / 2, base_z + height / 2)
        body_size = (width - 0.012, depth - 0.025, height)
        front_axis = "Y"
        face_center = (center[0], depth + 0.006, center[2])
    else:
        center = (depth / 2, start + width / 2, base_z + height / 2)
        body_size = (depth - 0.025, width - 0.012, height)
        front_axis = "X"
        face_center = (depth + 0.006, center[1], center[2])

    body = create_box(
        f"{name}_CARCASS",
        body_size,
        center,
        material=body_material,
        parent=parent,
        bevel=0.0025,
    )
    door_gap = 0.003
    door_width = (width - door_gap * (doors - 1)) / doors
    for index in range(doors):
        offset = -width / 2 + door_width / 2 + index * (door_width + door_gap)
        if run_axis == "X":
            door_center = (face_center[0] + offset, face_center[1], face_center[2])
        else:
            door_center = (face_center[0], face_center[1] + offset, face_center[2])
        create_shaker_front(
            f"{name}_DOOR_{index + 1:02d}",
            center=door_center,
            width=door_width,
            height=height - 0.012,
            thickness=0.018,
            face_axis=front_axis,
            material=front_material,
            hardware_material=hardware_material,
            parent=parent,
            pull_side=-1.0 if index == 0 and doors > 1 else 1.0,
        )

    if toe_kick and base_z < 0.2:
        if run_axis == "X":
            toe_size = (width - 0.025, 0.08, 0.095)
            toe_loc = (start + width / 2, depth - 0.10, 0.0475)
        else:
            toe_size = (0.08, width - 0.025, 0.095)
            toe_loc = (depth - 0.10, start + width / 2, 0.0475)
        create_box(f"{name}_TOE", toe_size, toe_loc, material=body_material, parent=parent, bevel=0.001)
    return body


def create_stool(
    name: str,
    *,
    location: tuple[float, float, float],
    upholstery: bpy.types.Material,
    metal: bpy.types.Material,
    parent: bpy.types.Object,
) -> bpy.types.Object:
    root = create_root(name, parent)
    x, y, _z = location
    create_cylinder(
        f"{name}_SEAT",
        radius=0.19,
        depth=0.075,
        location=(x, y, 0.69),
        material=upholstery,
        parent=root,
        vertices=48,
        bevel=0.008,
    )
    for index, (dx, dy) in enumerate(((-0.12, -0.10), (0.12, -0.10), (-0.12, 0.10), (0.12, 0.10))):
        create_cylinder(
            f"{name}_LEG_{index + 1}",
            radius=0.012,
            depth=0.64,
            location=(x + dx, y + dy, 0.34),
            material=metal,
            parent=root,
            vertices=20,
            bevel=0.001,
        )
    create_curve_tube(
        f"{name}_FOOTREST",
        [
            (x - 0.12, y - 0.105, 0.23),
            (x + 0.12, y - 0.105, 0.23),
            (x + 0.12, y + 0.105, 0.23),
            (x - 0.12, y + 0.105, 0.23),
            (x - 0.12, y - 0.105, 0.23),
        ],
        radius=0.008,
        material=metal,
        parent=root,
    )
    return root


def create_sofa(
    name: str,
    *,
    location: tuple[float, float, float],
    upholstery: bpy.types.Material,
    wood: bpy.types.Material,
    parent: bpy.types.Object,
) -> bpy.types.Object:
    """Build a rounded, segmented three-seat sofa facing +X."""

    root = create_root(name, parent)
    x, y, _z = location
    create_box(f"{name}_BASE", (0.82, 2.25, 0.22), (x, y, 0.30), material=upholstery, parent=root, bevel=0.075, bevel_segments=5)
    for index, offset in enumerate((-0.70, 0.0, 0.70)):
        create_box(
            f"{name}_SEAT_{index + 1}",
            (0.69, 0.64, 0.16),
            (x + 0.08, y + offset, 0.53),
            material=upholstery,
            parent=root,
            bevel=0.055,
            bevel_segments=5,
        )
        back = create_box(
            f"{name}_BACK_{index + 1}",
            (0.25, 0.64, 0.58),
            (x - 0.34, y + offset, 0.85),
            material=upholstery,
            parent=root,
            bevel=0.065,
            bevel_segments=5,
            rotation=(0.0, math.radians(-7.0), 0.0),
        )
        back["segment"] = index + 1
    for side, offset in (("N", -1.13), ("S", 1.13)):
        create_box(
            f"{name}_ARM_{side}",
            (0.80, 0.18, 0.47),
            (x, y + offset, 0.58),
            material=upholstery,
            parent=root,
            bevel=0.07,
            bevel_segments=5,
        )
    for index, (dx, dy) in enumerate(((-0.31, -0.91), (0.31, -0.91), (-0.31, 0.91), (0.31, 0.91))):
        create_cylinder(
            f"{name}_FOOT_{index + 1}",
            radius=0.035,
            depth=0.15,
            location=(x + dx, y + dy, 0.075),
            material=wood,
            parent=root,
            vertices=24,
        )
    return root


def _world_bounds(objects: Iterable[bpy.types.Object]) -> tuple[Vector, Vector]:
    points: list[Vector] = []
    for obj in objects:
        if obj.type != "MESH":
            continue
        points.extend(obj.matrix_world @ Vector(corner) for corner in obj.bound_box)
    if not points:
        raise ValueError("imported glTF did not contain mesh bounds")
    return (
        Vector((min(point.x for point in points), min(point.y for point in points), min(point.z for point in points))),
        Vector((max(point.x for point in points), max(point.y for point in points), max(point.z for point in points))),
    )


def import_gltf_asset(
    path: Path,
    *,
    name: str,
    parent: bpy.types.Object,
    floor_center: tuple[float, float, float],
    target_max_extent: float | None = None,
    rotation_z: float = 0.0,
    material_overrides: dict[str, bpy.types.Material] | None = None,
) -> bpy.types.Object:
    """Import a local glTF hierarchy, preserve it, place its base, and parent its roots."""

    path = Path(path)
    if not path.is_file():
        raise FileNotFoundError(f"glTF input is missing: {path}")
    before = {obj.as_pointer() for obj in bpy.data.objects}
    result = bpy.ops.import_scene.gltf(filepath=str(path), import_pack_images=True)
    if "FINISHED" not in result:
        raise RuntimeError(f"Blender failed to import {path}")
    imported = [obj for obj in bpy.data.objects if obj.as_pointer() not in before]
    root = create_root(name, parent)
    top_level = [obj for obj in imported if obj.parent not in imported]
    for obj in top_level:
        matrix = obj.matrix_world.copy()
        obj.parent = root
        obj.matrix_world = matrix

    bpy.context.view_layer.update()
    lower, upper = _world_bounds(imported)
    extents = upper - lower
    if target_max_extent is not None:
        scale = target_max_extent / max(extents)
        root.scale = (scale, scale, scale)
    root.rotation_euler.z = rotation_z
    bpy.context.view_layer.update()
    lower, upper = _world_bounds(imported)
    center = (lower + upper) * 0.5
    desired_x, desired_y, desired_z = floor_center
    root.location += Vector((desired_x - center.x, desired_y - center.y, desired_z - lower.z))
    bpy.context.view_layer.update()

    if material_overrides:
        for obj in imported:
            if obj.type != "MESH":
                continue
            for slot in obj.material_slots:
                lowered = (slot.material.name if slot.material else "").lower()
                for token, override in material_overrides.items():
                    if token.lower() in lowered:
                        slot.material = override
                        break
    root["source_asset"] = path.name
    root["source_path"] = path.as_posix()
    return root


def add_camera(
    name: str,
    *,
    position: tuple[float, float, float],
    target: tuple[float, float, float],
    lens_mm: float,
    parent: bpy.types.Object,
) -> bpy.types.Object:
    camera_data = bpy.data.cameras.new(name=f"{name}_DATA")
    camera_data.lens = lens_mm
    camera_data.sensor_width = 36.0
    camera_data.clip_start = 0.05
    camera_data.clip_end = 100.0
    camera = bpy.data.objects.new(name, camera_data)
    bpy.context.collection.objects.link(camera)
    camera.location = position
    direction = Vector(target) - camera.location
    camera.rotation_euler = direction.to_track_quat("-Z", "Y").to_euler()
    parent_to(camera, parent)
    camera["target"] = list(target)
    return camera


def add_area_light(
    name: str,
    *,
    location: tuple[float, float, float],
    energy: float,
    size: float,
    color: tuple[float, float, float],
    target: tuple[float, float, float],
    parent: bpy.types.Object,
) -> bpy.types.Object:
    data = bpy.data.lights.new(name=f"{name}_DATA", type="AREA")
    data.energy = energy
    data.shape = "RECTANGLE"
    data.size = size
    data.size_y = size
    data.color = color
    light = bpy.data.objects.new(name, data)
    bpy.context.collection.objects.link(light)
    light.location = location
    light.rotation_euler = (Vector(target) - light.location).to_track_quat("-Z", "Y").to_euler()
    parent_to(light, parent)
    return light


def add_point_light(
    name: str,
    *,
    location: tuple[float, float, float],
    energy: float,
    color: tuple[float, float, float],
    parent: bpy.types.Object,
    radius: float = 0.16,
) -> bpy.types.Object:
    data = bpy.data.lights.new(name=f"{name}_DATA", type="POINT")
    data.energy = energy
    data.color = color
    data.shadow_soft_size = radius
    light = bpy.data.objects.new(name, data)
    bpy.context.collection.objects.link(light)
    light.location = location
    parent_to(light, parent)
    return light


def tag_contract_boundary(obj: bpy.types.Object, *, label: str, canonical_geometry: bool, categories: Sequence[str]) -> None:
    obj["label"] = label
    obj["canonical_geometry"] = canonical_geometry
    # Blender ID properties do not portably support arrays of strings. The GLB-level
    # authoritative list is injected as an actual JSON array after export.
    obj["provisional_categories"] = ",".join(categories)
