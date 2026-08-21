from pathlib import Path

from scripts.doctor import collect_checks


def test_doctor_distinguishes_required_tools_from_optional_blender(tmp_path: Path) -> None:
    checks = collect_checks(tmp_path)

    assert checks["python"]["required"] is True
    assert checks["node"]["required"] is True
    assert checks["pdf_preview"]["required"] is True
    assert checks["blender"]["required"] is False
