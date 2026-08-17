"""Brush trainer backend.

Two disciplines matter more than convenience here:

1. **Flags are discovered, not assumed.** Brush is a moving target; a flag
   copied from a tutorial may be silently ignored by a different build, which
   would produce a run whose recorded config does not describe what happened.
   If a required capability is not present in `--help`, this backend fails with
   an explicit message rather than guessing.

2. **The split is enforced structurally.** Rather than trusting a flag, the
   trainer is handed a dataset view that physically contains no evaluation
   imagery. The canonical model keeps every camera, so held-out views can still
   be rendered afterwards.
"""

from __future__ import annotations

import re
import shutil
from pathlib import Path
from typing import Any, Sequence

from ...config import TrainConfig
from ...events import EventSink, emit
from ...models import AmberError
from ...tools import ProcessRunner, SubprocessFailure, discover_tool
from ..poses.colmap_model import write_filtered_model
from .base import BackendHealth, ColmapDataset, TrainResult

FLAG_PATTERN = re.compile(r"(--[a-z0-9][a-z0-9-]*)")

# capability -> candidate flag names, most likely first.
FLAG_CANDIDATES: dict[str, tuple[str, ...]] = {
    "output": ("--export-path", "--output", "--out-dir"),
    "max_resolution": ("--max-resolution", "--resolution", "--max-image-size"),
    "total_steps": ("--total-steps", "--steps", "--iterations"),
    "sh_degree": ("--sh-degree", "--sh"),
    "max_splats": ("--max-splats", "--max-gaussians", "--cap-max"),
    # Brush selects its evaluation set by stride and can only render the set it
    # chose itself; there is no render-from-given-cameras command. See ADR 0004
    # for how held-out rendering will be reconciled with Amber's locked split.
    # Detected here so `amber doctor` surfaces them; not yet used.
    "eval_split": ("--eval-split-every",),
    "eval_save_to_disk": ("--eval-save-to-disk",),
    "export_name": ("--export-name",),
}

REQUIRED_CAPABILITIES = ("output",)


def parse_flags(help_text: str) -> set[str]:
    return set(FLAG_PATTERN.findall(help_text))


def resolve_flags(available: set[str]) -> dict[str, str | None]:
    """Map each capability to the flag this build actually exposes."""
    resolved: dict[str, str | None] = {}
    for capability, candidates in FLAG_CANDIDATES.items():
        resolved[capability] = next((c for c in candidates if c in available), None)
    return resolved


