"""COLMAP pose backend.

Flags are *discovered* from the installed binary's own help output rather than
copied from a tutorial, because option names have moved between COLMAP versions
(for example `SiftExtraction.max_image_size` became
`FeatureExtraction.max_image_size`). Using an undiscovered flag would either
fail loudly or, worse, be silently ignored.
"""

from __future__ import annotations

import os
import re
import shutil
from pathlib import Path
from typing import Any, Sequence

from ...config import PoseConfig
from ...events import EventSink, emit
from ...models import AmberError, ReconstructionReport
from ...tools import ProcessRunner, SubprocessFailure, discover_tool
from .base import PoseBackendHealth, PoseFrame, PoseMask, PoseResult
from .colmap_model import model_stats

OPTION_PATTERN = re.compile(r"--([A-Za-z0-9_.]+)\s+arg(?:\s+\(=([^)]*)\))?")

# Option names that have differed across COLMAP versions, most recent first.
MAX_IMAGE_SIZE_OPTIONS = (
    "FeatureExtraction.max_image_size",
    "SiftExtraction.max_image_size",
)
CAMERA_MODEL_OPTIONS = ("ImageReader.camera_model",)
SINGLE_CAMERA_OPTIONS = ("ImageReader.single_camera",)
MASK_PATH_OPTIONS = ("ImageReader.mask_path",)
LOOP_DETECTION_OPTIONS = (
    "SequentialMatching.loop_detection",
    "SequentialMatching.vocab_tree_path",
)


def parse_help_options(help_text: str) -> dict[str, str | None]:
    """Extract `--Option arg (=default)` pairs from COLMAP help output."""
    options: dict[str, str | None] = {}
    for match in OPTION_PATTERN.finditer(help_text):
        options[match.group(1)] = match.group(2)
    return options


def resolve_option(
    options: dict[str, str | None], candidates: Sequence[str]
) -> str | None:
    """Return the first candidate this build actually supports."""
    for name in candidates:
        if name in options:
            return name
    return None


def parse_available_commands(help_text: str) -> set[str]:
    """COLMAP lists its subcommands one per line, indented, in `colmap help`."""
    commands: set[str] = set()
    for line in help_text.splitlines():
        stripped = line.strip()
        if not stripped or stripped.endswith(":") or stripped.startswith("-"):
            continue
        token = stripped.split()[0]
        if re.fullmatch(r"[a-z][a-z0-9_]+", token):
            commands.add(token)
    return commands


