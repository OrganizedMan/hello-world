"""Packaging: the archival PLY master and compressed delivery derivatives.

The master is never deleted because a compressed file exists. Splat count and
spherical-harmonic degree are separate controls, and the mobile default is
chosen from measurement rather than theory (plan §8.6).
"""

from __future__ import annotations

import re
import shutil
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any, Sequence

from ..config import DELIVERY_PROFILES, DeliveryProfile
from ..events import EventSink, emit
from ..models import AmberError
from ..tools import ProcessRunner, discover_tool, resolve_version

FLAG_PATTERN = re.compile(r"(--[a-z0-9][a-z0-9-]*)")

# Verified against playcanvas/splat-transform: `-H, --filter-harmonics <0|1|2|3>`
# removes SH bands above n, which is equivalent to setting the delivery SH
# degree. The older guesses are kept as fallbacks for other builds.
SH_FLAG_CANDIDATES = (
    "--filter-harmonics",
    "--harmonic-degree",
    "--sh-degree",
    "--shN",
)
SPLAT_LIMIT_FLAG_CANDIDATES = ("--max-splats", "--limit")


@dataclass
class DeliveryArtifact:
    profile: str
    path: str
    bytes: int
    sh_degree: int
    max_splats: int | None
    source_master_sha256: str
    compression_settings: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class SplatTransform:
    """Thin wrapper over the splat-transform CLI, with flag discovery."""

    name = "splat-transform"

    def __init__(
        self,
        runner: ProcessRunner | None = None,
        executable: str = "splat-transform",
    ) -> None:
        self.runner = runner or ProcessRunner()
        self.executable = executable

    def doctor(self) -> dict[str, Any]:
        info = discover_tool(
            self.name, version_args=("--help",), executable=self.executable
        )
        flags = set(FLAG_PATTERN.findall(info.raw_version_output or ""))
        return {
            "available": info.available,
            "version": resolve_version(self.runner, self.executable, info.version),
            "executable": info.executable,
            "flags": sorted(flags),
            "sh_flag": next((f for f in SH_FLAG_CANDIDATES if f in flags), None),
            "splat_limit_flag": next(
                (f for f in SPLAT_LIMIT_FLAG_CANDIDATES if f in flags), None
            ),
            "error": info.error,
        }

    def convert(
        self,
        source_ply: Path,
        destination: Path,
        profile: DeliveryProfile,
        events: EventSink,
    ) -> list[str]:
        health = self.doctor()
        if not health["available"]:
            raise AmberError(
                "splat-transform is not installed; the delivery derivative "
                "cannot be produced. The PLY master is unaffected."
            )
        destination.parent.mkdir(parents=True, exist_ok=True)
        command = [self.executable, str(source_ply), str(destination)]

        if health["sh_flag"]:
            command += [health["sh_flag"], str(profile.sh_degree)]
        else:
            emit(
                events,
                "package",
                "warning",
                "this splat-transform build exposes no spherical-harmonic flag; "
                f"profile {profile.name!r} could not set SH degree "
                f"{profile.sh_degree} and it is recorded as unset",
                profile=profile.name,
            )
        if profile.max_splats is not None:
            if health["splat_limit_flag"]:
                command += [health["splat_limit_flag"], str(profile.max_splats)]
            else:
                emit(
                    events,
                    "package",
                    "warning",
                    "this splat-transform build exposes no splat-limit flag; "
                    f"the {profile.max_splats} cap was NOT applied",
                    profile=profile.name,
                )
        self.runner.run(command)
        return command


def write_master(trained_ply: Path, master_dir: Path) -> Path:
    """Copy the trained result into the archive as the interchange master."""
    master_dir = Path(master_dir)
    master_dir.mkdir(parents=True, exist_ok=True)
    destination = master_dir / "scene.ply"
    if Path(trained_ply).resolve() != destination.resolve():
        shutil.copy2(trained_ply, destination)
    return destination


def copy_sparse_model(sparse_text_dir: Path, master_dir: Path) -> Path:
    """The sparse camera model is archival: it is what makes the scene re-derivable."""
    destination = Path(master_dir) / "cameras" / "colmap-sparse"
    destination.mkdir(parents=True, exist_ok=True)
    for item in Path(sparse_text_dir).iterdir():
        if item.is_file():
            shutil.copy2(item, destination / item.name)
    return destination


def build_delivery(
    master_ply: Path,
    master_sha256: str,
    delivery_dir: Path,
    profile_names: Sequence[str],
    transform: SplatTransform,
    events: EventSink,
) -> list[DeliveryArtifact]:
    """Produce one derivative per requested profile.

    A failure here is reported but never fatal: the master already exists, and
    an archive with a master and no derivative is still a complete memory.
    """
    artifacts: list[DeliveryArtifact] = []
    delivery_dir = Path(delivery_dir)
    for name in profile_names:
        profile = DELIVERY_PROFILES.get(name)
        if profile is None:
            raise AmberError(
                f"unknown delivery profile {name!r}; available: "
                f"{sorted(DELIVERY_PROFILES)}"
            )
        suffix = f".{profile.format}"
        destination = delivery_dir / (
            "scene.sog" if len(profile_names) == 1 else f"scene-{profile.name}{suffix}"
        )
        try:
            command = transform.convert(master_ply, destination, profile, events)
        except AmberError as exc:
            emit(events, "package", "warning", str(exc), profile=profile.name)
            continue
        artifacts.append(
            DeliveryArtifact(
                profile=profile.name,
                path=str(destination),
                bytes=destination.stat().st_size if destination.exists() else 0,
                sh_degree=profile.sh_degree,
                max_splats=profile.max_splats,
                source_master_sha256=master_sha256,
                compression_settings={"command": command},
            )
        )
    return artifacts
