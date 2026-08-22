"""The artifacts the browser actually serves must match the committed trace.

`measure_glb --spec` is the pipeline's one check that opens the exported GLB,
but it only runs by hand, on a Mac, straight after a Blender build. Nothing ran
it against what is *committed*, so `apps/web/public/tour-spike/` drifted nine
commits behind the spec and no suite noticed: the published model still comes
from the legacy hand-built spike, mirrored, from before the frame was made
right-handed.

Building the GLB needs Blender. Reading one needs only trimesh, so these run
everywhere the rest of the suite does. That is the whole point of the rule in
`docs/traced-tour-pipeline.md` §3 — a check that never opens the exported GLB
proves nothing about the model.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pytest

REPO = Path(__file__).resolve().parents[2]
SPEC_PATH = REPO / "spikes/tour_quality/a1_kitchen_scene_spec.json"
PUBLIC = REPO / "apps/web/public/tour-spike"
GLB_PATH = PUBLIC / "hearthview-kitchen-family.glb"
MANIFEST_PATH = PUBLIC / "manifest.json"

TRACED_SCHEMA = "hearthview-tour/v2"

# Remove these markers in the same commit that lands the rebuilt artifacts. They
# are strict, so a correct rebuild turns them into XPASS and fails this suite
# until the markers go — the guard cannot be left silently disabled.
STALE = (
    "the committed tour artifacts predate the right-handed frame; rebuild with "
    "scripts/kitchen_family_checkpoint.py and drop this marker"
)

pytestmark = pytest.mark.skipif(
    not (SPEC_PATH.is_file() and GLB_PATH.is_file() and MANIFEST_PATH.is_file()),
    reason="committed tour artifacts or scene spec missing",
)

sys.path.insert(0, str(REPO / "scripts"))


@pytest.fixture(scope="module")
def spec() -> dict:
    return json.loads(SPEC_PATH.read_text())


@pytest.fixture(scope="module")
def manifest() -> dict:
    return json.loads(MANIFEST_PATH.read_text())


@pytest.fixture(scope="module")
def landmarks() -> dict:
    """Landmark centres read out of the published GLB, in glTF world space."""
    trimesh = pytest.importorskip("trimesh")
    from measure_glb import centres

    scene = trimesh.load(GLB_PATH, force="scene", process=False)
    return centres(scene)


@pytest.mark.xfail(strict=True, reason=STALE)
def test_the_published_manifest_comes_from_the_traced_pipeline(manifest) -> None:
    """A v1 manifest means the browser is being served the pre-trace spike."""
    assert manifest["schema"] == TRACED_SCHEMA


@pytest.mark.xfail(strict=True, reason=STALE)
def test_the_published_model_is_not_a_mirror_of_the_drawing(landmarks) -> None:
    from hearthview.chirality import matches_drawing, model_turn, plan_turn
    from measure_glb import chirality_triangle

    triangle = chirality_triangle(landmarks)
    assert triangle is not None, "GLB is missing the landmarks the handedness test reads"

    sink, rng, island = triangle
    assert matches_drawing(sink, rng, island), (
        f"published model turns {model_turn(sink, rng, island):+.2f} where the "
        f"drawing turns {plan_turn():+.2f} — it is a reflection of the plan"
    )


@pytest.mark.xfail(strict=True, reason=STALE)
def test_every_landmark_lands_where_the_trace_puts_it(landmarks, spec) -> None:
    from measure_glb import TOLERANCE, landmark_offsets

    offsets, missing = landmark_offsets(landmarks, spec)
    assert not missing, f"landmarks absent from the published GLB: {sorted(missing)}"

    drifted = {n: round(d, 2) for n, d in offsets.items() if d > TOLERANCE}
    assert not drifted, (
        f"published GLB disagrees with the trace by up to "
        f"{max(offsets.values()):.2f} m (tolerance {TOLERANCE:.2f} m): {drifted}"
    )


def test_an_artifact_built_to_the_trace_would_satisfy_this_guard(spec) -> None:
    """The three checks above are about the stale GLB, not broken measuring.

    Feed the measuring code a synthetic artifact whose landmarks sit exactly
    where the trace puts them; it must report no drift and the drawing's own
    handedness. Without this, the xfails above could be hiding an inverted test
    that nothing could ever satisfy.
    """
    from hearthview.chirality import matches_drawing
    from measure_glb import (
        TOLERANCE,
        chirality_triangle,
        expected_from_spec,
        landmark_offsets,
    )

    built = {
        name: np.array([x, 0.0, z])
        for name, (x, z) in expected_from_spec(spec).items()
    }

    offsets, missing = landmark_offsets(built, spec)
    assert not missing
    assert max(offsets.values()) <= TOLERANCE

    sink, rng, island = chirality_triangle(built)
    assert matches_drawing(sink, rng, island)