class ColmapPoseBackend:
    """Implements `PoseBackend` over the COLMAP CLI."""

    name = "colmap"

    def __init__(
        self,
        workspace: Path,
        runner: ProcessRunner | None = None,
        executable: str = "colmap",
    ) -> None:
        self.workspace = Path(workspace)
        self.runner = runner or ProcessRunner()
        self.executable = executable
        self._commands: list[dict[str, Any]] = []

    # -- layout -----------------------------------------------------------

    @property
    def image_dir(self) -> Path:
        return self.workspace / "images"

    @property
    def mask_dir(self) -> Path:
        return self.workspace / "pose-masks"

    @property
    def database_path(self) -> Path:
        return self.workspace / "database.db"

    @property
    def sparse_dir(self) -> Path:
        return self.workspace / "sparse"

    @property
    def sparse_text_dir(self) -> Path:
        return self.workspace / "sparse-txt"

    # -- health -----------------------------------------------------------

    def doctor(self) -> PoseBackendHealth:
        info = discover_tool("colmap", version_args=("--help",), executable=self.executable)
        if not info.available:
            return PoseBackendHealth(
                name=self.name, available=False, error=info.error
            )

        help_text = info.raw_version_output or ""
        try:
            help_text = self.runner.run(
                [self.executable, "help"], check=False
            ).stdout or help_text
        except OSError:  # pragma: no cover - defensive
            pass
        commands = parse_available_commands(help_text)

        extractor_options: dict[str, str | None] = {}
        try:
            result = self.runner.run(
                [self.executable, "feature_extractor", "--help"], check=False
            )
            extractor_options = parse_help_options(result.stdout + result.stderr)
        except OSError:  # pragma: no cover - defensive
            pass

        max_size_option = resolve_option(extractor_options, MAX_IMAGE_SIZE_OPTIONS)
        capabilities = {
            "commands": sorted(commands),
            "has_global_mapper": "global_mapper" in commands,
            "has_view_graph_calibrator": "view_graph_calibrator" in commands,
            "max_image_size_option": max_size_option,
            "max_image_size_cli_default": (
                extractor_options.get(max_size_option) if max_size_option else None
            ),
            "feature_types": sorted(
                t
                for t in ("sift", "aliked")
                if any(t in name.lower() for name in extractor_options)
            )
            or ["sift"],
            # Deliberately not asserted: GPU SIFT availability on Apple silicon
            # is a measured property, recorded by the M0 doctor run.
            "gpu_acceleration": "unverified",
        }
        return PoseBackendHealth(
            name=self.name,
            available=True,
            version=_version_from_help(help_text) or info.version,
            executable=info.executable,
            capabilities=capabilities,
        )

    # -- control ----------------------------------------------------------

    def cancel(self) -> None:
        self.runner.cancel()

    # -- reconstruction ---------------------------------------------------

    def reconstruct(
        self,
        frames: Sequence[PoseFrame],
        masks: Sequence[PoseMask] | None,
        config: PoseConfig,
        events: EventSink,
    ) -> PoseResult:
        if not frames:
            raise AmberError("no frames supplied to the pose backend")

        health = self.doctor()
        if not health.available:
            raise AmberError(
                "COLMAP is not installed. Run `amber doctor` for the full list "
                "of missing tools."
            )

        self._commands = []
        self._stage_images(frames)
        if masks and config.use_pose_masks:
            self._stage_masks(masks)

        timings: dict[str, float] = {}
        capabilities = health.capabilities

        try:
            timings["extraction"] = self._extract_features(
                config, capabilities, bool(masks and config.use_pose_masks), events
            )
            timings["matching"] = self._match(config, capabilities, events)
            timings["mapping"] = self._map(config, capabilities, events)
        except SubprocessFailure as failure:
            return PoseResult(
                success=False,
                sparse_model_dir=None,
                database_path=self.database_path,
                report=ReconstructionReport(
                    total_pose_input_frames=len(frames),
                    selected_training_frames=sum(
                        1 for f in frames if f.role == "train"
                    ),
                    reserved_evaluation_frames=sum(
                        1 for f in frames if f.role == "eval"
                    ),
                    timings_seconds=timings,
                ),
                commands=list(self._commands),
                config=config.to_dict(),
                diagnostic=failure.diagnostic,
                message=str(failure),
            )

        models = self._converted_models(events)
        if not models:
            return PoseResult(
                success=False,
                sparse_model_dir=None,
                database_path=self.database_path,
                report=ReconstructionReport(
                    total_pose_input_frames=len(frames),
                    timings_seconds=timings,
                ),
                commands=list(self._commands),
                config=config.to_dict(),
                diagnostic="mapper_produced_no_model",
                message=(
                    "COLMAP finished without producing any camera model. The "
                    "views could not be linked into a single reconstruction."
                ),
            )

        report = self._build_report(frames, models, config, capabilities, timings)
        return PoseResult(
            success=True,
            sparse_model_dir=models[0]["dir"],
            database_path=self.database_path,
            report=report,
            commands=list(self._commands),
            config=config.to_dict(),
            effective_image_size=report.effective_image_size,
        )

    # -- stages -----------------------------------------------------------

    def _stage_images(self, frames: Sequence[PoseFrame]) -> None:
        """Materialise the pose tier in one flat directory COLMAP can read."""
        if self.image_dir.exists():
            shutil.rmtree(self.image_dir)
        self.image_dir.mkdir(parents=True, exist_ok=True)
        for frame in frames:
            dest = self.image_dir / f"{frame.id}{Path(frame.path).suffix}"
            try:
                os.link(frame.path, dest)  # hard link: no second copy on disk
            except OSError:
                shutil.copy2(frame.path, dest)

    def _stage_masks(self, masks: Sequence[PoseMask]) -> None:
        self.mask_dir.mkdir(parents=True, exist_ok=True)
        for mask in masks:
            shutil.copy2(mask.path, self.mask_dir / f"{mask.frame_id}.png")

    def _run(self, command: list[str], stage: str) -> float:
        result = self.runner.run(command)
        self._commands.append({"stage": stage, **result.to_dict()})
        return result.duration_seconds

    def _extract_features(
        self,
        config: PoseConfig,
        capabilities: dict[str, Any],
        use_masks: bool,
        events: EventSink,
    ) -> float:
        emit(events, "poses", "info", "extracting image features")
        command = [
            self.executable,
            "feature_extractor",
            "--database_path",
            str(self.database_path),
            "--image_path",
            str(self.image_dir),
        ]
        max_size_option = capabilities.get("max_image_size_option")
        if max_size_option:
            command += [f"--{max_size_option}", str(config.max_image_size)]
        command += [
            f"--{CAMERA_MODEL_OPTIONS[0]}",
            config.camera_model,
            f"--{SINGLE_CAMERA_OPTIONS[0]}",
            "1" if config.single_camera else "0",
        ]
        if use_masks:
            command += [f"--{MASK_PATH_OPTIONS[0]}", str(self.mask_dir)]
        return self._run(command, "feature_extraction")

    def _match(
        self, config: PoseConfig, capabilities: dict[str, Any], events: EventSink
    ) -> float:
        emit(events, "poses", "info", f"matching views ({config.matcher_type})")
        matcher = {
            "sequential": "sequential_matcher",
            "exhaustive": "exhaustive_matcher",
            "vocab_tree": "vocab_tree_matcher",
        }.get(config.matcher_type)
        if matcher is None:
            raise AmberError(f"unknown matcher type {config.matcher_type!r}")

        command = [
            self.executable,
            matcher,
            "--database_path",
            str(self.database_path),
        ]
        if matcher == "sequential_matcher" and config.loop_detection:
            command += ["--SequentialMatching.loop_detection", "1"]
            if config.vocab_tree_path:
                command += [
                    "--SequentialMatching.vocab_tree_path",
                    config.vocab_tree_path,
                ]
        return self._run(command, "matching")

    def _map(
        self, config: PoseConfig, capabilities: dict[str, Any], events: EventSink
    ) -> float:
        self.sparse_dir.mkdir(parents=True, exist_ok=True)
        elapsed = 0.0

        if config.mapper_type == "global":
            if not capabilities.get("has_global_mapper"):
                raise AmberError(
                    "this COLMAP build has no `global_mapper`. Amber does not "
                    "silently substitute a different mapper, because that would "
                    "make the run unattributable."
                )
            if capabilities.get("has_view_graph_calibrator"):
                emit(events, "poses", "info", "calibrating view graph")
                elapsed += self._run(
                    [
                        self.executable,
                        "view_graph_calibrator",
                        "--database_path",
                        str(self.database_path),
                    ],
                    "view_graph_calibration",
                )
            emit(events, "poses", "info", "reconstructing (global mapper)")
            elapsed += self._run(
                [
                    self.executable,
                    "global_mapper",
                    "--database_path",
                    str(self.database_path),
                    "--image_path",
                    str(self.image_dir),
                    "--output_path",
                    str(self.sparse_dir),
                ],
                "global_mapping",
            )
        elif config.mapper_type == "incremental":
            emit(events, "poses", "info", "reconstructing (incremental mapper)")
            elapsed += self._run(
                [
                    self.executable,
                    "mapper",
                    "--database_path",
                    str(self.database_path),
                    "--image_path",
                    str(self.image_dir),
                    "--output_path",
                    str(self.sparse_dir),
                ],
                "incremental_mapping",
            )
        else:
            raise AmberError(f"unknown mapper type {config.mapper_type!r}")
        return elapsed

    def _converted_models(self, events: EventSink) -> list[dict[str, Any]]:
        """Convert every produced model to text and rank them by size.

        More than one model means the capture broke into disconnected pieces —
        recorded, not hidden, because the dominant-model fraction is a gate
        condition.
        """
        models: list[dict[str, Any]] = []
        if not self.sparse_dir.is_dir():
            return models
        for sub in sorted(self.sparse_dir.iterdir()):
            if not sub.is_dir():
                continue
            out_dir = self.sparse_text_dir / sub.name
            out_dir.mkdir(parents=True, exist_ok=True)
            self._run(
                [
                    self.executable,
                    "model_converter",
                    "--input_path",
                    str(sub),
                    "--output_path",
                    str(out_dir),
                    "--output_type",
                    "TXT",
                ],
                "model_conversion",
            )
            try:
                stats = model_stats(out_dir)
            except FileNotFoundError:
                continue
            models.append({"dir": sub, "text_dir": out_dir, "stats": stats})
        models.sort(key=lambda m: m["stats"].registered_images, reverse=True)
        return models

    # -- reporting --------------------------------------------------------

    def _build_report(
        self,
        frames: Sequence[PoseFrame],
        models: list[dict[str, Any]],
        config: PoseConfig,
        capabilities: dict[str, Any],
        timings: dict[str, float],
    ) -> ReconstructionReport:
        largest = models[0]["stats"]
        registered_ids = {Path(name).stem for name in largest.image_names}
        total_registered = sum(m["stats"].registered_images for m in models)

        by_id = {f.id: f for f in frames}
        registered_frames = [f for f in frames if f.id in registered_ids]

        report = ReconstructionReport(
            selected_training_frames=sum(1 for f in frames if f.role == "train"),
            reserved_evaluation_frames=sum(1 for f in frames if f.role == "eval"),
            total_pose_input_frames=len(frames),
            registered_frames=len(registered_frames),
            registered_frame_ids=sorted(registered_ids & set(by_id)),
            registered_evaluation_frame_ids=sorted(
                f.id for f in registered_frames if f.role == "eval"
            ),
            sparse_point_count=largest.sparse_point_count,
            median_observations_per_point=largest.median_observations_per_point,
            mean_reprojection_error_px=largest.mean_reprojection_error_px,
            camera_path_extent=largest.camera_path_extent,
            median_scene_depth=largest.median_scene_depth,
            median_triangulation_angle_deg=largest.median_triangulation_angle_deg,
            connected_model_count=len(models),
            largest_model_frame_fraction=(
                largest.registered_images / total_registered
                if total_registered
                else 0.0
            ),
            timings_seconds=timings,
            effective_image_size={
                "option": capabilities.get("max_image_size_option"),
                "cli_default": capabilities.get("max_image_size_cli_default"),
                "requested": config.max_image_size,
            },
        )
        gap_seconds, gap_frames = temporal_gaps(frames, registered_ids)
        report.longest_temporal_gap_seconds = gap_seconds
        report.longest_consecutive_missing_selected = gap_frames
        return report


