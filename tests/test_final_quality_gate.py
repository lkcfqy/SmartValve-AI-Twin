from __future__ import annotations

import json
from hashlib import sha256
from pathlib import Path

import pytest
from defusedxml.common import EntitiesForbidden

from smartvalve.experiments.final_quality_gate import (
    CHECK_IDS,
    normalized_commands,
    run_final_quality_gate,
)
from smartvalve.experiments.final_quality_gate import (
    _pytest_counts as gate_pytest_counts,
)
from smartvalve.experiments.final_quality_validation import (
    _pytest_counts as validator_pytest_counts,
)
from smartvalve.experiments.final_quality_validation import (
    validate_final_quality_gate,
)


def _digest(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def _write_fixture(root: Path) -> tuple[Path, str]:
    output = root / "quality"
    output.mkdir()
    records = []
    output_hashes = {}
    commands = normalized_commands(output)
    for check_id in CHECK_IDS:
        stdout = output / f"{check_id}.stdout.log"
        stderr = output / f"{check_id}.stderr.log"
        stdout.write_text(f"{check_id} passed\n", encoding="utf-8")
        stderr.write_text("", encoding="utf-8")
        for path in (stdout, stderr):
            output_hashes[path.name] = _digest(path)
        records.append(
            {
                "check_id": check_id,
                "command": commands[check_id],
                "started_at": "2026-08-19T00:00:00+00:00",
                "completed_at": "2026-08-19T00:00:01+00:00",
                "duration_s": 1.0,
                "exit_code": 0,
                "stdout_path": stdout.name,
                "stdout_bytes": stdout.stat().st_size,
                "stdout_sha256": _digest(stdout),
                "stderr_path": stderr.name,
                "stderr_bytes": stderr.stat().st_size,
                "stderr_sha256": _digest(stderr),
            }
        )
    pytest_xml = output / "pytest.xml"
    pytest_xml.write_text(
        '<testsuites><testsuite tests="380" failures="0" errors="0" skipped="0"/>'
        "</testsuites>\n",
        encoding="utf-8",
    )
    coverage_json = output / "coverage.json"
    coverage_json.write_text(
        json.dumps({"totals": {"percent_covered": 78.125}}, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    for path in (pytest_xml, coverage_json):
        output_hashes[path.name] = _digest(path)
    summary = {
        "status": "passed_final_local_quality_gate",
        "quality_gate_version": "smartvalve-final-local-quality-gate-test",
        "project_root": root.as_posix(),
        "expected_test_count": 380,
        "pytest_counts": {"tests": 380, "failures": 0, "errors": 0, "skipped": 0},
        "coverage_percent": 78.125,
        "checks": records,
        "output_sha256": output_hashes,
        "empirical_model_refit_performed": False,
        "clean_checkout_claimed": False,
        "independent_reproduction_claimed": False,
        "human_review_claimed": False,
        "submission_ready": False,
    }
    summary_path = output / "final_quality_gate_summary.json"
    summary_path.write_text(json.dumps(summary, sort_keys=True) + "\n", encoding="utf-8")
    return summary_path, _digest(summary_path)


def test_final_quality_validator_accepts_complete_hash_locked_package(tmp_path: Path) -> None:
    summary, digest = _write_fixture(tmp_path)

    result = validate_final_quality_gate(
        summary_path=summary,
        expected_summary_sha256=digest,
    )

    assert result["status"] == "passed_independent_final_local_quality_validation"
    assert result["verified_check_count"] == len(CHECK_IDS) == 8
    assert result["verified_expected_test_count"] == 380
    assert result["verified_test_count"] == 380
    assert result["verified_coverage_percent"] == 78.125
    assert result["submission_ready"] is False

    value = json.loads(summary.read_text(encoding="utf-8"))
    value["expected_test_count"] = 379
    summary.write_text(json.dumps(value, sort_keys=True) + "\n", encoding="utf-8")
    with pytest.raises(ValueError, match="pytest topology did not pass"):
        validate_final_quality_gate(
            summary_path=summary,
            expected_summary_sha256=_digest(summary),
        )


def test_final_quality_bandit_covers_application_and_project_scripts(tmp_path: Path) -> None:
    command = normalized_commands(tmp_path)["bandit_medium_high"]

    assert command == [
        ".venv/bin/bandit",
        "-q",
        "-r",
        "src",
        "scripts",
        "research/scripts",
        "-ll",
    ]


def test_final_quality_validator_rejects_hash_consistent_low_coverage(tmp_path: Path) -> None:
    summary_path, _ = _write_fixture(tmp_path)
    coverage = summary_path.parent / "coverage.json"
    coverage.write_text(
        json.dumps({"totals": {"percent_covered": 74.9}}, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    summary["coverage_percent"] = 74.9
    summary["output_sha256"]["coverage.json"] = _digest(coverage)
    summary_path.write_text(json.dumps(summary, sort_keys=True) + "\n", encoding="utf-8")

    with pytest.raises(ValueError, match="coverage threshold"):
        validate_final_quality_gate(
            summary_path=summary_path,
            expected_summary_sha256=_digest(summary_path),
        )


def test_final_quality_validator_rejects_hash_consistent_scope_overclaim(tmp_path: Path) -> None:
    summary_path, _ = _write_fixture(tmp_path)
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    summary["human_review_claimed"] = True
    summary_path.write_text(json.dumps(summary, sort_keys=True) + "\n", encoding="utf-8")

    with pytest.raises(ValueError, match="overstates its evidence scope"):
        validate_final_quality_gate(
            summary_path=summary_path,
            expected_summary_sha256=_digest(summary_path),
        )


def test_final_quality_runner_rejects_invalid_output_scope_or_test_count(tmp_path: Path) -> None:
    root = tmp_path / "project"
    root.mkdir()

    with pytest.raises(ValueError, match="must stay inside"):
        run_final_quality_gate(
            project_root=root,
            output_directory=tmp_path / "outside",
            expected_test_count=1,
        )
    with pytest.raises(ValueError, match="must be positive"):
        run_final_quality_gate(
            project_root=root,
            output_directory=root / "quality",
            expected_test_count=0,
        )
    occupied = root / "occupied"
    occupied.mkdir()
    (occupied / "existing.txt").write_text("do not overwrite\n", encoding="utf-8")
    with pytest.raises(ValueError, match="absent or empty"):
        run_final_quality_gate(
            project_root=root,
            output_directory=occupied,
            expected_test_count=1,
        )


def test_final_quality_xml_parsers_reject_entity_expansion(tmp_path: Path) -> None:
    junit = tmp_path / "malicious.xml"
    junit.write_text(
        '<?xml version="1.0"?>\n'
        '<!DOCTYPE testsuites [<!ENTITY injected "not-a-test-count">]>\n'
        '<testsuites><testsuite tests="1" failures="0" errors="0" skipped="0">'
        '<testcase name="&injected;"/></testsuite></testsuites>\n',
        encoding="utf-8",
    )

    for parser in (gate_pytest_counts, validator_pytest_counts):
        with pytest.raises(EntitiesForbidden):
            parser(junit)
