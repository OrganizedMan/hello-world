"""Layer materials, light and sky onto the traced canvas.

The traced build is deliberately plain: `a1_tour` writes correct geometry with
flat placeholder colours, and every corner of it is measured against the drawing
before anyone looks at it. Photorealism is a separate pass, and this is it --
the canvas GLB goes in, materials, daylight and a sky go on, and a richer GLB
comes out. Geometry is never touched here, so the measurement gate still holds
over the result.

Runs under Blender, either as `blender --background --python` or against the
`bpy` module directly:

    python -m spikes.tour_quality.building_look -- --canvas <glb> --hdri <hdr> \
        --out <glb> --still <png>
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import bpy

# Part kinds the canvas paints, in the material names `a1_tour` writes.
CANVAS_MATERIALS = ("wall", "floor", "counter", "fixture", "deck", "stair")


ASSETS = Path(__file__).resolve().parents[2] / "spikes/tour_quality/assets/files"


def unwrap_by_size(metres_per_tile: float = 1.0) -> int:
    """Give every mesh a cube-projected UV set scaled to real size.

    The canvas is extruded boxes and carries no UVs at all, so image textures
    have nothing to sit on. Cube projection suits axis-aligned boxes exactly,
    and scaling by real size is what makes a floorboard the same width in a
    cupboard as in a living room -- a per-object unwrap would stretch each
    surface to fill the same square and the plank width would vary by room.
    """
    unwrapped = 0
    for obj in [o for o in bpy.data.objects if o.type == "MESH"]:
        bpy.context.view_layer.objects.active = obj
        obj.select_set(True)
        bpy.ops.object.mode_set(mode="EDIT")
        bpy.ops.mesh.select_all(action="SELECT")
        bpy.ops.uv.cube_project(cube_size=metres_per_tile, correct_aspect=True)
        bpy.ops.object.mode_set(mode="OBJECT")
        obj.select_set(False)
        unwrapped += 1
    return unwrapped


def _reset() -> None:
    bpy.ops.wm.read_factory_settings(use_empty=True)


def _clear_nodes(material: bpy.types.Material):
    material.use_nodes = True
    tree = material.node_tree
    tree.nodes.clear()
    output = tree.nodes.new("ShaderNodeOutputMaterial")
    shader = tree.nodes.new("ShaderNodeBsdfPrincipled")
    tree.links.new(shader.outputs["BSDF"], output.inputs["Surface"])
    output.location = (400, 0)
    return tree, shader


def image_maps(
    tree,
    shader,
    *,
    colour: Path,
    roughness: Path | None = None,
    normal: Path | None = None,
    scale: float = 1.0,
    tint: tuple[float, float, float, float] | None = None,
) -> None:
    """Wire real colour, roughness and normal maps onto a Principled shader.

    Photographed maps beat anything procedural for oak and stone, and unlike a
    node graph they survive glTF export -- which procedural materials do not,
    at all. Colour is sRGB; roughness and normal are data and must not be
    colour-managed or the surface reads wrong.
    """
    coords = tree.nodes.new("ShaderNodeTexCoord")
    mapping = tree.nodes.new("ShaderNodeMapping")
    mapping.inputs["Scale"].default_value = (scale, scale, scale)
    tree.links.new(coords.outputs["UV"], mapping.inputs["Vector"])

    base = tree.nodes.new("ShaderNodeTexImage")
    base.image = bpy.data.images.load(str(colour), check_existing=True)
    tree.links.new(mapping.outputs["Vector"], base.inputs["Vector"])
    if tint:
        multiply = tree.nodes.new("ShaderNodeMixRGB")
        multiply.blend_type = "MULTIPLY"
        multiply.inputs["Fac"].default_value = 1.0
        multiply.inputs["Color2"].default_value = tint
        tree.links.new(base.outputs["Color"], multiply.inputs["Color1"])
        tree.links.new(multiply.outputs["Color"], shader.inputs["Base Color"])
    else:
        tree.links.new(base.outputs["Color"], shader.inputs["Base Color"])

    if roughness is not None:
        rough = tree.nodes.new("ShaderNodeTexImage")
        rough.image = bpy.data.images.load(str(roughness), check_existing=True)
        rough.image.colorspace_settings.name = "Non-Color"
        tree.links.new(mapping.outputs["Vector"], rough.inputs["Vector"])
        tree.links.new(rough.outputs["Color"], shader.inputs["Roughness"])

    if normal is not None:
        normal_image = tree.nodes.new("ShaderNodeTexImage")
        normal_image.image = bpy.data.images.load(str(normal), check_existing=True)
        normal_image.image.colorspace_settings.name = "Non-Color"
        tree.links.new(mapping.outputs["Vector"], normal_image.inputs["Vector"])
        normal_map = tree.nodes.new("ShaderNodeNormalMap")
        tree.links.new(normal_image.outputs["Color"], normal_map.inputs["Color"])
        tree.links.new(normal_map.outputs["Normal"], shader.inputs["Normal"])


def _texture_coords(tree, scale: float):
    """Object-space coordinates, so a material tiles by real size not by UV.

    The canvas carries no UVs -- it is extruded boxes -- so generated or UV
    coordinates would smear. Object coordinates give every solid the same
    physical grain regardless of how large it is.
    """
    coords = tree.nodes.new("ShaderNodeTexCoord")
    mapping = tree.nodes.new("ShaderNodeMapping")
    mapping.inputs["Scale"].default_value = (scale, scale, scale)
    tree.links.new(coords.outputs["Object"], mapping.inputs["Vector"])
    return mapping


def oak_floor() -> bpy.types.Material:
    """Rift-sawn oak boards: plank seams across the grain, fine figure along it."""
    material = bpy.data.materials.new("HV_LOOK_OAK_FLOOR")
    tree, shader = _clear_nodes(material)
    mapping = _texture_coords(tree, 1.0)

    # Plank seams: a brick texture stretched into long boards.
    planks = tree.nodes.new("ShaderNodeTexBrick")
    planks.offset = 0.5
    planks.offset_frequency = 2
    planks.inputs["Scale"].default_value = 0.72
    planks.inputs["Mortar Size"].default_value = 0.0016
    planks.inputs["Mortar Smooth"].default_value = 0.1
    planks.inputs["Bias"].default_value = 0.0
    planks.inputs["Brick Width"].default_value = 2.6
    planks.inputs["Row Height"].default_value = 0.34
    planks.inputs["Color1"].default_value = (0.44, 0.30, 0.17, 1.0)
    planks.inputs["Color2"].default_value = (0.52, 0.37, 0.22, 1.0)
    planks.inputs["Mortar"].default_value = (0.20, 0.13, 0.07, 1.0)
    tree.links.new(mapping.outputs["Vector"], planks.inputs["Vector"])

    # Grain: noise stretched hard along the board direction.
    stretch = tree.nodes.new("ShaderNodeMapping")
    stretch.inputs["Scale"].default_value = (0.5, 26.0, 1.0)
    tree.links.new(mapping.outputs["Vector"], stretch.inputs["Vector"])
    grain = tree.nodes.new("ShaderNodeTexNoise")
    grain.inputs["Scale"].default_value = 5.5
    grain.inputs["Detail"].default_value = 9.0
    grain.inputs["Roughness"].default_value = 0.62
    tree.links.new(stretch.outputs["Vector"], grain.inputs["Vector"])

    tone = tree.nodes.new("ShaderNodeValToRGB")
    tone.color_ramp.elements[0].position = 0.36
    tone.color_ramp.elements[0].color = (0.40, 0.27, 0.15, 1.0)
    tone.color_ramp.elements[1].position = 0.68
    tone.color_ramp.elements[1].color = (0.62, 0.46, 0.29, 1.0)
    tree.links.new(grain.outputs["Fac"], tone.inputs["Fac"])

    blend = tree.nodes.new("ShaderNodeMixRGB")
    blend.blend_type = "OVERLAY"
    blend.inputs["Fac"].default_value = 0.55
    tree.links.new(planks.outputs["Color"], blend.inputs["Color1"])
    tree.links.new(tone.outputs["Color"], blend.inputs["Color2"])
    tree.links.new(blend.outputs["Color"], shader.inputs["Base Color"])

    # Satin finish, slightly duller in the seams.
    rough = tree.nodes.new("ShaderNodeValToRGB")
    rough.color_ramp.elements[0].position = 0.3
    rough.color_ramp.elements[0].color = (0.42, 0.42, 0.42, 1.0)
    rough.color_ramp.elements[1].position = 0.9
    rough.color_ramp.elements[1].color = (0.26, 0.26, 0.26, 1.0)
    tree.links.new(grain.outputs["Fac"], rough.inputs["Fac"])
    tree.links.new(rough.outputs["Color"], shader.inputs["Roughness"])

    bump = tree.nodes.new("ShaderNodeBump")
    bump.inputs["Strength"].default_value = 0.12
    tree.links.new(planks.outputs["Fac"], bump.inputs["Height"])
    tree.links.new(bump.outputs["Normal"], shader.inputs["Normal"])
    return material


def painted_plaster() -> bpy.types.Material:
    """Flat wall paint: near-white, very slight tooth so it is not plastic."""
    material = bpy.data.materials.new("HV_LOOK_PLASTER")
    tree, shader = _clear_nodes(material)
    mapping = _texture_coords(tree, 12.0)

    tooth = tree.nodes.new("ShaderNodeTexNoise")
    tooth.inputs["Scale"].default_value = 42.0
    tooth.inputs["Detail"].default_value = 6.0
    tree.links.new(mapping.outputs["Vector"], tooth.inputs["Vector"])

    shader.inputs["Base Color"].default_value = (0.878, 0.867, 0.843, 1.0)
    shader.inputs["Roughness"].default_value = 0.86
    bump = tree.nodes.new("ShaderNodeBump")
    bump.inputs["Strength"].default_value = 0.045
    tree.links.new(tooth.outputs["Fac"], bump.inputs["Height"])
    tree.links.new(bump.outputs["Normal"], shader.inputs["Normal"])
    return material


def honed_marble() -> bpy.types.Material:
    """Veined white marble for counters and the island top."""
    material = bpy.data.materials.new("HV_LOOK_MARBLE")
    tree, shader = _clear_nodes(material)
    mapping = _texture_coords(tree, 0.55)

    # Veins: noise pushed through a wave texture, which is what gives the
    # long directional streaks rather than isotropic blobs.
    warp = tree.nodes.new("ShaderNodeTexNoise")
    warp.inputs["Scale"].default_value = 2.1
    warp.inputs["Detail"].default_value = 8.0
    tree.links.new(mapping.outputs["Vector"], warp.inputs["Vector"])

    veins = tree.nodes.new("ShaderNodeTexWave")
    veins.wave_type = "BANDS"
    veins.bands_direction = "DIAGONAL"
    veins.wave_profile = "SIN"
    veins.inputs["Scale"].default_value = 1.6
    veins.inputs["Distortion"].default_value = 14.0
    veins.inputs["Detail"].default_value = 3.0
    tree.links.new(mapping.outputs["Vector"], veins.inputs["Vector"])

    ramp = tree.nodes.new("ShaderNodeValToRGB")
    ramp.color_ramp.interpolation = "EASE"
    ramp.color_ramp.elements[0].position = 0.42
    ramp.color_ramp.elements[0].color = (0.94, 0.93, 0.92, 1.0)
    ramp.color_ramp.elements[1].position = 0.72
    ramp.color_ramp.elements[1].color = (0.55, 0.55, 0.57, 1.0)
    tree.links.new(veins.outputs["Fac"], ramp.inputs["Fac"])
    tree.links.new(ramp.outputs["Color"], shader.inputs["Base Color"])

    shader.inputs["Roughness"].default_value = 0.22
    return material


def brushed_metal() -> bpy.types.Material:
    material = bpy.data.materials.new("HV_LOOK_APPLIANCE")
    _tree, shader = _clear_nodes(material)
    shader.inputs["Base Color"].default_value = (0.62, 0.63, 0.65, 1.0)
    shader.inputs["Metallic"].default_value = 0.85
    shader.inputs["Roughness"].default_value = 0.32
    return material


def exterior_stone() -> bpy.types.Material:
    material = bpy.data.materials.new("HV_LOOK_STONE")
    tree, shader = _clear_nodes(material)
    mapping = _texture_coords(tree, 3.0)
    grit = tree.nodes.new("ShaderNodeTexNoise")
    grit.inputs["Scale"].default_value = 12.0
    grit.inputs["Detail"].default_value = 7.0
    tree.links.new(mapping.outputs["Vector"], grit.inputs["Vector"])
    ramp = tree.nodes.new("ShaderNodeValToRGB")
    ramp.color_ramp.elements[0].color = (0.34, 0.33, 0.31, 1.0)
    ramp.color_ramp.elements[1].color = (0.47, 0.46, 0.43, 1.0)
    tree.links.new(grit.outputs["Fac"], ramp.inputs["Fac"])
    tree.links.new(ramp.outputs["Color"], shader.inputs["Base Color"])
    shader.inputs["Roughness"].default_value = 0.82
    bump = tree.nodes.new("ShaderNodeBump")
    bump.inputs["Strength"].default_value = 0.25
    tree.links.new(grit.outputs["Fac"], bump.inputs["Height"])
    tree.links.new(bump.outputs["Normal"], shader.inputs["Normal"])
    return material


def textured_oak_floor() -> bpy.types.Material:
    """Poly Haven wood_floor: straight boards, as the reference interiors are laid.

    Tinted up because the map is a darker walnut than the pale oak in the
    reference, and these rooms are lit by one window each -- a dark floor eats
    what little bounce there is.
    """
    material = bpy.data.materials.new("HV_LOOK_OAK_FLOOR_TEX")
    tree, shader = _clear_nodes(material)
    image_maps(
        tree, shader,
        colour=ASSETS / "wood_floor_diff_2k.jpg",
        roughness=ASSETS / "wood_floor_rough_2k.jpg",
        normal=ASSETS / "wood_floor_nor_gl_2k.jpg",
        scale=0.42,
        tint=(1.45, 1.34, 1.16, 1.0),
    )
    return material


def parquet_floor() -> bpy.types.Material:
    """ambientCG WoodFloor070, herringbone. Not used by default; kept for rooms
    that should read as patterned rather than boarded."""
    material = bpy.data.materials.new("HV_LOOK_PARQUET_TEX")
    tree, shader = _clear_nodes(material)
    folder = ASSETS / "WoodFloor070"
    image_maps(
        tree, shader,
        colour=folder / "WoodFloor070_2K-JPG_Color.jpg",
        roughness=folder / "WoodFloor070_2K-JPG_Roughness.jpg",
        normal=folder / "WoodFloor070_2K-JPG_NormalGL.jpg",
        scale=0.55,
    )
    return material


def textured_plaster() -> bpy.types.Material:
    material = bpy.data.materials.new("HV_LOOK_PLASTER_TEX")
    tree, shader = _clear_nodes(material)
    image_maps(
        tree, shader,
        colour=ASSETS / "beige_wall_001_diff_1k.jpg",
        roughness=ASSETS / "beige_wall_001_rough_1k.jpg",
        normal=ASSETS / "beige_wall_001_nor_gl_1k.jpg",
        scale=1.6,
        tint=(1.06, 1.05, 1.02, 1.0),
    )
    return material


def textured_stone() -> bpy.types.Material:
    """Honed travertine for counters and the island top."""
    material = bpy.data.materials.new("HV_LOOK_STONE_TEX")
    tree, shader = _clear_nodes(material)
    folder = ASSETS / "Travertine009"
    image_maps(
        tree, shader,
        colour=folder / "Travertine009_2K-JPG_Color.jpg",
        roughness=folder / "Travertine009_2K-JPG_Roughness.jpg",
        normal=folder / "Travertine009_2K-JPG_NormalGL.jpg",
        scale=0.7,
    )
    return material


LOOKS = {
    "floor": textured_oak_floor,
    "ceiling": painted_plaster,
    "wall": textured_plaster,
    "counter": textured_stone,
    "fixture": brushed_metal,
    "stair": textured_oak_floor,
    "deck": exterior_stone,
}


def apply_looks() -> dict[str, str]:
    """Swap every canvas material for its authored equivalent, in place."""
    applied: dict[str, str] = {}
    for kind, factory in LOOKS.items():
        canvas = bpy.data.materials.get(kind)
        if canvas is None:
            continue
        look = factory()
        for obj in bpy.data.objects:
            if obj.type != "MESH":
                continue
            for index, slot in enumerate(obj.material_slots):
                if slot.material is not None and slot.material.name == kind:
                    obj.material_slots[index].material = look
        applied[kind] = look.name
    return applied


# Floor finish per room kind. Everything not named here keeps the default oak.
ROOM_FLOORS = {
    "bathroom": "tile",
    "utility": "tile",
    "kitchen": "oak",
    "storage": "tile",
    "exterior": "stone",
}


def tiled_floor() -> bpy.types.Material:
    """Travertine, laid at a tile size rather than a slab size."""
    material = bpy.data.materials.new("HV_LOOK_TILE_TEX")
    tree, shader = _clear_nodes(material)
    folder = ASSETS / "Travertine009"
    image_maps(
        tree, shader,
        colour=folder / "Travertine009_2K-JPG_Color.jpg",
        roughness=folder / "Travertine009_2K-JPG_Roughness.jpg",
        normal=folder / "Travertine009_2K-JPG_NormalGL.jpg",
        scale=1.9,
        tint=(1.06, 1.04, 1.0, 1.0),
    )
    return material


def _subdivide_floor(obj, *, floor_material_hint: str, target_metres: float) -> int:
    """Cut the floor slab into a grid so a finish can change partway across it.

    The canvas puts one floor slab per storey, so its top is a single polygon
    covering every room. Assigning materials per face changes nothing until
    there are faces to assign: this cuts them to roughly `target_metres`, which
    is fine enough to follow a wall line and coarse enough not to explode the
    mesh.
    """
    import bmesh

    floor_slot = next(
        (index for index, slot in enumerate(obj.material_slots)
         if slot.material is not None and floor_material_hint in slot.material.name),
        None,
    )
    if floor_slot is None:
        return 0

    mesh = bmesh.new()
    mesh.from_mesh(obj.data)
    faces = [f for f in mesh.faces if f.material_index == floor_slot]
    if not faces:
        mesh.free()
        return 0

    longest = max(
        max((v.co - w.co).length for v, w in zip(f.verts, list(f.verts)[1:] + [f.verts[0]]))
        for f in faces
    )
    cuts = max(0, min(64, int(longest / target_metres) - 1))
    if cuts:
        edges = {e for f in faces for e in f.edges}
        bmesh.ops.subdivide_edges(mesh, edges=list(edges), cuts=cuts, use_grid_fill=True)
    mesh.to_mesh(obj.data)
    mesh.free()
    obj.data.update()
    return cuts


def apply_room_finishes(rooms_block: dict, datum_origin: tuple[float, float]) -> dict[str, int]:
    """Give each floor face the finish its room asks for.

    The canvas has one floor mesh per storey, so a finish cannot vary by room
    without going per-face: every floor polygon is asked which room its centre
    falls in, and takes that room's material.

    Room extents arrive in the manifest rather than being recomputed, because
    Blender's Python has no PDF toolchain and should not need one. Blender's
    axes after a glTF import are x east, y north, in metres from the datum
    storey's south-west corner, so converting a face centre back to sheet
    coordinates is the inverse of the mapping that built the canvas.
    """
    FT = 0.3048
    POINTS_PER_FOOT = 18.0
    cell = rooms_block["cell_points"]
    datum_x, datum_y1 = datum_origin

    finishes = {"tile": tiled_floor(), "stone": exterior_stone()}
    counted: dict[str, int] = {}

    for storey in rooms_block["storeys"]:
        obj = bpy.data.objects.get(storey["node"])
        if obj is None:
            continue

        # Rebuild the ownership grid from its runs.
        columns, rows = storey["columns"], storey["rows"]
        owner = [-1] * (columns * rows)
        for who, row, first, last in storey["runs"]:
            base = row * columns
            for column in range(first, last + 1):
                owner[base + column] = who
        kinds = [room["kind"] for room in storey["rooms"]]
        origin_x, origin_y = storey["origin_pdf"]

        _subdivide_floor(obj, floor_material_hint="OAK_FLOOR", target_metres=0.35)

        slots = {
            slot.material.name: index
            for index, slot in enumerate(obj.material_slots)
            if slot.material is not None
        }
        floor_slot = next((i for name, i in slots.items() if "OAK_FLOOR" in name), None)
        if floor_slot is None:
            continue
        for material in finishes.values():
            if material.name not in slots:
                obj.data.materials.append(material)
                slots[material.name] = len(obj.data.materials) - 1

        for polygon in obj.data.polygons:
            if polygon.material_index != floor_slot:
                continue
            centre = obj.matrix_world @ polygon.center
            pdf_x = datum_x + (centre.x / FT) * POINTS_PER_FOOT
            pdf_y = datum_y1 - (centre.y / FT) * POINTS_PER_FOOT
            cx = int((pdf_x - origin_x) / cell)
            cy = int((pdf_y - origin_y) / cell)
            if not (0 <= cx < columns and 0 <= cy < rows):
                continue
            who = owner[cy * columns + cx]
            if who < 0:
                continue
            kind = kinds[who]
            wanted = ROOM_FLOORS.get(kind)
            if wanted in finishes:
                polygon.material_index = slots[finishes[wanted].name]
                counted[kind] = counted.get(kind, 0) + 1
    return counted


def painted_cabinet() -> bpy.types.Material:
    material = bpy.data.materials.new("HV_LOOK_CABINET")
    _tree, shader = _clear_nodes(material)
    shader.inputs["Base Color"].default_value = (0.855, 0.833, 0.788, 1.0)
    shader.inputs["Roughness"].default_value = 0.42
    return material


def _drop_faces(node_name: str, material_hint: str) -> int:
    """Remove the canvas's placeholder solids for a part kind.

    The canvas draws a counter as a plain box, which is the right thing for a
    measured model and the wrong thing to look at. Once real casework stands in
    its place the box has to go, or it sits inside the cabinet it represents.
    """
    import bmesh

    obj = bpy.data.objects.get(node_name)
    if obj is None:
        return 0
    slots = [
        index for index, slot in enumerate(obj.material_slots)
        if slot.material is not None and material_hint in slot.material.name
    ]
    if not slots:
        return 0
    mesh = bmesh.new()
    mesh.from_mesh(obj.data)
    doomed = [f for f in mesh.faces if f.material_index in slots]
    count = len(doomed)
    bmesh.ops.delete(mesh, geom=doomed, context="FACES")
    mesh.to_mesh(obj.data)
    mesh.free()
    obj.data.update()
    return count


def _box(name, size, location, material, parent=None, rotation_z=0.0):
    bpy.ops.mesh.primitive_cube_add(size=1.0, location=location)
    obj = bpy.context.active_object
    obj.name = name
    obj.scale = (size[0] / 2.0, size[1] / 2.0, size[2] / 2.0)
    obj.rotation_euler = (0.0, 0.0, rotation_z)
    obj.data.materials.append(material)
    if parent is not None:
        obj.parent = parent
    return obj


def build_casework(entries: list[dict], *, doors_every: float = 0.58) -> int:
    """Turn every traced counter run into carcass, doors and a worktop.

    Driven by the run and the room it stands in, not by which room it is: the
    kitchen gets the same treatment as the mudroom and both bathrooms, with the
    worktop material the only thing the room decides. That is the whole point --
    a kitchen is a room with more counter in it, not a special case.
    """
    import math

    cabinet = painted_cabinet()
    tops = {"kitchen": honed_marble(), "bathroom": honed_marble()}
    default_top = tiled_floor()
    made = 0

    for entry in entries:
        width_x, width_y, height = entry["size"]
        cx, cy, cz = entry["centre"]
        base_z = cz - height / 2.0
        along = width_x if entry["run_axis"] == "X" else width_y
        across = width_y if entry["run_axis"] == "X" else width_x
        if along < 0.25 or across < 0.15:
            continue

        yaw = math.radians(entry["facing_degrees"])
        top_thickness = 0.038
        carcass_height = max(0.2, height - top_thickness)
        toe = 0.09

        # Carcass, held off the floor by a toe kick.
        _box(f"HV_CASE_{entry['id']}_BODY",
             (width_x - 0.01, width_y - 0.01, carcass_height - toe),
             (cx, cy, base_z + toe + (carcass_height - toe) / 2.0), cabinet)
        _box(f"HV_CASE_{entry['id']}_KICK",
             (width_x - 0.09, width_y - 0.09, toe),
             (cx, cy, base_z + toe / 2.0), cabinet)

        # Worktop, slightly proud of the carcass on every side.
        top_material = tops.get(entry["room_kind"], default_top)
        _box(f"HV_CASE_{entry['id']}_TOP",
             (width_x + 0.024, width_y + 0.024, top_thickness),
             (cx, cy, base_z + carcass_height + top_thickness / 2.0), top_material)

        # Door fronts along the run, with a recessed panel each.
        count = max(1, int(round(along / doors_every)))
        door_width = along / count
        for index in range(count):
            offset = -along / 2.0 + door_width * (index + 0.5)
            if entry["run_axis"] == "X":
                door_centre = (cx + offset, cy, base_z + toe + (carcass_height - toe) / 2.0)
                door_size = (door_width - 0.008, 0.02, carcass_height - toe - 0.012)
                face_shift = (0.0, across / 2.0, 0.0)
            else:
                door_centre = (cx, cy + offset, base_z + toe + (carcass_height - toe) / 2.0)
                door_size = (0.02, door_width - 0.008, carcass_height - toe - 0.012)
                face_shift = (across / 2.0, 0.0, 0.0)
            sign = -1.0 if entry["facing_degrees"] in (180.0, 270.0) else 1.0
            placed = (
                door_centre[0] + face_shift[0] * sign,
                door_centre[1] + face_shift[1] * sign,
                door_centre[2],
            )
            _box(f"HV_CASE_{entry['id']}_DOOR{index}", door_size, placed, cabinet)
            # Shaker rail: a slightly proud frame reads as a panel edge.
            inset = 0.055
            if entry["run_axis"] == "X":
                panel = (max(0.02, door_size[0] - inset), 0.008, max(0.02, door_size[2] - inset))
            else:
                panel = (0.008, max(0.02, door_size[1] - inset), max(0.02, door_size[2] - inset))
            # Proud of the door by a few millimetres. Scaling this by the
            # counter depth pushed the panel clear of the cabinet entirely, so
            # deep runs grew a stack of floating fins instead of a door face.
            proud = 0.012
            nudge = (
                0.0 if entry["run_axis"] == "X" else proud * sign,
                proud * sign if entry["run_axis"] == "X" else 0.0,
            )
            _box(f"HV_CASE_{entry['id']}_PANEL{index}", panel,
                 (placed[0] + nudge[0], placed[1] + nudge[1], placed[2]), cabinet)
        made += 1
    return made


def build_world(hdri: Path, strength: float = 1.0, rotation: float = 0.0) -> None:
    """Sky and daylight from the HDRI, which is also what shows through windows."""
    world = bpy.data.worlds.new("HV_LOOK_WORLD")
    bpy.context.scene.world = world
    world.use_nodes = True
    tree = world.node_tree
    tree.nodes.clear()

    output = tree.nodes.new("ShaderNodeOutputWorld")
    background = tree.nodes.new("ShaderNodeBackground")
    background.inputs["Strength"].default_value = strength
    environment = tree.nodes.new("ShaderNodeTexEnvironment")
    environment.image = bpy.data.images.load(str(hdri), check_existing=True)
    mapping = tree.nodes.new("ShaderNodeMapping")
    mapping.inputs["Rotation"].default_value = (0.0, 0.0, rotation)
    coords = tree.nodes.new("ShaderNodeTexCoord")

    tree.links.new(coords.outputs["Generated"], mapping.inputs["Vector"])
    tree.links.new(mapping.outputs["Vector"], environment.inputs["Vector"])
    tree.links.new(environment.outputs["Color"], background.inputs["Color"])
    tree.links.new(background.outputs["Background"], output.inputs["Surface"])


def add_sun(strength: float = 3.0, angle_degrees: float = 2.5) -> bpy.types.Object:
    """A single sun for crisp shadow direction; the HDRI supplies the rest."""
    import math

    light = bpy.data.lights.new("HV_LOOK_SUN", type="SUN")
    light.energy = strength
    light.angle = math.radians(angle_degrees)
    light.color = (1.0, 0.957, 0.898)
    sun = bpy.data.objects.new("HV_LOOK_SUN", light)
    sun.rotation_euler = (math.radians(52), 0.0, math.radians(214))
    bpy.context.scene.collection.objects.link(sun)
    return sun


def _scene_bounds() -> tuple[tuple[float, float, float], tuple[float, float, float]]:
    from mathutils import Vector

    low = Vector((1e9, 1e9, 1e9))
    high = Vector((-1e9, -1e9, -1e9))
    for obj in bpy.data.objects:
        if obj.type != "MESH":
            continue
        for corner in obj.bound_box:
            world = obj.matrix_world @ Vector(corner)
            low = Vector((min(low[i], world[i]) for i in range(3)))
            high = Vector((max(high[i], world[i]) for i in range(3)))
    return tuple(low), tuple(high)


def add_dollhouse_camera(lens: float = 38.0) -> bpy.types.Object:
    """Three-quarter view framing the whole model, for judging the look."""
    import math

    from mathutils import Vector

    low, high = _scene_bounds()
    centre = Vector(((low[i] + high[i]) / 2 for i in range(3)))
    size = Vector((high[i] - low[i] for i in range(3)))
    reach = max(size.x, size.y) * 1.5

    camera_data = bpy.data.cameras.new("HV_LOOK_CAM")
    camera_data.lens = lens
    camera = bpy.data.objects.new("HV_LOOK_CAM", camera_data)
    camera.location = (
        centre.x + reach * 0.72,
        centre.y - reach * 0.86,
        centre.z + size.z * 0.85 + reach * 0.32,
    )
    direction = centre - Vector(camera.location)
    camera.rotation_euler = direction.to_track_quat("-Z", "Y").to_euler()
    bpy.context.scene.collection.objects.link(camera)
    bpy.context.scene.camera = camera
    return camera


def add_interior_camera(
    storey_node: str,
    *,
    eye_metres: float = 1.562,
    yaw_degrees: float = 0.0,
    lens: float = 16.0,
) -> bpy.types.Object:
    """Eye-height camera standing inside one storey.

    16 mm, which is wide even for an interior. Rooms this size shot at 24 mm
    read as corridors: a wall two metres away fills the frame and there is no
    sense of being able to turn your head. The default eye height is a 5'6"
    person, whose eyes sit about 4.5" below the top of their head.
    """
    import math

    from mathutils import Vector

    storey = bpy.data.objects.get(storey_node)
    if storey is None:
        raise SystemExit(f"No storey node called {storey_node}")

    corners = [storey.matrix_world @ Vector(c) for c in storey.bound_box]
    low = Vector((min(c[i] for c in corners) for i in range(3)))
    high = Vector((max(c[i] for c in corners) for i in range(3)))
    centre = (low + high) / 2

    camera_data = bpy.data.cameras.new("HV_LOOK_INTERIOR")
    camera_data.lens = lens
    camera = bpy.data.objects.new("HV_LOOK_INTERIOR", camera_data)
    # Stand back towards one corner rather than dead centre, which is how a
    # room actually gets photographed.
    camera.location = (
        centre.x - (high.x - low.x) * 0.30,
        centre.y - (high.y - low.y) * 0.34,
        low.z + eye_metres,
    )
    camera.rotation_euler = (math.radians(90.0), 0.0, math.radians(yaw_degrees))
    bpy.context.scene.collection.objects.link(camera)
    bpy.context.scene.camera = camera
    return camera


def configure_render(width: int, height: int, samples: int, *, engine: str = "CYCLES") -> None:
    scene = bpy.context.scene
    scene.render.engine = engine
    scene.render.resolution_x = width
    scene.render.resolution_y = height
    scene.render.resolution_percentage = 100
    scene.render.film_transparent = False
    if engine == "CYCLES":
        scene.cycles.samples = samples
        scene.cycles.use_denoising = True
        scene.cycles.max_bounces = 8
        scene.cycles.transparent_max_bounces = 4
    # Filmic-style highlight rolloff; without it daylight through a window
    # clips to flat white and the interior reads as blown out.
    try:
        scene.view_settings.view_transform = "AgX"
        scene.view_settings.look = "AgX - Medium Contrast"
    except TypeError:
        scene.view_settings.view_transform = "Filmic"


def main(argv: list[str] | None = None) -> int:
    raw = argv if argv is not None else sys.argv
    if "--" in raw:
        raw = raw[raw.index("--") + 1:]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--canvas", type=Path, required=True)
    parser.add_argument("--hdri", type=Path, required=True)
    parser.add_argument("--out", type=Path)
    parser.add_argument("--still", type=Path)
    parser.add_argument("--samples", type=int, default=48)
    parser.add_argument("--width", type=int, default=1280)
    parser.add_argument("--height", type=int, default=800)
    parser.add_argument("--sun", type=float, default=3.0)
    parser.add_argument("--sky", type=float, default=1.0)
    parser.add_argument("--interior", type=str, help="storey node to stand inside, e.g. storey_a1")
    parser.add_argument("--yaw", type=float, default=0.0)
    parser.add_argument("--eye", type=float, default=1.562)
    parser.add_argument("--casework", action="store_true",
                        help="build cabinetry from every traced counter run")
    parser.add_argument("--rooms", action="store_true",
                        help="vary floor finish by room kind, read from the sheets")
    parser.add_argument("--tile", type=float, default=1.0,
                        help="metres per texture tile for the cube projection")
    args = parser.parse_args(raw)

    for required in (args.canvas, args.hdri):
        if not required.is_file():
            print(f"Missing input: {required}")
            return 1

    _reset()
    bpy.ops.import_scene.gltf(filepath=str(args.canvas))
    unwrapped = unwrap_by_size(args.tile)
    applied = apply_looks()

    finishes: dict[str, int] = {}
    if args.rooms:
        manifest_path = args.canvas.with_name("manifest.json")
        if manifest_path.is_file():
            manifest = json.loads(manifest_path.read_text())
            block = manifest.get("rooms")
            envelope = manifest.get("datum_pdf_origin")
            if block and envelope:
                finishes = apply_room_finishes(block, tuple(envelope))

    casework = 0
    if args.casework:
        manifest_path = args.canvas.with_name("manifest.json")
        if manifest_path.is_file():
            entries = json.loads(manifest_path.read_text()).get("casework", [])
            if entries:
                for node in {e["node"] for e in entries}:
                    _drop_faces(node, "MARBLE")
                    _drop_faces(node, "APPLIANCE")
                casework = build_casework(entries)

    build_world(args.hdri, strength=args.sky)
    add_sun(strength=args.sun)

    print(f"canvas    {args.canvas.name}")
    print(f"unwrapped {unwrapped} meshes at {args.tile} m per tile")
    if casework:
        print(f"casework  {casework} runs built as cabinetry")
    if finishes:
        print("finishes  " + ", ".join(f"{k}:{v} faces" for k, v in sorted(finishes.items())))
    print(f"materials {', '.join(f'{k} -> {v}' for k, v in sorted(applied.items()))}")

    if args.still:
        if args.interior:
            add_interior_camera(args.interior, eye_metres=args.eye, yaw_degrees=args.yaw)
        else:
            add_dollhouse_camera()
        configure_render(args.width, args.height, args.samples)
        bpy.context.scene.render.filepath = str(args.still)
        bpy.ops.render.render(write_still=True)
        print(f"still     {args.still}")

    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        bpy.ops.export_scene.gltf(
            filepath=str(args.out),
            export_format="GLB",
            export_apply=True,
        )
        print(f"glb       {args.out} ({args.out.stat().st_size:,} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
