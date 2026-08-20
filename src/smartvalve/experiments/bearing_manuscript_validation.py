"""Independently validate the empirically final bearing manuscript and render report."""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any

from smartvalve.experiments.bearing_manuscript import (
    FORBIDDEN_RENDERED_MARKERS,
    RAW_METHOD_LABELS,
    RAW_METHOD_ORDER,
)
from smartvalve.experiments.ress_submission import (
    REQUIRED_MANUSCRIPT_CALLOUTS,
    render_ress_headline_content,
)

VALIDATOR_VERSION = "smartvalve-bearing-manuscript-validator-0.2.0"


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(4 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _locked(path: Path, expected_sha256: str, role: str) -> Path:
    resolved = path.resolve(strict=True)
    observed = _sha256_file(resolved)
    if observed != expected_sha256:
        raise ValueError(
            f"{role} SHA-256 changed: expected {expected_sha256}, observed {observed}"
        )
    return resolved


def _json_object(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"JSON input is not an object: {path}")
    return value


def _sections(text: str) -> dict[str, str]:
    matches = list(re.finditer(r"(?m)^## ([^\n]+)\s*$", text))
    result = {}
    for index, match in enumerate(matches):
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        result[match.group(1).strip()] = text[match.end() : end].strip()
    return result


def _word_count(text: str) -> int:
    return len(re.findall(r"[A-Za-z0-9]+(?:[’'-][A-Za-z0-9]+)*", text))


def validate_empirical_final_manuscript(
    *,
    manuscript_path: Path,
    expected_manuscript_sha256: str,
    report_path: Path,
    expected_report_sha256: str,
    template_path: Path,
    expected_template_sha256: str,
    artifact_manifest_path: Path,
    expected_artifact_manifest_sha256: str,
) -> dict[str, Any]:
    """Recheck manuscript facts and hashes without calling the manuscript renderer."""

    manuscript_file = _locked(
        manuscript_path,
        expected_manuscript_sha256,
        "empirical manuscript",
    )
    report_file = _locked(report_path, expected_report_sha256, "manuscript render report")
    _locked(template_path, expected_template_sha256, "manuscript template")
    manifest_file = _locked(
        artifact_manifest_path,
        expected_artifact_manifest_sha256,
        "bearing artifact manifest",
    )
    manuscript = manuscript_file.read_text(encoding="utf-8")
    report = _json_object(report_file)
    headline = render_ress_headline_content(
        artifact_manifest_path=manifest_file,
        expected_manifest_sha256=expected_artifact_manifest_sha256,
    )

    if report.get("status") != "rendered_empirical_final_human_fields_pending":
        raise ValueError("manuscript report status is not empirical-final/human-pending")
    if report.get("submission_ready") is not False:
        raise ValueError("empirical manuscript report must retain submission_ready=false")
    if report.get("template_sha256") != expected_template_sha256:
        raise ValueError("manuscript report template hash does not match the locked template")
    if report.get("artifact_manifest_sha256") != expected_artifact_manifest_sha256:
        raise ValueError("manuscript report artifact-manifest hash does not match")
    if report.get("rendered_sha256") != expected_manuscript_sha256:
        raise ValueError("manuscript report rendered hash does not match")

    forbidden = [marker for marker in FORBIDDEN_RENDERED_MARKERS if marker in manuscript]
    if forbidden:
        raise ValueError(f"empirical manuscript retains forbidden markers: {forbidden}")
    sections = _sections(manuscript)
    abstract = " ".join(sections.get("Abstract", "").split())
    if abstract != " ".join(str(headline["abstract"]).split()):
        raise ValueError("empirical manuscript abstract differs from the locked headline values")

    snapshot = headline["raw_effect_snapshot"]
    for method in RAW_METHOD_ORDER:
        item = snapshot["by_method"][method]
        expected_text = (
            f"{RAW_METHOD_LABELS[method]} {float(item['effect']):.6f} "
            f"[{float(item['lower_95']):.6f}, {float(item['upper_95']):.6f}]"
        )
        if expected_text not in manuscript:
            raise ValueError(f"empirical manuscript raw result changed for {method}")

    raw_positive = int(headline["raw_positive_interval_count"])
    raw_rule = bool(headline["raw_representation_sensitivity_rule_passed"])
    total_positive = (
        int(headline["sensor_positive_interval_count"])
        + int(headline["hust_positive_interval_count"])
        + raw_positive
    )
    required_rule_phrase = (
        "The frozen sensitivity rule passed"
        if raw_rule
        else "The frozen sensitivity rule did not pass"
    )
    prohibited_rule_phrase = (
        "The frozen sensitivity rule did not pass"
        if raw_rule
        else "The frozen sensitivity rule passed"
    )
    if required_rule_phrase not in manuscript or prohibited_rule_phrase in manuscript:
        raise ValueError("empirical manuscript raw rule wording contradicts the manifest")
    if f"{total_positive}/39" not in manuscript:
        raise ValueError("empirical manuscript final contrast count changed")

    influence_count = int(headline["hust_influence_method_comparison_count"])
    influence_bearing_stable = int(headline["hust_influence_bearing_stable_count"])
    influence_group_stable = int(headline["hust_influence_group_stable_count"])
    influence_min_bearing = float(headline["hust_influence_minimum_bearing_loo_effect"])
    influence_min_group = float(headline["hust_influence_minimum_group_loo_effect"])
    influence_max_bearing = float(
        headline["hust_influence_maximum_bearing_absolute_change"]
    )
    influence_max_group = float(headline["hust_influence_maximum_group_absolute_change"])
    expected_influence_text = " ".join(
        (
            "A post-hoc no-refit HUST influence audit retained positive effects in",
            f"{influence_bearing_stable}/{influence_count} method-comparison cells under",
            "leave-one-bearing-out deletion and",
            f"{influence_group_stable}/{influence_count} under class-balanced",
            "leave-one-specification-group-out deletion. The minimum deleted-sample effects were",
            f"{influence_min_bearing:.6f} and {influence_min_group:.6f}, respectively; maximum",
            "absolute changes from the full-cohort effects were",
            f"{influence_max_bearing:.6f} and {influence_max_group:.6f}. Supplementary Table S4",
            "reports every cell. These deletion ranges are sensitivity diagnostics, not confidence",
            "intervals or independent replicates.",
        )
    )
    if expected_influence_text not in " ".join(manuscript.split()):
        raise ValueError("empirical manuscript HUST influence result changed")

    missing_callouts = [
        label
        for label in REQUIRED_MANUSCRIPT_CALLOUTS
        if re.search(rf"\b{re.escape(label)}\b", manuscript) is None
    ]
    if missing_callouts:
        raise ValueError(f"empirical manuscript lacks artifact callouts: {missing_callouts}")
    words = _word_count(manuscript)
    if report.get("word_count") != words:
        raise ValueError("manuscript report word count changed")
    if not 5_000 <= words <= 13_000:
        raise ValueError(f"empirical manuscript has {words} words")
    human_actions = manuscript.casefold().count("author action required")
    if human_actions < 3 or report.get("human_action_marker_count") != human_actions:
        raise ValueError("empirical manuscript human-owned disclosure holds changed")
    expected_report_values = {
        "raw_positive_interval_count": raw_positive,
        "raw_representation_sensitivity_rule_passed": raw_rule,
        "final_positive_interval_count": total_positive,
        "final_contrast_count": 39,
        "hust_influence_method_comparison_count": influence_count,
        "hust_influence_bearing_stable_count": influence_bearing_stable,
        "hust_influence_group_stable_count": influence_group_stable,
        "hust_influence_minimum_bearing_loo_effect": influence_min_bearing,
        "hust_influence_minimum_group_loo_effect": influence_min_group,
        "hust_influence_maximum_bearing_absolute_change": influence_max_bearing,
        "hust_influence_maximum_group_absolute_change": influence_max_group,
        "table_6_figure_3_and_supplementary_table_s4_cited": True,
    }
    for name, expected in expected_report_values.items():
        if report.get(name) != expected:
            raise ValueError(f"manuscript report decision changed: {name}")

    return {
        "status": "passed_independent_empirical_manuscript_validation",
        "validator_version": VALIDATOR_VERSION,
        "manuscript_sha256": expected_manuscript_sha256,
        "render_report_sha256": expected_report_sha256,
        "template_sha256": expected_template_sha256,
        "artifact_manifest_sha256": expected_artifact_manifest_sha256,
        "word_count": words,
        "raw_positive_interval_count": raw_positive,
        "raw_representation_sensitivity_rule_passed": raw_rule,
        "final_positive_interval_count": total_positive,
        "final_contrast_count": 39,
        "hust_influence_method_comparison_count": influence_count,
        "hust_influence_bearing_stable_count": influence_bearing_stable,
        "hust_influence_group_stable_count": influence_group_stable,
        "hust_influence_minimum_bearing_loo_effect": influence_min_bearing,
        "hust_influence_minimum_group_loo_effect": influence_min_group,
        "hust_influence_maximum_bearing_absolute_change": influence_max_bearing,
        "hust_influence_maximum_group_absolute_change": influence_max_group,
        "required_artifact_callout_count": len(REQUIRED_MANUSCRIPT_CALLOUTS),
        "human_action_marker_count": human_actions,
        "refit_performed": False,
        "submission_ready": False,
    }
