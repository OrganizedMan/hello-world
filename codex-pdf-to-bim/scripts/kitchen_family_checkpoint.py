"""Kitchen/family checkpoint: Blender-authored tour GLB plus validation stills.

Runs the established spike pipeline end to end and stops there. It does not
touch the rest of the floor.

    uv run python scripts/kitchen_family_checkpoint.py \
        --assets /absolute/path/to/tour-quality-assets

Steps:
  1. build_scene.py inside Blender  -> tour GLB, manifest, poster, environment
  2. validate_artifact              -> contract and payload gates
  3. render_scene.py x4             -> PLAN, AXONOMETRIC, KITCHEN, LIVING_ROOM

Stills are written to work/checkpoint-kitchen-family/ (git-ignored) so the
browser artifact set stays exactly what Blender produced.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
PUBLIC = REPO / "apps/web/public/tour-spike"
STILLS = REPO / "work/checkpoint-kitchen-family"
CAMERAS = ("PLAN", "AXONOMETRIC", "KITCHEN", "LIVING_ROOM")
SPEC = REPO / "spikes/tour_quality/a1_kitchen_scene_spec.json"
DEFAULT_BLENDER = Path("/Applications/Blender.app/Contents/MacOS/Blender")
GLB_NAME = "hearthview-kitchen-family.glb"


def _run(label: str, command: list[str], log: Path) -> None:
    print(f"\n=== {label} ===")
    print(" ".join(command))
    log.parent.mkdir(parents=True, exist_ok=True)
    completed = subprocess.run(command, cwd=REPO, capture_output=True, text=True)
    log.write_text(
        f"$ {' '.join(command)}\n\n--- stdout ---\n{completed.stdout}\n"
        f"--- stderr ---\n{completed.stderr}\n",
        encoding="utf-8",
    )
    if completed.returncode != 0:
        tail = "\n".join((completed.stdout + completed.stderr).strip().splitlines()[-25:])
        raise SystemExit(
            f"{label} failed (exit {completed.returncode}).\nFull log: {log}\n\n{tail}"
        )
    print(f"ok -> {log}")


def _digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()[:16]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--assets", type=Path, required=True)
    parser.add_argument("--blender", type=Path, default=DEFAULT_BLENDER)
    parser.add_argument(
        "--engine",
        default="FINAL",
        choices=["DRAFT", "FINAL", "BLENDER_EEVEE_NEXT", "CYCLES"],
        help="FINAL and CYCLES render Cycles at 160 samples; DRAFT uses EEVEE.",
    )
    parser.add_argument("--width", type=int, default=1600)
    parser.add_argument("--height", type=int, default=1000)
    parser.add_argument("--skip-build", action="store_true", help="Only re-render stills.")
    parser.add_argument(
        "--spike",
        action="store_true",
        help="Build the original hand-transcribed spike instead of the A-1 traced scene.",
    )
    args = parser.parse_args()

    if not args.blender.is_file():
        raise SystemExit(f"Blender not found at {args.blender}. Pass --blender.")
    if not args.assets.is_dir():
        raise SystemExit(f"Asset directory not found: {args.assets}")
    provenance = REPO / "spikes/tour_quality/assets/provenance.json"
    expected = {
        file["path"]
        for asset in json.loads(provenance.read_text())["assets"]
        for file in asset["files"]
    }
    missing = sorted(name for name in expected if not (args.assets / name).exists())
    if missing:
        raise SystemExit(
            "The asset directory is missing files recorded in provenance.json:\n  "
            + "\n  ".join(missing[:12])
        )
    print(f"assets ok: {len(expected)} files present in {args.assets}")

    if not args.spike and not SPEC.is_file():
        raise SystemExit(f"traced scene spec is missing: {SPEC}")
    mode = "hand-built spike" if args.spike else "A-1 traced scene"
    print(f"building: {mode}")

    logs = STILLS / "logs"
    if not args.skip_build:
        PUBLIC.mkdir(parents=True, exist_ok=True)
        command = [
            str(args.blender), "--background", "--factory-startup",
            "--python", str(REPO / "spikes/tour_quality/build_scene.py"), "--",
            "--repo", str(REPO),
            "--assets", str(args.assets),
            "--output-dir", str(PUBLIC),
        ]
        if not args.spike:
            command += ["--spec", str(SPEC)]
        _run("1/3 build_scene.py", command, logs / "build_scene.log")

    glb = PUBLIC / GLB_NAME
    manifest = PUBLIC / "manifest.json"
    for required in (glb, manifest, PUBLIC / "poster.webp", PUBLIC / "environment.hdr"):
        if not required.exists():
            raise SystemExit(f"Expected artifact missing after build: {required}")

    validate = [
        sys.executable, "-m", "spikes.tour_quality.validate_artifact",
        "--glb", str(glb),
        "--manifest", str(manifest),
        "--public-dir", str(PUBLIC),
    ]
    if not args.spike:
        validate += ["--spec", str(SPEC)]
    _run("2/3 validate_artifact", validate, logs / "validate_artifact.log")

    STILLS.mkdir(parents=True, exist_ok=True)
    for index, camera in enumerate(CAMERAS, start=1):
        # render_scene.py reads this file and writes render metadata back into
        # it, so give each still its own copy rather than the tour manifest.
        job_manifest = STILLS / f"{camera.lower()}.render.json"
        shutil.copyfile(manifest, job_manifest)
        _run(
            f"3/3 render {camera} ({index}/{len(CAMERAS)})",
            [
                str(args.blender), "--background", "--factory-startup",
                "--python", str(REPO / "services/blender/render_scene.py"), "--",
                "--geometry", str(glb),
                "--output", str(STILLS / f"{camera.lower()}.png"),
                "--manifest", str(job_manifest),
                "--camera", camera,
                "--engine", args.engine,
                "--width", str(args.width),
                "--height", str(args.height),
                "--style", "WARM_BLANK_SLATE",
            ],
            logs / f"render_{camera.lower()}.log",
        )

    print("\n=== checkpoint complete ===")
    print(f"tour GLB   {glb}  {glb.stat().st_size:,} bytes  sha256:{_digest(glb)}")
    print(f"manifest   {manifest}")
    for camera in CAMERAS:
        still = STILLS / f"{camera.lower()}.png"
        if still.exists():
            print(f"still      {still}  {still.stat().st_size:,} bytes")
    print(f"logs       {logs}")
    print("\nSend back the four PNGs and the logs directory.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
