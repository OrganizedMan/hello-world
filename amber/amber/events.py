"""Structured pipeline events.

Backends and pipeline stages never print to stdout. They emit events into an
injected sink, so the CLI today and a local web UI later consume identical
data (ADR 0002, rule 3).
"""

from __future__ import annotations

import json
import sys
import time
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any, Protocol

# Canonical stage identifiers, in pipeline order.
STAGES: tuple[str, ...] = (
    "import",
    "frames",
    "poses",
    "train",
    "quality",
    "package",
)

# Plain-language names shown to a user (plan §6, step 4).
STAGE_LABELS: dict[str, str] = {
    "import": "Preparing the video",
    "frames": "Finding clear viewpoints",
    "poses": "Reconstructing the camera path",
    "train": "Building the scene",
    "quality": "Reviewing quality",
    "package": "Cleaning and packaging",
}


@dataclass(frozen=True)
class Event:
    stage: str
    kind: str  # started | progress | info | warning | failed | completed
    message: str
    data: dict[str, Any] = field(default_factory=dict)
    ts: float = field(default_factory=time.time)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class EventSink(Protocol):
    def emit(self, event: Event) -> None: ...


class NullEventSink:
    """Discards events. Used in unit tests and dry runs."""

    def emit(self, event: Event) -> None:  # noqa: D102
        return None


class MemoryEventSink:
    """Collects events for assertions and for post-run reporting."""

    def __init__(self) -> None:
        self.events: list[Event] = []

    def emit(self, event: Event) -> None:
        self.events.append(event)

    def of_kind(self, kind: str) -> list[Event]:
        return [e for e in self.events if e.kind == kind]


class JsonlEventSink:
    """Appends events to a JSONL log inside the scene.

    Opened in append mode per emit so that a crash cannot lose buffered lines.
    """

    def __init__(self, path: Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def emit(self, event: Event) -> None:
        with self.path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(event.to_dict(), sort_keys=True) + "\n")


class ConsoleEventSink:
    """Human-readable progress on stderr, using plain-language stage names."""

    def __init__(self, stream: Any = None, verbose: bool = False) -> None:
        self.stream = stream if stream is not None else sys.stderr
        self.verbose = verbose
        self._last_stage: str | None = None

    def emit(self, event: Event) -> None:
        label = STAGE_LABELS.get(event.stage, event.stage)
        if event.kind == "started":
            self._last_stage = event.stage
            print(f"→ {label}", file=self.stream, flush=True)
        elif event.kind == "completed":
            print(f"  ✓ {event.message}", file=self.stream, flush=True)
        elif event.kind == "failed":
            print(f"  ✗ {event.message}", file=self.stream, flush=True)
        elif event.kind == "warning":
            print(f"  ! {event.message}", file=self.stream, flush=True)
        elif self.verbose or event.kind == "info":
            print(f"    {event.message}", file=self.stream, flush=True)


class CompositeEventSink:
    def __init__(self, *sinks: EventSink) -> None:
        self.sinks = list(sinks)

    def emit(self, event: Event) -> None:
        for sink in self.sinks:
            sink.emit(event)


def emit(
    sink: EventSink,
    stage: str,
    kind: str,
    message: str,
    **data: Any,
) -> Event:
    """Convenience helper so call sites stay one line."""
    event = Event(stage=stage, kind=kind, message=message, data=data)
    sink.emit(event)
    return event
