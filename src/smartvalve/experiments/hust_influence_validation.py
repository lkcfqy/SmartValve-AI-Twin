"""Independent no-refit validation for the HUST physical-unit influence audit."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

VALIDATOR_VERSION = "smartvalve-hust-physical-unit-influence-validation-0.1.0"
METHODS = (
    "pirl_ratio",
    "erm",
    "coral",
    "vrex",
    "groupdro",
    "dann",
    "lisa",
    "matchdg",
    "ccdg",
)
CLASSES = ("healthy", "inner", "outer")
COMPARISONS = (
    (
        "recording_random_minus_crossed",
        "recording_random",
        "crossed_holdout",
        "primary",
    ),
    (
        "size_matched_shared_access_minus_crossed",
        "size_matched_shared_access",
        "crossed_holdout",
        "control",
    ),
)
OUTPUT_NAMES = (
    "hust_influence_full_effects.csv",
    "hust_influence_leave_one_bearing.csv",
    "hust_influence_leave_one_group.csv",
    "hust_influence_summary.csv",
)


def sha256_file(path: Path) -> str:
    """Return a streaming SHA-256 digest."""

    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(4 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _locked_json(path: Path, expected_sha256: str, role: str) -> dict[str, Any]:
    resolved = path.resolve(strict=True)
    if sha256_file(resolved) != expected_sha256:
        raise ValueError(f"{role} SHA-256 changed")
    value = json.loads(resolved.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{role} is not a JSON object")
    return value


def _validated_predictions(
    *,
    summary_path: Path,
    summary_sha256: str,
    summary_status: str,
    prediction_filename: str,
    validation_path: Path,
    validation_sha256: str,
    role: str,
) -> tuple[pd.DataFrame, str]:
    summary = _locked_json(summary_path, summary_sha256, f"{role} summary")
    if summary.get("status") != summary_status:
        raise ValueError(f"{role} summary status changed")
    output_hashes = summary.get("output_sha256")
    if not isinstance(output_hashes, dict) or prediction_filename not in output_hashes:
        raise ValueError(f"{role} summary does not lock predictions")
    prediction_hash = str(output_hashes[prediction_filename])
    prediction_path = summary_path.resolve(strict=True).parent / prediction_filename
    if sha256_file(prediction_path) != prediction_hash:
        raise ValueError(f"{role} predictions changed")
    validation = _locked_json(validation_path, validation_sha256, f"{role} validation")
    if (
        validation.get("status") != "passed_independent_no_refit_recomputation"
        or validation.get("refit_performed") is not False
    ):
        raise ValueError(f"{role} independent validation state changed")
    inputs = validation.get("input_sha256")
    if not isinstance(inputs, dict) or inputs.get("outcome_summary") != summary_sha256:
        raise ValueError(f"{role} validation does not lock the summary")
    return pd.read_parquet(prediction_path), prediction_hash


def _check_topology(primary: pd.DataFrame, control: pd.DataFrame) -> None:
    required = {
        "protocol",
        "method",
        "filename",
        "bearing_code",
        "specification_group",
        "load_w",
        "truth",
        "prediction",
    }
    for role, frame, expected_rows, expected_protocols in (
        (
            "primary",
            primary,
            1620,
            {
                "recording_random",
                "load_holdout",
                "matched_specification_holdout",
                "crossed_holdout",
            },
        ),
        ("control", control, 810, {"size_matched_shared_access", "crossed_holdout"}),
    ):
        if not required.issubset(frame.columns):
            raise ValueError(f"{role} predictions are missing required columns")
        if len(frame) != expected_rows:
            raise ValueError(f"{role} prediction count changed")
        if set(frame["protocol"].astype(str)) != expected_protocols:
            raise ValueError(f"{role} protocol axis changed")
        if set(frame["method"].astype(str)) != set(METHODS):
            raise ValueError(f"{role} method axis changed")
        if frame.duplicated(["protocol", "method", "filename"]).any():
            raise ValueError(f"{role} prediction keys are duplicated")
        counts = frame.groupby(["protocol", "method"], observed=True).size()
        if not counts.eq(45).all():
            raise ValueError(f"{role} protocol/method topology changed")

    metadata = primary[
        ["filename", "bearing_code", "specification_group", "load_w", "truth"]
    ].drop_duplicates()
    if (
        len(metadata) != 45
        or metadata["bearing_code"].nunique() != 15
        or metadata["specification_group"].nunique() != 5
        or set(metadata["truth"].astype(str)) != set(CLASSES)
    ):
        raise ValueError("HUST physical hierarchy changed")
    if not metadata.groupby("bearing_code", observed=True).size().eq(3).all():
        raise ValueError("HUST bearing recording counts changed")

    columns = [
        "method",
        "filename",
        "bearing_code",
        "specification_group",
        "load_w",
        "truth",
        "prediction",
        "probability_healthy",
        "probability_outer",
        "probability_inner",
    ]
    left = (
        primary.loc[primary["protocol"] == "crossed_holdout", columns]
        .sort_values(["method", "filename"])
        .reset_index(drop=True)
    )
    right = (
        control.loc[control["protocol"] == "crossed_holdout", columns]
        .sort_values(["method", "filename"])
        .reset_index(drop=True)
    )
    if not left.equals(right):
        raise ValueError("primary and control crossed predictions differ")


def _manual_macro_f1(frame: pd.DataFrame) -> float:
    truth = frame["truth"].astype(str).to_numpy()
    prediction = frame["prediction"].astype(str).to_numpy()
    class_scores: list[float] = []
    for label in CLASSES:
        true_positive = int(((truth == label) & (prediction == label)).sum())
        false_positive = int(((truth != label) & (prediction == label)).sum())
        false_negative = int(((truth == label) & (prediction != label)).sum())
        denominator = 2 * true_positive + false_positive + false_negative
        class_scores.append(0.0 if denominator == 0 else 2 * true_positive / denominator)
    return float(np.mean(class_scores))


def _recompute(primary: pd.DataFrame, control: pd.DataFrame) -> dict[str, pd.DataFrame]:
    _check_topology(primary, control)
    sources = {"primary": primary, "control": control}
    full: list[dict[str, Any]] = []
    bearing: list[dict[str, Any]] = []
    group: list[dict[str, Any]] = []
    summary: list[dict[str, Any]] = []
    for comparison, accessible_protocol, reference_protocol, source_name in COMPARISONS:
        source = sources[source_name]
        for method in METHODS:
            method_rows = source.loc[source["method"] == method]
            accessible = method_rows.loc[method_rows["protocol"] == accessible_protocol]
            reference = method_rows.loc[method_rows["protocol"] == reference_protocol]
            full_effect = _manual_macro_f1(accessible) - _manual_macro_f1(reference)
            full.append(
                {
                    "comparison": comparison,
                    "method": method,
                    "accessible_protocol": accessible_protocol,
                    "reference_protocol": reference_protocol,
                    "recording_count": 45,
                    "effect_macro_f1": full_effect,
                }
            )
            bearing_effects: list[float] = []
            bearing_influences: list[float] = []
            for code in sorted(accessible["bearing_code"].astype(str).unique()):
                effect = _manual_macro_f1(
                    accessible.loc[accessible["bearing_code"] != code]
                ) - _manual_macro_f1(reference.loc[reference["bearing_code"] != code])
                bearing_effects.append(effect)
                bearing_influences.append(effect - full_effect)
                bearing.append(
                    {
                        "comparison": comparison,
                        "method": method,
                        "omitted_bearing_code": code,
                        "omitted_truth": str(
                            accessible.loc[accessible["bearing_code"] == code, "truth"].iloc[0]
                        ),
                        "remaining_recording_count": 42,
                        "effect_macro_f1": effect,
                        "influence_from_full": effect - full_effect,
                    }
                )
            group_effects: list[float] = []
            group_influences: list[float] = []
            for specification in sorted(
                accessible["specification_group"].astype(int).unique()
            ):
                effect = _manual_macro_f1(
                    accessible.loc[accessible["specification_group"] != specification]
                ) - _manual_macro_f1(
                    reference.loc[reference["specification_group"] != specification]
                )
                group_effects.append(effect)
                group_influences.append(effect - full_effect)
                group.append(
                    {
                        "comparison": comparison,
                        "method": method,
                        "omitted_specification_group": int(specification),
                        "remaining_recording_count": 36,
                        "effect_macro_f1": effect,
                        "influence_from_full": effect - full_effect,
                    }
                )
            bearing_values = np.asarray(bearing_effects)
            group_values = np.asarray(group_effects)
            summary.append(
                {
                    "comparison": comparison,
                    "method": method,
                    "full_effect_macro_f1": full_effect,
                    "bearing_loo_minimum": float(bearing_values.min()),
                    "bearing_loo_median": float(np.median(bearing_values)),
                    "bearing_loo_maximum": float(bearing_values.max()),
                    "bearing_loo_positive_count": int((bearing_values > 0).sum()),
                    "bearing_loo_sign_stable": bool((bearing_values > 0).all()),
                    "bearing_maximum_absolute_influence": float(
                        np.abs(bearing_influences).max()
                    ),
                    "group_loo_minimum": float(group_values.min()),
                    "group_loo_median": float(np.median(group_values)),
                    "group_loo_maximum": float(group_values.max()),
                    "group_loo_positive_count": int((group_values > 0).sum()),
                    "group_loo_sign_stable": bool((group_values > 0).all()),
                    "group_maximum_absolute_influence": float(
                        np.abs(group_influences).max()
                    ),
                }
            )
    return {
        "hust_influence_full_effects.csv": pd.DataFrame(full),
        "hust_influence_leave_one_bearing.csv": pd.DataFrame(bearing),
        "hust_influence_leave_one_group.csv": pd.DataFrame(group),
        "hust_influence_summary.csv": pd.DataFrame(summary),
    }


def _compare_frame(observed: pd.DataFrame, expected: pd.DataFrame, name: str) -> float:
    if list(observed.columns) != list(expected.columns) or len(observed) != len(expected):
        raise ValueError(f"{name} topology changed")
    maximum = 0.0
    for column in expected.columns:
        if pd.api.types.is_numeric_dtype(expected[column]) and not pd.api.types.is_bool_dtype(
            expected[column]
        ):
            difference = np.abs(
                observed[column].to_numpy(dtype=float) - expected[column].to_numpy(dtype=float)
            )
            if not np.isfinite(difference).all():
                raise ValueError(f"{name} contains non-finite numeric differences")
            column_maximum = float(difference.max(initial=0.0))
            maximum = max(maximum, column_maximum)
            if column_maximum > 1e-10:
                raise ValueError(f"{name} numeric content changed")
        elif observed[column].astype(str).tolist() != expected[column].astype(str).tolist():
            raise ValueError(f"{name} categorical content changed")
    return maximum


def validate_hust_influence_audit(
    *,
    primary_summary: Path,
    primary_summary_sha256: str,
    primary_validation: Path,
    primary_validation_sha256: str,
    control_summary: Path,
    control_summary_sha256: str,
    control_validation: Path,
    control_validation_sha256: str,
    analysis_plan: Path,
    analysis_plan_sha256: str,
    audit_summary: Path,
    audit_summary_sha256: str,
) -> dict[str, Any]:
    """Independently recompute every deletion effect without calling the producer."""

    if sha256_file(analysis_plan.resolve(strict=True)) != analysis_plan_sha256:
        raise ValueError("analysis plan SHA-256 changed")
    primary, primary_prediction_hash = _validated_predictions(
        summary_path=primary_summary,
        summary_sha256=primary_summary_sha256,
        summary_status="one_shot_protocol_prospective_signal_unopened_before_seal",
        prediction_filename="recording_predictions.parquet",
        validation_path=primary_validation,
        validation_sha256=primary_validation_sha256,
        role="primary HUST",
    )
    control, control_prediction_hash = _validated_predictions(
        summary_path=control_summary,
        summary_sha256=control_summary_sha256,
        summary_status="outcome_blind_equal_source_volume_control",
        prediction_filename="combined_recording_predictions.parquet",
        validation_path=control_validation,
        validation_sha256=control_validation_sha256,
        role="equal-volume HUST",
    )
    summary = _locked_json(audit_summary, audit_summary_sha256, "influence audit summary")
    if summary.get("status") != "posthoc_no_refit_physical_unit_influence_audit":
        raise ValueError("influence audit status changed")
    if (
        summary.get("refit_performed") is not False
        or summary.get("p_values_computed") is not False
        or summary.get("primary_endpoints_replaced") is not False
    ):
        raise ValueError("influence audit scope declarations changed")
    expected_inputs = {
        "analysis_plan": analysis_plan_sha256,
        "primary_summary": primary_summary_sha256,
        "primary_validation": primary_validation_sha256,
        "primary_recording_predictions": primary_prediction_hash,
        "control_summary": control_summary_sha256,
        "control_validation": control_validation_sha256,
        "control_recording_predictions": control_prediction_hash,
    }
    if summary.get("input_sha256") != expected_inputs:
        raise ValueError("influence audit input hash map changed")
    output_hashes = summary.get("output_sha256")
    if not isinstance(output_hashes, dict) or set(output_hashes) != set(OUTPUT_NAMES):
        raise ValueError("influence audit output hash map changed")
    output_directory = audit_summary.resolve(strict=True).parent
    observed_tables: dict[str, pd.DataFrame] = {}
    for name in OUTPUT_NAMES:
        path = output_directory / name
        if sha256_file(path) != output_hashes[name]:
            raise ValueError(f"influence audit output SHA-256 changed: {name}")
        observed_tables[name] = pd.read_csv(path)

    expected_tables = _recompute(primary, control)
    differences = {
        name: _compare_frame(observed_tables[name], expected_tables[name], name)
        for name in OUTPUT_NAMES
    }
    influence = expected_tables["hust_influence_summary.csv"]
    expected_findings = {
        "method_comparison_count": int(len(influence)),
        "bearing_loo_sign_stable_count": int(influence["bearing_loo_sign_stable"].sum()),
        "group_loo_sign_stable_count": int(influence["group_loo_sign_stable"].sum()),
        "minimum_bearing_loo_effect": float(influence["bearing_loo_minimum"].min()),
        "minimum_group_loo_effect": float(influence["group_loo_minimum"].min()),
        "maximum_bearing_absolute_influence": float(
            influence["bearing_maximum_absolute_influence"].max()
        ),
        "maximum_group_absolute_influence": float(
            influence["group_maximum_absolute_influence"].max()
        ),
    }
    observed_findings = summary.get("findings")
    if not isinstance(observed_findings, dict):
        raise ValueError("influence audit findings are absent")
    for name, expected in expected_findings.items():
        observed = observed_findings.get(name)
        if isinstance(expected, float):
            if observed is None or abs(float(observed) - expected) > 1e-12:
                raise ValueError(f"influence audit finding changed: {name}")
        elif observed != expected:
            raise ValueError(f"influence audit finding changed: {name}")

    return {
        "status": "passed_independent_no_refit_hust_physical_unit_influence_validation",
        "validator_version": VALIDATOR_VERSION,
        "audit_summary_sha256": audit_summary_sha256,
        "refit_performed": False,
        "confirmatory_analysis": False,
        "p_values_computed": False,
        "validated_counts": {
            "method_comparisons": 18,
            "leave_one_bearing_rows": 270,
            "leave_one_group_rows": 90,
            "physical_bearings": 15,
            "matched_specification_groups": 5,
        },
        "maximum_absolute_numeric_difference": differences,
        "findings": expected_findings,
    }
