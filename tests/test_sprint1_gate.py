"""Sprint 1 "done when" gate (plan §20):

  all five sheets open and display; tier detection correctly reports
  Tier A for the originals and Tier C for the degraded raster; the
  assertion suite runs and fails cleanly with readable output.

(The fourth clause, "the units test suite is exhaustive," is verified by
packages/units/tests directly.) This test is the single place all four
packages — ingest, store, core_schema, and the fixture itself — are
proven to work together against the real Garrigan PDFs, not mocks.
"""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path

import pytest

from ingest import PyMuPdfBackend, Tier, detect_tier
from store import ProjectStore

FIXTURE_ROOT = Path(__file__).resolve().parent.parent / "fixtures" / "garrigan-261-grove"
SOURCE_DIR = FIXTURE_ROOT / "source"
REPO_ROOT = Path(__file__).resolve().parent.parent


def test_manifest_sha256_matches_pinned_files():
    manifest = json.loads((SOURCE_DIR / "manifest.json").read_text())
    for filename, meta in manifest["files"].items():
        if "sha256" not in meta:
            continue  # the derived Tier C fixture is intentionally not hash-pinned
        actual = hashlib.sha256((SOURCE_DIR / filename).read_bytes()).hexdigest()
        assert actual == meta["sha256"], f"{filename} has drifted from the pinned fixture"


def test_all_five_sheets_open_and_display():
    backend = PyMuPdfBackend()
    sheet_count = 0
    for filename in ("garrigan-main-set.pdf", "garrigan-attic-idea.pdf"):
        with backend.open(str(SOURCE_DIR / filename)) as handle:
            for i in range(handle.page_count):
                sig = handle.page_signals(i)
                assert sig.width_pt > 0 and sig.height_pt > 0
                # rasterisation "at any zoom" — exercise two different DPIs
                for dpi in (72, 150):
                    png = handle.rasterize_page(i, dpi)
                    assert png[:8] == b"\x89PNG\r\n\x1a\n", "rasterize_page must return valid PNG bytes"
                sheet_count += 1
    assert sheet_count == 5, f"expected 5 sheets across both source PDFs, got {sheet_count}"


def test_tier_detection_reports_a_for_originals_and_c_for_degraded():
    backend = PyMuPdfBackend()

    with backend.open(str(SOURCE_DIR / "garrigan-main-set.pdf")) as h:
        for i in range(h.page_count):
            result = detect_tier(h.page_signals(i))
            assert result.tier == Tier.A, f"main-set page {i+1} expected Tier A, got {result.tier}"

    with backend.open(str(SOURCE_DIR / "garrigan-attic-idea.pdf")) as h:
        result = detect_tier(h.page_signals(0))
        assert result.tier == Tier.A

    with backend.open(str(SOURCE_DIR / "garrigan-a1-degraded-150dpi.pdf")) as h:
        result = detect_tier(h.page_signals(0))
        assert result.tier == Tier.C, f"degraded fixture expected Tier C, got {result.tier}"


def test_store_ingests_fixture_documents_content_addressed(tmp_path):
    store = ProjectStore.create(tmp_path / "garrigan.g3d")
    try:
        for filename in (
            "garrigan-main-set.pdf",
            "garrigan-attic-idea.pdf",
            "garrigan-a1-degraded-150dpi.pdf",
        ):
            data = (SOURCE_DIR / filename).read_bytes()
            backend = PyMuPdfBackend()
            with backend.open(str(SOURCE_DIR / filename)) as h:
                page_count = h.page_count
            doc = store.add_source_document(filename, data, page_count=page_count, is_vector=True)
            assert doc.filename == filename
            assert store.get_source_document_bytes(doc.id) == data

        docs = store.list_source_documents()
        assert len(docs) == 3
        assert {d.page_count for d in docs} == {4, 1, 1}
    finally:
        store.close()


def test_assertion_suite_runs_and_fails_cleanly():
    result = subprocess.run(
        [sys.executable, str(REPO_ROOT / "tools" / "run_assertions.py"), "--root", str(REPO_ROOT)],
        capture_output=True,
        text=True,
        timeout=30,
    )
    # It must exit non-zero (nothing is implemented yet) but never crash:
    # a Python traceback means "fails cleanly" was violated.
    assert result.returncode == 1
    assert "Traceback" not in result.stderr
    assert "FAIL" in result.stdout
    assert "passed, 25 failed, 25 total" in result.stdout


def test_import_boundary_check_runs_clean():
    result = subprocess.run(
        [sys.executable, str(REPO_ROOT / "tools" / "check_import_boundaries.py")],
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0
    assert "Traceback" not in result.stderr
