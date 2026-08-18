"""End-to-end smoke test for the running product (plan §11 review UI,
Stage 0). Boots the real FastAPI server and the real Vite dev server,
drives the real page with Playwright, and checks it renders the family
room correctly with no console errors — this is the closest thing to "did
a human open this and see what they expected" that can run unattended.

Skips cleanly (not a failure) when the prerequisites for booting a live
browser session aren't present: node_modules not installed, no system
Chromium, or the Python `playwright` package missing. This test owns
ports 8000/5173 for its duration and will skip rather than hang if
they're already occupied by another running instance.
"""
from __future__ import annotations

import os
import shutil
import signal
import socket
import subprocess
import sys
import time
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
UI_DIR = REPO_ROOT / "packages" / "ui"
CHROMIUM_CANDIDATES = [
    Path("/opt/pw-browsers/chromium-1194/chrome-linux/chrome"),
    Path("/opt/pw-browsers/chromium/chrome-linux/chrome"),
]
BACKEND_PORT = 8000
FRONTEND_PORT = 5173

playwright = pytest.importorskip("playwright.sync_api", reason="playwright not installed")


def _port_free(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex(("127.0.0.1", port)) != 0


def _find_chromium() -> str | None:
    for c in CHROMIUM_CANDIDATES:
        if c.exists():
            return str(c)
    return None


def _wait_http(url: str, timeout_s: float) -> bool:
    import urllib.request

    deadline = time.time() + timeout_s
    while time.time() < deadline:
        try:
            urllib.request.urlopen(url, timeout=1)
            return True
        except Exception:
            time.sleep(0.3)
    return False


@pytest.fixture(scope="module")
def running_app():
    if not (UI_DIR / "node_modules").is_dir():
        pytest.skip("packages/ui/node_modules not installed (npm install)")
    if not shutil.which("npm"):
        pytest.skip("npm not on PATH")
    chromium = _find_chromium()
    if chromium is None:
        pytest.skip("no system Chromium found under /opt/pw-browsers")
    if not (_port_free(BACKEND_PORT) and _port_free(FRONTEND_PORT)):
        pytest.skip(f"ports {BACKEND_PORT}/{FRONTEND_PORT} already in use by another process")

    # `npm run dev` spawns vite as a child process; terminating the npm
    # wrapper alone leaves that child running and holding the port. Both
    # processes launch in their own session (start_new_session=True) so
    # cleanup can signal the whole process group, not just the direct
    # child — the first version of this fixture leaked a live vite
    # process on every run because it skipped this.
    backend = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "server:app", "--app-dir", "packages/server/src",
         "--host", "127.0.0.1", "--port", str(BACKEND_PORT)],
        cwd=REPO_ROOT, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        start_new_session=True,
    )
    frontend = subprocess.Popen(
        ["npm", "run", "dev", "--", "--host", "127.0.0.1", "--port", str(FRONTEND_PORT)],
        cwd=UI_DIR, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        start_new_session=True,
    )
    try:
        if not _wait_http(f"http://127.0.0.1:{BACKEND_PORT}/api/health", 15):
            pytest.fail("backend did not become healthy in time")
        if not _wait_http(f"http://127.0.0.1:{FRONTEND_PORT}/", 15):
            pytest.fail("frontend dev server did not become ready in time")
        yield {"chromium": chromium, "url": f"http://127.0.0.1:{FRONTEND_PORT}/"}
    finally:
        for proc in (backend, frontend):
            try:
                os.killpg(os.getpgid(proc.pid), signal.SIGTERM)
            except ProcessLookupError:
                pass
        for proc in (backend, frontend):
            try:
                proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
                proc.wait(timeout=5)


def test_app_renders_family_room_with_no_console_errors(running_app):
    from playwright.sync_api import sync_playwright

    console_errors: list[str] = []
    with sync_playwright() as p:
        browser = p.chromium.launch(executable_path=running_app["chromium"], args=["--no-sandbox"])
        page = browser.new_page(viewport={"width": 1440, "height": 900})
        page.on("console", lambda m: console_errors.append(m.text) if m.type == "error" else None)
        page.on("pageerror", lambda e: console_errors.append(str(e)))
        page.goto(running_app["url"], wait_until="networkidle", timeout=15000)
        page.wait_for_timeout(1000)

        assert console_errors == []

        # The four panes exist and carry the expected content.
        assert page.locator('[data-testid="source-image"]').count() == 1
        assert page.locator('[data-testid="three-viewer"] canvas').count() == 1
        overall = page.locator('[data-testid="overall-status"]').inner_text()
        assert "Not blocking" in overall

        wall_inspector_text = page.locator('[data-testid="wall-inspector"]').inner_text()
        assert "LIVING_ROOM.EAST" in wall_inspector_text
        assert "LIVING_ROOM.SOUTH" in wall_inspector_text
        assert "60\" TV mounts on the solid wall" in wall_inspector_text

        # Toggling to the degraded scan updates the tier badge to Tier C.
        page.click("text=150 DPI scan (degraded)")
        page.wait_for_timeout(500)
        badge_text = page.locator('[data-testid="tier-badge-degraded"]').inner_text()
        assert "Tier C" in badge_text

        browser.close()
