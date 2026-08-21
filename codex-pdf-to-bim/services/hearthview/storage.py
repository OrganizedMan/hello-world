from __future__ import annotations

import hashlib
import os
import re
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import BinaryIO, Callable


_SHA256 = re.compile(r"[0-9a-f]{64}")


class ArtifactPathError(ValueError):
    """Raised when an artifact identity is not a safe SHA-256."""


class ArtifactTooLarge(ValueError):
    """Raised before an oversized stream can enter the artifact store."""


@dataclass(frozen=True)
class ArtifactRef:
    sha256: str
    path: Path
    byte_count: int


class ArtifactStore:
    def __init__(self, root: Path) -> None:
        self.root = root.resolve()
        self.root.mkdir(parents=True, exist_ok=True)

    def install(
        self,
        stream: BinaryIO,
        *,
        max_bytes: int | None = None,
        validator: Callable[[Path], object] | None = None,
    ) -> ArtifactRef:
        digest = hashlib.sha256()
        byte_count = 0
        temporary_path: Path | None = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="wb",
                dir=self.root,
                prefix=".install-",
                suffix=".partial",
                delete=False,
            ) as temporary:
                temporary_path = Path(temporary.name)
                while chunk := stream.read(1024 * 1024):
                    digest.update(chunk)
                    byte_count += len(chunk)
                    if max_bytes is not None and byte_count > max_bytes:
                        raise ArtifactTooLarge(
                            f"Artifact exceeds the {max_bytes}-byte limit."
                        )
                    temporary.write(chunk)
                temporary.flush()
                os.fsync(temporary.fileno())
            if validator is not None:
                validator(temporary_path)
            sha256 = digest.hexdigest()
            final_path = self.root / sha256[:2] / sha256
            final_path.parent.mkdir(parents=True, exist_ok=True)
            if final_path.exists():
                temporary_path.unlink()
            else:
                os.replace(temporary_path, final_path)
            return ArtifactRef(sha256=sha256, path=final_path, byte_count=byte_count)
        except BaseException:
            if temporary_path is not None:
                temporary_path.unlink(missing_ok=True)
            raise

    def resolve(self, sha256: str) -> Path:
        if not _SHA256.fullmatch(sha256):
            raise ArtifactPathError("Artifact IDs must be 64 lowercase hexadecimal characters.")
        return self.root / sha256[:2] / sha256
