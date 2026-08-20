"""Independently validate a completed final local quality-gate package."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from defusedxml import ElementTree

from smartvalve.experiments.final_quality_gate import CHECK_IDS, normalized_commands

VALIDATOR_VERSION = "smartvalve-final-local-quality-validator-0.2.0"


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(4 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _json_object(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"JSON input is not an object: {path}")
    return value


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


def validate_final_quality_gate(
    *,
    summary_path: Path,
    expected_summary_sha256: str,
) -> dict[str, Any]:
    """Recheck commands, hashes, JUnit counts, and coverage without rerunning the gate."""

    summary_file = summary_path.resolve(strict=True)
    observed_summary_sha256 = _sha256_file(summary_file)
    if observed_summary_sha256 != expected_summary_sha256:
        raise ValueError(
            "final quality summary SHA-256 changed: "
            f"expected {expected_summary_sha256}, observed {observed_summary_sha256}"
        )
    summary = _json_object(summary_file)
    if summary.get("status") != "passed_final_local_quality_gate":
        raise ValueError("final local quality gate did not pass")
    if any(
        summary.get(name) is not False
        for name in (
            "empirical_model_refit_performed",
            "clean_checkout_claimed",
            "independent_reproduction_claimed",
            "human_review_claimed",
            "submission_ready",
        )
    ):
        raise ValueError("final local quality summary overstates its evidence scope")
    expected_test_count = int(summary.get("expected_test_count", 0))
    if expected_test_count < 1:
        raise ValueError("final quality expected test count is invalid")

    records = summary.get("checks")
    if not isinstance(records, list) or len(records) != len(CHECK_IDS):
        raise ValueError("final quality check topology changed")
    record_by_id = {
        str(record.get("check_id")): record for record in records if isinstance(record, dict)
    }
    if tuple(record_by_id) != CHECK_IDS:
        raise ValueError("final quality check identifiers or order changed")
    expected_commands = normalized_commands(summary_file.parent)
    output_hashes = summary.get("output_sha256")
    if not isinstance(output_hashes, dict):
        raise ValueError("final quality output hash map is absent")
    for check_id, record in record_by_id.items():
        if record.get("command") != expected_commands[check_id]:
            raise ValueError(f"final quality command changed: {check_id}")
        if record.get("exit_code") != 0:
            raise ValueError(f"final quality check did not exit zero: {check_id}")
        for stream in ("stdout", "stderr"):
            name = str(record.get(f"{stream}_path", ""))
            path = summary_file.parent / name
            if path.name != name or not path.is_file():
                raise ValueError(f"final quality {check_id} {stream} path changed")
            if path.stat().st_size != int(record.get(f"{stream}_bytes", -1)):
                raise ValueError(f"final quality {check_id} {stream} byte count changed")
            digest = _sha256_file(path)
            if digest != record.get(f"{stream}_sha256") or digest != output_hashes.get(name):
                raise ValueError(f"final quality {check_id} {stream} hash changed")

    pytest_xml = summary_file.parent / "pytest.xml"
    coverage_json = summary_file.parent / "coverage.json"
    for path in (pytest_xml, coverage_json):
        if _sha256_file(path.resolve(strict=True)) != output_hashes.get(path.name):
            raise ValueError(f"final quality structured output hash changed: {path.name}")
    pytest_counts = _pytest_counts(pytest_xml)
    if pytest_counts != summary.get("pytest_counts"):
        raise ValueError("final quality pytest counts changed")
    if (
        pytest_counts["tests"] != expected_test_count
        or pytest_counts["failures"] != 0
        or pytest_counts["errors"] != 0
        or pytest_counts["skipped"] != 0
    ):
        raise ValueError("final quality pytest topology did not pass")
    coverage = _json_object(coverage_json)
    coverage_percent = float(coverage["totals"]["percent_covered"])
    if coverage_percent < 75.0 or coverage_percent != float(summary.get("coverage_percent", -1)):
        raise ValueError("final quality coverage threshold or summary changed")

    return {
        "status": "passed_independent_final_local_quality_validation",
        "validator_version": VALIDATOR_VERSION,
        "quality_summary_sha256": expected_summary_sha256,
        "verified_check_count": len(CHECK_IDS),
        "verified_expected_test_count": expected_test_count,
        "verified_test_count": pytest_counts["tests"],
        "verified_skipped_count": pytest_counts["skipped"],
        "verified_coverage_percent": coverage_percent,
        "empirical_model_refit_performed": False,
        "clean_checkout_claimed": False,
        "independent_reproduction_claimed": False,
        "human_review_claimed": False,
        "submission_ready": False,
    }