class BrushBackend:
    """Implements `TrainerBackend` over the Brush CLI."""

    name = "brush"

    def __init__(
        self,
        workspace: Path,
        runner: ProcessRunner | None = None,
        executable: str = "brush",
    ) -> None:
        self.workspace = Path(workspace)
        self.runner = runner or ProcessRunner()
        self.executable = executable

    @property
    def dataset_view_dir(self) -> Path:
        return self.workspace / "train-view"

    @property
    def output_dir(self) -> Path:
        return self.workspace / "brush-output"

    # -- health -----------------------------------------------------------

    def doctor(self) -> BackendHealth:
        info = discover_tool(
            "brush", version_args=("--help",), executable=self.executable
        )
        if not info.available:
            return BackendHealth(name=self.name, available=False, error=info.error)

        help_text = info.raw_version_output or ""
        flags = parse_flags(help_text)
        resolved = resolve_flags(flags)
        missing = [c for c in REQUIRED_CAPABILITIES if resolved.get(c) is None]
        return BackendHealth(
            name=self.name,
            available=True,
            version=info.version,
            executable=info.executable,
            capabilities={
                "flags": sorted(flags),
                "resolved": resolved,
                "missing_required": missing,
                # Never asserted from documentation: whether the Metal/WebGPU
                # path is actually in use is recorded from a real run.
                "acceleration": "unverified",
            },
            error=(
                f"this Brush build does not expose {missing}; record the actual "
                "flags before training"
                if missing
                else None
            ),
        )

    def cancel(self) -> None:
        self.runner.cancel()

    # -- training ---------------------------------------------------------

    def prepare_dataset_view(self, dataset: ColmapDataset) -> Path:
        """Build a trainer-visible dataset containing only training frames."""
        view = self.dataset_view_dir
        if view.exists():
            shutil.rmtree(view)
        images = view / "images"
        sparse = view / "sparse" / "0"
        images.mkdir(parents=True, exist_ok=True)
        sparse.mkdir(parents=True, exist_ok=True)

        keep = set(dataset.training_frame_ids)
        excluded = set(dataset.evaluation_frame_ids)
        for image in sorted(Path(dataset.image_dir).iterdir()):
            if not image.is_file():
                continue
            if image.stem in keep and image.stem not in excluded:
                try:
                    (images / image.name).hardlink_to(image)
                except OSError:
                    shutil.copy2(image, images / image.name)

        kept = write_filtered_model(dataset.sparse_model_dir, sparse, keep)
        if kept == 0:
            raise AmberError(
                "the training dataset view contains no registered training "
                "images; the split and the camera model disagree"
            )
        leaked = [p.stem for p in images.iterdir() if p.stem in excluded]
        if leaked:  # pragma: no cover - defensive; the filter above prevents it
            raise AmberError(
                f"evaluation frames leaked into training supervision: {leaked[:5]}"
            )
        return view

    def train(
        self, dataset: ColmapDataset, config: TrainConfig, events: EventSink
    ) -> TrainResult:
        health = self.doctor()
        if not health.available:
            raise AmberError(
                "Brush is not installed. Run `amber doctor` for the full list "
                "of missing tools."
            )
        if health.error:
            raise AmberError(health.error)

        resolved: dict[str, str | None] = health.capabilities["resolved"]
        view = self.prepare_dataset_view(dataset)
        self.output_dir.mkdir(parents=True, exist_ok=True)

        command = [self.executable, str(view)]
        command += [str(resolved["output"]), str(self.output_dir)]
        command += _optional(resolved, "max_resolution", config.max_resolution, events)
        command += _optional(resolved, "total_steps", config.total_steps, events)
        command += _optional(resolved, "sh_degree", config.sh_degree, events)
        command += _optional(resolved, "max_splats", config.max_splats, events)
        command += list(config.extra_args)

        emit(events, "train", "info", "training Gaussian scene")
        try:
            result = self.runner.run(command)
        except SubprocessFailure as failure:
            return TrainResult(
                success=False,
                ply_path=None,
                command=command,
                config=config.to_dict(),
                dataset_view_dir=view,
                diagnostic=failure.diagnostic,
                message=str(failure),
            )

        ply = self._find_ply()
        if ply is None:
            return TrainResult(
                success=False,
                ply_path=None,
                command=command,
                config=config.to_dict(),
                dataset_view_dir=view,
                duration_seconds=result.duration_seconds,
                diagnostic="no_output_produced",
                message=(
                    "Brush exited successfully but produced no .ply file in "
                    f"{self.output_dir}."
                ),
            )
        return TrainResult(
            success=True,
            ply_path=ply,
            checkpoint_dir=self.output_dir,
            steps=config.total_steps,
            duration_seconds=result.duration_seconds,
            command=command,
            config=config.to_dict(),
            dataset_view_dir=view,
        )

    def _find_ply(self) -> Path | None:
        candidates = sorted(
            self.output_dir.rglob("*.ply"),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )
        return candidates[0] if candidates else None


def _optional(
    resolved: dict[str, str | None],
    capability: str,
    value: Any,
    events: EventSink,
) -> list[str]:
    """Add a flag only if this build exposes it; otherwise say so out loud.

    Silently dropping a setting would make the recorded config a fiction.
    """
    flag = resolved.get(capability)
    if flag is None:
        emit(
            events,
            "train",
            "warning",
            f"this Brush build exposes no flag for {capability}; the requested "
            f"value {value!r} was NOT applied and is recorded as unset",
            capability=capability,
            requested=value,
        )
        return []
    return [flag, str(value)]
