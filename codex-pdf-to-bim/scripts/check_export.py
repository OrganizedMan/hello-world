"""Open the exported GLB and check it is what the look pass meant to build.

Three failures cost most of a day between them, and all three were visible in
the export and invisible in the source: a material grade that lives in a node
tree does not survive glTF and is dropped without a warning; a lightmap atlas
can be ninety-six per cent empty and still export cleanly; and a texture graded
in the wrong colour space can come back pure white. None of them raise an
error. All of them are one read of the artifact away.

    uv run python scripts/check_export.py <glb> [--albedo NAME=R,G,B[:tol]]
"""

from __future__ import annotations

import argparse
import io
import json
import struct
import sys
from pathlib import Path


def read_glb(path: Path) -> tuple[dict, bytes]:
    raw = path.read_bytes()
    if raw[:4] != b"glTF":
        raise SystemExit(f"{path} is not a GLB")
    length = struct.unpack_from("<I", raw, 12)[0]
    return json.loads(raw[20:20 + length]), raw[20 + length + 8:]


def image_bytes(gltf: dict, blob: bytes, index: int) -> bytes:
    view = gltf["bufferViews"][gltf["images"][index]["bufferView"]]
    start = view.get("byteOffset", 0)
    return blob[start:start + view["byteLength"]]


def mean_colour(data: bytes) -> tuple[float, float, float] | None:
    try:
        from PIL import Image
        import numpy as np
    except ImportError:
        return None
    pixels = np.asarray(Image.open(io.BytesIO(data)).convert("RGB"), dtype="float32")
    return tuple(round(float(v), 1) for v in pixels.reshape(-1, 3).mean(0))


def coverage(gltf: dict, blob: bytes) -> float | None:
    """What fraction of the second UV set's square any face actually lands on.

    An empty atlas is the difference between baked light and baked blocks, and
    it looks identical to a full one from outside the file.
    """
    try:
        import numpy as np
    except ImportError:
        return None

    def accessor(index: int):
        spec = gltf["accessors"][index]
        view = gltf["bufferViews"][spec["bufferView"]]
        start = view.get("byteOffset", 0) + spec.get("byteOffset", 0)
        kinds = {5121: np.uint8, 5123: np.uint16, 5125: np.uint32, 5126: np.float32}
        size = {"SCALAR": 1, "VEC2": 2, "VEC3": 3}[spec["type"]]
        flat = np.frombuffer(blob, dtype=kinds[spec["componentType"]],
                             count=spec["count"] * size, offset=start)
        return flat.reshape(-1, size) if size > 1 else flat

    total = 0.0
    for mesh in gltf.get("meshes", []):
        for primitive in mesh["primitives"]:
            if "TEXCOORD_1" not in primitive["attributes"] or "indices" not in primitive:
                continue
            uv = accessor(primitive["attributes"]["TEXCOORD_1"]).astype("float64")
            tri = accessor(primitive["indices"]).reshape(-1, 3)
            a, b, c = uv[tri[:, 0]], uv[tri[:, 1]], uv[tri[:, 2]]
            cross = (b[:, 0] - a[:, 0]) * (c[:, 1] - a[:, 1]) \
                - (c[:, 0] - a[:, 0]) * (b[:, 1] - a[:, 1])
            total += float(np.abs(cross).sum()) / 2
    return total


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("glb", type=Path)
    parser.add_argument("--albedo", action="append", default=[],
                        help="MATERIAL=R,G,B[:tol] -- mean sRGB the base colour map must have")
    parser.add_argument("--min-coverage", type=float, default=None,
                        help="fail when the lightmap atlas is emptier than this")
    args = parser.parse_args(argv)

    gltf, blob = read_glb(args.glb)
    materials = {m.get("name"): m for m in gltf.get("materials", [])}
    problems: list[str] = []

    print(f"{args.glb.name}: {len(materials)} materials, "
          f"{len(gltf.get('images', []))} images, {len(gltf.get('meshes', []))} meshes")

    baked = [name for name, m in materials.items() if "emissiveTexture" in m]
    print(f"  carrying baked light: {len(baked)} of {len(materials)}")

    if args.min_coverage is not None:
        area = coverage(gltf, blob)
        if area is None:
            problems.append("numpy is needed to measure atlas coverage")
        else:
            print(f"  lightmap atlas coverage: {area:.1%}")
            if area < args.min_coverage:
                problems.append(
                    f"atlas coverage {area:.1%} is below {args.min_coverage:.1%}: "
                    "the bake is mostly empty texels and will render as blocks"
                )

    for spec in args.albedo:
        name, _, wanted = spec.partition("=")
        wanted, _, tolerance = wanted.partition(":")
        target = [float(v) for v in wanted.split(",")]
        limit = float(tolerance) if tolerance else 12.0
        material = materials.get(name)
        if material is None:
            problems.append(f"no material named {name} in the export")
            continue
        texture = material.get("pbrMetallicRoughness", {}).get("baseColorTexture")
        if texture is None:
            problems.append(f"{name} has no base colour texture")
            continue
        source = gltf["textures"][texture["index"]]["source"]
        mean = mean_colour(image_bytes(gltf, blob, source))
        if mean is None:
            problems.append("Pillow is needed to read the base colour map")
            continue
        drift = max(abs(m - t) for m, t in zip(mean, target))
        print(f"  {name} base colour mean sRGB {mean} (wanted {target}, drift {drift:.1f})")
        if drift > limit:
            problems.append(
                f"{name} base colour is {mean}, not {target}: the grade did not survive "
                "the export -- glTF carries no node graphs"
            )

    for problem in problems:
        print(f"FAIL {problem}")
    return 1 if problems else 0


if __name__ == "__main__":
    raise SystemExit(main())
