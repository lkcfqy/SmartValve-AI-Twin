from __future__ import annotations

import json
from hashlib import sha256
from pathlib import Path

import pytest

from smartvalve.config import project_root
from smartvalve.experiments.bearing_manuscript import (
    MARKER_PREFIX,
    render_empirical_final_manuscript,
)
from smartvalve.experiments.bearing_manuscript_validation import (
    validate_empirical_final_manuscript,
)


def _snapshot(
    methods: tuple[str, ...],
    *,
    effect: float,
    nonpositive_method: str | None = None,
) -> dict[str, object]:
    by_method = {}
    for method in methods:
        lower = -0.05 if method == nonpositive_method else effect - 0.1
        by_method[method] = {
            "effect": effect,
            "lower_95": lower,
            "upper_95": effect + 0.1,
        }
    lowers = [float(item["lower_95"]) for item in by_method.values()]
    return {
        "effect_minimum": effect,
        "effect_median": effect,
        "effect_maximum": effect,
        "interval_lower_minimum": min(lowers),
        "interval_upper_maximum": effect + 0.1,
        "all_interval_lower_limits_above_zero": all(value > 0 for value in lowers),
        "by_method": by_method,
    }


def _write_manifest(root: Path, *, raw_rule: bool) -> tuple[Path, str]:
    methods = tuple(f"method-{index}" for index in range(9))
    common_view = {
        "measurement_random_macro_f1": {"minimum": 0.95, "maximum": 0.98},
        "crossed_holdout_macro_f1": {"minimum": 0.36, "maximum": 0.40},
        "random_minus_crossed": _snapshot(methods, effect=0.5),
    }
    raw_snapshot = _snapshot(
        ("cnn1d", "fft", "stft"),
        effect=0.25,
        nonpositive_method=None if raw_rule else "stft",
    )
    manifest = {
        "generator_version": "smartvalve-bearing-paper-artifacts-test",
        "deterministic": True,
        "decision": {
            "raw_representation_sensitivity_rule_passed": raw_rule,
            "headline_values": {
                "paderborn_fusion": common_view,
                "paderborn_sensor_views": {
                    family: common_view
                    for family in ("vibration", "motor_current", "fusion")
                },
                "paderborn_raw_architectures": {
                    "measurement_random_macro_f1": {"minimum": 0.80, "maximum": 0.90},
                    "crossed_holdout_macro_f1": {"minimum": 0.50, "maximum": 0.60},
                    "random_minus_crossed": raw_snapshot,
                },
                "hust_replication": {
                    "recording_random_macro_f1": {"minimum": 1.0, "maximum": 1.0},
                    "crossed_holdout_macro_f1": {"minimum": 0.747, "maximum": 0.774},
                    "random_minus_crossed": _snapshot(methods, effect=0.226),
                },
                "hust_equal_volume_control": {
                    "shared_access_macro_f1": {"minimum": 1.0, "maximum": 1.0},
                    "crossed_holdout_macro_f1": {"minimum": 0.747, "maximum": 0.774},
                    "shared_minus_crossed": _snapshot(methods, effect=0.226),
                },
                "hust_physical_unit_influence": {
                    "method_comparison_count": 18,
                    "bearing_loo_sign_stable_count": 18,
                    "group_loo_sign_stable_count": 18,
                    "minimum_bearing_loo_effect": 0.1745457916203188,
                    "minimum_group_loo_effect": 0.11223443223443219,
                    "maximum_bearing_absolute_influence": 0.05148467432950199,
                    "maximum_group_absolute_influence": 0.1137960337153886,
                    "posthoc_sensitivity_not_confirmatory": True,
                },
            },
        },
    }
    path = root / "bearing_artifact_manifest.json"
    path.write_text(json.dumps(manifest, sort_keys=True) + "\n", encoding="utf-8")
    return path, sha256(path.read_bytes()).hexdigest()


def test_empirical_manuscript_renderer_is_deterministic_and_preserves_human_holds(
    tmp_path: Path,
) -> None:
    manifest, digest = _write_manifest(tmp_path, raw_rule=True)
    arguments = {
        "template_path": project_root() / "paper" / "BEARING_MANUSCRIPT.md",
        "artifact_manifest_path": manifest,
        "expected_manifest_sha256": digest,
    }

    first_text, first_report = render_empirical_final_manuscript(**arguments)
    second_text, second_report = render_empirical_final_manuscript(**arguments)

    assert first_text == second_text
    assert first_report == second_report
    assert MARKER_PREFIX not in first_text
    assert "Submission hold" not in first_text
    assert "Table 6" in first_text
    assert "Figure 3" in first_text
    assert "Supplementary Table S4" in first_text
    assert "The frozen sensitivity rule passed" in first_text
    assert "raw 1D CNN 0.250000 [0.150000, 0.350000]" in first_text
    assert "18/18 method-comparison cells" in first_text
    assert "0.174546 and 0.112234" in first_text
    assert first_report["raw_positive_interval_count"] == 3
    assert first_report["final_positive_interval_count"] == 39
    assert first_report["hust_influence_bearing_stable_count"] == 18
    assert first_report["hust_influence_group_stable_count"] == 18
    assert first_report["human_action_marker_count"] >= 3
    assert first_report["submission_ready"] is False


def test_empirical_manuscript_renderer_reports_a_failed_raw_rule_without_promotion(
    tmp_path: Path,
) -> None:
    manifest, digest = _write_manifest(tmp_path, raw_rule=False)

    rendered, report = render_empirical_final_manuscript(
        template_path=project_root() / "paper" / "BEARING_MANUSCRIPT.md",
        artifact_manifest_path=manifest,
        expected_manifest_sha256=digest,
    )

    assert "The frozen sensitivity rule did not pass" in rendered
    assert "does not support a uniform extension" in rendered
    assert "log-STFT CNN 0.250000 [-0.050000, 0.350000]" in rendered
    assert report["raw_positive_interval_count"] == 2
    assert report["final_positive_interval_count"] == 38
    assert report["raw_representation_sensitivity_rule_passed"] is False


