"""Amber command-line interface.

    amber doctor
    amber process VIDEO --profile beautiful --title "Living room"
    amber inspect SCENE
    amber retry SCENE --from poses
    amber prune --dry-run SCENE
    amber prune --working SCENE
"""

from __future__ import annotations

import argparse
import json
import platform
import shutil
import sys
from pathlib import Path
from typing import Any

from . import __version__
from .config import default_library_root, get_profile, load_thresholds
from .events import CompositeEventSink, ConsoleEventSink, JsonlEventSink, STAGES
from .models import AmberError, PRUNABLE_CLASSES
from .pipeline.run import Pipeline, RunOptions
from .services.jobs import StageState
from .services.projects import SceneStore, find_scenes
from .services.storage import (
    apply_prune,
    free_bytes,
    measure_scene,
    plan_prune,
    repair_interrupted_prune,
)
from .tools import ProcessRunner, discover_tool


def _human(num_bytes: float) -> str:
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if abs(num_bytes) < 1024 or unit == "TB":
            return f"{num_bytes:.1f} {unit}" if unit != "B" else f"{int(num_bytes)} B"
        num_bytes /= 1024
    return f"{num_bytes:.1f} TB"


# --------------------------------------------------------------------------
# doctor
# --------------------------------------------------------------------------


def collect_doctor_report() -> dict[str, Any]:
    """Report what is actually installed. Nothing here is assumed."""
    from .backends.poses.colmap import ColmapPoseBackend
    from .backends.trainers.brush import BrushBackend
    from .backends.trainers.opensplat import OpenSplatBackend
    from .pipeline.package import SplatTransform

    runner = ProcessRunner()
    workspace = Path(".amber-doctor")

    tools = {
        "ffmpeg": discover_tool("ffmpeg", ("-version",)).to_dict(),
        "ffprobe": discover_tool("ffprobe", ("-version",)).to_dict(),
    }
    backends = {
        "colmap": ColmapPoseBackend(workspace, runner=runner).doctor().to_dict(),
        "brush": BrushBackend(workspace, runner=runner).doctor().to_dict(),
        "opensplat": OpenSplatBackend(workspace).doctor().to_dict(),
        "splat_transform": SplatTransform(runner=runner).doctor(),
    }

    try:
        thresholds: Any = load_thresholds()
        thresholds_error = None
    except AmberError as exc:
        thresholds, thresholds_error = None, str(exc)

    library = default_library_root()
    report = {
        "amber_version": __version__,
        "platform": {
            "system": platform.system(),
            "release": platform.release(),
            "machine": platform.machine(),
            "python": platform.python_version(),
        },
        "tools": tools,
        "backends": backends,
        "library_root": str(library),
        "free_bytes": free_bytes(library.parent if not library.exists() else library),
        "predeclared_thresholds": thresholds,
        "predeclared_thresholds_error": thresholds_error,
    }

    missing = [name for name, info in tools.items() if not info["available"]]
    missing += [
        name
        for name, info in backends.items()
        if name != "opensplat" and not info.get("available")
    ]
    report["missing"] = missing
    report["ready"] = not missing and thresholds_error is None
    return report


def cmd_doctor(args: argparse.Namespace) -> int:
    report = collect_doctor_report()
    if args.json:
        print(json.dumps(report, indent=2))
        return 0 if report["ready"] else 1

    print(f"Amber {report['amber_version']}")
    plat = report["platform"]
    print(f"  platform      {plat['system']} {plat['release']} ({plat['machine']})")
    print(f"  python        {plat['python']}")
    print(f"  library       {report['library_root']}")
    print(f"  free space    {_human(report['free_bytes'])}")
    print()
    print("External tools")
    for name, info in report["tools"].items():
        status = info["version"] if info["available"] else "NOT FOUND"
        print(f"  {name:<16} {status}")
    print()
    print("Backends")
    for name, info in report["backends"].items():
        if name == "opensplat":
            print(f"  {name:<16} not implemented (by design; see ADR 0002)")
            continue
        if info.get("available"):
            caps = info.get("capabilities", {})
            extra = ""
            if name == "colmap":
                extra = (
                    f"  [global_mapper={caps.get('has_global_mapper')}, "
                    f"max_image_size option={caps.get('max_image_size_option')}, "
                    f"cli default={caps.get('max_image_size_cli_default')}]"
                )
            print(f"  {name:<16} {info.get('version') or 'installed'}{extra}")
        else:
            print(f"  {name:<16} NOT FOUND")
    if report["predeclared_thresholds_error"]:
        print()
        print(f"  ! {report['predeclared_thresholds_error']}")

    print()
    if report["ready"]:
        print("Ready to process.")
    else:
        print(f"Not ready. Missing: {', '.join(report['missing']) or 'thresholds'}")
        print("Install the missing tools, then run `amber doctor` again.")
    return 0 if report["ready"] else 1


