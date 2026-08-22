from __future__ import annotations

import os
import shutil
import signal
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def find_free_port(preferred: int) -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        try:
            probe.bind(("127.0.0.1", preferred))
        except OSError:
            probe.bind(("127.0.0.1", 0))
        return int(probe.getsockname()[1])


def _port(name: str, preferred: int) -> int:
    configured = os.environ.get(name)
    if configured:
        return int(configured)
    return find_free_port(preferred)


def _reachable(url: str) -> bool:
    try:
        with urllib.request.urlopen(url, timeout=1) as response:
            return 200 <= response.status < 500
    except (urllib.error.URLError, TimeoutError):
        return False


def _stop(processes: list[subprocess.Popen[bytes]]) -> None:
    for process in processes:
        if process.poll() is None:
            process.terminate()
    deadline = time.monotonic() + 5
    for process in processes:
        remaining = max(0.0, deadline - time.monotonic())
        try:
            process.wait(timeout=remaining)
        except subprocess.TimeoutExpired:
            process.kill()


def main() -> int:
    npm = shutil.which("npm")
    if npm is None:
        print("HearthView needs Node.js and npm. Run npm run doctor for details.", file=sys.stderr)
        return 1
    api_port = _port("HEARTHVIEW_API_PORT", 8008)
    web_port = _port("HEARTHVIEW_WEB_PORT", 5178)
    environment = os.environ.copy()
    environment["HEARTHVIEW_API_PORT"] = str(api_port)
    environment["HEARTHVIEW_WEB_PORT"] = str(web_port)
    environment.setdefault("HEARTHVIEW_DATA_DIR", str(ROOT / "work" / "hearthview-data"))
    python_paths = [str(ROOT / "apps" / "api"), str(ROOT / "services")]
    existing_python_path = environment.get("PYTHONPATH")
    if existing_python_path:
        python_paths.append(existing_python_path)
    environment["PYTHONPATH"] = os.pathsep.join(python_paths)

    api = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "hearthview_api.main:app", "--host", "127.0.0.1", "--port", str(api_port)],
        cwd=ROOT,
        env=environment,
    )
    web = subprocess.Popen(
        [npm, "--workspace", "apps/web", "run", "dev", "--", "--host", "127.0.0.1", "--port", str(web_port), "--strictPort"],
        cwd=ROOT,
        env=environment,
    )
    processes = [api, web]

    def request_shutdown(_signum, _frame):
        _stop(processes)
        raise SystemExit(0)

    signal.signal(signal.SIGINT, request_shutdown)
    signal.signal(signal.SIGTERM, request_shutdown)
    try:
        deadline = time.monotonic() + 35
        while time.monotonic() < deadline:
            if any(process.poll() is not None for process in processes):
                raise RuntimeError("A local HearthView service stopped during startup.")
            if _reachable(f"http://127.0.0.1:{api_port}/health") and _reachable(f"http://127.0.0.1:{web_port}/"):
                print(f"HearthView is ready: http://127.0.0.1:{web_port}", flush=True)
                break
            time.sleep(0.15)
        else:
            raise RuntimeError("HearthView did not become ready within 35 seconds.")
        while all(process.poll() is None for process in processes):
            time.sleep(0.3)
        return 1
    except (KeyboardInterrupt, RuntimeError) as error:
        if isinstance(error, RuntimeError):
            print(str(error), file=sys.stderr)
        return 1 if isinstance(error, RuntimeError) else 0
    finally:
        _stop(processes)


if __name__ == "__main__":
    raise SystemExit(main())