def temporal_gaps(
    frames: Sequence[PoseFrame], registered_ids: set[str]
) -> tuple[float, int]:
    """Longest unregistered stretch, in seconds and in consecutive frames.

    Both are reported because they answer different questions: seconds says how
    much of the walk is missing, consecutive frames says whether the camera
    track was broken.
    """
    ordered = sorted(frames, key=lambda f: (f.timestamp, f.id))
    longest_seconds = 0.0
    longest_run = 0
    run = 0
    run_start_time: float | None = None
    last_registered_time: float | None = None

    for frame in ordered:
        if frame.id in registered_ids:
            if run:
                start = (
                    last_registered_time
                    if last_registered_time is not None
                    else run_start_time or frame.timestamp
                )
                longest_seconds = max(longest_seconds, frame.timestamp - start)
                longest_run = max(longest_run, run)
            run = 0
            run_start_time = None
            last_registered_time = frame.timestamp
        else:
            if run == 0:
                run_start_time = frame.timestamp
            run += 1

    if run:
        longest_run = max(longest_run, run)
        start = (
            last_registered_time
            if last_registered_time is not None
            else run_start_time or 0.0
        )
        longest_seconds = max(longest_seconds, ordered[-1].timestamp - start)
    return longest_seconds, longest_run


def _version_from_help(text: str) -> str | None:
    match = re.search(r"COLMAP\s+([0-9]+\.[0-9]+(?:\.[0-9]+)?)", text)
    return match.group(1) if match else None
