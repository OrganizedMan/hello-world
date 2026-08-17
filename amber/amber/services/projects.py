"""Scene archive on disk: layout, atomic manifest writes, and checksums.

The archive is the product. It must remain readable and verifiable without
Amber installed, so everything here is plain files (ADR 0003).
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable

from ..models import (
    ARCHIVAL_CORE,
    Artifact,
    Manifest,
    PRESENT,
    RetentionError,
)

CHUNK = 1024 * 1024

SCENE_DIRS = (
    "source",
    "working/candidate-frames",
    "working/pose-frames",
    "working/training-frames",
    "working/evaluation-frames",
    "working/pose-masks",
    "working/training-masks",
    "working/colmap",
    "working/checkpoints",
    "master/cameras/colmap-sparse",
    "delivery",
    "viewer/assets",
    "qa/evaluation-renders",
    "qa/delivery-profiles",
)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as fh:
        for chunk in iter(lambda: fh.read(CHUNK), b""):
            digest.update(chunk)
    return digest.hexdigest()


def sha256_of_strings(items: Iterable[str]) -> str:
    """Stable hash of an ordered sequence of identifiers.

    Used for the candidate-pool hash that pins a comparison group.
    """
    digest = hashlib.sha256()
    for item in items:
        digest.update(item.encode("utf-8"))
        digest.update(b"\0")
    return digest.hexdigest()


def tree_bytes(path: Path) -> int:
    path = Path(path)
    if path.is_file():
        return path.stat().st_size
    if not path.exists():
        return 0
    total = 0
    for root, _dirs, files in os.walk(path):
        for name in files:
            fp = Path(root) / name
            try:
                total += fp.stat().st_size
            except OSError:
                continue
    return total


def atomic_write_text(path: Path, text: str) -> None:
    """Write via a temporary file in the same directory, then replace.

    An interrupted write therefore leaves the previous complete file, never a
    half-written one. This is what makes an interrupted prune recoverable.
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(dir=str(path.parent), prefix=f".{path.name}.")
    tmp = Path(tmp_name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(text)
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp, path)
    except BaseException:
        tmp.unlink(missing_ok=True)
        raise


def slugify(title: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", (title or "").lower()).strip("-")
    return slug or "memory"


class SceneStore:
    """Reads and writes one scene directory."""

    def __init__(self, root: Path) -> None:
        self.root = Path(root)

    # -- layout -----------------------------------------------------------

    @property
    def manifest_path(self) -> Path:
        return self.root / "manifest.json"

    @property
    def checksums_path(self) -> Path:
        return self.root / "checksums.sha256"

    @property
    def source_dir(self) -> Path:
        return self.root / "source"

    @property
    def working_dir(self) -> Path:
        return self.root / "working"

    @property
    def master_dir(self) -> Path:
        return self.root / "master"

    @property
    def delivery_dir(self) -> Path:
        return self.root / "delivery"

    @property
    def qa_dir(self) -> Path:
        return self.root / "qa"

    @property
    def log_path(self) -> Path:
        return self.root / "qa" / "events.jsonl"

    def rel(self, path: Path) -> str:
        return str(Path(path).resolve().relative_to(self.root.resolve()))

    def abs(self, relpath: str) -> Path:
        return self.root / relpath

    # -- creation ---------------------------------------------------------

    @classmethod
    def create(
        cls,
        library_root: Path,
        title: str,
        captured_at: str | None = None,
    ) -> "SceneStore":
        date = (captured_at or datetime.now().isoformat())[:10]
        scene_id_short = os.urandom(4).hex()
        name = f"{date}-{slugify(title)}-{scene_id_short}"
        root = Path(library_root) / name
        if root.exists():
            raise RetentionError(f"scene directory already exists: {root}")
        for sub in SCENE_DIRS:
            (root / sub).mkdir(parents=True, exist_ok=True)
        store = cls(root)
        manifest = Manifest(title=title, captured_at=captured_at)
        store.write_manifest(manifest)
        return store

    @classmethod
    def open(cls, root: Path) -> "SceneStore":
        store = cls(Path(root))
        if not store.manifest_path.is_file():
            raise RetentionError(f"no manifest.json under {root}; not a scene")
        return store

    # -- manifest ---------------------------------------------------------

    def read_manifest(self) -> Manifest:
        with self.manifest_path.open(encoding="utf-8") as fh:
            return Manifest.from_dict(json.load(fh))

    def write_manifest(self, manifest: Manifest) -> None:
        atomic_write_text(
            self.manifest_path,
            json.dumps(manifest.to_dict(), indent=2, sort_keys=False) + "\n",
        )

    # -- artifacts --------------------------------------------------------

    def register_artifact(
        self,
        manifest: Manifest,
        path: Path,
        role: str,
        retention_class: str,
        source_sha256: str | None = None,
        regeneration_cost_seconds: float | None = None,
        hash_contents: bool = True,
    ) -> Artifact:
        """Record a produced file or directory in the manifest.

        Refuses an unclassified artifact: retention class is decided at
        creation, never inferred later (ADR 0003).
        """
        path = Path(path)
        relpath = self.rel(path)
        is_file = path.is_file()
        artifact = Artifact(
            path=relpath,
            role=role,
            retention_class=retention_class,
            bytes=tree_bytes(path),
            sha256=sha256_file(path) if (is_file and hash_contents) else None,
            status=PRESENT,
            source_sha256=source_sha256,
            regeneration_cost_seconds=regeneration_cost_seconds,
        )
        return manifest.add_artifact(artifact)

    # -- checksums --------------------------------------------------------

    def write_checksums(self, manifest: Manifest) -> Path:
        """Write checksums for every present archival-core file artifact."""
        lines: list[str] = []
        for art in sorted(manifest.artifacts, key=lambda a: a.path):
            if art.status != PRESENT or art.retention_class != ARCHIVAL_CORE:
                continue
            target = self.abs(art.path)
            if not target.is_file():
                continue
            digest = art.sha256 or sha256_file(target)
            lines.append(f"{digest}  {art.path}")
        atomic_write_text(self.checksums_path, "\n".join(lines) + "\n")
        return self.checksums_path

    def verify_checksums(self) -> list[tuple[str, str]]:
        """Return (path, problem) for every mismatch or missing file."""
        problems: list[tuple[str, str]] = []
        if not self.checksums_path.is_file():
            return [("checksums.sha256", "missing")]
        for line in self.checksums_path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            digest, _, relpath = line.partition("  ")
            target = self.abs(relpath)
            if not target.is_file():
                problems.append((relpath, "missing"))
            elif sha256_file(target) != digest:
                problems.append((relpath, "checksum mismatch"))
        return problems

    # -- source -----------------------------------------------------------

    def ingest_source(self, video: Path) -> tuple[Path, str]:
        """Copy the original video into the archive without rewriting it.

        The source is copied, never moved or transcoded, so the user's original
        file is left exactly as it was (AGENTS.md rule 1).
        """
        video = Path(video)
        dest = self.source_dir / video.name
        self.source_dir.mkdir(parents=True, exist_ok=True)
        if not dest.exists():
            shutil.copy2(video, dest)
        return dest, sha256_file(dest)

    # -- reporting --------------------------------------------------------

    def write_json(self, relpath: str, data: Any) -> Path:
        path = self.abs(relpath)
        atomic_write_text(path, json.dumps(data, indent=2, sort_keys=False) + "\n")
        return path


def find_scenes(library_root: Path) -> list[Path]:
    root = Path(library_root)
    if not root.is_dir():
        return []
    return sorted(p for p in root.iterdir() if (p / "manifest.json").is_file())
