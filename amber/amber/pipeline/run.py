"""The golden path: one video in, one complete scene archive out.

Every stage is atomic and resumable, records its storage, and either produces
its artifacts or fails with a diagnostic naming the responsible stage.
"""

from __future__ import annotations

import shutil
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ..config import (
    CandidateConfig,
    PoseGateThresholds,
    Profile,
    SplitConfig,
    default_library_root,
)
from ..events import (
    CompositeEventSink,
    ConsoleEventSink,
    EventSink,
    JsonlEventSink,
    emit,
)
from ..models import (
    AmberError,
    ARCHIVAL_CORE,
    EVAL,
    FrameRecord,
    Manifest,
    REGENERABLE,
    Split,
    TRAIN,
)
from ..services.jobs import StageState
from ..services.projects import SceneStore, sha256_file, tree_bytes
from ..services.storage import (
    StorageReport,
    estimate_required_space,
    measure_scene,
)
from ..tools import ProcessRunner, SubprocessFailure
from ..backends.poses.base import PoseFrame
from ..backends.poses.colmap import ColmapPoseBackend
from ..backends.trainers.base import ColmapDataset
from ..backends.trainers.brush import BrushBackend
from . import frames as frames_mod
from . import import_video, package as package_mod, poses as poses_mod
from .quality import MotionArtifactReview, evaluate_holdout

FRAME_REPORT = "qa/frame-report.json"
RECONSTRUCTION_REPORT = "qa/reconstruction-report.json"
EVALUATION_METRICS = "qa/evaluation-metrics.json"
MOTION_REVIEW = "qa/motion-artifact-review.json"
STORAGE_REPORT = "qa/storage-report.json"


@dataclass
class RunOptions:
    profile: Profile
    title: str = ""
    capture_class: str = "room"
    comparison_group_id: str | None = None
    notes: str = ""
    skip_space_check: bool = False


