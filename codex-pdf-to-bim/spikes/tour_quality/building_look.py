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
import time
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


def painted(source: Path, *, saturation: float, value: float) -> Path:
    """Grade a photographed texture into paint, on disk, once.

    This has to happen to the image file and not in the node tree. A Hue/
    Saturation node is a node graph, and glTF has no node graphs -- the
    exporter drops it without complaint and ships the photograph, so the bake
    lights walls that the browser then paints a different colour. The same trap
    that made the procedural materials export as nothing, and the same trap
    that has been quietly discarding the tints in `image_maps` all along.

    The result is cached next to the asset it derives from, and is reproducible
    from a committed input by construction.
    """
    import numpy as np

    out = source.parent / "derived" / f"{source.stem}_s{saturation:.2f}_v{value:.2f}.png"
    if out.is_file():
        return out

    original = bpy.data.images.load(str(source), check_existing=False)
    width, height = original.size
    buffer = np.empty(width * height * original.channels, dtype=np.float32)
    original.pixels.foreach_get(buffer)
    pixels = buffer.reshape(-1, original.channels)

    # These are the stored values, not linear ones: for an 8-bit image Blender
    # hands back the bytes over 255 without decoding them, so the grade is in
    # display space and the multiplier is smaller than a linear one would be.
    # Treating them as linear multiplied an already-bright wall past white.
    rgb = pixels[:, :3]
    grey = rgb.mean(axis=1, keepdims=True)
    rgb[:] = np.clip((grey + (rgb - grey) * saturation) * value, 0.0, 1.0)
    if original.channels > 3:
        pixels[:, 3] = 1.0

    out.parent.mkdir(parents=True, exist_ok=True)
    graded = bpy.data.images.new(out.stem, width, height, alpha=False)
    graded.colorspace_settings.name = "sRGB"
    graded.pixels.foreach_set(pixels.reshape(-1))
    graded.filepath_raw = str(out)
    graded.file_format = "PNG"
    graded.save()
    bpy.data.images.remove(original)
    bpy.data.images.remove(graded)
    return out


