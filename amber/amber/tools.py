"""External tool discovery and subprocess execution.

Every external invocation goes through here so that the command line, the exit
status, and the timing are recorded, and so a failure becomes an actionable
diagnostic rather than an unexplained subprocess error (plan §4, item 10).
"""

from __future__ import annotations

import shutil
import subprocess
import time
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any, Sequence

from .models import AmberError

STDERR_TAIL_CHARS = 4000


@dataclass
class ToolInfo:
    name: str
    executable: str | None = None
    available: bool = False
    version: str | None = None
    raw_version_output: str | None = None
    capabilities: dict[str, Any] = field(default_factory=dict)
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class ProcessResult:
    command: list[str]
    returncode: int
    stdout: str
    stderr: str
    duration_seconds: float

    @property
    def ok(self) -> bool:
        return self.returncode == 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "command": self.command,
            "returncode": self.returncode,
            "duration_seconds": self.duration_seconds,
            "stderr_tail": self.stderr[-STDERR_TAIL_CHARS:],
        }


class ToolMissingError(AmberError):
    """A required external tool is not installed."""


class SubprocessFailure(AmberError):
    """An external tool exited non-zero, with a parsed diagnostic."""

    def __init__(self, message: str, diagnostic: str, result: ProcessResult):
        super().__init__(message)
        self.diagnostic = diagnostic
        self.result = result


# --------------------------------------------------------------------------
# Failure parsing
# --------------------------------------------------------------------------

# (diagnostic, substring to look for, user-facing advice)
_FAILURE_PATTERNS: tuple[tuple[str, str, str], ...] = (
    (
        "out_of_memory",
        "out of memory",
        "The machine ran out of memory. Lower the training resolution or the "
        "splat cap, or select fewer training frames.",
    ),
    (
        "out_of_memory",
        "std::bad_alloc",
        "The machine ran out of memory. Lower the training resolution or the "
        "splat cap, or select fewer training frames.",
    ),
    (
        "out_of_disk",
        "no space left on device",
        "The disk filled up. Free space or prune working data from an older "
        "scene, then retry from the failed stage.",
    ),
    (
        "mapper_initialization_failed",
        "no good initial image pair",
        "COLMAP could not find a reliable pair of starting views. This usually "
        "means the camera barely moved, or the scene is too blank or blurry to "
        "match. Re-record while walking around the subject.",
    ),
    (
        "no_features",
        "no features",
        "Too few image features were found. The footage may be blurry, very "
        "dark, or dominated by blank surfaces.",
    ),
    (
        "gpu_unavailable",
        "cuda",
        "A CUDA path was requested but is unavailable on this machine. Amber "
        "does not silently fall back to the CPU; choose a supported backend "
        "path instead.",
    ),
    (
        "gpu_unavailable",
        "no suitable adapter",
        "No suitable GPU adapter was found for the trainer. Amber does not "
        "silently fall back to the CPU.",
    ),
    (
        "invalid_input",
        "invalid data found when processing input",
        "The video could not be decoded. It may be truncated or use an "
        "unsupported codec.",
    ),
)


def parse_failure(result: ProcessResult) -> tuple[str, str]:
    """Map a failed process to (diagnostic, human-readable advice)."""
    haystack = f"{result.stderr}\n{result.stdout}".lower()
    for diagnostic, needle, advice in _FAILURE_PATTERNS:
        if needle in haystack:
            return diagnostic, advice

    # Negative return codes are signals. -9 is SIGKILL, which on macOS and
    # Linux most often means the OOM killer, not a tool bug.
    if result.returncode < 0:
        signal_number = -result.returncode
        if signal_number == 9:
            return (
                "out_of_memory",
                "The process was killed by the operating system, which almost "
                "always means it exhausted memory. Reduce resolution, frame "
                "count, or splat cap.",
            )
        return (
            "terminated_by_signal",
            f"The process was terminated by signal {signal_number}.",
        )

    tool = Path(result.command[0]).name if result.command else "the tool"
    return (
        "subprocess_failed",
        f"{tool} exited with status {result.returncode}. "
        "See the recorded stderr for details.",
    )


# --------------------------------------------------------------------------
# Running
# --------------------------------------------------------------------------


class ProcessRunner:
    """Runs external commands and supports cooperative cancellation."""

    def __init__(self) -> None:
        self._process: subprocess.Popen[str] | None = None
        self._cancelled = False

    def cancel(self) -> None:
        self._cancelled = True
        proc = self._process
        if proc is not None and proc.poll() is None:
            proc.terminate()

    @property
    def cancelled(self) -> bool:
        return self._cancelled

    def run(
        self,
        command: Sequence[str],
        cwd: Path | None = None,
        env: dict[str, str] | None = None,
        check: bool = True,
        timeout: float | None = None,
    ) -> ProcessResult:
        command = [str(c) for c in command]
        if shutil.which(command[0]) is None and not Path(command[0]).is_file():
            raise ToolMissingError(
                f"{command[0]!r} is not installed or not on PATH. "
                "Run `amber doctor` to see what is missing."
            )
        start = time.monotonic()
        try:
            self._process = subprocess.Popen(  # noqa: S603
                command,
                cwd=str(cwd) if cwd else None,
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
            stdout, stderr = self._process.communicate(timeout=timeout)
            returncode = self._process.returncode
        finally:
            duration = time.monotonic() - start
            self._process = None

        result = ProcessResult(
            command=command,
            returncode=returncode,
            stdout=stdout or "",
            stderr=stderr or "",
            duration_seconds=duration,
        )
        if check and not result.ok:
            diagnostic, advice = parse_failure(result)
            raise SubprocessFailure(advice, diagnostic, result)
        return result


def discover_tool(
    name: str,
    version_args: Sequence[str] = ("--version",),
    executable: str | None = None,
) -> ToolInfo:
    """Locate a tool and read its version from the installed binary.

    Versions are discovered, never assumed from documentation (ADR 0002).
    """
    exe = executable or name
    path = shutil.which(exe)
    if path is None:
        return ToolInfo(
            name=name,
            available=False,
            error=f"{exe!r} not found on PATH",
        )
    try:
        result = ProcessRunner().run([path, *version_args], check=False)
    except OSError as exc:  # pragma: no cover - defensive
        return ToolInfo(name=name, executable=path, available=False, error=str(exc))

    output = (result.stdout or result.stderr).strip()
    return ToolInfo(
        name=name,
        executable=path,
        available=True,
        version=_first_line(output),
        raw_version_output=output[:2000],
    )


def _first_line(text: str) -> str | None:
    for line in text.splitlines():
        line = line.strip()
        if line:
            return line
    return None
