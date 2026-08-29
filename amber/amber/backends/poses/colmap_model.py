"""Reader and statistics for COLMAP's text sparse model.

Kept separate from the backend so the health statistics can be unit-tested
against synthetic models without COLMAP installed.
"""

from __future__ import annotations

import math
import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable, Sequence

MAX_PAIRS_PER_POINT = 32


@dataclass
class ImagePose:
    image_id: int
    qvec: tuple[float, float, float, float]
    tvec: tuple[float, float, float]
    camera_id: int
    name: str
    point3d_ids: list[int] = field(default_factory=list)

    @property
    def center(self) -> tuple[float, float, float]:
        """Camera centre C = -R^T t."""
        r = quaternion_to_rotation(self.qvec)
        t = self.tvec
        return (
            -(r[0][0] * t[0] + r[1][0] * t[1] + r[2][0] * t[2]),
            -(r[0][1] * t[0] + r[1][1] * t[1] + r[2][1] * t[2]),
            -(r[0][2] * t[0] + r[1][2] * t[1] + r[2][2] * t[2]),
        )


@dataclass
class Point3D:
    point_id: int
    xyz: tuple[float, float, float]
    error: float
    track: list[int] = field(default_factory=list)  # observing image ids


def quaternion_to_rotation(
    q: Sequence[float],
) -> tuple[tuple[float, float, float], ...]:
    """COLMAP stores (qw, qx, qy, qz), normalized."""
    w, x, y, z = q
    norm = math.sqrt(w * w + x * x + y * y + z * z) or 1.0
    w, x, y, z = w / norm, x / norm, y / norm, z / norm
    return (
        (1 - 2 * y * y - 2 * z * z, 2 * x * y - 2 * z * w, 2 * x * z + 2 * y * w),
        (2 * x * y + 2 * z * w, 1 - 2 * x * x - 2 * z * z, 2 * y * z - 2 * x * w),
        (2 * x * z - 2 * y * w, 2 * y * z + 2 * x * w, 1 - 2 * x * x - 2 * y * y),
    )


