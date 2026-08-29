"""OpenSplat trainer backend — registered but deliberately not implemented.

The plan compares OpenSplat only to answer a concrete question about Brush's
quality, reliability, or output compatibility, and only after the same healthy
COLMAP dataset has trained successfully in Brush. Implementing it speculatively
would invite an unjustified backend switch and a comparison nobody planned.

Selecting this backend therefore fails with instructions, and enabling it
requires a trainer ADR recording the concrete question it answers.
"""

from __future__ import annotations

from pathlib import Path

from ...config import TrainConfig
from ...events import EventSink
from ...models import AmberError
from ...tools import discover_tool
from .base import BackendHealth, ColmapDataset, TrainResult

ENABLE_MESSAGE = (
    "The OpenSplat backend is not implemented. The plan calls for it only to "
    "answer a specific backend question after Brush has trained a healthy "
    "COLMAP dataset. To enable it: record a trainer ADR in docs/decisions/ "
    "stating the question, then implement this backend against the installed "
    "OpenSplat build's discovered flags."
)


class OpenSplatBackend:
    name = "opensplat"

    def __init__(self, workspace: Path, executable: str = "opensplat") -> None:
        self.workspace = Path(workspace)
        self.executable = executable

    def doctor(self) -> BackendHealth:
        info = discover_tool(
            "opensplat", version_args=("--help",), executable=self.executable
        )
        return BackendHealth(
            name=self.name,
            available=False,
            version=info.version,
            executable=info.executable,
            capabilities={"binary_present": info.available},
            error=ENABLE_MESSAGE,
        )

    def train(
        self, dataset: ColmapDataset, config: TrainConfig, events: EventSink
    ) -> TrainResult:
        raise AmberError(ENABLE_MESSAGE)

    def cancel(self) -> None:
        return None
