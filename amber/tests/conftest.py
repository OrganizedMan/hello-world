from __future__ import annotations

import math
from pathlib import Path

import pytest

from amber.models import FrameRecord


@pytest.fixture()
def frames() -> list[FrameRecord]:
    """A 40-frame candidate pool at 4 fps, all eligible."""
    return [
        FrameRecord(id=f"cand_{i:06d}", index=i, timestamp=i / 4.0, sharpness=1.0)
        for i in range(40)
    ]


def write_model(
    directory: Path,
    camera_centers: list[tuple[float, float, float]],
    points: list[tuple[float, float, float]],
    names: list[str] | None = None,
    error: float = 0.5,
) -> Path:
    """Write a synthetic COLMAP text model with identity-rotation cameras.

    With R = I the camera centre C satisfies t = -C, which keeps the fixture
    readable while still exercising the real centre/parallax arithmetic.
    """
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "cameras.txt").write_text(
        "# Camera list\n1 PINHOLE 1920 1080 1000 1000 960 540\n", encoding="utf-8"
    )

    names = names or [f"cand_{i:06d}.png" for i in range(len(camera_centers))]
    lines = ["# Images"]
    for index, (center, name) in enumerate(zip(camera_centers, names), start=1):
        t = (-center[0], -center[1], -center[2])
        lines.append(f"{index} 1 0 0 0 {t[0]} {t[1]} {t[2]} 1 {name}")
        lines.append("")
    (directory / "images.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")

    point_lines = ["# Points"]
    for point_index, xyz in enumerate(points, start=1):
        track = " ".join(f"{i} 0" for i in range(1, len(camera_centers) + 1))
        point_lines.append(
            f"{point_index} {xyz[0]} {xyz[1]} {xyz[2]} 128 128 128 {error} {track}"
        )
    (directory / "points3D.txt").write_text(
        "\n".join(point_lines) + "\n", encoding="utf-8"
    )
    return directory


@pytest.fixture()
def healthy_model(tmp_path: Path) -> Path:
    """Three cameras with a real baseline, observing points 10 units away."""
    return write_model(
        tmp_path / "model",
        camera_centers=[(-1.0, 0.0, 0.0), (0.0, 0.0, 0.0), (1.0, 0.0, 0.0)],
        points=[(0.0, 0.0, 10.0), (1.0, 1.0, 10.0), (-1.0, -1.0, 10.0)],
    )


@pytest.fixture()
def pure_pan_model(tmp_path: Path) -> Path:
    """Every camera at the same point: a pan, not a walk-around."""
    return write_model(
        tmp_path / "pan-model",
        camera_centers=[(0.0, 0.0, 0.0)] * 3,
        points=[(0.0, 0.0, 10.0), (1.0, 1.0, 10.0)],
    )


def make_image(path: Path, size: tuple[int, int] = (64, 64), value: int = 128) -> Path:
    from PIL import Image

    path.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", size, (value, value, value)).save(path)
    return path


def make_noisy_image(path: Path, size: tuple[int, int] = (64, 64), seed: int = 0):
    import numpy as np
    from PIL import Image

    rng = np.random.default_rng(seed)
    data = rng.integers(0, 255, size=(size[1], size[0], 3), dtype=np.uint8)
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.fromarray(data).save(path)
    return path
