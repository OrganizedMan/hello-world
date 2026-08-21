from __future__ import annotations

from copy import deepcopy
import hashlib
import json
from pathlib import Path
import struct
from typing import Callable

import pytest
import trimesh

import spikes.tour_quality

_STAGED_MODULE_DIR = Path(__file__).parents[2] / "spikes" / "tour_quality"
spikes.tour_quality.__path__.insert(0, str(_STAGED_MODULE_DIR))

from spikes.tour_quality.validate_artifact import validate_artifact
from spikes.tour_quality.scene_contract import build_scene_contract


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


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _patch_glb_json(glb: bytes, mutate: Callable[[dict[str, object]], None]) -> bytes:
    magic, version, _length = struct.unpack_from("<4sII", glb, 0)
    assert magic == b"glTF"
    assert version == 2
    offset = 12
    chunks: list[tuple[bytes, bytes]] = []
    while offset < len(glb):
        chunk_length, chunk_type = struct.unpack_from("<I4s", glb, offset)
        offset += 8
        chunks.append((chunk_type, glb[offset : offset + chunk_length]))
        offset += chunk_length

    gltf = json.loads(chunks[0][1].rstrip(b" \x00").decode("utf-8"))
    mutate(gltf)
    json_chunk = json.dumps(
        gltf, ensure_ascii=False, separators=(",", ":"), sort_keys=True
    ).encode("utf-8")
    json_chunk += b" " * ((-len(json_chunk)) % 4)
    chunks[0] = (b"JSON", json_chunk)

    body = b"".join(
        struct.pack("<I4s", len(chunk), chunk_type) + chunk
        for chunk_type, chunk in chunks
    )
    return struct.pack("<4sII", b"glTF", 2, 12 + len(body)) + body


def _box(extents: tuple[float, float, float], center: tuple[float, float, float]):
    transform = trimesh.transformations.translation_matrix(center)
    return trimesh.creation.box(extents=extents, transform=transform)


def _write_glb(
    path: Path,
    *,
    floor_min_x: float = 0.0,
    floor_max_x: float = 9.1694,
    floor_min_z: float = -4.8514,
    floor_max_z: float = 0.0,
    island_min_x: float = 1.7272,
    island_max_x: float = 4.3434,
    island_min_z: float = -3.0226,
    island_max_z: float = -1.7272,
    image_uri: str | None = None,
    canonical_geometry_hash: str | None = None,
) -> None:
    scene = trimesh.Scene()
    scene.add_geometry(
        _box(
            (floor_max_x - floor_min_x, 0.02, floor_max_z - floor_min_z),
            ((floor_min_x + floor_max_x) / 2.0, -0.01, (floor_min_z + floor_max_z) / 2.0),
        ),
        node_name="HV_FLOOR",
        geom_name="HV_FLOOR_MESH",
    )
    scene.add_geometry(
        _box(
            (island_max_x - island_min_x, 0.91, island_max_z - island_min_z),
            ((island_min_x + island_max_x) / 2.0, 0.455, (island_min_z + island_max_z) / 2.0),
        ),
        node_name="HV_ISLAND_STRUCTURE",
        geom_name="HV_ISLAND_STRUCTURE_MESH",
    )
    scene.add_geometry(
        _box((8.8094, 0.002, 4.4914), (4.5847, 0.002, -2.4257)),
        node_name="HV_WALKABLE",
        geom_name="HV_WALKABLE_MESH",
    )
    for index, name in enumerate(SCENE_NODES[:5]):
        scene.add_geometry(
            _box((0.01, 0.01, 0.01), (0.02 + index * 0.02, 0.02, -0.02)),
            node_name=name,
            geom_name=f"{name}_MESH",
        )

    glb = scene.export(file_type="glb")

    def add_metadata(gltf: dict[str, object]) -> None:
        contract = build_scene_contract()
        asset = gltf.setdefault("asset", {})
        assert isinstance(asset, dict)
        asset["extras"] = {
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
            "canonical_model_hash": contract.canonical_model_hash,
            "canonical_geometry_hash": canonical_geometry_hash
            or contract.canonical_geometry_hash,
        }
        if image_uri is not None:
            gltf["images"] = [{"uri": image_uri}]

    path.write_bytes(_patch_glb_json(glb, add_metadata))


