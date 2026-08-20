"""Run one command while preserving a research-grade provenance bundle."""

from __future__ import annotations

import argparse
import importlib.metadata
import json
import os
import platform
import re
import subprocess
import sys
from collections.abc import Sequence
from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path
from time import monotonic
from typing import Any

from smartvalve.config import project_root

SCHEMA_VERSION = "smartvalve-recorded-run-0.1.0"
PACKAGE_NAMES = ("numpy", "pandas", "scipy", "scikit-learn", "torch")
RUN_ID_PATTERN = re.compile(r"^[A-Z0-9][A-Z0-9._-]{2,63}$")
FINGERPRINT_EXCLUDED_PARTS = {
    ".git",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    ".venv",
    "__pycache__",
}
FINGERPRINT_EXCLUDED_PREFIXES = (
    "artifacts/research/runs/",
    "data/external/",
)
FINGERPRINT_EXCLUDED_ROOT_FILES = {".coverage"}


def _utc_now() -> datetime:
    return datetime.now(UTC)


def _digest(path: Path) -> str:
    hasher = sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def _run_git(root: Path, *arguments: str, binary: bool = False) -> str | bytes | None:
    try:
        completed = subprocess.run(
            ("git", *arguments),
            cwd=root,
            check=True,
            capture_output=True,
            text=not binary,
            timeout=30,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    return completed.stdout


def _safe_slug(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return slug[:48] or "run"


def _replace_run_directory(command: Sequence[str], run_directory: Path) -> list[str]:
    return [part.replace("{run_dir}", str(run_directory)) for part in command]


def _source_fingerprint(root: Path) -> dict[str, Any]:
    raw_paths = _run_git(
        root,
        "ls-files",
        "--cached",
        "--others",
        "--exclude-standard",
        "-z",
        binary=True,
    )
    paths: list[str] = []
    discovery = "git_ls_files"
    if isinstance(raw_paths, bytes):
        paths = sorted(item.decode("utf-8") for item in raw_paths.split(b"\0") if item)
    else:
        discovery = "filesystem_fallback"
        paths = sorted(
            path.relative_to(root).as_posix()
            for path in root.rglob("*")
            if path.is_file()
            and path.name not in FINGERPRINT_EXCLUDED_ROOT_FILES
            and not FINGERPRINT_EXCLUDED_PARTS.intersection(path.relative_to(root).parts)
            and not path.relative_to(root).as_posix().startswith(
                FINGERPRINT_EXCLUDED_PREFIXES
            )
        )
    hasher = sha256()
    file_count = 0
    for relative in paths:
        if relative.startswith("artifacts/research/runs/"):
            continue
        path = root / relative
        if not path.is_file():
            continue
        hasher.update(relative.encode("utf-8"))
        hasher.update(b"\0")
        hasher.update(_digest(path).encode("ascii"))
        hasher.update(b"\0")
        file_count += 1
    diff = _run_git(root, "diff", "--binary", "HEAD", binary=True)
    return {
        "sha256": hasher.hexdigest(),
        "file_count": file_count,
        "git_diff_sha256": sha256(diff).hexdigest() if isinstance(diff, bytes) else None,
        "discovery": discovery,
    }


def _memory_state() -> dict[str, int]:
    result: dict[str, int] = {}
    try:
        for line in Path("/proc/meminfo").read_text(encoding="utf-8").splitlines():
            name, value = line.split(":", maxsplit=1)
            if name in {"MemTotal", "MemAvailable", "SwapTotal", "SwapFree"}:
                result[f"{name.lower()}_kib"] = int(value.strip().split()[0])
    except (OSError, ValueError, IndexError):
        return {}
    return result


def _gpu_state() -> list[dict[str, str]]:
    command = (
        "nvidia-smi",
        "--query-gpu=name,driver_version,memory.total",
        "--format=csv,noheader,nounits",
    )
    try:
        output = subprocess.run(
            command,
            check=True,
            capture_output=True,
            text=True,
            timeout=10,
        ).stdout
    except (OSError, subprocess.SubprocessError):
        return []
    result = []
    for line in output.splitlines():
        values = [value.strip() for value in line.split(",")]
        if len(values) == 3:
            result.append(
                {
                    "name": values[0],
                    "driver_version": values[1],
                    "memory_total_mib": values[2],
                }
            )
    return result


def _package_versions() -> dict[str, str | None]:
    versions: dict[str, str | None] = {}
    for name in PACKAGE_NAMES:
        try:
            versions[name] = importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            versions[name] = None
    return versions


def _external_data_state(root: Path) -> dict[str, Any]:
    manifest_path = root / "data" / "external" / "manifest.json"
    result: dict[str, Any] = {
        "manifest": str(manifest_path.relative_to(root)),
        "manifest_sha256": _digest(manifest_path) if manifest_path.is_file() else None,
        "files": [],
    }
    if not manifest_path.is_file():
        return result
    try:
        records = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return result
    for record in records:
        filename = str(record.get("filename", ""))
        path = manifest_path.parent / filename
        actual_sha256 = _digest(path) if path.is_file() else None
        result["files"].append(
            {
                "filename": filename,
                "available": path.is_file(),
                "bytes": path.stat().st_size if path.is_file() else 0,
                "expected_sha256": record.get("sha256"),
                "actual_sha256": actual_sha256,
                "integrity_verified": bool(
                    actual_sha256 and actual_sha256 == record.get("sha256")
                ),
            }
        )
    return result


def _file_manifest(run_directory: Path) -> list[dict[str, Any]]:
    records = []
    for path in sorted(run_directory.rglob("*")):
        if not path.is_file() or path.name == "metadata.json":
            continue
        records.append(
            {
                "path": str(path.relative_to(run_directory)),
                "bytes": path.stat().st_size,
                "sha256": _digest(path),
            }
        )
    return records


def _write_json(path: Path, value: Any) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


def run_recorded_experiment(
    *,
    experiment_id: str,
    name: str,
    description: str,
    command: Sequence[str],
    output_root: Path | None = None,
    root: Path | None = None,
) -> tuple[int, Path]:
    """Execute ``command`` without a shell and preserve logs plus provenance metadata."""

    if not RUN_ID_PATTERN.fullmatch(experiment_id):
        raise ValueError("experiment ID must match [A-Z0-9][A-Z0-9._-]{2,63}")
    if not command:
        raise ValueError("an experiment command is required")
    root = (root or project_root()).resolve()
    output_root = (output_root or root / "artifacts" / "research" / "runs").resolve()
    started_at = _utc_now()
    timestamp = started_at.strftime("%Y%m%dT%H%M%S.%fZ")
    run_directory = output_root / f"{experiment_id}__{timestamp}__{_safe_slug(name)}"
    run_directory.mkdir(parents=True, exist_ok=False)
    (run_directory / "outputs").mkdir()
    expanded_command = _replace_run_directory(command, run_directory)
    source_state = _source_fingerprint(root)
    status_output = _run_git(root, "status", "--short", "--branch")
    if isinstance(status_output, str):
        status_output = status_output.rstrip()
    commit = _run_git(root, "rev-parse", "HEAD")
    branch = _run_git(root, "branch", "--show-current")
    metadata: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "experiment_id": experiment_id,
        "name": name,
        "description": description,
        "started_at": started_at.isoformat(),
        "completed_at": None,
        "duration_s": None,
        "status": "running",
        "exit_code": None,
        "command": expanded_command,
        "working_directory": str(root),
        "repository": {
            "commit": commit.strip() if isinstance(commit, str) else None,
            "branch": branch.strip() if isinstance(branch, str) else None,
            "status": status_output,
            "dirty": bool(status_output and len(str(status_output).splitlines()) > 1),
            "source_fingerprint": source_state,
        },
        "environment": {
            "python_executable": sys.executable,
            "python_version": platform.python_version(),
            "platform": platform.platform(),
            "hostname": platform.node(),
            "machine": platform.machine(),
            "cpu_count": os.cpu_count(),
            "memory": _memory_state(),
            "gpus": _gpu_state(),
            "packages": _package_versions(),
        },
        "inputs_before": _external_data_state(root),
        "inputs_after": None,
        "output_files": [],
    }
    _write_json(run_directory / "metadata.json", metadata)
    _write_json(run_directory / "command.json", expanded_command)
    stdout_path = run_directory / "stdout.log"
    stderr_path = run_directory / "stderr.log"
    start_clock = monotonic()
    exit_code = 1
    try:
        with stdout_path.open("w", encoding="utf-8") as stdout, stderr_path.open(
            "w", encoding="utf-8"
        ) as stderr:
            completed = subprocess.run(
                expanded_command,
                cwd=root,
                stdout=stdout,
                stderr=stderr,
                text=True,
                check=False,
            )
        exit_code = completed.returncode
        status = "complete" if exit_code == 0 else "failed"
    except OSError as error:
        stderr_path.write_text(f"{type(error).__name__}: {error}\n", encoding="utf-8")
        status = "failed_to_start"
        exit_code = 127
    completed_at = _utc_now()
    metadata.update(
        {
            "completed_at": completed_at.isoformat(),
            "duration_s": round(monotonic() - start_clock, 6),
            "status": status,
            "exit_code": exit_code,
            "inputs_after": _external_data_state(root),
            "output_files": _file_manifest(run_directory),
        }
    )
    _write_json(run_directory / "metadata.json", metadata)
    return exit_code, run_directory


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--experiment-id", required=True)
    parser.add_argument("--name", required=True)
    parser.add_argument("--description", required=True)
    parser.add_argument("--output-root", type=Path)
    parser.add_argument("command", nargs=argparse.REMAINDER)
    args = parser.parse_args()
    command = args.command[1:] if args.command[:1] == ["--"] else args.command
    exit_code, run_directory = run_recorded_experiment(
        experiment_id=args.experiment_id,
        name=args.name,
        description=args.description,
        command=command,
        output_root=args.output_root,
    )
    print(json.dumps({"exit_code": exit_code, "run_directory": str(run_directory)}))
    raise SystemExit(exit_code)


if __name__ == "__main__":
    main()
