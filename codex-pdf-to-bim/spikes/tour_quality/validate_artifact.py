"""Validate the HearthView tour-spike browser artifact without Blender."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import struct
from typing import Any

import trimesh

from spikes.tour_quality.scene_contract import (
    DIMENSION_TOLERANCE_METERS,
    EYE_HEIGHT_METERS,
    ISLAND_DEPTH_METERS,
    ISLAND_WIDTH_METERS,
    ROOM_DEPTH_METERS,
    SCENE_LABEL,
    SCHEMA,
    SPAN_METERS,
    build_scene_contract,
)


MAX_BROWSER_BYTES = 45_000_000
COORDINATE_RULE = "three_x=source_x;three_y=source_z;three_z=-source_y"
REQUIRED_SCENE_NODES = (
    "HV_ARCHITECTURE",
    "HV_CABINETRY",
    "HV_FURNITURE",
    "HV_LIGHTING",
    "HV_NAVIGATION",
    "HV_FLOOR",
    "HV_ISLAND_STRUCTURE",
    "HV_WALKABLE",
)
_EXPECTED_CONTRACT = build_scene_contract()
EXPECTED_WALKABLE = {
    "min_x": min(point[0] for point in _EXPECTED_CONTRACT.walkable_polygon),
    "max_x": max(point[0] for point in _EXPECTED_CONTRACT.walkable_polygon),
    "min_z": -max(point[1] for point in _EXPECTED_CONTRACT.walkable_polygon),
    "max_z": -min(point[1] for point in _EXPECTED_CONTRACT.walkable_polygon),
}
EXPECTED_BARRIERS = tuple(
    {
        "name": rectangle.name,
        "min_x": rectangle.min_x,
        "max_x": rectangle.max_x,
        "min_z": -rectangle.max_y,
        "max_z": -rectangle.min_y,
    }
    for rectangle in _EXPECTED_CONTRACT.collision_rectangles
)
EXPECTED_CAMERAS = tuple(
    {
        "name": camera.name,
        "position": [camera.position[0], camera.position[2], -camera.position[1]],
        "target": [camera.target[0], camera.target[2], -camera.target[1]],
        "up": [camera.up[0], camera.up[2], -camera.up[1]],
    }
    for camera in _EXPECTED_CONTRACT.camera_presets
)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _read_glb_json(path: Path) -> dict[str, Any]:
    data = path.read_bytes()
    if len(data) < 20:
        raise ValueError("GLB is shorter than its header and JSON chunk")
    magic, version, declared_length = struct.unpack_from("<4sII", data, 0)
    if magic != b"glTF":
        raise ValueError("GLB magic is not glTF")
    if version != 2:
        raise ValueError("GLB version must be 2")
    if declared_length != len(data):
        raise ValueError("GLB header length does not match the file")
    json_length, json_type = struct.unpack_from("<I4s", data, 12)
    if json_type != b"JSON" or 20 + json_length > len(data):
        raise ValueError("GLB first chunk must be a complete JSON chunk")
    return json.loads(data[20 : 20 + json_length].rstrip(b" \x00").decode("utf-8"))


def _same_number(actual: object, expected: float) -> bool:
    return isinstance(actual, (int, float)) and not isinstance(actual, bool) and abs(float(actual) - expected) <= DIMENSION_TOLERANCE_METERS


def _validate_dimensions(manifest: dict[str, Any], errors: list[str]) -> None:
    expected = {
        item.name: (item.meters, item.source)
        for item in build_scene_contract().printed_dimensions
    }
    raw_dimensions = manifest.get("printed_dimensions")
    if not isinstance(raw_dimensions, list):
        errors.append("printed_dimensions must be a list")
        return
    dimensions = {
        item.get("name"): item
        for item in raw_dimensions
        if isinstance(item, dict) and isinstance(item.get("name"), str)
    }
    for name, (meters, source) in expected.items():
        item = dimensions.get(name)
        if item is None:
            errors.append(f"missing printed dimension {name}")
            continue
        if not _same_number(item.get("meters"), meters):
            errors.append(
                f"printed dimension {name} must be {meters} m within 0.003 m"
            )
        if item.get("source") != source:
            errors.append(f"printed dimension {name} must cite {source!r}")


def _validate_named_records(
    actual: object,
    expected: tuple[dict[str, Any], ...],
    label: str,
    errors: list[str],
) -> None:
    if not isinstance(actual, list):
        errors.append(f"runtime {label} must be present as a list")
        return
    by_name = {
        item.get("name"): item
        for item in actual
        if isinstance(item, dict) and isinstance(item.get("name"), str)
    }
    for expected_item in expected:
        name = expected_item["name"]
        item = by_name.get(name)
        if item is None:
            errors.append(f"runtime {label} missing {name}")
            continue
        for key, expected_value in expected_item.items():
            if key == "name":
                continue
            actual_value = item.get(key)
            if isinstance(expected_value, list):
                if not isinstance(actual_value, list) or len(actual_value) != len(expected_value) or any(
                    not _same_number(value, expected_component)
                    for value, expected_component in zip(actual_value, expected_value)
                ):
                    errors.append(f"runtime {label} {name}.{key} is outside 0.003 m tolerance")
            elif not _same_number(actual_value, expected_value):
                errors.append(f"runtime {label} {name}.{key} is outside 0.003 m tolerance")


def _validate_runtime(manifest: dict[str, Any], errors: list[str]) -> None:
    runtime = manifest.get("runtime")
    if not isinstance(runtime, dict):
        errors.append("runtime navigation metadata must be present")
        return
    if runtime.get("coordinate_rule") != COORDINATE_RULE:
        errors.append(f"coordinate rule must be {COORDINATE_RULE!r}")
    if not _same_number(runtime.get("eye_height_meters"), EYE_HEIGHT_METERS):
        errors.append("runtime eye height must be 1.65 m within 0.003 m")

    walkable = runtime.get("walkable")
    if not isinstance(walkable, dict):
        errors.append("runtime walkable metadata must be present")
    else:
        for key, expected in EXPECTED_WALKABLE.items():
            if not _same_number(walkable.get(key), expected):
                errors.append(f"runtime walkable.{key} is outside 0.003 m tolerance")
    _validate_named_records(runtime.get("barriers"), EXPECTED_BARRIERS, "barriers", errors)
    _validate_named_records(runtime.get("camera_presets"), EXPECTED_CAMERAS, "camera_presets", errors)


def _validate_glb_resources(
    gltf: dict[str, Any], glb_path: Path, errors: list[str]
) -> None:
    for index, image in enumerate(gltf.get("images", [])):
        if not isinstance(image, dict):
            errors.append(f"GLB image {index} metadata must be an object")
            continue
        if "uri" in image:
            errors.append(
                f"GLB image must use an embedded bufferView, not URI: {image.get('uri')}"
            )
            continue
        if not isinstance(image.get("bufferView"), int):
            errors.append(f"GLB image {index} must use an embedded bufferView")

    for index, buffer in enumerate(gltf.get("buffers", [])):
        if isinstance(buffer, dict) and "uri" in buffer:
            errors.append(f"GLB buffer {index} must be embedded, not URI-backed")


def _named_world_bounds(scene: trimesh.Scene, node_name: str) -> tuple[list[float], list[float]] | None:
    if node_name not in scene.graph.nodes_geometry:
        return None
    transform, geometry_name = scene.graph.get(node_name)
    geometry = scene.geometry.get(geometry_name)
    if geometry is None:
        return None
    mesh = geometry.copy()
    mesh.apply_transform(transform)
    return mesh.bounds[0].tolist(), mesh.bounds[1].tolist()


def _validate_actual_geometry(glb_path: Path, errors: list[str]) -> None:
    try:
        loaded = trimesh.load(glb_path, force="scene", process=False)
        scene = loaded if isinstance(loaded, trimesh.Scene) else trimesh.Scene(loaded)
    except Exception as exc:
        errors.append(f"GLB geometry could not be loaded by trimesh: {exc}")
        return

    floor_bounds = _named_world_bounds(scene, "HV_FLOOR")
    if floor_bounds is None:
        errors.append("actual GLB geometry is missing named mesh HV_FLOOR")
    else:
        lower, upper = floor_bounds
        checks = (
            ("HV_FLOOR min X", lower[0], 0.0),
            ("HV_FLOOR max X", upper[0], SPAN_METERS),
            ("HV_FLOOR min Z", lower[2], -ROOM_DEPTH_METERS),
            ("HV_FLOOR max Z", upper[2], 0.0),
            ("HV_FLOOR X span", upper[0] - lower[0], SPAN_METERS),
            ("HV_FLOOR depth", upper[2] - lower[2], ROOM_DEPTH_METERS),
        )
        for label, actual, expected in checks:
            if not _same_number(actual, expected):
                errors.append(f"actual {label} must be {expected} m within 0.003 m")

    island_bounds = _named_world_bounds(scene, "HV_ISLAND_STRUCTURE")
    if island_bounds is None:
        errors.append("actual GLB geometry is missing named mesh HV_ISLAND_STRUCTURE")
    else:
        lower, upper = island_bounds
        checks = (
            ("HV_ISLAND_STRUCTURE min X", lower[0], 1.7272),
            ("HV_ISLAND_STRUCTURE max X", upper[0], 4.3434),
            ("HV_ISLAND_STRUCTURE min Z", lower[2], -3.0226),
            ("HV_ISLAND_STRUCTURE max Z", upper[2], -1.7272),
            ("HV_ISLAND_STRUCTURE width", upper[0] - lower[0], ISLAND_WIDTH_METERS),
            ("HV_ISLAND_STRUCTURE depth", upper[2] - lower[2], ISLAND_DEPTH_METERS),
        )
        for label, actual, expected in checks:
            if not _same_number(actual, expected):
                errors.append(f"actual {label} must be {expected} m within 0.003 m")


def validate_artifact(
    glb_path: Path,
    manifest_path: Path,
    *,
    public_dir: Path | None = None,
) -> tuple[str, ...]:
    """Return every actionable GLB/manifest/payload validation error."""
    glb_path = Path(glb_path)
    manifest_path = Path(manifest_path)
    public_dir = Path(public_dir) if public_dir is not None else manifest_path.parent
    errors: list[str] = []

    if not manifest_path.is_file():
        return (f"manifest is missing: {manifest_path}",)
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        return (f"manifest could not be read as JSON: {exc}",)
    if not isinstance(manifest, dict):
        return ("manifest root must be an object",)

    if manifest.get("schema") != SCHEMA:
        errors.append(f"schema must be {SCHEMA!r}")
    if manifest.get("label") != SCENE_LABEL:
        errors.append(f"label must be {SCENE_LABEL!r}")
    if manifest.get("canonical_geometry") is not False:
        errors.append("canonical_geometry must be false for visual staging")
    expected_contract = build_scene_contract()
    expected_categories = list(expected_contract.provisional_categories)
    if manifest.get("canonical_model_hash") != expected_contract.canonical_model_hash:
        errors.append("canonical model hash must match the current A-1 spatial model")
    if manifest.get("canonical_geometry_hash") != expected_contract.canonical_geometry_hash:
        errors.append("canonical geometry hash must match the current A-1 tour projection")
    if manifest.get("provisional_categories") != expected_categories:
        errors.append("provisional_categories must name exactly the six visual-staging categories")
    _validate_dimensions(manifest, errors)
    _validate_runtime(manifest, errors)

    scene_nodes = manifest.get("scene_nodes")
    if not isinstance(scene_nodes, list):
        errors.append("scene_nodes must be a list")
    else:
        for name in REQUIRED_SCENE_NODES:
            if name not in scene_nodes:
                errors.append(f"scene_nodes missing {name}")

    artifact = manifest.get("artifact")
    if not isinstance(artifact, dict):
        errors.append("artifact metadata must be present")
        artifact = {}
    expected_names = {
        "glb": "hearthview-kitchen-family.glb",
        "poster": "poster.webp",
        "environment": "environment.hdr",
    }
    hashes = artifact.get("sha256") if isinstance(artifact.get("sha256"), dict) else {}
    byte_counts = artifact.get("bytes") if isinstance(artifact.get("bytes"), dict) else {}
    if set(hashes) != set(expected_names):
        errors.append(
            "artifact sha256 keys must be exactly glb, poster, and environment; "
            "manifest must not hash itself"
        )
    actual_paths: dict[str, Path] = {}
    for key, expected_name in expected_names.items():
        if artifact.get(key) != expected_name:
            errors.append(f"artifact {key} filename must be {expected_name!r}")
        path = glb_path if key == "glb" else public_dir / expected_name
        actual_paths[key] = path
        if not path.is_file():
            errors.append(f"artifact {key} is missing: {path}")
            continue
        actual_size = path.stat().st_size
        if byte_counts.get(key) != actual_size:
            errors.append(f"artifact {key} bytes do not match the file")
        if hashes.get(key) != _sha256(path):
            errors.append(f"artifact {key} hash does not match the file")

    manifest_size = manifest_path.stat().st_size
    if byte_counts.get("manifest") != manifest_size:
        errors.append("artifact manifest bytes do not match the file")
    actual_total = manifest_size + sum(
        path.stat().st_size for path in actual_paths.values() if path.is_file()
    )
    declared_total = artifact.get("total_browser_bytes")
    if declared_total != actual_total:
        errors.append("artifact total_browser_bytes does not match actual browser payload")
    if isinstance(declared_total, int) and declared_total > MAX_BROWSER_BYTES:
        errors.append("artifact browser payload exceeds 45,000,000 bytes")
    if actual_total > MAX_BROWSER_BYTES:
        errors.append("actual browser payload exceeds 45,000,000 bytes")

    if glb_path.is_file():
        try:
            gltf = _read_glb_json(glb_path)
        except (OSError, UnicodeDecodeError, json.JSONDecodeError, ValueError, struct.error) as exc:
            errors.append(f"GLB JSON could not be decoded: {exc}")
        else:
            node_names = {
                node.get("name")
                for node in gltf.get("nodes", [])
                if isinstance(node, dict)
            }
            for name in REQUIRED_SCENE_NODES:
                if name not in node_names:
                    errors.append(f"GLB scene node is missing {name}")
            asset_metadata = gltf.get("asset", {}).get("extras", {})
            if not isinstance(asset_metadata, dict):
                errors.append("GLB asset extras must contain visual-staging metadata")
            else:
                if asset_metadata.get("label") != SCENE_LABEL:
                    errors.append(f"GLB asset label must be {SCENE_LABEL!r}")
                if asset_metadata.get("canonical_geometry") is not False:
                    errors.append("GLB asset canonical_geometry must be false")
                if asset_metadata.get("provisional_categories") != expected_categories:
                    errors.append("GLB asset must name exactly the six provisional categories")
                if asset_metadata.get("canonical_model_hash") != manifest.get(
                    "canonical_model_hash"
                ):
                    errors.append("GLB canonical model hash must match the manifest")
                if asset_metadata.get("canonical_geometry_hash") != manifest.get(
                    "canonical_geometry_hash"
                ):
                    errors.append("GLB canonical geometry hash must match the manifest")
            _validate_glb_resources(gltf, glb_path, errors)
        _validate_actual_geometry(glb_path, errors)
    return tuple(errors)


def _default_public_dir() -> Path:
    return Path(__file__).resolve().parents[2] / "apps" / "web" / "public" / "tour-spike"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    default_public = _default_public_dir()
    parser.add_argument("--glb", type=Path, default=default_public / "hearthview-kitchen-family.glb")
    parser.add_argument("--manifest", type=Path, default=default_public / "manifest.json")
    parser.add_argument("--public-dir", type=Path, default=default_public)
    args = parser.parse_args()
    errors = validate_artifact(args.glb, args.manifest, public_dir=args.public_dir)
    if errors:
        for error in errors:
            print(error)
        return 1
    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    artifact = manifest["artifact"]
    print(
        "validated "
        f"{artifact['total_browser_bytes']} browser bytes; "
        f"GLB sha256 {artifact['sha256']['glb']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
