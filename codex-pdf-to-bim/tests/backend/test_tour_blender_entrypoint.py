from __future__ import annotations

import runpy
import subprocess
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


def test_contract_loader_adds_the_services_package_for_blender(monkeypatch) -> None:
    """Break caught: embedded Blender Python cannot import hearthview services."""
    loaded = _load_entrypoint_without_blender_launcher_paths(monkeypatch)
    repo = Path(__file__).parents[2]
    services = str(repo / "services")
    monkeypatch.setattr(
        sys,
        "path",
        [entry for entry in sys.path if entry not in {services, str(repo)}],
    )
    for name in tuple(sys.modules):
        if name == "hearthview" or name.startswith("hearthview."):
            monkeypatch.delitem(sys.modules, name, raising=False)

    contract, _module, spec = loaded["_load_contract"](repo, None)

    assert contract.canonical_model_hash
    assert services in sys.path
    # Without --spec the loader must still yield the hand-built spike contract.
    assert spec is None
    assert contract.schema == "hearthview-tour-spike/v1"


def test_validator_subprocess_receives_repo_service_paths(monkeypatch, tmp_path) -> None:
    loaded = _load_entrypoint_without_blender_launcher_paths(monkeypatch)
    repo = Path(__file__).parents[2]
    captured: dict[str, object] = {}

    monkeypatch.setattr(loaded["shutil"], "which", lambda _name: "/usr/bin/uv")

    def fake_run(command, **kwargs):
        captured["command"] = command
        captured.update(kwargs)
        return subprocess.CompletedProcess(command, 0, stdout="valid", stderr="")

    monkeypatch.setattr(loaded["subprocess"], "run", fake_run)

    loaded["_run_validator"](repo, tmp_path)

    python_path = str(captured["env"]["PYTHONPATH"])
    assert str(repo) in python_path.split(":")
    assert str(repo / "services") in python_path.split(":")
