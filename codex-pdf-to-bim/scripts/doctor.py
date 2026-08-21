from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
from dataclasses import asdict
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SERVICES = ROOT / "services"
if str(SERVICES) not in sys.path:
    sys.path.insert(0, str(SERVICES))

from hearthview.rendering import detect_blender  # noqa: E402


def _node_check() -> dict[str, object]:
    executable = shutil.which("node")
    if executable is None:
        return {"required": True, "available": False, "version": None, "action": "Install Node.js 24 or newer."}
    completed = subprocess.run([executable, "--version"], capture_output=True, text=True, check=False, timeout=5)
    return {"required": True, "available": completed.returncode == 0, "version": completed.stdout.strip(), "action": None}


def _pdf_check() -> dict[str, object]:
    try:
        import pymupdf
        return {"required": True, "available": True, "version": pymupdf.VersionBind, "action": None}
    except ImportError:
        return {"required": True, "available": False, "version": None, "action": "Run uv sync to install the local PDF preview engine."}


def _storage_check(data_root: Path) -> dict[str, object]:
    try:
        data_root.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(dir=data_root, prefix=".doctor-", delete=True):
            pass
        return {"required": True, "available": True, "path": str(data_root.resolve()), "action": None}
    except OSError:
        return {"required": True, "available": False, "path": str(data_root), "action": "Choose a writable HEARTHVIEW_DATA_DIR."}


def collect_checks(data_root: Path) -> dict[str, dict[str, object]]:
    blender = asdict(detect_blender())
    blender["required"] = False
    return {
        "python": {"required": True, "available": sys.version_info >= (3, 12), "version": sys.version.split()[0], "action": None if sys.version_info >= (3, 12) else "Install Python 3.12 or newer."},
        "node": _node_check(),
        "pdf_preview": _pdf_check(),
        "local_storage": _storage_check(data_root),
        "blender": blender,
    }


def main() -> int:
    checks = collect_checks(ROOT / "work" / "hearthview-data")
    print(json.dumps(checks, indent=2))
    missing_required = [name for name, check in checks.items() if check["required"] and not check["available"]]
    if missing_required:
        print(f"HearthView needs attention: {', '.join(missing_required)}", file=sys.stderr)
        return 1
    if not checks["blender"]["available"]:
        print("Core plan review and interactive 3D are ready. Blender is optional until you create a photoreal render.")
    else:
        print("Core plan review, interactive 3D, and photoreal rendering are ready.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
