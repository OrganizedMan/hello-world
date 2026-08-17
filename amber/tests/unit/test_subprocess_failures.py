from __future__ import annotations

import sys
from pathlib import Path

import pytest

from amber.tools import (
    ProcessResult,
    ProcessRunner,
    SubprocessFailure,
    ToolMissingError,
    discover_tool,
    parse_failure,
)


def result(stderr: str = "", stdout: str = "", returncode: int = 1) -> ProcessResult:
    return ProcessResult(
        command=["colmap", "mapper"],
        returncode=returncode,
        stdout=stdout,
        stderr=stderr,
        duration_seconds=1.0,
    )


@pytest.mark.parametrize(
    "stderr,expected",
    [
        ("terminate called: std::bad_alloc", "out_of_memory"),
        ("Error: Out of memory while allocating", "out_of_memory"),
        ("write failed: No space left on device", "out_of_disk"),
        ("No good initial image pair found.", "mapper_initialization_failed"),
        ("ERROR: no features detected", "no_features"),
        ("CUDA error: no kernel image is available", "gpu_unavailable"),
        ("No suitable adapter found", "gpu_unavailable"),
        ("Invalid data found when processing input", "invalid_input"),
    ],
)
def test_known_failures_map_to_diagnostics(stderr, expected):
    diagnostic, advice = parse_failure(result(stderr=stderr))
    assert diagnostic == expected
    assert advice, "every diagnostic must carry actionable advice"


def test_a_kill_signal_is_read_as_running_out_of_memory():
    diagnostic, advice = parse_failure(result(returncode=-9))
    assert diagnostic == "out_of_memory"
    assert "exhausted memory" in advice


def test_other_signals_are_reported_as_signals():
    diagnostic, advice = parse_failure(result(returncode=-15))
    assert diagnostic == "terminated_by_signal"
    assert "signal 15" in advice


def test_an_unrecognised_failure_still_names_the_tool():
    diagnostic, advice = parse_failure(result(stderr="something odd", returncode=3))
    assert diagnostic == "subprocess_failed"
    assert "colmap" in advice and "status 3" in advice


def test_stdout_is_searched_as_well_as_stderr():
    diagnostic, _ = parse_failure(result(stdout="No good initial image pair"))
    assert diagnostic == "mapper_initialization_failed"


def test_matching_is_case_insensitive():
    diagnostic, _ = parse_failure(result(stderr="NO SPACE LEFT ON DEVICE"))
    assert diagnostic == "out_of_disk"


def test_a_missing_tool_is_named_clearly():
    with pytest.raises(ToolMissingError, match="amber doctor"):
        ProcessRunner().run(["definitely-not-a-real-binary-xyz"])


def test_a_failing_process_raises_with_its_diagnostic_attached(tmp_path: Path):
    script = tmp_path / "fail.py"
    script.write_text(
        "import sys; sys.stderr.write('No space left on device'); sys.exit(1)"
    )
    with pytest.raises(SubprocessFailure) as excinfo:
        ProcessRunner().run([sys.executable, str(script)])

    assert excinfo.value.diagnostic == "out_of_disk"
    assert excinfo.value.result.returncode == 1
    assert "No space left" in excinfo.value.result.stderr


def test_check_false_returns_the_failure_instead_of_raising(tmp_path: Path):
    script = tmp_path / "fail.py"
    script.write_text("import sys; sys.exit(7)")
    outcome = ProcessRunner().run([sys.executable, str(script)], check=False)

    assert outcome.returncode == 7
    assert not outcome.ok


def test_a_successful_run_records_its_command_and_duration():
    outcome = ProcessRunner().run([sys.executable, "-c", "print('hi')"])

    assert outcome.ok
    assert outcome.stdout.strip() == "hi"
    assert outcome.duration_seconds >= 0
    assert outcome.to_dict()["command"][-1] == "print('hi')"


def test_discovery_reports_a_missing_tool_without_raising():
    info = discover_tool("definitely-not-a-real-binary-xyz")
    assert info.available is False
    assert "not found" in info.error


def test_discovery_reads_the_version_from_the_installed_binary():
    info = discover_tool("python3", version_args=("--version",))
    if not info.available:  # pragma: no cover - python3 should exist
        pytest.skip("python3 not on PATH")
    assert "Python" in info.version