def _literal_manifest() -> dict[str, object]:
    contract = build_scene_contract()
    return {
        "schema": "hearthview-tour-spike/v1",
        "label": "Quality spike · visual staging",
        "canonical_geometry": False,
        "canonical_model_hash": contract.canonical_model_hash,
        "canonical_geometry_hash": contract.canonical_geometry_hash,
        "envelope": {
            "min_x": 0.0,
            "min_y": 0.0,
            "min_z": 0.0,
            "max_x": 9.1694,
            "max_y": 4.8514,
            "max_z": 2.5654,
        },
        "counter_zone_depth_meters": 0.6604,
        "printed_dimensions": [
            {"name": "span", "meters": 9.1694, "source": "A-1 printed dimension"},
            {"name": "room_depth", "meters": 4.8514, "source": "A-1 printed dimension"},
            {"name": "counter_zone_depth", "meters": 0.6604, "source": "A-1 derived dimension"},
            {"name": "ceiling", "meters": 2.5654, "source": "A-1 printed dimension"},
            {"name": "island_width", "meters": 2.6162, "source": "A-1 printed dimension"},
            {"name": "island_depth", "meters": 1.2954, "source": "A-1 printed dimension"},
            {"name": "west_clearance", "meters": 1.0668, "source": "A-1 printed dimension"},
            {"name": "north_clearance", "meters": 1.0668, "source": "A-1 printed dimension"},
            {"name": "south_transition", "meters": 1.8288, "source": "A-1 printed dimension"},
            {"name": "living_clear_width", "meters": 4.4958, "source": "A-1 printed dimension"},
            {"name": "eye_height", "meters": 1.65, "source": "tour navigation requirement"},
        ],
        "wall_openings": [],
        "island_footprint": {
            "name": "island",
            "min_x": 1.7272,
            "min_y": 1.7272,
            "max_x": 4.3434,
            "max_y": 3.0226,
        },
        "living_clear_area": {
            "name": "living_clear_area",
            "min_x": 4.6736,
            "min_y": 0.0,
            "max_x": 9.1694,
            "max_y": 4.8514,
        },
        "cabinet_appliance_order": [],
        "walkable_polygon": [
            [0.18, 0.18],
            [8.9894, 0.18],
            [8.9894, 4.6714],
            [0.18, 4.6714],
        ],
        "collision_rectangles": [],
        "camera_presets": [],
        "provisional_categories": [
            "cabinetry_detail",
            "hardware",
            "finishes",
            "furniture",
            "decor",
            "undimensioned_offsets",
        ],
        "artifact": {
            "glb": "hearthview-kitchen-family.glb",
            "poster": "poster.webp",
            "environment": "environment.hdr",
            "sha256": {"glb": "", "poster": "", "environment": ""},
            "bytes": {"glb": 0, "poster": 0, "environment": 0, "manifest": 0},
            "total_browser_bytes": 0,
        },
        "runtime": {
            "coordinate_rule": "three_x=source_x;three_y=source_z;three_z=-source_y",
            "eye_height_meters": 1.65,
            "walkable": {"min_x": 0.18, "max_x": 8.9894, "min_z": -4.6714, "max_z": -0.18},
            "barriers": [
                {"name": "west_counter", "min_x": 0.0, "max_x": 0.6604, "min_z": -2.75, "max_z": 0.0},
                {"name": "north_counter", "min_x": 0.0, "max_x": 3.70, "min_z": -0.6604, "max_z": 0.0},
                {"name": "island", "min_x": 1.7272, "max_x": 4.3434, "min_z": -3.0226, "max_z": -1.7272},
                {"name": "tv_wall", "min_x": 8.9894, "max_x": 9.1694, "min_z": -3.3528, "max_z": -1.524},
            ],
            "camera_presets": [
                {"name": "kitchen_overview", "position": [0.70, 1.65, -4.3014], "target": [4.3434, 0.90, -3.0226], "up": [0.0, 1.0, -0.0]},
                {"name": "walk_start", "position": [4.15, 1.65, -4.2014], "target": [5.20, 1.65, -2.10], "up": [0.0, 1.0, -0.0]},
                {"name": "overhead", "position": [4.5847, 8.0, -2.4257], "target": [4.5847, 0.0, -2.4257], "up": [0.0, 0.0, 1.0]},
            ],
        },
        "scene_nodes": deepcopy(SCENE_NODES),
    }