def _data_lines(path: Path) -> Iterable[str]:
    with Path(path).open(encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line and not line.startswith("#"):
                yield line


def _paired_lines(path: Path) -> list[str]:
    """Non-comment lines with blanks preserved.

    `images.txt` is strictly two lines per image and the second line is empty
    for an image with no 2D observations — which is exactly what a filtered
    model view contains. Dropping blank lines here would silently pair each
    header with the *next* image's header.
    """
    lines: list[str] = []
    with Path(path).open(encoding="utf-8") as fh:
        for line in fh:
            stripped = line.strip()
            if stripped.startswith("#"):
                continue
            lines.append(stripped)
    while lines and lines[-1] == "":
        lines.pop()
    if len(lines) % 2:
        lines.append("")
    return lines


def read_images_text(path: Path) -> dict[int, ImagePose]:
    """Parse `images.txt`: two lines per image, the second being 2D points."""
    images: dict[int, ImagePose] = {}
    lines = _paired_lines(path)
    for i in range(0, len(lines), 2):
        header = lines[i].split()
        if len(header) < 10:
            continue
        image_id = int(header[0])
        pose = ImagePose(
            image_id=image_id,
            qvec=(
                float(header[1]),
                float(header[2]),
                float(header[3]),
                float(header[4]),
            ),
            tvec=(float(header[5]), float(header[6]), float(header[7])),
            camera_id=int(header[8]),
            name=" ".join(header[9:]),
        )
        if i + 1 < len(lines):
            values = lines[i + 1].split()
            pose.point3d_ids = [
                int(values[j + 2])
                for j in range(0, len(values) - 2, 3)
                if int(values[j + 2]) != -1
            ]
        images[image_id] = pose
    return images


def read_points3d_text(path: Path) -> dict[int, Point3D]:
    points: dict[int, Point3D] = {}
    for line in _data_lines(path):
        values = line.split()
        if len(values) < 8:
            continue
        point_id = int(values[0])
        track = [int(values[j]) for j in range(8, len(values), 2)]
        points[point_id] = Point3D(
            point_id=point_id,
            xyz=(float(values[1]), float(values[2]), float(values[3])),
            error=float(values[7]),
            track=track,
        )
    return points


def _median(values: Sequence[float]) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    mid = len(ordered) // 2
    if len(ordered) % 2:
        return float(ordered[mid])
    return float((ordered[mid - 1] + ordered[mid]) / 2.0)


def _distance(a: Sequence[float], b: Sequence[float]) -> float:
    return math.sqrt(sum((x - y) ** 2 for x, y in zip(a, b)))


def camera_path_extent(images: dict[int, ImagePose]) -> float:
    """Largest distance between any two camera centres.

    This is the translation term of the pure-pan check: a camera that only
    rotated has an extent near zero regardless of how healthy the rest of the
    solution looks.
    """
    centers = [img.center for img in images.values()]
    if len(centers) < 2:
        return 0.0
    return max(
        _distance(centers[i], centers[j])
        for i in range(len(centers))
        for j in range(i + 1, len(centers))
    )


def median_scene_depth(
    images: dict[int, ImagePose], points: dict[int, Point3D]
) -> float:
    """Median distance from each point to the centroid of its observers."""
    depths: list[float] = []
    centers = {i: img.center for i, img in images.items()}
    for point in points.values():
        observers = [centers[i] for i in point.track if i in centers]
        if not observers:
            continue
        centroid = tuple(
            sum(c[axis] for c in observers) / len(observers) for axis in range(3)
        )
        depths.append(_distance(point.xyz, centroid))
    return _median(depths)


def median_triangulation_angle_deg(
    images: dict[int, ImagePose], points: dict[int, Point3D]
) -> float:
    """Median over points of the widest angle between observing rays.

    This is the scale-independent parallax statistic §8.3 asks for. A capture
    with plenty of registered frames but no real baseline produces tiny angles,
    which is what distinguishes a pan from a walk-around.
    """
    centers = {i: img.center for i, img in images.items()}
    angles: list[float] = []
    for point in points.values():
        observers = [centers[i] for i in point.track if i in centers]
        if len(observers) < 2:
            continue
        rays: list[tuple[float, float, float]] = []
        for center in observers[: MAX_PAIRS_PER_POINT]:
            vec = tuple(point.xyz[a] - center[a] for a in range(3))
            norm = math.sqrt(sum(v * v for v in vec))
            if norm > 0:
                rays.append(tuple(v / norm for v in vec))  # type: ignore[arg-type]
        best = 0.0
        for i in range(len(rays)):
            for j in range(i + 1, len(rays)):
                dot = max(-1.0, min(1.0, sum(a * b for a, b in zip(rays[i], rays[j]))))
                best = max(best, math.degrees(math.acos(dot)))
        if best > 0:
            angles.append(best)
    return _median(angles)


def write_filtered_model(
    src_dir: Path,
    dst_dir: Path,
    keep_names: set[str],
    min_track_length: int = 2,
) -> int:
    """Write a copy of a text model containing only `keep_names` images.

    This is how an evaluation split is enforced against a trainer that cannot
    honour a split flag: the trainer is handed a dataset view with no
    evaluation imagery at all, while the canonical model on disk keeps every
    camera so the held-out views can still be rendered afterwards
    (AGENTS.md rule 10).

    Returns the number of images kept.
    """
    src_dir, dst_dir = Path(src_dir), Path(dst_dir)
    dst_dir.mkdir(parents=True, exist_ok=True)

    images = read_images_text(src_dir / "images.txt")
    points = read_points3d_text(src_dir / "points3D.txt")

    kept = {
        image_id: pose
        for image_id, pose in images.items()
        if Path(pose.name).stem in keep_names or pose.name in keep_names
    }
    kept_ids = set(kept)

    shutil.copyfile(src_dir / "cameras.txt", dst_dir / "cameras.txt")

    with (dst_dir / "images.txt").open("w", encoding="utf-8") as fh:
        fh.write("# Image list with two lines of data per image:\n")
        fh.write("#   IMAGE_ID, QW, QX, QY, QZ, TX, TY, TZ, CAMERA_ID, NAME\n")
        fh.write("#   POINTS2D[] as (X, Y, POINT3D_ID)\n")
        for image_id in sorted(kept):
            pose = kept[image_id]
            q, t = pose.qvec, pose.tvec
            fh.write(
                f"{image_id} {q[0]} {q[1]} {q[2]} {q[3]} "
                f"{t[0]} {t[1]} {t[2]} {pose.camera_id} {pose.name}\n"
            )
            # The 2D observation line is preserved as empty: the trainer needs
            # poses and the point cloud, not the original feature indices.
            fh.write("\n")

    with (dst_dir / "points3D.txt").open("w", encoding="utf-8") as fh:
        fh.write("# 3D point list with one line of data per point:\n")
        fh.write("#   POINT3D_ID, X, Y, Z, R, G, B, ERROR, TRACK[]\n")
        for point_id in sorted(points):
            point = points[point_id]
            track = [i for i in point.track if i in kept_ids]
            if len(track) < min_track_length:
                continue
            xyz = point.xyz
            entries = " ".join(f"{i} 0" for i in track)
            fh.write(
                f"{point_id} {xyz[0]} {xyz[1]} {xyz[2]} 128 128 128 "
                f"{point.error} {entries}\n"
            )
    return len(kept)


@dataclass
class ModelStats:
    registered_images: int
    image_names: list[str]
    sparse_point_count: int
    median_observations_per_point: float
    mean_reprojection_error_px: float
    camera_path_extent: float
    median_scene_depth: float
    median_triangulation_angle_deg: float


def model_stats(model_dir: Path) -> ModelStats:
    model_dir = Path(model_dir)
    images = read_images_text(model_dir / "images.txt")
    points = read_points3d_text(model_dir / "points3D.txt")
    track_lengths = [len(p.track) for p in points.values()]
    errors = [p.error for p in points.values()]
    return ModelStats(
        registered_images=len(images),
        image_names=[img.name for img in images.values()],
        sparse_point_count=len(points),
        median_observations_per_point=_median(track_lengths),
        mean_reprojection_error_px=(sum(errors) / len(errors)) if errors else 0.0,
        camera_path_extent=camera_path_extent(images),
        median_scene_depth=median_scene_depth(images, points),
        median_triangulation_angle_deg=median_triangulation_angle_deg(images, points),
    )
