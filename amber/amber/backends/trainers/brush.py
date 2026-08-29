"""Brush trainer backend.

Two disciplines matter more than convenience here:

1. **Flags are discovered, not assumed.** Brush is a moving target; a flag
   copied from a tutorial may be silently ignored by a different build, which
   would produce a run whose recorded config does not describe what happened.
   If a required capability is not present in `--help`, this backend fails with
   an explicit message rather than guessing.

2. **The split is aligned, then verified.** Brush can only render an evaluation
   set it selected itself, by stride, and offers no render-from-given-cameras
   mode (ADR 0004). So the dataset view is built such that Brush's own stride
   selection lands on exactly the frames Amber locked — Amber's frame IDs sort
   temporally, and its production split is every Nth frame from the first, which
   is precisely what `--eval-split-every N` picks. Alignment is checked
   arithmetically *before* training starts, and the set Brush actually rendered
   is checked against the locked set *after*. A mismatch fails the run; it is
   never reconciled by substituting or dropping a frame.
"""

from __future__ import annotations

import re
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Sequence

from ...config import TrainConfig
from ...events import EventSink, emit
from ...models import AmberError
from ...tools import (
    ProcessRunner,
    SubprocessFailure,
    discover_tool,
    resolve_version,
)
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

REQUIRED_CAPABILITIES = ("output", "eval_split", "eval_save_to_disk")

# Brush writes each evaluation pass to `eval_<step>/` beneath --export-path.
EVAL_DIR_PATTERN = re.compile(r"^eval_(\d+)$")


def parse_flags(help_text: str) -> set[str]:
    return set(FLAG_PATTERN.findall(help_text))


@dataclass
class DatasetView:
    """A trainer-visible dataset whose stride selection matches Amber's split."""

    path: Path
    stride: int
    ordered_frame_ids: list[str]
    expected_evaluation_ids: list[str]

    def to_dict(self) -> dict[str, Any]:
        return {
            "path": str(self.path),
            "stride": self.stride,
            "frame_count": len(self.ordered_frame_ids),
            "expected_evaluation_ids": self.expected_evaluation_ids,
        }


