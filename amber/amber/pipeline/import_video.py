"""Import: probe the video, record provenance, and summarise footage health.

The original is copied and hashed, never rewritten. Everything learned here is
recorded so a later run can be explained without re-reading the video.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field, asdict
from fractions import Fraction
from pathlib import Path
from typing import Any

from ..events import EventSink, emit
from ..models import AmberError
from ..tools import ProcessRunner

SUPPORTED_CONTAINERS = {".mov", ".mp4", ".m4v"}
SUPPORTED_VIDEO_CODECS = {"hevc", "h264"}

# color_transfer values that indicate HDR
HLG_TRANSFER = "arib-std-b67"
PQ_TRANSFER = "smpte2084"


@dataclass
class VideoMetadata:
    filename: str
    duration_seconds: float | None = None
    width: int | None = None
    height: int | None = None
    codec: str | None = None
    nominal_frame_rate: float | None = None
    average_frame_rate: float | None = None
    variable_frame_rate: bool = False
    rotation: int = 0
    color_primaries: str | None = None
    color_transfer: str | None = None
    color_space: str | None = None
    is_hdr: bool = False
    hdr_kind: str | None = None
    device: str | None = None
    creation_time: str | None = None
    gps: str | None = None
    bit_rate: int | None = None
    raw: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @property
    def long_edge(self) -> int | None:
        if self.width and self.height:
            return max(self.width, self.height)
        return None


def _to_float_rate(value: str | None) -> float | None:
    if not value or value in ("0/0", "N/A"):
        return None
    try:
        return float(Fraction(value))
    except (ValueError, ZeroDivisionError):
        return None


def probe(video: Path, runner: ProcessRunner, ffprobe: str = "ffprobe") -> VideoMetadata:
    """Read streams and container metadata with ffprobe."""
    video = Path(video)
    if not video.is_file():
        raise AmberError(f"video not found: {video}")
    if video.suffix.lower() not in SUPPORTED_CONTAINERS:
        raise AmberError(
            f"unsupported container {video.suffix!r}; Amber accepts "
            f"{sorted(SUPPORTED_CONTAINERS)}"
        )

    result = runner.run(
        [
            ffprobe,
            "-hide_banner",
            "-loglevel",
            "error",
            "-print_format",
            "json",
            "-show_format",
            "-show_streams",
            str(video),
        ]
    )
    return parse_probe(json.loads(result.stdout), video.name)


def parse_probe(data: dict[str, Any], filename: str) -> VideoMetadata:
    """Turn ffprobe JSON into recorded metadata. Pure, so it is unit-testable."""
    streams = data.get("streams", [])
    fmt = data.get("format", {})
    video_streams = [s for s in streams if s.get("codec_type") == "video"]
    if not video_streams:
        raise AmberError("the file contains no video stream")
    stream = video_streams[0]

    tags = {**fmt.get("tags", {}), **stream.get("tags", {})}
    rotation = 0
    for side in stream.get("side_data_list", []) or []:
        if "rotation" in side:
            try:
                rotation = int(side["rotation"]) % 360
            except (TypeError, ValueError):
                rotation = 0

    nominal = _to_float_rate(stream.get("r_frame_rate"))
    average = _to_float_rate(stream.get("avg_frame_rate"))
    vfr = bool(
        nominal and average and abs(nominal - average) / max(nominal, 1e-9) > 0.02
    )

    transfer = stream.get("color_transfer")
    hdr_kind = None
    if transfer == HLG_TRANSFER:
        hdr_kind = "hlg"
    elif transfer == PQ_TRANSFER:
        hdr_kind = "pq"

    duration = fmt.get("duration") or stream.get("duration")

    return VideoMetadata(
        filename=filename,
        duration_seconds=float(duration) if duration else None,
        width=stream.get("width"),
        height=stream.get("height"),
        codec=stream.get("codec_name"),
        nominal_frame_rate=nominal,
        average_frame_rate=average,
        variable_frame_rate=vfr,
        rotation=rotation,
        color_primaries=stream.get("color_primaries"),
        color_transfer=transfer,
        color_space=stream.get("color_space"),
        is_hdr=hdr_kind is not None,
        hdr_kind=hdr_kind,
        device=tags.get("com.apple.quicktime.model") or tags.get("model"),
        creation_time=tags.get("creation_time"),
        gps=tags.get("com.apple.quicktime.location.ISO6709") or tags.get("location"),
        bit_rate=int(fmt["bit_rate"]) if fmt.get("bit_rate") else None,
        raw={"format": fmt, "video_stream": stream},
    )


@dataclass
class FootageHealth:
    """A plain-language summary shown before processing starts."""

    warnings: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def assess_footage(meta: VideoMetadata) -> FootageHealth:
    """Warn, never scold (plan §7). Nothing here blocks processing."""
    health = FootageHealth()

    if meta.codec and meta.codec not in SUPPORTED_VIDEO_CODECS:
        health.warnings.append(
            f"Video codec is {meta.codec}; Amber is tested with HEVC and H.264."
        )
    if meta.duration_seconds is not None:
        if meta.duration_seconds < 20:
            health.warnings.append(
                f"The clip is {meta.duration_seconds:.0f}s. Captures under about "
                "30s rarely cover a scene from enough angles."
            )
        elif meta.duration_seconds > 180:
            health.notes.append(
                f"The clip is {meta.duration_seconds / 60:.1f} minutes; expect a "
                "long processing run."
            )
    if meta.variable_frame_rate:
        health.notes.append(
            "Variable frame rate detected. Frame timestamps are taken from the "
            "decoded sequence rather than assumed."
        )
    if meta.is_hdr:
        health.notes.append(
            f"HDR ({meta.hdr_kind.upper()}) footage. The original is preserved "
            "untouched; working frames are converted to SDR Rec.709 and the "
            "transform is recorded."
        )
    if meta.long_edge and meta.long_edge < 1920:
        health.warnings.append(
            f"Long edge is {meta.long_edge}px. 1080p or 4K is recommended."
        )
    if meta.gps:
        health.notes.append(
            "The video carries GPS metadata. It stays local and is omitted from "
            "any future export unless you opt in."
        )
    if meta.rotation:
        health.notes.append(f"Orientation metadata: {meta.rotation}°, normalized.")
    return health


def import_source(
    video: Path,
    store: Any,
    runner: ProcessRunner,
    events: EventSink,
) -> tuple[VideoMetadata, FootageHealth, str]:
    """Copy the original into the archive and probe it."""
    emit(events, "import", "started", "Preparing the video")
    metadata = probe(video, runner)
    health = assess_footage(metadata)
    dest, digest = store.ingest_source(video)
    for warning in health.warnings:
        emit(events, "import", "warning", warning)
    emit(
        events,
        "import",
        "completed",
        f"imported {dest.name} ({metadata.width}x{metadata.height}, "
        f"{metadata.duration_seconds:.0f}s)"
        if metadata.duration_seconds
        else f"imported {dest.name}",
        sha256=digest,
    )
    return metadata, health, digest