# --------------------------------------------------------------------------
# process / retry
# --------------------------------------------------------------------------


def _events(store: SceneStore, quiet: bool):
    sinks = [JsonlEventSink(store.log_path)]
    if not quiet:
        sinks.insert(0, ConsoleEventSink())
    return CompositeEventSink(*sinks)


def cmd_process(args: argparse.Namespace) -> int:
    video = Path(args.video).expanduser()
    if not video.is_file():
        print(f"error: no such video: {video}", file=sys.stderr)
        return 2

    library = Path(args.library).expanduser() if args.library else default_library_root()
    library.mkdir(parents=True, exist_ok=True)
    options = RunOptions(
        profile=get_profile(args.profile),
        title=args.title or video.stem,
        capture_class=args.capture_class,
        comparison_group_id=args.comparison_group,
        notes=args.notes or "",
        skip_space_check=args.skip_space_check,
    )
    store = SceneStore.create(library, options.title)
    pipeline = Pipeline(store, options, events=_events(store, args.quiet))
    try:
        pipeline.run(video)
    except AmberError as exc:
        print(f"\nProcessing stopped: {exc}", file=sys.stderr)
        print(f"Scene kept for inspection: {store.root}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        pipeline.cancel()
        print("\nCancelled. The scene archive is intact.", file=sys.stderr)
        return 130
    print(f"\nScene: {store.root}")
    return 0


def cmd_retry(args: argparse.Namespace) -> int:
    store = SceneStore.open(Path(args.scene).expanduser())
    manifest = store.read_manifest()
    state = StageState.load(store.working_dir / "state.json")
    invalidated = state.invalidate_from(args.from_stage)
    print(f"Invalidated stages: {', '.join(invalidated) or 'none'}")

    options = RunOptions(
        profile=get_profile(args.profile),
        title=manifest.title,
        capture_class=manifest.pipeline.get("capture_class", "room"),
        skip_space_check=args.skip_space_check,
    )
    pipeline = Pipeline(store, options, events=_events(store, args.quiet))
    source = manifest.source.get("filename")
    video = store.source_dir / source if source else None
    try:
        pipeline.run(video)
    except AmberError as exc:
        print(f"\nProcessing stopped: {exc}", file=sys.stderr)
        return 1
    print(f"\nScene: {store.root}")
    return 0


# --------------------------------------------------------------------------
# inspect
# --------------------------------------------------------------------------


def cmd_inspect(args: argparse.Namespace) -> int:
    store = SceneStore.open(Path(args.scene).expanduser())
    manifest = store.read_manifest()
    state = StageState.load(store.working_dir / "state.json")
    measure_scene(store, manifest)
    plan = plan_prune(manifest)
    problems = store.verify_checksums() if args.verify else []

    if args.json:
        print(
            json.dumps(
                {
                    "scene_id": manifest.scene_id,
                    "title": manifest.title,
                    "stages": state.to_dict(),
                    "retained_bytes": manifest.retained_bytes(),
                    "prunable_bytes": plan.total_bytes,
                    "prune_plan": plan.to_dict(),
                    "quality": manifest.quality,
                    "split": manifest.frame_config.to_dict(),
                    "checksum_problems": problems,
                },
                indent=2,
            )
        )
        return 0

    print(f"{manifest.title or '(untitled)'}  [{manifest.scene_id}]")
    print(f"  captured      {manifest.captured_at or 'unknown'}")
    print(f"  source        {manifest.source.get('filename', '-')}")
    print()
    print("Stages")
    for name in STAGES:
        record = state.stages[name]
        detail = f"  {record.error}" if record.error else ""
        print(f"  {name:<10} {record.status}{detail}")
    print()
    cfg = manifest.frame_config
    print("Split")
    print(f"  policy        {cfg.split_policy} (locked={cfg.split_locked})")
    print(f"  training      {len(cfg.training_frame_ids)} frames")
    print(f"  evaluation    {len(cfg.evaluation_frame_ids)} frames (never trained on)")
    if cfg.comparison_group_id:
        print(f"  comparison    {cfg.comparison_group_id}")
    print()
    print("Storage")
    print(f"  retained      {_human(manifest.retained_bytes())}")
    print(f"  prunable      {_human(plan.total_bytes)} in {len(plan.targets)} artifacts")
    cost = sum(t.regeneration_cost_seconds or 0 for t in plan.targets)
    print(
        f"  regeneration  {cost / 60:.1f} min (measured)"
        if cost
        else "  regeneration  not yet measured"
    )
    pruned = [a for a in manifest.artifacts if a.status == "pruned"]
    if pruned:
        print(f"  pruned        {len(pruned)} artifacts, recipes retained")
    if args.verify:
        print()
        if problems:
            print(f"Checksum problems ({len(problems)}):")
            for path, problem in problems:
                print(f"  {path}: {problem}")
        else:
            print("Checksums verified.")
    return 0


def cmd_list(args: argparse.Namespace) -> int:
    library = Path(args.library).expanduser() if args.library else default_library_root()
    scenes = find_scenes(library)
    if not scenes:
        print(f"No scenes under {library}")
        return 0
    for scene in scenes:
        manifest = SceneStore(scene).read_manifest()
        print(f"{manifest.captured_at or '-':<26} {manifest.title or scene.name}")
        print(f"  {scene}")
    return 0


# --------------------------------------------------------------------------
# prune
# --------------------------------------------------------------------------


def cmd_prune(args: argparse.Namespace) -> int:
    store = SceneStore.open(Path(args.scene).expanduser())
    manifest = store.read_manifest()
    measure_scene(store, manifest)

    if args.repair:
        freed = repair_interrupted_prune(store, manifest)
        print(f"Completed an interrupted prune, freeing {_human(freed)}.")
        return 0

    plan = plan_prune(manifest, PRUNABLE_CLASSES)
    if not plan.targets:
        print("Nothing to prune. All remaining artifacts are archival core.")
        return 0

    print(f"Would remove {len(plan.targets)} artifacts, {_human(plan.total_bytes)}:")
    for target in plan.targets:
        cost = (
            f"  (regenerate: {target.regeneration_cost_seconds / 60:.1f} min)"
            if target.regeneration_cost_seconds
            else ""
        )
        print(f"  {target.path:<40} {_human(target.bytes):>10}{cost}")
    print()
    print(f"Protected (never pruned): {len(plan.protected)} archival-core artifacts")

    if args.dry_run:
        print("\nDry run. Nothing was removed.")
        return 0
    if not args.working:
        print(
            "\nRefusing to prune without --working. Use --dry-run to preview, "
            "then --working to confirm.",
            file=sys.stderr,
        )
        return 2

    freed = apply_prune(store, manifest, plan)
    store.write_checksums(manifest)
    print(f"\nFreed {_human(freed)}. Every artifact's recipe and hash was kept.")
    return 0


# --------------------------------------------------------------------------
# parser
# --------------------------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="amber", description=__doc__)
    parser.add_argument("--version", action="version", version=f"amber {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)

    doctor = sub.add_parser("doctor", help="report installed tools and capabilities")
    doctor.add_argument("--json", action="store_true")
    doctor.set_defaults(func=cmd_doctor)

    process = sub.add_parser("process", help="turn a video into a scene archive")
    process.add_argument("video")
    process.add_argument("--profile", default="beautiful")
    process.add_argument("--title", default=None)
    process.add_argument(
        "--capture-class",
        default="room",
        help="capture class for the predeclared registration floor",
    )
    process.add_argument(
        "--comparison-group",
        default=None,
        help="run as part of a comparison group, using the fixed stratified split",
    )
    process.add_argument("--notes", default=None)
    process.add_argument("--library", default=None)
    process.add_argument("--quiet", action="store_true")
    process.add_argument("--skip-space-check", action="store_true")
    process.set_defaults(func=cmd_process)

    retry = sub.add_parser("retry", help="re-run a scene from a given stage")
    retry.add_argument("scene")
    retry.add_argument(
        "--from", dest="from_stage", required=True, choices=list(STAGES)
    )
    retry.add_argument("--profile", default="beautiful")
    retry.add_argument("--quiet", action="store_true")
    retry.add_argument("--skip-space-check", action="store_true")
    retry.set_defaults(func=cmd_retry)

    inspect = sub.add_parser("inspect", help="show stage state, split, and storage")
    inspect.add_argument("scene")
    inspect.add_argument("--json", action="store_true")
    inspect.add_argument("--verify", action="store_true", help="verify checksums")
    inspect.set_defaults(func=cmd_inspect)

    listing = sub.add_parser("list", help="list scenes in the library")
    listing.add_argument("--library", default=None)
    listing.set_defaults(func=cmd_list)

    prune = sub.add_parser("prune", help="remove regenerable working data")
    prune.add_argument("scene")
    prune.add_argument("--dry-run", action="store_true")
    prune.add_argument("--working", action="store_true")
    prune.add_argument(
        "--repair", action="store_true", help="finish an interrupted prune"
    )
    prune.set_defaults(func=cmd_prune)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return int(args.func(args))
    except AmberError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:  # pragma: no cover
        return 130


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
