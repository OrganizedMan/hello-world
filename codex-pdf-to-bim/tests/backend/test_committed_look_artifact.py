"""The model the browser is served must be the finished one.

`build_a1_building.py` points the manifest at the plain canvas and the look pass
points it at the textured model when it finishes -- last, after a bake that runs
for half an hour. Commit between the two and the repository ships untextured,
unlit massing that loads perfectly, raises nothing, and looks like nothing. That
is not hypothetical: it is what happened, and it was found by a person opening
the page on their phone.

Every check here reads the artifact rather than the source, because that is the
only place any of this is visible.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
TOUR = REPO / "apps/web/public/tour-building"
MANIFEST = TOUR / "manifest.json"

sys.path.insert(0, str(REPO / "scripts"))

pytestmark = pytest.mark.skipif(not MANIFEST.is_file(), reason="no building tour committed")


@pytest.fixture(scope="module")
def manifest() -> dict:
    return json.loads(MANIFEST.read_text())


@pytest.fixture(scope="module")
def artifact(manifest):
    from check_export import read_glb

    served = TOUR / manifest["artifact"]["glb"]
    if not served.is_file():
        pytest.fail(f"the manifest serves {served.name}, which is not committed")
    return read_glb(served)


def test_the_manifest_serves_the_finished_model(manifest) -> None:
    artifact = manifest["artifact"]
    assert artifact["glb"] != artifact.get("canvas_glb"), (
        "the manifest is pointing at the plain canvas -- the look pass either "
        "did not run or had not finished when this was committed"
    )
    assert artifact.get("lightmap"), "no baked lighting is declared"


def test_every_material_carries_the_baked_light(artifact) -> None:
    gltf, _ = artifact
    materials = gltf.get("materials", [])
    lit = [m for m in materials if "emissiveTexture" in m]
    assert materials and len(lit) == len(materials), (
        f"only {len(lit)} of {len(materials)} materials carry the bake"
    )


def test_the_lightmap_atlas_is_not_mostly_empty(artifact) -> None:
    """Coverage decides a lightmap's resolution, not image size.

    The first 4096-pixel bake was ninety-six per cent black -- twelve texels to
    the metre, which renders as blocks -- and it exported without complaint.
    """
    from check_export import coverage

    gltf, blob = artifact
    assert coverage(gltf, blob) > 0.30


def test_the_walls_are_painted_not_photographed(artifact) -> None:
    """A grade that lives in a node tree does not survive glTF: the exporter
    drops it silently and ships the photograph, so the bake lights walls the
    browser then paints a different colour."""
    from check_export import image_bytes, mean_colour

    gltf, blob = artifact
    wall = next(m for m in gltf["materials"] if m.get("name") == "HV_LOOK_PLASTER_TEX")
    texture = wall["pbrMetallicRoughness"]["baseColorTexture"]
    mean = mean_colour(image_bytes(gltf, blob, gltf["textures"][texture["index"]]["source"]))
    if mean is None:
        pytest.skip("Pillow is needed to read the base colour map")

    assert min(mean) > 180, f"the wall reads {mean}, which is not paint"
    assert max(mean) - min(mean) < 20, f"the wall reads {mean}, which is tan not white"
