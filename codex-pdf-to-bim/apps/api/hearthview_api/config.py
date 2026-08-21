"""Runtime configuration for the local HearthView service."""

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class AppConfig:
    data_root: Path
    max_upload_bytes: int = 50 * 1024 * 1024
    supported_source_sha256: str = "3191113683d3b79d7a2b7cf59d2bf879e7a7d4a695ce215b7de97e8a2cbf133d"

    @classmethod
    def from_environment(cls) -> "AppConfig":
        configured = os.environ.get("HEARTHVIEW_DATA_DIR")
        data_root = Path(configured) if configured else Path.cwd() / "work" / "hearthview-data"
        return cls(data_root=data_root)
