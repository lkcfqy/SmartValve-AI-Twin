"""Run the API and Streamlit console as one local demonstration stack."""

from __future__ import annotations

import os
import signal
import subprocess
import sys
import time
import urllib.request
from collections.abc import Sequence


def _terminate(processes: Sequence[subprocess.Popen[bytes]]) -> None:
    for process in processes:
        if process.poll() is None:
            process.terminate()
    deadline = time.monotonic() + 5.0
    for process in processes:
        if process.poll() is None:
            try:
                process.wait(timeout=max(0.1, deadline - time.monotonic()))
            except subprocess.TimeoutExpired:
                process.kill()


def _wait_for_api(process: subprocess.Popen[bytes], timeout_s: float = 30.0) -> None:
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise RuntimeError(f"API exited during startup with code {process.returncode}")
        try:
            # Fixed loopback readiness endpoint; no user-controlled scheme or host.
            with urllib.request.urlopen(  # nosec B310
                "http://127.0.0.1:8000/health/ready", timeout=1.0
            ) as response:
                if response.status == 200:
                    return
        except OSError:
            time.sleep(0.25)
    raise RuntimeError("API did not become ready within 30 seconds")


def main() -> int:
    environment = os.environ.copy()
    environment.setdefault("SMARTVALVE_API_URL", "http://127.0.0.1:8000")
    bind_host = environment.get("SMARTVALVE_BIND_HOST", "127.0.0.1")
    api = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "uvicorn",
            "smartvalve.service.app:app",
            "--host",
            bind_host,
            "--port",
            "8000",
        ],
        env=environment,
    )
    processes = [api]
    previous_handlers: dict[int, object] = {}

    def stop_stack(signum: int, _frame: object) -> None:
        _terminate(processes)
        raise SystemExit(128 + signum)

    for signum in (signal.SIGINT, signal.SIGTERM):
        previous_handlers[signum] = signal.signal(signum, stop_stack)

    try:
        _wait_for_api(api)
        dashboard = subprocess.Popen(
            [
                sys.executable,
                "-m",
                "streamlit",
                "run",
                "dashboard/app.py",
                f"--server.address={bind_host}",
            ],
            env=environment,
        )
        processes.append(dashboard)
        while all(process.poll() is None for process in processes):
            time.sleep(0.5)
        return next(
            (process.returncode or 0 for process in processes if process.returncode is not None),
            0,
        )
    finally:
        _terminate(processes)
        for signum, handler in previous_handlers.items():
            signal.signal(signum, handler)


if __name__ == "__main__":
    raise SystemExit(main())
