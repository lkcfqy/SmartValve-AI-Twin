"""Run and record the final local source-quality gate for the bearing submission."""

from __future__ import annotations

import hashlib
import json

# Commands are fixed project checks invoked only as argument vectors.
import subprocess  # nosec B404
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from defusedxml import ElementTree

QUALITY_GATE_VERSION = "smartvalve-final-local-quality-gate-0.3.0"
CHECK_IDS = (
    "ruff",
    "pytest",
    "coverage",
    "bandit_medium_high",
    "pip_audit_runtime_build",
    "pip_audit_ci",
    "pip_audit_research",
    "git_diff_check",
)


def sha256_file(path: Path) -> str:
    """Return a streaming SHA-256 digest."""

    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(4 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _utc_now() -> str:
    return datetime.now(UTC).isoformat()


def _commands(output_directory: Path) -> dict[str, tuple[str, ...]]:
    pytest_xml = output_directory / "pytest.xml"
    coverage_json = output_directory / "coverage.json"
    return {
        "ruff": (".venv/bin/ruff", "check", "."),
        "pytest": (
            ".venv/bin/python",
            "-m",
            "pytest",
            "-q",
            "--junitxml",
            str(pytest_xml),
        ),
        "coverage": (
            ".venv/bin/python",
            "-m",
            "pytest",
            "-q",
            "--cov=src/smartvalve",
            "--cov-report=term-missing",
            f"--cov-report=json:{coverage_json}",
            "--cov-fail-under=75",
        ),
        "bandit_medium_high": (
            ".venv/bin/bandit",
            "-q",
            "-r",
            "src",
            "scripts",
            "research/scripts",
            "-ll",
        ),
        "pip_audit_runtime_build": (
            ".venv/bin/pip-audit",
            "-r",
            "requirements.lock",
            "-r",
            "build-requirements.lock",
            "--disable-pip",
            "--strict",
        ),
        "pip_audit_ci": (
            ".venv/bin/pip-audit",
            "-r",
            "requirements-ci.lock",
            "--disable-pip",
            "--strict",
            "--vulnerability-service",
            "osv",
        ),
        "pip_audit_research": (
            ".venv/bin/pip-audit",
            "-r",
            "requirements-research.lock",
            "--disable-pip",
            "--strict",
        ),
        "git_diff_check": ("git", "diff", "--check"),
    }


def normalized_commands(output_directory: Path) -> dict[str, list[str]]:
    """Expose deterministic command records with the run directory normalized."""

    marker = str(output_directory)
    return {
        check_id: [token.replace(marker, "{output_directory}") for token in command]
        for check_id, command in _commands(output_directory).items()
    }


def _run_check(
    *,
    check_id: str,
    command: tuple[str, ...],
    project_root: Path,
    output_directory: Path,
) -> dict[str, Any]:
    stdout_path = output_directory / f"{check_id}.stdout.log"
    stderr_path = output_directory / f"{check_id}.stderr.log"
    started_at = _utc_now()
    started = time.monotonic()
    # The executable and every argument vector are defined in _commands above.
    completed = subprocess.run(  # nosec B603
        command,
        cwd=project_root,
        check=False,
        capture_output=True,
    )
    duration = time.monotonic() - started
    stdout_path.write_bytes(completed.stdout)
    stderr_path.write_bytes(completed.stderr)
    return {
        "check_id": check_id,
        "command": normalized_commands(output_directory)[check_id],
        "started_at": started_at,
        "completed_at": _utc_now(),
        "duration_s": duration,
        "exit_code": completed.returncode,
        "stdout_path": stdout_path.name,
        "stdout_bytes": stdout_path.stat().st_size,
        "stdout_sha256": sha256_file(stdout_path),
        "stderr_path": stderr_path.name,
        "stderr_bytes": stderr_path.stat().st_size,
        "stderr_sha256": sha256_file(stderr_path),
    }


def _pytest_counts(path: Path) -> dict[str, int]:
    root = ElementTree.parse(path).getroot()
    if root.tag == "testsuite":
        suites = (root,)
    elif root.tag == "testsuites":
        suites = tuple(root.findall("testsuite"))
    else:
        raise ValueError("pytest XML root is not testsuite/testsuites")
    return {
        name: sum(int(suite.attrib.get(name, "0")) for suite in suites)
        for name in ("tests", "failures", "errors", "skipped")
    }


def _coverage_percent(path: Path) -> float:
    value = json.loads(path.read_text(encoding="utf-8"))
    return float(value["totals"]["percent_covered"])


def run_final_quality_gate(
    *,
    project_root: Path,
    output_directory: Path,
    expected_test_count: int,
) -> dict[str, Any]:
    """Run every fixed local gate and write a hash-linked machine-readable report."""

    root = project_root.resolve(strict=True)
    output = output_directory.resolve()
    try:
        output.relative_to(root)
    except ValueError as error:
        raise ValueError("quality-gate output directory must stay inside the project") from error
    if expected_test_count < 1:
        raise ValueError("expected test count must be positive")
    if output.exists():
        if not output.is_dir() or any(output.iterdir()):
            raise ValueError("quality-gate output directory must be absent or empty")
    else:
        output.mkdir(parents=True)

    records = [
        _run_check(
            check_id=check_id,
            command=_commands(output)[check_id],
            project_root=root,
            output_directory=output,
        )
        for check_id in CHECK_IDS
    ]
    pytest_xml = output / "pytest.xml"
    coverage_json = output / "coverage.json"
    pytest_counts = (
        _pytest_counts(pytest_xml)
        if pytest_xml.is_file()
        else {name: -1 for name in ("tests", "failures", "errors", "skipped")}
    )
    coverage_percent = _coverage_percent(coverage_json) if coverage_json.is_file() else -1.0
    checks_passed = all(int(record["exit_code"]) == 0 for record in records)
    topology_passed = (
        pytest_counts["tests"] == expected_test_count
        and pytest_counts["failures"] == 0
        and pytest_counts["errors"] == 0
        and pytest_counts["skipped"] == 0
        and coverage_percent >= 75.0
    )
    output_paths = [
        output / str(record[path_name])
        for record in records
        for path_name in ("stdout_path", "stderr_path")
    ]
    output_paths.extend(path for path in (pytest_xml, coverage_json) if path.is_file())
    summary = {
        "status": (
            "passed_final_local_quality_gate"
            if checks_passed and topology_passed
            else "failed_final_local_quality_gate"
        ),
        "quality_gate_version": QUALITY_GATE_VERSION,
        "project_root": root.as_posix(),
        "expected_test_count": expected_test_count,
        "pytest_counts": pytest_counts,
        "coverage_percent": coverage_percent,
        "checks": records,
        "output_sha256": {
            path.name: sha256_file(path)
            for path in sorted(output_paths, key=lambda item: item.name)
        },
        "empirical_model_refit_performed": False,
        "clean_checkout_claimed": False,
        "independent_reproduction_claimed": False,
        "human_review_claimed": False,
        "submission_ready": False,
    }
    summary_path = output / "final_quality_gate_summary.json"
    summary_path.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    return summary
