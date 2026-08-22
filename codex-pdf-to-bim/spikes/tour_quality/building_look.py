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
    build_world(args.hdri, strength=args.sky)
    add_sun(strength=args.sun)

    print(f"canvas    {args.canvas.name}")
    print(f"unwrapped {unwrapped} meshes at {args.tile} m per tile")
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
