from __future__ import annotations

import runpy
import sys
from pathlib import Path
from types import ModuleType


def _load_entrypoint_without_blender_launcher_paths(monkeypatch):
    script = (
        Path(__file__).parents[2]
        / "spikes"
        / "tour_quality"
        / "build_scene.py"
    )
    script_dir = str(script.parent)
    original_path = sys.path[:]

    fake_bpy = ModuleType("bpy")
    fake_mathutils = ModuleType("mathutils")
    fake_mathutils.Vector = object
    monkeypatch.setitem(sys.modules, "bpy", fake_bpy)
    monkeypatch.setitem(sys.modules, "mathutils", fake_mathutils)
    monkeypatch.delitem(sys.modules, "blender_builders", raising=False)
    sys.path[:] = [entry for entry in sys.path if entry != script_dir]

    try:
        return runpy.run_path(
            str(script), run_name="hearthview_blender_entrypoint_probe"
        )
    finally:
        sys.path[:] = original_path


def test_blender_entrypoint_loads_its_adjacent_builder_without_launcher_path_support(
    monkeypatch,
) -> None:
    """Break caught: Blender omits the script directory and the build dies before main."""

    loaded = _load_entrypoint_without_blender_launcher_paths(monkeypatch)

    assert callable(loaded["build"])


def test_scene_setup_falls_back_to_the_blender_52_eevee_identifier(monkeypatch) -> None:
    """Break caught: Blender 5.2 rejects the obsolete BLENDER_EEVEE_NEXT enum."""

    class Blender52RenderSettings:
        def __init__(self) -> None:
            self.attempts: list[str] = []
            self._engine = ""

        @property
        def engine(self) -> str:
            return self._engine

        @engine.setter
        def engine(self, value: str) -> None:
            self.attempts.append(value)
            if value != "BLENDER_EEVEE":
                raise TypeError(f"unsupported engine: {value}")
            self._engine = value

    loaded = _load_entrypoint_without_blender_launcher_paths(monkeypatch)
    render = Blender52RenderSettings()

    loaded["_set_eevee_engine"](render)

    assert render.engine == "BLENDER_EEVEE"
    assert render.attempts == ["BLENDER_EEVEE_NEXT", "BLENDER_EEVEE"]