def _write_manifest(path: Path, manifest: dict[str, object], *, update_total: bool = True) -> None:
    artifact = manifest["artifact"]
    assert isinstance(artifact, dict)
    byte_counts = artifact["bytes"]
    assert isinstance(byte_counts, dict)
    for _iteration in range(8):
        encoded = (json.dumps(manifest, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
        if byte_counts["manifest"] == len(encoded):
            path.write_bytes(encoded)
            return
        byte_counts["manifest"] = len(encoded)
        if update_total:
            artifact["total_browser_bytes"] = sum(int(value) for value in byte_counts.values())
    raise AssertionError("manifest byte size did not stabilize")


def _write_artifact_fixture(
    root: Path,
    *,
    floor_min_x: float = 0.0,
    floor_max_x: float = 9.1694,
    floor_min_z: float = -4.8514,
    floor_max_z: float = 0.0,
    island_min_x: float = 1.7272,
    island_max_x: float = 4.3434,
    island_min_z: float = -3.0226,
    island_max_z: float = -1.7272,
    image_uri: str | None = None,
    canonical_geometry_hash: str | None = None,
) -> tuple[Path, Path, dict[str, object]]:
    public_dir = root / "tour-spike"
    public_dir.mkdir()
    glb_path = public_dir / "hearthview-kitchen-family.glb"
    poster_path = public_dir / "poster.webp"
    environment_path = public_dir / "environment.hdr"
    manifest_path = public_dir / "manifest.json"
    _write_glb(
        glb_path,
        floor_min_x=floor_min_x,
        floor_max_x=floor_max_x,
        floor_min_z=floor_min_z,
        floor_max_z=floor_max_z,
        island_min_x=island_min_x,
        island_max_x=island_max_x,
        island_min_z=island_min_z,
        island_max_z=island_max_z,
        image_uri=image_uri,
        canonical_geometry_hash=canonical_geometry_hash,
    )
    poster_path.write_bytes(b"RIFFfixture-WEBP")
    environment_path.write_bytes(b"#?RADIANCE\nfixture")

    manifest = _literal_manifest()
    artifact = manifest["artifact"]
    assert isinstance(artifact, dict)
    hashes = artifact["sha256"]
    byte_counts = artifact["bytes"]
    assert isinstance(hashes, dict)
    assert isinstance(byte_counts, dict)
    for key, artifact_path in (
        ("glb", glb_path),
        ("poster", poster_path),
        ("environment", environment_path),
    ):
        hashes[key] = _sha256(artifact_path)
        byte_counts[key] = artifact_path.stat().st_size
    _write_manifest(manifest_path, manifest)
    return glb_path, manifest_path, manifest


def test_valid_literal_fixture_returns_no_errors(tmp_path: Path) -> None:
    """Break caught: a local, contract-aligned self-contained artifact is rejected."""
    glb_path, manifest_path, _manifest = _write_artifact_fixture(tmp_path)

    assert validate_artifact(glb_path, manifest_path, public_dir=glb_path.parent) == ()


def test_wrong_schema_is_rejected(tmp_path: Path) -> None:
    """Break caught: a consumer receives an artifact with an incompatible schema."""
    glb_path, manifest_path, manifest = _write_artifact_fixture(tmp_path)
    manifest["schema"] = "hearthview-tour-spike/v0"
    _write_manifest(manifest_path, manifest)

    errors = validate_artifact(glb_path, manifest_path, public_dir=glb_path.parent)

    assert any("schema" in error for error in errors)


def test_stale_manifest_canonical_hash_is_rejected(tmp_path: Path) -> None:
    glb_path, manifest_path, manifest = _write_artifact_fixture(tmp_path)
    manifest["canonical_model_hash"] = "0" * 64
    _write_manifest(manifest_path, manifest)

    errors = validate_artifact(glb_path, manifest_path, public_dir=glb_path.parent)

    assert any("canonical model hash" in error for error in errors)


def test_glb_cannot_disagree_with_the_manifest_geometry_hash(tmp_path: Path) -> None:
    glb_path, manifest_path, _manifest = _write_artifact_fixture(
        tmp_path,
        canonical_geometry_hash="0" * 64,
    )

    errors = validate_artifact(glb_path, manifest_path, public_dir=glb_path.parent)

    assert any("GLB canonical geometry hash" in error for error in errors)


@pytest.mark.parametrize(
    ("key", "value", "fragment"),
    [
        ("canonical_geometry", True, "canonical"),
        ("label", "HearthView kitchen", "Quality spike"),
    ],
)
def test_canonical_claim_or_wrong_label_is_rejected(
    tmp_path: Path, key: str, value: object, fragment: str
) -> None:
    """Break caught: visual staging is mislabeled as measured/canonical geometry."""
    glb_path, manifest_path, manifest = _write_artifact_fixture(tmp_path)
    manifest[key] = value
    _write_manifest(manifest_path, manifest)

    errors = validate_artifact(glb_path, manifest_path, public_dir=glb_path.parent)

    assert any(fragment.lower() in error.lower() for error in errors)


@pytest.mark.parametrize("mutation", ["missing", "drift"])
def test_missing_or_drifted_printed_dimension_is_rejected(
    tmp_path: Path, mutation: str
) -> None:
    """Break caught: an A-1 dimension is dropped or drifts beyond three millimeters."""
    glb_path, manifest_path, manifest = _write_artifact_fixture(tmp_path)
    dimensions = manifest["printed_dimensions"]
    assert isinstance(dimensions, list)
    if mutation == "missing":
        dimensions[:] = [item for item in dimensions if item["name"] != "span"]
    else:
        next(item for item in dimensions if item["name"] == "span")["meters"] = 9.1730
    _write_manifest(manifest_path, manifest)

    errors = validate_artifact(glb_path, manifest_path, public_dir=glb_path.parent)

    assert any("span" in error and ("missing" in error or "0.003" in error) for error in errors)


def test_absent_required_scene_node_is_rejected(tmp_path: Path) -> None:
    """Break caught: a browser-critical named scene component disappears from the GLB."""
    glb_path, manifest_path, manifest = _write_artifact_fixture(tmp_path)
    manifest["scene_nodes"].remove("HV_WALKABLE")
    _write_manifest(manifest_path, manifest)

    errors = validate_artifact(glb_path, manifest_path, public_dir=glb_path.parent)

    assert any("HV_WALKABLE" in error for error in errors)


@pytest.mark.parametrize("runtime_key", ["walkable", "barriers", "camera_presets"])
def test_absent_runtime_navigation_metadata_is_rejected(
    tmp_path: Path, runtime_key: str
) -> None:
    """Break caught: runtime navigation loses a walkable extent, barrier, or recovery camera."""
    glb_path, manifest_path, manifest = _write_artifact_fixture(tmp_path)
    del manifest["runtime"][runtime_key]
    _write_manifest(manifest_path, manifest)

    errors = validate_artifact(glb_path, manifest_path, public_dir=glb_path.parent)

    assert any(runtime_key in error for error in errors)


@pytest.mark.parametrize(
    ("runtime_key", "wrong_value", "fragment"),
    [
        ("coordinate_rule", "three_x=source_x;three_z=source_y", "coordinate"),
        ("eye_height_meters", 1.654, "eye height"),
    ],
)
def test_wrong_coordinate_rule_or_eye_height_is_rejected(
    tmp_path: Path, runtime_key: str, wrong_value: object, fragment: str
) -> None:
    """Break caught: Blender floor coordinates or navigation eye height reach Three.js incorrectly."""
    glb_path, manifest_path, manifest = _write_artifact_fixture(tmp_path)
    manifest["runtime"][runtime_key] = wrong_value
    _write_manifest(manifest_path, manifest)

    errors = validate_artifact(glb_path, manifest_path, public_dir=glb_path.parent)

    assert any(fragment in error for error in errors)


@pytest.mark.parametrize("corruption", ["hash", "bytes"])
def test_wrong_artifact_hash_or_byte_count_is_rejected(
    tmp_path: Path, corruption: str
) -> None:
    """Break caught: stale browser files pass despite disagreeing with the manifest."""
    glb_path, manifest_path, manifest = _write_artifact_fixture(tmp_path)
    artifact = manifest["artifact"]
    if corruption == "hash":
        artifact["sha256"]["glb"] = "0" * 64
    else:
        artifact["bytes"]["glb"] += 1
    _write_manifest(manifest_path, manifest)

    errors = validate_artifact(glb_path, manifest_path, public_dir=glb_path.parent)

    assert any(corruption in error for error in errors)


def test_manifest_sha256_key_is_rejected(tmp_path: Path) -> None:
    """Break caught: the manifest attempts to hash itself instead of only browser files."""
    glb_path, manifest_path, manifest = _write_artifact_fixture(tmp_path)
    manifest["artifact"]["sha256"]["manifest"] = "0" * 64
    _write_manifest(manifest_path, manifest)

    errors = validate_artifact(glb_path, manifest_path, public_dir=glb_path.parent)

    assert any("sha256" in error and "manifest" in error for error in errors)


@pytest.mark.parametrize("uri", ["https://example.invalid/texture.jpg", "missing-texture.jpg"])
def test_remote_or_missing_external_glb_image_is_rejected(tmp_path: Path, uri: str) -> None:
    """Break caught: the GLB needs a network or missing sidecar image at runtime."""
    glb_path, manifest_path, _manifest = _write_artifact_fixture(tmp_path, image_uri=uri)

    errors = validate_artifact(glb_path, manifest_path, public_dir=glb_path.parent)

    assert any("image" in error and uri in error for error in errors)


def test_existing_local_sidecar_glb_image_is_rejected(tmp_path: Path) -> None:
    """Break caught: a nominally local GLB still depends on a non-embedded sidecar image."""
    uri = "present-texture.jpg"
    glb_path, manifest_path, _manifest = _write_artifact_fixture(
        tmp_path, image_uri=uri
    )
    (glb_path.parent / uri).write_bytes(b"fixture image")

    errors = validate_artifact(glb_path, manifest_path, public_dir=glb_path.parent)

    assert any("embedded bufferView" in error and uri in error for error in errors)


def test_browser_payload_over_45_megabytes_is_rejected(tmp_path: Path) -> None:
    """Break caught: the initial tour payload exceeds its browser delivery budget."""
    glb_path, manifest_path, manifest = _write_artifact_fixture(tmp_path)
    manifest["artifact"]["total_browser_bytes"] = 45_000_001
    _write_manifest(manifest_path, manifest, update_total=False)

    errors = validate_artifact(glb_path, manifest_path, public_dir=glb_path.parent)

    assert any("45,000,000" in error for error in errors)


@pytest.mark.parametrize(
    ("geometry_overrides", "expected_error"),
    [
        ({"floor_min_x": -0.004}, "HV_FLOOR min X"),
        ({"floor_max_x": 9.1734}, "HV_FLOOR max X"),
        ({"floor_min_z": -4.8554}, "HV_FLOOR min Z"),
        ({"floor_max_z": 0.004}, "HV_FLOOR max Z"),
        ({"island_min_x": 1.7232}, "HV_ISLAND_STRUCTURE min X"),
        ({"island_max_x": 4.3474}, "HV_ISLAND_STRUCTURE max X"),
        ({"island_min_z": -3.0266}, "HV_ISLAND_STRUCTURE min Z"),
        ({"island_max_z": -1.7232}, "HV_ISLAND_STRUCTURE max Z"),
    ],
)
def test_each_actual_y_up_floor_or_island_bound_drift_is_rejected(
    tmp_path: Path, geometry_overrides: dict[str, float], expected_error: str
) -> None:
    """Break caught: one converted X/negative-Z GLB edge drifts while the manifest stays correct."""
    glb_path, manifest_path, _manifest = _write_artifact_fixture(
        tmp_path, **geometry_overrides
    )

    errors = validate_artifact(glb_path, manifest_path, public_dir=glb_path.parent)

    assert any(expected_error in error and "0.003" in error for error in errors)