def image_maps(
    tree,
    shader,
    *,
    colour: Path,
    roughness: Path | None = None,
    normal: Path | None = None,
    scale: float = 1.0,
    tint: tuple[float, float, float, float] | None = None,
    saturation: float | None = None,
    value: float | None = None,
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
    colour_out = base.outputs["Color"]
    if tint:
        multiply = tree.nodes.new("ShaderNodeMixRGB")
        multiply.blend_type = "MULTIPLY"
        multiply.inputs["Fac"].default_value = 1.0
        multiply.inputs["Color2"].default_value = tint
        tree.links.new(colour_out, multiply.inputs["Color1"])
        colour_out = multiply.outputs["Color"]
    if saturation is not None or value is not None:
        # A photographed surface is not the same thing as a painted one. The
        # texture is kept for its grain and pulled towards the colour the
        # material actually is -- which for interior plaster is a light
        # near-neutral, not the mid-tan the photograph was shot on.
        grade = tree.nodes.new("ShaderNodeHueSaturation")
        grade.inputs["Saturation"].default_value = 1.0 if saturation is None else saturation
        grade.inputs["Value"].default_value = 1.0 if value is None else value
        tree.links.new(colour_out, grade.inputs["Color"])
        colour_out = grade.outputs["Color"]
    tree.links.new(colour_out, shader.inputs["Base Color"])

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
        # The photograph averages a mid-tan -- around a third of the light it
        # receives -- and interior paint reflects three-quarters of it. Left as
        # shot, every room came back brown and starved of bounce, because a
        # dark wall is also a wall that passes almost nothing on. Nearly all
        # the photograph's colour goes too: seventeen points of saturation
        # between channels reads as tan on a large flat surface, and interior
        # walls here are white. Graded on
        # disk rather than in the node tree, because a node tree does not
        # survive the export and the bake would then disagree with the render.
        colour=painted(ASSETS / "beige_wall_001_diff_1k.jpg", saturation=0.12, value=1.54),
        roughness=ASSETS / "beige_wall_001_rough_1k.jpg",
        normal=ASSETS / "beige_wall_001_nor_gl_1k.jpg",
        scale=1.6,
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


def painted_trim() -> bpy.types.Material:
    """Whiter and slightly glossier than the cabinets: it is joinery, not a wall."""
    material = bpy.data.materials.new("HV_LOOK_TRIM")
    _tree, shader = _clear_nodes(material)
    shader.inputs["Base Color"].default_value = (0.918, 0.911, 0.894, 1.0)
    shader.inputs["Roughness"].default_value = 0.33
    return material


def glazing() -> bpy.types.Material:
    """Glass as a blended surface, not as transmission.

    Real transmission would export as KHR_materials_transmission and force the
    browser into a separate render pass for every one of the thirty-six windows
    in this house. A mostly transparent, very smooth surface picks up the sky
    from the environment map and reads as glass at a fraction of the cost.
    """
    material = bpy.data.materials.new("HV_LOOK_GLASS")
    _tree, shader = _clear_nodes(material)
    shader.inputs["Base Color"].default_value = (0.74, 0.80, 0.86, 1.0)
    shader.inputs["Roughness"].default_value = 0.04
    shader.inputs["Metallic"].default_value = 0.0
    # The exporter reads alphaMode off this socket: anything between 0 and 1
    # becomes BLEND.
    shader.inputs["Alpha"].default_value = 0.17
    return material


# Which stock pieces belong in which kind of room. Bathrooms, cupboards and
# circulation get nothing but a light: furniture there would be invention, not
# staging. Nothing here is measured -- it is declared provisional in the
# manifest, like every other finish.
ROOM_FURNITURE: dict[str, tuple[str, ...]] = {
    "living": ("modern_coffee_table_01", "modern_arm_chair_01"),
    "dining": ("modern_arm_chair_01",),
    "bedroom": ("modern_arm_chair_01",),
    "office": ("modern_arm_chair_01",),
}
CEILING_LAMP = "modern_ceiling_lamp_01"
LAMP_ROOM_KINDS = frozenset({
    "living", "dining", "bedroom", "office", "kitchen", "bathroom", "utility",
})


def _room_clearance(owner: list[int], columns: int, rows: int) -> list[int]:
    """How many cells each cell is from the edge of its own room.

    A chamfer transform in two passes. It answers the only question placement
    really has -- where is there room to stand something -- without needing to
    know anything about the shape of the room, which on a traced plan is
    frequently not a rectangle.
    """
    far = columns + rows
    distance = [0] * (columns * rows)
    for y in range(rows):
        base = y * columns
        for x in range(columns):
            index = base + x
            if owner[index] < 0:
                continue
            best = far
            for nx, ny in ((x - 1, y), (x, y - 1)):
                if 0 <= nx < columns and 0 <= ny < rows and owner[ny * columns + nx] == owner[index]:
                    best = min(best, distance[ny * columns + nx])
                else:
                    best = 0
            distance[index] = best + 1
    for y in range(rows - 1, -1, -1):
        base = y * columns
        for x in range(columns - 1, -1, -1):
            index = base + x
            if owner[index] < 0:
                continue
            best = distance[index]
            for nx, ny in ((x + 1, y), (x, y + 1)):
                if 0 <= nx < columns and 0 <= ny < rows and owner[ny * columns + nx] == owner[index]:
                    best = min(best, distance[ny * columns + nx] + 1)
                else:
                    best = min(best, 1)
            distance[index] = best
    return distance


def _load_piece(assets: Path, name: str):
    """Import one stock model once and return its objects, hidden as a library."""
    path = assets / "models" / name / f"{name}_1k.gltf"
    if not path.is_file():
        return None
    before = set(bpy.data.objects)
    bpy.ops.import_scene.gltf(filepath=str(path))
    arrived = [obj for obj in bpy.data.objects if obj not in before]
    for obj in arrived:
        obj.hide_render = True
        obj.hide_viewport = True
    return [obj for obj in arrived if obj.type == "MESH"]


def _place_piece(pieces, name: str, location, yaw: float, parent):
    """Copy an imported piece into the room, sharing its mesh and materials.

    The copy carries the original's own world matrix, turned and moved into
    place. Reading `location` alone would lose whatever transform the imported
    model arrived with -- and glTF models routinely arrive parented to an empty
    that holds the whole of it.
    """
    from mathutils import Matrix

    placement = Matrix.Translation(location) @ Matrix.Rotation(yaw, 4, "Z")
    made = []
    for index, source in enumerate(pieces):
        copy = source.copy()
        copy.data = source.data
        copy.name = f"HV_FURN_{name}_{index:02d}"
        copy.hide_render = False
        copy.hide_viewport = False
        copy.parent = None
        bpy.context.collection.objects.link(copy)
        copy.matrix_world = placement @ source.matrix_world
        if parent is not None:
            world = copy.matrix_world.copy()
            copy.parent = parent
            copy.matrix_world = world
        made.append(copy)
    return made


def build_furniture(rooms_block: dict, datum_origin, storeys: list[dict], assets: Path) -> dict:
    """Stand a few stock pieces in the rooms that would have them.

    Empty rooms are the last thing that stops a lit, textured, glazed model
    reading as a house: there is nothing in them at human scale to judge the
    room against. Placement is derived, not authored -- the clearance transform
    finds the most open point in each room, whatever shape the trace gave it --
    and what goes there is decided by the room's kind, exactly as the floor
    finish and the worktop already are.
    """
    import math

    FT = 0.3048
    POINTS_PER_FOOT = 18.0
    cell = rooms_block["cell_points"]
    datum_x, datum_y1 = datum_origin
    elevations = {s["node"]: s for s in storeys}

    library: dict[str, list] = {}

    def pieces_for(name: str):
        if name not in library:
            library[name] = _load_piece(assets, name) or []
        return library[name]

    placed: dict[str, int] = {}

    for storey in rooms_block["storeys"]:
        node = storey["node"]
        parent = bpy.data.objects.get(node)
        elevation = elevations.get(node)
        if elevation is None:
            continue
        base = elevation["base_meters"]
        ceiling = base + elevation["ceiling_meters"]

        columns, rows = storey["columns"], storey["rows"]
        owner = [-1] * (columns * rows)
        for who, row, first, last in storey["runs"]:
            line = row * columns
            for column in range(first, last + 1):
                owner[line + column] = who
        clearance = _room_clearance(owner, columns, rows)
        origin_x, origin_y = storey["origin_pdf"]

        best: dict[int, tuple[int, int, int]] = {}
        for index, room in enumerate(clearance):
            if room <= 0:
                continue
            who = owner[index]
            if who < 0:
                continue
            if who not in best or room > best[who][0]:
                best[who] = (room, index % columns, index // columns)

        metres_per_cell = cell / POINTS_PER_FOOT * FT
        for who, (room_clearance, column, row) in sorted(best.items()):
            room = storey["rooms"][who]
            kind = room["kind"]
            east = (origin_x + (column + 0.5) * cell - datum_x) / POINTS_PER_FOOT * FT
            north = (datum_y1 - (origin_y + (row + 0.5) * cell)) / POINTS_PER_FOOT * FT
            open_radius = room_clearance * metres_per_cell

            if kind in LAMP_ROOM_KINDS and room["area_square_feet"] >= 30.0:
                lamp = pieces_for(CEILING_LAMP)
                if lamp:
                    _place_piece(lamp, f"{node}_{who:02d}_lamp",
                                 (east, north, ceiling - 0.42), 0.0, parent)
                    placed["lamp"] = placed.get("lamp", 0) + 1

            # Only stand something on the floor where a person could stand.
            if open_radius < 0.75:
                continue
            for offset, name in enumerate(ROOM_FURNITURE.get(kind, ())):
                pieces = pieces_for(name)
                if not pieces:
                    continue
                angle = math.radians(35.0 + offset * 150.0)
                reach = min(open_radius - 0.45, 0.9) * offset
                spot = (east + math.cos(angle) * reach, north + math.sin(angle) * reach, base)
                _place_piece(pieces, f"{node}_{who:02d}_{name}", spot,
                             angle + math.pi, parent)
                placed[name] = placed.get(name, 0) + 1

    # The imported originals are a library, not part of the house. Left behind
    # they would export -- glTF export does not skip hidden objects -- and pile
    # every stock model on top of itself at the world origin.
    for pieces in library.values():
        for source in pieces:
            root = source
            while root.parent is not None:
                root = root.parent
            for obj in [root, *root.children_recursive]:
                if obj.name in bpy.data.objects:
                    bpy.data.objects.remove(obj, do_unlink=True)

    return placed


def _clear_of_rays(obj):
    """Let light through this object when Cycles bakes occlusion.

    The occlusion bake treats every surface as an occluder, so a pane of glass
    would darken the room behind the window it was put there to open up. The
    browser still draws it; only the bake looks through it.
    """
    obj.visible_diffuse = False
    obj.visible_glossy = False
    obj.visible_shadow = False
    return obj


def build_openings(entries: list[dict]) -> int:
    """Line every traced opening and glaze the windows.

    A hole cut in a wall reads as a hole. What makes it a window is the reveal
    around it, the sill it sits on and the glass in it -- and every one of
    those is derived from the void the trace already cut, so a window in a
    bathroom is built exactly like a window in a bedroom.

    Nothing here closes a door: the leaves are left off deliberately, because a
    walkable tour whose doors are shut is a tour of one room.
    """
    trim = painted_trim()
    glass = glazing()
    made = 0

    for entry in entries:
        width_x, width_y, height = entry["size"]
        cx, cy, cz = entry["centre"]
        storey = bpy.data.objects.get(entry.get("node", ""))
        along_x = entry["run_axis"] == "X"
        along = width_x if along_x else width_y
        through = width_y if along_x else width_x
        if along < 0.25 or height < 0.4 or through < 0.05:
            continue

        board = min(0.06, height / 6.0, along / 6.0)
        reveal = max(0.02, through * 0.9)

        def lining(name, size, location):
            _box(f"HV_OPEN_{entry['id']}_{name}", size, location, trim, parent=storey)

        # Head and jambs, lining the thickness of the wall.
        head_z = cz + height / 2.0 - board / 2.0
        foot_z = cz - height / 2.0 + board / 2.0
        if along_x:
            lining("HEAD", (along, reveal, board), (cx, cy, head_z))
            for side in (-1.0, 1.0):
                lining("JAMB" + ("A" if side < 0 else "B"),
                       (board, reveal, height - board * 2),
                       (cx + side * (along / 2.0 - board / 2.0), cy, cz))
        else:
            lining("HEAD", (reveal, along, board), (cx, cy, head_z))
            for side in (-1.0, 1.0):
                lining("JAMB" + ("A" if side < 0 else "B"),
                       (reveal, board, height - board * 2),
                       (cx, cy + side * (along / 2.0 - board / 2.0), cz))

        if entry["kind"] == "window":
            # A sill wide enough to overhang the reveal on both faces, because
            # which face is the room is not something this pass knows.
            sill = through + 0.06
            if along_x:
                lining("SILL", (along + 0.08, sill, board * 0.8), (cx, cy, foot_z))
                _clear_of_rays(_box(f"HV_OPEN_{entry['id']}_GLASS",
                                    (along - board * 2.2, 0.014, height - board * 2.4),
                                    (cx, cy, cz), glass, parent=storey))
                lining("MUNTIN", (0.028, 0.024, height - board * 2.4), (cx, cy, cz))
            else:
                lining("SILL", (sill, along + 0.08, board * 0.8), (cx, cy, foot_z))
                _clear_of_rays(_box(f"HV_OPEN_{entry['id']}_GLASS",
                                    (0.014, along - board * 2.2, height - board * 2.4),
                                    (cx, cy, cz), glass, parent=storey))
                lining("MUNTIN", (0.024, 0.028, height - board * 2.4), (cx, cy, cz))
        made += 1

    return made


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

        # Everything built here hangs off the storey it stands on. Cabinets are
        # exported as their own glTF nodes, and left at the top level they stay
        # on screen when you switch to another floor -- a kitchen run hanging in
        # the air over the basement. Parenting nests them inside the storey node
        # instead, so hiding the floor hides its casework with it.
        storey = bpy.data.objects.get(entry.get("node", ""))

        yaw = math.radians(entry["facing_degrees"])
        top_thickness = 0.038
        carcass_height = max(0.2, height - top_thickness)
        toe = 0.09

        # Carcass, held off the floor by a toe kick.
        _box(f"HV_CASE_{entry['id']}_BODY",
             (width_x - 0.01, width_y - 0.01, carcass_height - toe),
             (cx, cy, base_z + toe + (carcass_height - toe) / 2.0), cabinet,
             parent=storey)
        _box(f"HV_CASE_{entry['id']}_KICK",
             (width_x - 0.09, width_y - 0.09, toe),
             (cx, cy, base_z + toe / 2.0), cabinet, parent=storey)

        # Worktop, slightly proud of the carcass on every side.
        top_material = tops.get(entry["room_kind"], default_top)
        _box(f"HV_CASE_{entry['id']}_TOP",
             (width_x + 0.024, width_y + 0.024, top_thickness),
             (cx, cy, base_z + carcass_height + top_thickness / 2.0), top_material,
             parent=storey)

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
            _box(f"HV_CASE_{entry['id']}_DOOR{index}", door_size, placed, cabinet,
                 parent=storey)
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
                 (placed[0] + nudge[0], placed[1] + nudge[1], placed[2]), cabinet,
                 parent=storey)
        made += 1
    return made


BAKE_UV = "HV_BAKE"


def bake_lighting(*, mode: str = "light", size: int = 2048, samples: int = 16,
                  distance: float = 1.4, reuse: Path | None = None,
                  reuse_scale: float = 1.0) -> tuple[int, float]:
    """Bake what Cycles knows about light into a texture the browser can read.

    This is the only way any of Blender's rendering reaches the page. glTF
    carries geometry, images and PBR factors and nothing else -- no node
    graphs, no lights, no bounce -- and a real-time renderer has no global
    illumination of its own, so it lights an inside corner exactly as brightly
    as an open wall and the whole interior reads as paper.

    Two modes, and the difference matters:

    ``occlusion`` bakes ambient occlusion and rides out through
    ``occlusionTexture``, which dims the ambient term. It is cheap, it is
    honest, and it is only a contact shadow -- the room is still lit by a
    uniform sky.

    ``light`` bakes the diffuse irradiance itself: sun, sky and every bounce
    between them, which is the actual Cycles solution for this house at this
    time of day. It travels as ``emissiveTexture`` because that is the one
    RGB slot in glTF core that survives with a UV set of its own -- the
    occlusion slot gets packed into the red channel of an ORM texture
    alongside roughness and metallic, which would shred a colour lightmap. The
    browser promotes it back to a three.js ``lightMap`` on load.

    Baked light is linear and goes well above 1.0 in sunlight, so the atlas is
    normalised to fit an 8-bit image and the divisor is returned. The browser
    multiplies it back in; without that the sunlit half of every room clips to
    white.
    """
    meshes = [obj for obj in bpy.data.objects if obj.type == "MESH" and len(obj.data.polygons)]
    if not meshes:
        return 0, 1.0

    unwrap_started = time.monotonic()
    bpy.ops.object.select_all(action="DESELECT")
    for obj in meshes:
        layers = obj.data.uv_layers
        if not layers:
            continue
        layers[0].active_render = True
        bake_layer = layers.get(BAKE_UV) or layers.new(name=BAKE_UV)
        bake_layer.active = True
        obj.select_set(True)
    bpy.context.view_layer.objects.active = meshes[0]

    # Pack every selected object into one square, and pack it *hard*. Baking
    # is expensive and packing is free, so this is where the resolution comes
    # from: smart project's own packer left the atlas ninety-six per cent empty
    # -- twelve texels to the metre, which renders as blocks rather than as
    # light. Unwrapping with no margin, levelling the texel density by real
    # area so a wall gets more of the atlas than a drawer edge, and repacking
    # with concave island shapes takes coverage to forty per cent and thirty-
    # eight texels to the metre. Same second of work, three times the
    # resolution; buying that with image size instead would have cost nine
    # times the bake.
    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.mesh.select_all(action="SELECT")
    bpy.ops.uv.smart_project(
        angle_limit=1.4,
        island_margin=0.0,
        correct_aspect=False,
        scale_to_bounds=False,
    )
    bpy.ops.uv.average_islands_scale()
    bpy.ops.uv.pack_islands(rotate=True, margin=0.0006, scale=True,
                            shape_method="CONCAVE")
    bpy.ops.object.mode_set(mode="OBJECT")
    print(f"          unwrap took {time.monotonic() - unwrap_started:.0f}s", flush=True)

    lit = mode == "light"
    if reuse is not None:
        # The unwrap above is deterministic on identical geometry, so an atlas
        # baked from this same build can be loaded straight back in. That is
        # worth having: baking is measured in hours and everything downstream
        # of it -- denoising, grading, export -- is measured in seconds, and
        # they should not be chained to each other.
        image = bpy.data.images.load(str(reuse), check_existing=False)
        image.colorspace_settings.name = "sRGB"
        scale = reuse_scale
    else:
        image = None

    if image is None:
        image = bpy.data.images.new(
            "HV_LIGHTMAP" if lit else "HV_OCCLUSION", width=size, height=size,
            alpha=False, float_buffer=lit,
        )
        # Occlusion is data. Baked light is colour, and wants the precision
        # that sRGB encoding buys an 8-bit image in the shadows.
        image.colorspace_settings.name = "sRGB" if lit else "Non-Color"

    # The bake target is whichever image texture node is active in each
    # material, so every material needs one and it has to read the bake UVs --
    # not the render UVs, which tile and would fold the atlas over itself.
    materials = {slot.material for obj in meshes for slot in obj.material_slots if slot.material}
    targets = []
    for material in materials:
        tree = material.node_tree
        uv_node = tree.nodes.new("ShaderNodeUVMap")
        uv_node.uv_map = BAKE_UV
        uv_node.location = (-900, -600)
        texture = tree.nodes.new("ShaderNodeTexImage")
        texture.image = image
        texture.location = (-700, -600)
        tree.links.new(uv_node.outputs["UV"], texture.inputs["Vector"])
        tree.nodes.active = texture
        texture.select = True
        targets.append((material, texture))

    scene = bpy.context.scene
    scene.render.engine = "CYCLES"
    scene.cycles.samples = samples
    scene.cycles.use_denoising = True
    # Cycles charges by covered texel times samples, and packing the atlas
    # properly multiplied the covered texels by ten. These three settings buy
    # that back. Adaptive sampling stops paying for texels that have already
    # converged, which on a diffuse bake is most of them; fast GI approximates
    # the deep bounces that contribute least; and four bounces is enough for a
    # room lit through a window, where the light that matters has arrived by
    # the second or third.
    scene.cycles.use_adaptive_sampling = True
    # A loose threshold and a floor of three samples left dark interiors
    # blotchy, and no spatial filter can tell low-frequency Monte Carlo
    # variance from a real light gradient -- 5x5, 7x7 and 9x9 medians all
    # plateaued at the same residue. Adaptive sampling only ever saves time on
    # texels that have converged, so tightening it costs nothing where the
    # answer was already clean.
    scene.cycles.adaptive_threshold = 0.01
    scene.cycles.adaptive_min_samples = 0
    scene.cycles.max_bounces = 4
    scene.cycles.diffuse_bounces = 4
    # Clamp indirect fireflies. A handful of extreme samples dominate the
    # variance of an interior lit through a window, and clamping them is far
    # cheaper than out-sampling them.
    scene.cycles.sample_clamp_indirect = 4.0
    # Fast GI approximates the deep bounces, which biases exactly the soft
    # indirect light this bake exists to capture, and adds variance doing it.
    try:
        scene.cycles.use_fast_gi = False
    except AttributeError:
        pass
    scene.render.bake.use_clear = True
    scene.render.bake.use_selected_to_active = False
    scene.render.bake.margin = max(2, size // 256)

    if reuse is not None:
        for material, texture in targets:
            _wire_bake(material, texture, lit=lit)
        for obj in meshes:
            obj.select_set(False)
        return len(targets), scale

    started = time.monotonic()
    if lit:
        scene.cycles.bake_type = "DIFFUSE"
        # Direct and indirect but *not* colour: the albedo is already in the
        # base colour map, and multiplying it in twice turns oak into mud.
        scene.render.bake.use_pass_direct = True
        scene.render.bake.use_pass_indirect = True
        scene.render.bake.use_pass_color = False
        bpy.ops.object.bake(type="DIFFUSE")
    else:
        scene.cycles.bake_type = "AO"
        if scene.world is not None:
            # How far a surface looks for something blocking it. A metre and a
            # bit darkens corners and the underside of a worktop without
            # turning a whole small room grey.
            scene.world.light_settings.distance = distance
        bpy.ops.object.bake(type="AO")

    print(f"          bake took {time.monotonic() - started:.0f}s", flush=True)

    scale = 1.0
    if lit:
        _denoise_atlas(image)
        scale = _normalise(image)
    image.pack()

    for material, texture in targets:
        _wire_bake(material, texture, lit=lit)

    for obj in meshes:
        obj.select_set(False)
    return len(targets), scale


def _wire_bake(material, texture, *, lit: bool) -> None:
    """Put a baked atlas where the exporter will actually pick it up."""
    tree = material.node_tree
    if lit:
        shader = next(
            (n for n in tree.nodes if n.type in ("BSDF_PRINCIPLED", "EMISSION")), None
        )
        if shader is None:
            return
        socket = "Emission Color" if "Emission Color" in shader.inputs else "Color"
        tree.links.new(texture.outputs["Color"], shader.inputs[socket])
        if "Emission Strength" in shader.inputs:
            shader.inputs["Emission Strength"].default_value = 1.0
        return

    # The exporter only writes occlusionTexture when it finds the glTF settings
    # group; a stray image texture node is otherwise ignored entirely.
    from io_scene_gltf2.blender.com.material_helpers import (
        create_settings_group,
        get_gltf_node_name,
    )

    group_name = get_gltf_node_name()
    group = bpy.data.node_groups.get(group_name) or create_settings_group(group_name)
    settings = tree.nodes.new("ShaderNodeGroup")
    settings.location = (-400, -600)
    settings.node_tree = group
    tree.links.new(texture.outputs["Color"], settings.inputs["Occlusion"])


def _denoise_atlas(image) -> None:
    """Take the Monte Carlo noise out of a baked atlas.

    Cycles denoising is a *render* setting: `scene.render.bake` has no
    equivalent and the bake operator does not denoise, so a baked atlas comes
    back exactly as noisy as its sample count leaves it. Blender 5's compositor
    could run OpenImageDenoise over it, but it needs a GPU context this build
    has none of.

    A median is the right filter for what is actually there. Path-traced
    undersampling leaves salt and pepper -- isolated texels far from their
    neighbours -- which a median removes outright while a mean would only
    spread. The gentle blur afterwards is what a lightmap can afford, being
    low-frequency by nature; the albedo carries all the detail.

    Unlit gutters are held at black so nothing bleeds between islands packed
    next to each other.
    """
    import numpy as np

    width, height = image.size
    channels = image.channels
    buffer = np.empty(width * height * channels, dtype=np.float32)
    image.pixels.foreach_get(buffer)
    pixels = buffer.reshape(height, width, channels)
    lit = pixels[:, :, :3].max(axis=2) > (2.0 / 255.0)

    for channel in range(3):
        plane = pixels[:, :, channel]
        stack = np.stack([
            np.roll(np.roll(plane, dy, axis=0), dx, axis=1)
            for dy in (-1, 0, 1) for dx in (-1, 0, 1)
        ])
        plane[:] = np.median(stack, axis=0)
        del stack
        # Separable three-tap blur, once across and once down.
        plane[:] = (np.roll(plane, 1, axis=1) + 2 * plane + np.roll(plane, -1, axis=1)) / 4
        plane[:] = (np.roll(plane, 1, axis=0) + 2 * plane + np.roll(plane, -1, axis=0)) / 4

    pixels[:, :, :3] *= lit[..., None]
    image.pixels.foreach_set(pixels.reshape(-1))
    image.update()


def _normalise(image) -> float:
    """Scale a baked light atlas into 0..1 and return what it was divided by.

    Sunlight is not bounded by one. Clamping it instead of scaling it would
    flatten every lit surface to the same white, which is precisely the look
    the bake is meant to replace.
    """
    import numpy as np

    count = image.size[0] * image.size[1] * image.channels
    buffer = np.empty(count, dtype=np.float32)
    image.pixels.foreach_get(buffer)
    pixels = buffer.reshape(-1, image.channels)
    rgb = pixels[:, :3]

    live = rgb[rgb > 0.0]
    peak = float(np.percentile(live, 99.6)) if live.size else 1.0
    scale = max(peak, 1e-3)

    rgb /= scale
    np.clip(rgb, 0.0, 1.0, out=rgb)
    if image.channels > 3:
        pixels[:, 3] = 1.0
    image.pixels.foreach_set(pixels.reshape(-1))
    image.update()
    return round(scale, 4)


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
    # sys.argv[0] is this script. Blender passes its own arguments first and
    # separates ours with `--`; run as a plain script there is no separator.
    raw = argv if argv is not None else sys.argv[1:]
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
    parser.add_argument("--furniture", type=Path,
                        help="asset folder holding models/, to stage rooms with")
    parser.add_argument("--openings", action="store_true",
                        help="line every traced opening and glaze the windows")
    parser.add_argument("--bake", choices=("none", "occlusion", "light"), default="none",
                        help="bake contact shadow, or the whole Cycles lighting solution")
    parser.add_argument("--bake-size", type=int, default=2048)
    parser.add_argument("--bake-samples", type=int, default=16)
    parser.add_argument("--atlas", type=Path,
                        help="where to keep the baked atlas for later reuse")
    parser.add_argument("--reuse-lightmap", type=Path,
                        help="load an atlas baked earlier instead of baking again")
    parser.add_argument("--reuse-scale", type=float, default=1.0,
                        help="the scale that atlas was normalised by")
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

    openings = 0
    if args.openings:
        manifest_path = args.canvas.with_name("manifest.json")
        if manifest_path.is_file():
            entries = json.loads(manifest_path.read_text()).get("openings", [])
            if entries:
                openings = build_openings(entries)

    furniture: dict[str, int] = {}
    if args.furniture:
        manifest_path = args.canvas.with_name("manifest.json")
        if manifest_path.is_file():
            manifest = json.loads(manifest_path.read_text())
            block = manifest.get("rooms")
            envelope = manifest.get("datum_pdf_origin")
            storeys = manifest.get("storeys", [])
            if block and envelope and storeys:
                furniture = build_furniture(block, tuple(envelope), storeys, args.furniture)

    build_world(args.hdri, strength=args.sky)
    add_sun(strength=args.sun)

    # Last, because it bakes the geometry as it finally stands -- casework,
    # joinery, furniture and room finishes included.
    baked, light_scale = 0, 1.0
    if args.bake != "none":
        baked, light_scale = bake_lighting(
            mode=args.bake, size=args.bake_size, samples=args.bake_samples,
            reuse=args.reuse_lightmap, reuse_scale=args.reuse_scale,
        )

    print(f"canvas    {args.canvas.name}")
    print(f"unwrapped {unwrapped} meshes at {args.tile} m per tile")
    if casework:
        print(f"casework  {casework} runs built as cabinetry")
    if openings:
        print(f"openings  {openings} lined, windows glazed")
    if furniture:
        print("furniture " + ", ".join(f"{k}:{v}" for k, v in sorted(furniture.items())))
    if finishes:
        print("finishes  " + ", ".join(f"{k}:{v} faces" for k, v in sorted(finishes.items())))
    if baked and args.bake == "light" and args.atlas and args.reuse_lightmap is None:
        # Keep the atlas somewhere it is not served. Baking is measured in
        # hours and everything after it in seconds, so the two should not be
        # chained: grading, tone and export can all be re-run against this
        # without paying for the bake again. It is deliberately not beside the
        # GLB, where the browser would never ask for it and every deployment
        # would carry it anyway.
        atlas = bpy.data.images.get("HV_LIGHTMAP")
        if atlas is not None:
            args.atlas.parent.mkdir(parents=True, exist_ok=True)
            atlas.filepath_raw = str(args.atlas)
            atlas.file_format = "PNG"
            atlas.save()
            print(f"atlas     kept at {args.atlas} (scale {light_scale})")

    if baked:
        print(f"bake      {args.bake} into {baked} materials at {args.bake_size}px"
              + (f", scaled by {light_scale}" if args.bake == "light" else ""))
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
        # Cull back faces. Blender renders both sides by default and writes
        # doubleSided into the glTF, which costs the browser every wall twice
        # and, worse, lets the far side of a wall shade as if it were lit --
        # a solid box has no inside to look at.
        for material in bpy.data.materials:
            material.use_backface_culling = True

        args.out.parent.mkdir(parents=True, exist_ok=True)
        bpy.ops.export_scene.gltf(
            filepath=str(args.out),
            export_format="GLB",
            export_apply=True,
            # Every source map is already a JPEG; a baked occlusion atlas as
            # lossless PNG costs more than the rest of the model put together.
            export_image_format="JPEG",
            export_jpeg_quality=82,
        )
        print(f"glb       {args.out} ({args.out.stat().st_size:,} bytes)")

        # Point the manifest at the finished model, keeping the canvas beside it.
        # The canvas is what the corner measurement opens, and this export is
        # not a substitute for it: casework replaces the plain counter solids,
        # so its corners no longer match the trace by construction.
        manifest_path = args.out.with_name("manifest.json")
        if manifest_path.is_file():
            manifest = json.loads(manifest_path.read_text())
            artifact = manifest.setdefault("artifact", {})
            artifact.setdefault("canvas_glb", artifact.get("glb"))
            artifact["glb"] = args.out.name
            artifact["total_browser_bytes"] = args.out.stat().st_size
            # How the baked lighting was scaled to fit an 8-bit image. The
            # browser multiplies it back in; without it every sunlit surface
            # renders at the same clipped white.
            if args.bake == "light":
                artifact["lightmap"] = {"carried_as": "emissive", "scale": light_scale}
            else:
                artifact.pop("lightmap", None)
            manifest_path.write_text(json.dumps(manifest, indent=2) + "\n")
            print(f"manifest  now serves {args.out.name}, canvas kept as "
                  f"{artifact['canvas_glb']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