def stride_for_split(
    ordered_frame_ids: Sequence[str], evaluation_ids: Iterable[str]
) -> int:
    """Find the `--eval-split-every` value that selects exactly this split.

    Brush selects sorted-filename indices 0, N, 2N, … (measured against the M0
    public control; see ADR 0004). A split is expressible only when its members
    sit at exactly those positions. Anything else raises, because quietly
    training on a near-enough split would make every held-out metric describe an
    experiment nobody specified.
    """
    wanted = set(evaluation_ids)
    positions = [i for i, fid in enumerate(ordered_frame_ids) if fid in wanted]
    total = len(ordered_frame_ids)

    if not positions:
        raise AmberError(
            "no evaluation frames are present in the dataset view; the split and "
            "the camera model disagree"
        )
    if positions[0] != 0:
        raise AmberError(
            "this evaluation split is not expressible as a stride: its first "
            f"member sits at position {positions[0]}, but the trainer's stride "
            "selection always begins at position 0. A stratified comparison "
            "split needs a renderer that accepts arbitrary cameras (ADR 0004)."
        )

    if len(positions) == 1:
        stride = total
    else:
        gaps = {b - a for a, b in zip(positions, positions[1:])}
        if len(gaps) != 1:
            raise AmberError(
                "this evaluation split is not expressible as a stride: its "
                f"members are spaced irregularly ({sorted(gaps)}). A stratified "
                "comparison split needs a renderer that accepts arbitrary "
                "cameras (ADR 0004)."
            )
        stride = gaps.pop()

    selected = list(range(0, total, stride))
    if selected != positions:
        raise AmberError(
            f"stride {stride} would hold out {len(selected)} frames but the "
            f"locked split has {len(positions)}; refusing to train against a "
            "split the trainer would not reproduce"
        )
    return stride


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

        # `--help` opens with a banner, not a version, so ask separately.
        version = resolve_version(self.runner, self.executable, info.version)

        return BackendHealth(
            name=self.name,
            available=True,
            version=version,
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

    def prepare_dataset_view(self, dataset: ColmapDataset) -> DatasetView:
        """Build a trainer-visible dataset aligned to Amber's locked split.

        The view contains training *and* evaluation frames, because Brush can
        only render a set it selected itself. What keeps that honest is that the
        stride is derived from the locked split and checked arithmetically here,
        before a single training step runs — so an unexpressible split fails now
        rather than producing metrics for the wrong frames.
        """
        view = self.dataset_view_dir
        if view.exists():
            shutil.rmtree(view)
        images = view / "images"
        sparse = view / "sparse" / "0"
        images.mkdir(parents=True, exist_ok=True)
        sparse.mkdir(parents=True, exist_ok=True)

        training = list(dataset.training_frame_ids)
        evaluation = list(dataset.evaluation_frame_ids)
        overlap = set(training) & set(evaluation)
        if overlap:
            raise AmberError(
                "the same frame is marked both training and evaluation: "
                f"{sorted(overlap)[:5]}"
            )

        sources: dict[str, Path] = {}
        for frame_id in training:
            sources[frame_id] = Path(dataset.image_dir) / f"{frame_id}.png"
        eval_dir = Path(
            dataset.evaluation_image_dir or dataset.image_dir
        )
        for frame_id in evaluation:
            sources[frame_id] = eval_dir / f"{frame_id}.png"

        missing = sorted(fid for fid, path in sources.items() if not path.is_file())
        if missing:
            raise AmberError(
                f"{len(missing)} frame image(s) named in the split are missing "
                f"from disk, first few: {missing[:5]}"
            )

        # Frame IDs are zero-padded and sequential, so filename order is
        # temporal order. Brush sorts by filename, which is what makes the
        # stride alignment below hold.
        ordered = sorted(sources)
        for frame_id in ordered:
            destination = images / f"{frame_id}.png"
            try:
                destination.hardlink_to(sources[frame_id])
            except OSError:
                shutil.copy2(sources[frame_id], destination)

        stride = stride_for_split(ordered, evaluation)

        kept = write_filtered_model(dataset.sparse_model_dir, sparse, set(ordered))
        if kept != len(ordered):
            raise AmberError(
                f"the camera model covers {kept} of {len(ordered)} split frames; "
                "the split and the camera model disagree"
            )
        return DatasetView(
            path=view,
            stride=stride,
            ordered_frame_ids=ordered,
            expected_evaluation_ids=sorted(evaluation),
        )

    def collect_evaluation_renders(
        self, expected_ids: Sequence[str]
    ) -> tuple[Path, list[str]]:
        """Find the latest eval render directory and check what it contains.

        Brush names each pass `eval_<step>/` and each render after its source
        image's stem, so the filenames come back already keyed to Amber's frame
        IDs. The set is compared to the locked split and any difference is
        fatal — a missing held-out render is evidence about the run, not
        permission to score a smaller test set.
        """
        candidates: list[tuple[int, Path]] = []
        for child in self.output_dir.iterdir() if self.output_dir.is_dir() else []:
            match = EVAL_DIR_PATTERN.match(child.name)
            if child.is_dir() and match:
                candidates.append((int(match.group(1)), child))
        if not candidates:
            raise AmberError(
                "the trainer produced no evaluation renders. Amber will not "
                "report a quality result it did not measure."
            )
        _step, render_dir = max(candidates, key=lambda item: item[0])

        rendered = sorted(p.stem for p in render_dir.iterdir() if p.is_file())
        expected = sorted(expected_ids)
        if rendered != expected:
            missing = sorted(set(expected) - set(rendered))
            extra = sorted(set(rendered) - set(expected))
            raise AmberError(
                "the trainer held out a different set of views than the locked "
                f"evaluation split: {len(missing)} missing "
                f"{missing[:3]}, {len(extra)} unexpected {extra[:3]}. Refusing "
                "to score this run against a split it did not honour."
            )
        return render_dir, rendered

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

        command = [self.executable, str(view.path)]
        command += [str(resolved["output"]), str(self.output_dir)]
        command += [str(resolved["eval_split"]), str(view.stride)]
        command += [str(resolved["eval_save_to_disk"])]
        command += _optional(resolved, "max_resolution", config.max_resolution, events)
        command += _optional(resolved, "total_steps", config.total_steps, events)
        command += _optional(resolved, "sh_degree", config.sh_degree, events)
        command += _optional(resolved, "max_splats", config.max_splats, events)
        command += list(config.extra_args)

        emit(
            events,
            "train",
            "info",
            f"training on {len(view.ordered_frame_ids) - len(view.expected_evaluation_ids)} "
            f"views, holding out {len(view.expected_evaluation_ids)} "
            f"(stride {view.stride})",
            stride=view.stride,
        )
        try:
            result = self.runner.run(command)
        except SubprocessFailure as failure:
            return TrainResult(
                success=False,
                ply_path=None,
                command=command,
                config=config.to_dict(),
                dataset_view_dir=view.path,
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
                dataset_view_dir=view.path,
                duration_seconds=result.duration_seconds,
                diagnostic="no_output_produced",
                message=(
                    "Brush exited successfully but produced no .ply file in "
                    f"{self.output_dir}."
                ),
            )

        render_dir, rendered_ids = self.collect_evaluation_renders(
            view.expected_evaluation_ids
        )
        return TrainResult(
            success=True,
            ply_path=ply,
            checkpoint_dir=self.output_dir,
            steps=config.total_steps,
            duration_seconds=result.duration_seconds,
            command=command,
            config=config.to_dict(),
            dataset_view_dir=view.path,
            evaluation_render_dir=render_dir,
            evaluation_rendered_ids=rendered_ids,
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