class Pipeline:
    """Runs stages in order, skipping those already complete."""

    def __init__(
        self,
        store: SceneStore,
        options: RunOptions,
        events: EventSink | None = None,
        runner: ProcessRunner | None = None,
    ) -> None:
        self.store = store
        self.options = options
        self.runner = runner or ProcessRunner()
        self.state = StageState.load(store.working_dir / "state.json")
        self.storage = StorageReport()
        self.events: EventSink = events or CompositeEventSink(
            ConsoleEventSink(), JsonlEventSink(store.log_path)
        )

    # -- helpers ----------------------------------------------------------

    def _manifest(self) -> Manifest:
        return self.store.read_manifest()

    def _save(self, manifest: Manifest) -> None:
        self.store.write_manifest(manifest)

    def _record_storage(self, stage: str, input_bytes: int, output_paths: list[Path]):
        output = sum(tree_bytes(p) for p in output_paths)
        self.storage.record(stage, input_bytes=input_bytes, output_bytes=output)

    def cancel(self) -> None:
        self.runner.cancel()

    # -- stages -----------------------------------------------------------

    def run(self, video: Path | None = None) -> Manifest:
        manifest = self._manifest()
        try:
            manifest = self.stage_import(manifest, video)
            manifest = self.stage_frames(manifest)
            manifest = self.stage_poses(manifest)
            manifest = self.stage_train(manifest)
            manifest = self.stage_quality(manifest)
            manifest = self.stage_package(manifest)
        finally:
            self._write_storage_report(manifest)
        return manifest

    # -- import -----------------------------------------------------------

    def stage_import(self, manifest: Manifest, video: Path | None) -> Manifest:
        if self.state.is_complete("import"):
            return manifest
        if video is None:
            raise AmberError("no video supplied and the import stage is incomplete")

        self.state.begin("import")
        emit(self.events, "import", "started", "Preparing the video")
        try:
            metadata = import_video.probe(video, self.runner)
            health = import_video.assess_footage(metadata)

            if not self.options.skip_space_check:
                estimate = estimate_required_space(
                    Path(video).stat().st_size, self.store.root
                )
                if not estimate.sufficient:
                    raise AmberError(
                        "not enough free disk space: " + estimate.message() + ". "
                        "Free space or prune working data from an older scene "
                        "before processing."
                    )

            destination, digest = self.store.ingest_source(video)
            for warning in health.warnings:
                emit(self.events, "import", "warning", warning)

            manifest.title = manifest.title or self.options.title
            manifest.captured_at = manifest.captured_at or metadata.creation_time
            manifest.notes = manifest.notes or self.options.notes
            manifest.source = {
                "filename": metadata.filename,
                "sha256": digest,
                "device": metadata.device,
                "video_metadata": metadata.to_dict(),
                "footage_health": health.to_dict(),
            }
            manifest.pipeline.setdefault("amber_version", _amber_version())
            manifest.pipeline["profile"] = self.options.profile.to_dict()
            manifest.pipeline["capture_class"] = self.options.capture_class
            manifest.pipeline["color_transform"] = {
                "source_transfer": metadata.color_transfer,
                "source_primaries": metadata.color_primaries,
                "working_space": "rec709-sdr",
                "applied": bool(metadata.is_hdr),
            }
            self.store.register_artifact(
                manifest, destination, "source_video", ARCHIVAL_CORE
            )
            self._save(manifest)
            self._record_storage(
                "import", Path(video).stat().st_size, [destination]
            )
            self.state.complete("import", sha256=digest)
            emit(self.events, "import", "completed", f"imported {destination.name}")
        except (AmberError, SubprocessFailure) as exc:
            self._fail("import", exc)
            raise
        return manifest

    # -- frames -----------------------------------------------------------

    def stage_frames(self, manifest: Manifest) -> Manifest:
        if self.state.is_complete("frames"):
            return manifest

        self.state.begin("frames")
        emit(self.events, "frames", "started", "Finding clear viewpoints")
        try:
            profile = self.options.profile
            candidate_config = CandidateConfig.from_plan()
            candidate_dir = self.store.working_dir / "candidate-frames"

            candidates = frames_mod.extract_candidates(
                self.store.source_dir / manifest.source["filename"],
                candidate_dir,
                candidate_config,
                self.runner,
                self.events,
            )
            frames_mod.score_frames(candidates, candidate_dir, self.events)
            frames_mod.apply_eligibility(candidates, candidate_config)

            eligible = frames_mod.eligible_frames(candidates)
            if not eligible:
                raise AmberError(
                    "every candidate frame was rejected as too blurry or too "
                    "badly exposed to use. Re-record with steadier movement and "
                    "more even light."
                )
            emit(
                self.events,
                "frames",
                "info",
                f"{len(eligible)} of {len(candidates)} candidates are eligible",
            )

            split, selected = self._build_selection(manifest, eligible, profile)
            frames_mod.apply_roles(candidates, split)

            training = [f for f in selected if f.role == TRAIN]
            evaluation = [f for f in selected if f.role == EVAL]

            pose_paths = frames_mod.write_tier(
                selected,
                candidate_dir,
                self.store.working_dir / "pose-frames",
                profile.pose_long_edge,
            )
            train_paths = frames_mod.write_tier(
                training,
                candidate_dir,
                self.store.working_dir / "training-frames",
                profile.training_long_edge,
            )
            eval_paths = frames_mod.write_tier(
                evaluation,
                candidate_dir,
                self.store.working_dir / "evaluation-frames",
                profile.training_long_edge,
            )

            cfg = manifest.frame_config
            cfg.pose_long_edge = profile.pose_long_edge
            cfg.training_long_edge = profile.training_long_edge
            cfg.decode_fps = candidate_config.decode_fps
            manifest.set_frame_config(cfg)
            manifest.set_split(split)

            self.store.write_json(
                FRAME_REPORT,
                frames_mod.frame_report(
                    candidates, split, candidate_config.to_dict()
                ),
            )
            for directory, role in (
                (self.store.working_dir / "candidate-frames", "candidate_frames"),
                (self.store.working_dir / "pose-frames", "pose_frames"),
                (self.store.working_dir / "training-frames", "training_frames"),
                (self.store.working_dir / "evaluation-frames", "evaluation_frames"),
            ):
                self.store.register_artifact(manifest, directory, role, REGENERABLE)
            self.store.register_artifact(
                manifest, self.store.abs(FRAME_REPORT), "frame_report", ARCHIVAL_CORE
            )
            self._save(manifest)
            self._record_storage(
                "frames",
                tree_bytes(candidate_dir),
                [
                    self.store.working_dir / "pose-frames",
                    self.store.working_dir / "training-frames",
                    self.store.working_dir / "evaluation-frames",
                ],
            )
            self.state.complete(
                "frames",
                candidates=len(candidates),
                selected=len(selected),
                training=len(training),
                evaluation=len(evaluation),
            )
            emit(
                self.events,
                "frames",
                "completed",
                f"selected {len(selected)} views "
                f"({len(training)} training, {len(evaluation)} held out)",
            )
        except (AmberError, SubprocessFailure) as exc:
            self._fail("frames", exc)
            raise
        return manifest

    def _build_selection(
        self, manifest: Manifest, eligible: list[FrameRecord], profile: Profile
    ) -> tuple[Split, list[FrameRecord]]:
        """Reserve evaluation views and choose training views.

        For a comparison group the evaluation set is reserved *before* any
        training selection, so no configuration can influence what tests it.
        For a production run the holdout is assigned after registration, so at
        this point only the pose input is chosen.
        """
        if self.options.comparison_group_id:
            split_config = SplitConfig.comparative(self.options.comparison_group_id)
            split = frames_mod.reserve_fixed_evaluation(eligible, split_config)
            training = frames_mod.select_training_frames(
                eligible, split, profile.target_training_frames
            )
            split.training_frame_ids = [f.id for f in training]
            split.lock()
            emit(
                self.events,
                "frames",
                "info",
                f"reserved and locked {len(split.evaluation_frame_ids)} evaluation "
                f"frames for comparison group "
                f"{self.options.comparison_group_id!r}",
            )
            by_id = {f.id: f for f in eligible}
            selected_ids = frames_mod.pose_input_ids(split)
            return split, [by_id[i] for i in selected_ids if i in by_id]

        # Production run: every selected frame goes to the pose solver; the
        # holdout is assigned once we know which frames actually registered.
        selected = frames_mod.stratified_pick(
            eligible, profile.target_training_frames
        )
        split = Split(
            policy=SplitConfig.production().policy,
            evaluation_interval=SplitConfig.production().evaluation_interval,
            training_frame_ids=[f.id for f in selected],
            evaluation_frame_ids=[],
            candidate_pool_sha256=frames_mod.candidate_pool_hash(eligible),
        )
        return split, selected

    # -- poses ------------------------------------------------------------

    def stage_poses(self, manifest: Manifest) -> Manifest:
        if self.state.is_complete("poses"):
            return manifest

        self.state.begin("poses")
        emit(self.events, "poses", "started", "Reconstructing the camera path")
        try:
            split = manifest.frame_config.as_split()
            pose_dir = self.store.working_dir / "pose-frames"
            report_doc = self.store.abs(FRAME_REPORT)
            frame_records = _load_frame_records(report_doc)
            by_id = {f.id: f for f in frame_records}

            pose_frames = [
                PoseFrame(
                    id=frame_id,
                    path=pose_dir / f"{frame_id}.png",
                    timestamp=by_id[frame_id].timestamp if frame_id in by_id else 0.0,
                    role=EVAL if frame_id in set(split.evaluation_frame_ids) else TRAIN,
                )
                for frame_id in frames_mod.pose_input_ids(split)
            ]

            backend = ColmapPoseBackend(
                self.store.working_dir / "colmap", runner=self.runner
            )
            result = backend.reconstruct(
                pose_frames, None, self.options.profile.pose, self.events
            )

            if not result.success:
                self.store.write_json(
                    RECONSTRUCTION_REPORT,
                    {"pose_result": result.to_dict(), "gate": None},
                )
                raise AmberError(
                    f"camera reconstruction failed: {result.message}"
                    if result.message
                    else "camera reconstruction failed"
                )

            # Production split: assign the holdout now that registration is known.
            if not split.evaluation_frame_ids:
                registered = [
                    by_id[i] for i in result.report.registered_frame_ids if i in by_id
                ]
                split = frames_mod.registered_interval_split(
                    registered, SplitConfig.production()
                )
                split.lock()
                manifest.set_split(split)
                result.report.selected_training_frames = len(split.training_frame_ids)
                result.report.reserved_evaluation_frames = len(
                    split.evaluation_frame_ids
                )
                result.report.registered_evaluation_frame_ids = list(
                    split.evaluation_frame_ids
                )
                emit(
                    self.events,
                    "poses",
                    "info",
                    f"held out {len(split.evaluation_frame_ids)} registered views "
                    "from training supervision and locked the split",
                )

            thresholds = PoseGateThresholds.for_capture_class(
                self.options.capture_class
            )
            gate = poses_mod.evaluate_pose_gate(result.report, thresholds)
            poses_mod.emit_gate(self.events, gate)

            self.store.write_json(
                RECONSTRUCTION_REPORT,
                {
                    **poses_mod.reconstruction_report_document(
                        result.report, gate, thresholds, result.config
                    ),
                    "commands": result.commands,
                },
            )
            self.store.register_artifact(
                manifest,
                self.store.abs(RECONSTRUCTION_REPORT),
                "reconstruction_report",
                ARCHIVAL_CORE,
            )
            self.store.register_artifact(
                manifest,
                self.store.working_dir / "colmap",
                "colmap_workspace",
                REGENERABLE,
            )
            manifest.pipeline["pose_config"] = result.config
            manifest.quality["pose_gate"] = gate.to_dict()
            self._save(manifest)
            self._record_storage(
                "poses",
                tree_bytes(pose_dir),
                [self.store.working_dir / "colmap"],
            )

            if not gate.passed:
                message = poses_mod.gate_message(gate)
                self.state.fail(
                    "poses", message, diagnostic=gate.primary_diagnostic()
                )
                emit(self.events, "poses", "failed", message)
                raise AmberError(message)

            self.state.complete(
                "poses",
                registered=result.report.registered_frames,
                sparse_model_dir=str(result.sparse_model_dir),
                text_model_dir=str(backend.sparse_text_dir / result.sparse_model_dir.name),
            )
            emit(
                self.events,
                "poses",
                "completed",
                f"registered {result.report.registered_frames} of "
                f"{result.report.total_pose_input_frames} views",
            )
        except (AmberError, SubprocessFailure) as exc:
            self._fail("poses", exc)
            raise
        return manifest

    # -- train ------------------------------------------------------------

    def stage_train(self, manifest: Manifest) -> Manifest:
        if self.state.is_complete("train"):
            return manifest
        if not self.state.is_complete("poses"):
            raise AmberError(
                "training is gated on a healthy camera solution; the pose stage "
                "has not passed"
            )

        self.state.begin("train")
        emit(self.events, "train", "started", "Building the scene")
        try:
            split = manifest.frame_config.as_split()
            if not manifest.split_locked:
                raise AmberError(
                    "refusing to train against an unlocked split; the metrics "
                    "would describe an experiment that could still change"
                )
            split.validate_disjoint()

            text_model = Path(
                self.state.record("poses").outputs["text_model_dir"]
            )
            dataset = ColmapDataset(
                image_dir=self.store.working_dir / "training-frames",
                evaluation_image_dir=self.store.working_dir / "evaluation-frames",
                sparse_model_dir=text_model,
                training_frame_ids=list(split.training_frame_ids),
                evaluation_frame_ids=list(split.evaluation_frame_ids),
            )
            backend = BrushBackend(
                self.store.working_dir / "brush", runner=self.runner
            )
            result = backend.train(dataset, self.options.profile.train, self.events)
            if not result.success:
                raise AmberError(result.message or "training failed")

            manifest.pipeline["trainer_backend"] = backend.name
            manifest.pipeline["trainer_config"] = result.config
            manifest.pipeline.setdefault("tools", {})["brush"] = (
                backend.doctor().to_dict()
            )
            self.store.register_artifact(
                manifest,
                self.store.working_dir / "checkpoints",
                "trainer_checkpoints",
                REGENERABLE,
            )
            self._save(manifest)
            self._record_storage(
                "train",
                tree_bytes(self.store.working_dir / "training-frames"),
                [result.ply_path] if result.ply_path else [],
            )
            self.state.complete(
                "train",
                ply=str(result.ply_path),
                evaluation_render_dir=str(result.evaluation_render_dir)
                if result.evaluation_render_dir
                else None,
                evaluation_rendered_ids=result.evaluation_rendered_ids,
            )
            emit(
                self.events,
                "train",
                "completed",
                f"trained scene in {result.duration_seconds:.0f}s",
            )
        except (AmberError, SubprocessFailure) as exc:
            self._fail("train", exc)
            raise
        return manifest

    # -- quality ----------------------------------------------------------

    def stage_quality(self, manifest: Manifest) -> Manifest:
        if self.state.is_complete("quality"):
            return manifest

        self.state.begin("quality")
        emit(self.events, "quality", "started", "Reviewing quality")
        try:
            split = manifest.frame_config.as_split()
            render_dir = self.store.qa_dir / "evaluation-renders"
            render_dir.mkdir(parents=True, exist_ok=True)
            self._import_trainer_renders(render_dir)

            metrics = evaluate_holdout(
                render_dir,
                self.store.working_dir / "evaluation-frames",
                split.evaluation_frame_ids,
            )
            document: dict[str, Any] = {
                "split_policy": split.policy,
                "evaluation_frame_ids": list(split.evaluation_frame_ids),
                "metrics": metrics.to_dict(),
                "pipeline_version": _amber_version(),
            }

            review = _load_or_init_motion_review(
                self.store, self.options.capture_class
            )
            document["motion_artifact_review"] = review.to_dict()
            self.store.write_json(EVALUATION_METRICS, document)
            self.store.write_json(MOTION_REVIEW, review.to_dict())

            for relpath, role in (
                (EVALUATION_METRICS, "evaluation_metrics"),
                (MOTION_REVIEW, "motion_artifact_review"),
            ):
                self.store.register_artifact(
                    manifest, self.store.abs(relpath), role, ARCHIVAL_CORE
                )
            manifest.quality["evaluation"] = metrics.aggregate()
            manifest.quality["motion_artifact_review"] = review.to_dict()
            self._save(manifest)

            if not metrics.views:
                raise AmberError(
                    "no held-out renders were available, so the scene has not "
                    "been evaluated. Amber will not report a quality result it "
                    f"did not measure. Render the {len(split.evaluation_frame_ids)} "
                    f"evaluation cameras into {render_dir} and retry this stage."
                )
            if review.blocks_success:
                raise AmberError(
                    "the motion-artifact review has not passed. A capture with "
                    "possible moving subjects is not presented as a successful "
                    "preservation until a human has reviewed it."
                )

            self.state.complete("quality", evaluated_views=len(metrics.views))
            emit(
                self.events,
                "quality",
                "completed",
                f"evaluated {len(metrics.views)} held-out views",
            )
        except (AmberError, SubprocessFailure) as exc:
            self._fail("quality", exc)
            raise
        return manifest

    # -- package ----------------------------------------------------------

    def stage_package(self, manifest: Manifest) -> Manifest:
        if self.state.is_complete("package"):
            return manifest

        self.state.begin("package")
        emit(self.events, "package", "started", "Cleaning and packaging")
        try:
            trained = Path(self.state.record("train").outputs["ply"])
            master = package_mod.write_master(trained, self.store.master_dir)
            master_hash = sha256_file(master)
            self.store.register_artifact(
                manifest, master, "master_ply", ARCHIVAL_CORE
            )

            text_model = Path(self.state.record("poses").outputs["text_model_dir"])
            sparse = package_mod.copy_sparse_model(text_model, self.store.master_dir)
            self.store.register_artifact(
                manifest, sparse, "sparse_camera_model", ARCHIVAL_CORE
            )

            derivatives = package_mod.build_delivery(
                master,
                master_hash,
                self.store.delivery_dir,
                self.options.profile.delivery_profiles,
                package_mod.SplatTransform(runner=self.runner),
                self.events,
            )
            for artifact in derivatives:
                self.store.register_artifact(
                    manifest,
                    Path(artifact.path),
                    f"delivery_{artifact.profile}",
                    ARCHIVAL_CORE,
                    source_sha256=master_hash,
                )
            manifest.pipeline["delivery_profiles"] = [
                a.to_dict() for a in derivatives
            ]

            measure_scene(self.store, manifest)
            self._save(manifest)
            self.store.write_checksums(manifest)
            self._record_storage("package", tree_bytes(trained), [master])
            self.state.complete("package", master=str(master))
            emit(
                self.events,
                "package",
                "completed",
                f"packaged master and {len(derivatives)} delivery derivative(s)",
            )
        except (AmberError, SubprocessFailure) as exc:
            self._fail("package", exc)
            raise
        return manifest

    # -- shared -----------------------------------------------------------

    def _import_trainer_renders(self, destination: Path) -> int:
        """Copy the trainer's held-out renders into the scene's QA evidence.

        The trainer writes them under its own working directory, which is
        regenerable and prunable. QA evidence is archival, so the renders are
        copied rather than referenced in place.
        """
        source = self.state.record("train").outputs.get("evaluation_render_dir")
        if not source:
            return 0
        source_dir = Path(source)
        if not source_dir.is_dir():
            return 0
        copied = 0
        for render in sorted(source_dir.iterdir()):
            if render.is_file():
                shutil.copy2(render, destination / f"{render.stem}.png")
                copied += 1
        return copied

    def _fail(self, stage: str, exc: Exception) -> None:
        diagnostic = getattr(exc, "diagnostic", None)
        if self.state.record(stage).status != "failed":
            self.state.fail(stage, str(exc), diagnostic=diagnostic)
        emit(self.events, stage, "failed", str(exc), diagnostic=diagnostic)

    def _write_storage_report(self, manifest: Manifest) -> None:
        self.storage.retained_bytes = manifest.retained_bytes()
        self.storage.prunable_bytes = manifest.prunable_bytes()
        try:
            self.store.write_json(STORAGE_REPORT, self.storage.to_dict())
        except OSError:  # pragma: no cover - reporting must never mask a failure
            pass


# --------------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------------


def _amber_version() -> str:
    from .. import __version__

    return __version__


def _load_frame_records(path: Path) -> list[FrameRecord]:
    import json

    with Path(path).open(encoding="utf-8") as fh:
        data = json.load(fh)
    return [FrameRecord.from_dict(f) for f in data.get("frames", [])]


def _load_or_init_motion_review(
    store: SceneStore, capture_class: str
) -> MotionArtifactReview:
    import json

    path = store.abs(MOTION_REVIEW)
    if path.is_file():
        with path.open(encoding="utf-8") as fh:
            data = json.load(fh)
        data.pop("blocks_success", None)
        return MotionArtifactReview(**data)
    # Whether review is *required* is a property of the capture, not of the
    # result. Outdoor and people-bearing captures always need a human look.
    return MotionArtifactReview(required=capture_class != "object")


def create_and_run(
    video: Path,
    options: RunOptions,
    library_root: Path | None = None,
    events: EventSink | None = None,
) -> tuple[SceneStore, Manifest]:
    store = SceneStore.create(
        library_root or default_library_root(),
        options.title or Path(video).stem,
    )
    pipeline = Pipeline(store, options, events=events)
    manifest = pipeline.run(video)
    return store, manifest