def test_empirical_manuscript_renderer_rejects_a_missing_template_marker(
    tmp_path: Path,
) -> None:
    manifest, digest = _write_manifest(tmp_path, raw_rule=True)
    template = tmp_path / "template.md"
    source = (project_root() / "paper" / "BEARING_MANUSCRIPT.md").read_text(encoding="utf-8")
    template.write_text(
        source.replace(
            f"<!-- {MARKER_PREFIX}:RAW_RESULTS:START -->",
            "",
            1,
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="exactly one RAW_RESULTS marker pair"):
        render_empirical_final_manuscript(
            template_path=template,
            artifact_manifest_path=manifest,
            expected_manifest_sha256=digest,
        )


def _write_rendered_package(
    root: Path,
) -> tuple[Path, Path, Path, str, str, str]:
    manifest, manifest_digest = _write_manifest(root, raw_rule=True)
    template = project_root() / "paper" / "BEARING_MANUSCRIPT.md"
    rendered, report = render_empirical_final_manuscript(
        template_path=template,
        artifact_manifest_path=manifest,
        expected_manifest_sha256=manifest_digest,
    )
    manuscript = root / "BEARING_MANUSCRIPT_EMPIRICAL_FINAL.md"
    report_path = root / "render_report.json"
    manuscript.write_text(rendered, encoding="utf-8")
    report_path.write_text(json.dumps(report, sort_keys=True) + "\n", encoding="utf-8")
    return (
        manuscript,
        report_path,
        manifest,
        sha256(manuscript.read_bytes()).hexdigest(),
        sha256(report_path.read_bytes()).hexdigest(),
        manifest_digest,
    )


def test_empirical_manuscript_independent_validator_passes_locked_package(
    tmp_path: Path,
) -> None:
    manuscript, report, manifest, manuscript_sha, report_sha, manifest_sha = (
        _write_rendered_package(tmp_path)
    )
    template = project_root() / "paper" / "BEARING_MANUSCRIPT.md"

    result = validate_empirical_final_manuscript(
        manuscript_path=manuscript,
        expected_manuscript_sha256=manuscript_sha,
        report_path=report,
        expected_report_sha256=report_sha,
        template_path=template,
        expected_template_sha256=sha256(template.read_bytes()).hexdigest(),
        artifact_manifest_path=manifest,
        expected_artifact_manifest_sha256=manifest_sha,
    )

    assert result["status"] == "passed_independent_empirical_manuscript_validation"
    assert result["required_artifact_callout_count"] == 15
    assert result["hust_influence_bearing_stable_count"] == 18
    assert result["hust_influence_group_stable_count"] == 18
    assert result["refit_performed"] is False
    assert result["submission_ready"] is False


def test_empirical_manuscript_validator_rejects_a_hash_consistent_raw_number_tamper(
    tmp_path: Path,
) -> None:
    manuscript, report, manifest, _, _, manifest_sha = _write_rendered_package(tmp_path)
    template = project_root() / "paper" / "BEARING_MANUSCRIPT.md"
    manuscript.write_text(
        manuscript.read_text(encoding="utf-8").replace(
            "raw 1D CNN 0.250000",
            "raw 1D CNN 0.260000",
            1,
        ),
        encoding="utf-8",
    )
    manuscript_sha = sha256(manuscript.read_bytes()).hexdigest()
    report_value = json.loads(report.read_text(encoding="utf-8"))
    report_value["rendered_sha256"] = manuscript_sha
    report.write_text(json.dumps(report_value, sort_keys=True) + "\n", encoding="utf-8")

    with pytest.raises(ValueError, match="raw result changed for cnn1d"):
        validate_empirical_final_manuscript(
            manuscript_path=manuscript,
            expected_manuscript_sha256=manuscript_sha,
            report_path=report,
            expected_report_sha256=sha256(report.read_bytes()).hexdigest(),
            template_path=template,
            expected_template_sha256=sha256(template.read_bytes()).hexdigest(),
            artifact_manifest_path=manifest,
            expected_artifact_manifest_sha256=manifest_sha,
        )


def test_empirical_manuscript_validator_rejects_a_hash_consistent_influence_tamper(
    tmp_path: Path,
) -> None:
    manuscript, report, manifest, _, _, manifest_sha = _write_rendered_package(tmp_path)
    template = project_root() / "paper" / "BEARING_MANUSCRIPT.md"
    manuscript.write_text(
        manuscript.read_text(encoding="utf-8").replace(
            "0.174546 and 0.112234",
            "0.174547 and 0.112234",
            1,
        ),
        encoding="utf-8",
    )
    manuscript_sha = sha256(manuscript.read_bytes()).hexdigest()
    report_value = json.loads(report.read_text(encoding="utf-8"))
    report_value["rendered_sha256"] = manuscript_sha
    report.write_text(json.dumps(report_value, sort_keys=True) + "\n", encoding="utf-8")

    with pytest.raises(ValueError, match="HUST influence result changed"):
        validate_empirical_final_manuscript(
            manuscript_path=manuscript,
            expected_manuscript_sha256=manuscript_sha,
            report_path=report,
            expected_report_sha256=sha256(report.read_bytes()).hexdigest(),
            template_path=template,
            expected_template_sha256=sha256(template.read_bytes()).hexdigest(),
            artifact_manifest_path=manifest,
            expected_artifact_manifest_sha256=manifest_sha,
        )
