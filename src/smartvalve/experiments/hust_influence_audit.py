"""Post-hoc physical-unit influence audit for the validated HUST protocol effects."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from sklearn.metrics import f1_score

AUDIT_VERSION = "smartvalve-hust-physical-unit-influence-audit-0.1.0"
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
PRIMARY_PROTOCOLS = (
    "recording_random",
    "load_holdout",
    "matched_specification_holdout",
    "crossed_holdout",
)
CONTROL_PROTOCOLS = ("size_matched_shared_access", "crossed_holdout")
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
PREDICTION_COLUMNS = (
    "protocol",
    "method",
    "filename",
    "bearing_code",
    "specification_group",
    "load_w",
    "truth",
    "probability_healthy",
    "probability_outer",
    "probability_inner",
    "prediction",
)


def sha256_file(path: Path) -> str:
    """Return a streaming SHA-256 digest."""

    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(4 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _load_locked_json(path: Path, expected_sha256: str, role: str) -> dict[str, Any]:
    resolved = path.resolve(strict=True)
    observed = sha256_file(resolved)
    if observed != expected_sha256:
        raise ValueError(f"{role} SHA-256 changed: expected {expected_sha256}, observed {observed}")
    value = json.loads(resolved.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{role} must be a JSON object")
    return value


def _load_validated_predictions(
    *,
    summary_path: Path,
    summary_sha256: str,
    expected_summary_status: str,
    prediction_filename: str,
    validation_path: Path,
    validation_sha256: str,
    role: str,
) -> tuple[pd.DataFrame, dict[str, str]]:
    summary_path = summary_path.resolve(strict=True)
    summary = _load_locked_json(summary_path, summary_sha256, f"{role} summary")
    if summary.get("status") != expected_summary_status:
        raise ValueError(f"{role} summary status changed")
    output_hashes = summary.get("output_sha256")
    if not isinstance(output_hashes, dict):
        raise ValueError(f"{role} summary has no output hash map")
    expected_prediction_hash = str(output_hashes.get(prediction_filename, ""))
    prediction_path = summary_path.parent / prediction_filename
    if sha256_file(prediction_path) != expected_prediction_hash:
        raise ValueError(f"{role} recording predictions changed")

    validation = _load_locked_json(validation_path, validation_sha256, f"{role} validation")
    if validation.get("status") != "passed_independent_no_refit_recomputation":
        raise ValueError(f"{role} did not pass independent validation")
    if validation.get("refit_performed") is not False:
        raise ValueError(f"{role} validation must declare refit_performed=false")
    validation_inputs = validation.get("input_sha256")
    if not isinstance(validation_inputs, dict):
        raise ValueError(f"{role} validation has no input hash map")
    if validation_inputs.get("outcome_summary") != summary_sha256:
        raise ValueError(f"{role} validation does not lock the supplied outcome summary")

    frame = pd.read_parquet(prediction_path)
    return frame, {
        "summary": summary_sha256,
        "validation": validation_sha256,
        "recording_predictions": expected_prediction_hash,
    }


def _require_prediction_topology(primary: pd.DataFrame, control: pd.DataFrame) -> None:
    for role, frame, protocols, expected_rows in (
        ("primary", primary, PRIMARY_PROTOCOLS, 1620),
        ("control", control, CONTROL_PROTOCOLS, 810),
    ):
        missing = set(PREDICTION_COLUMNS).difference(frame.columns)
        if missing:
            raise ValueError(f"{role} predictions are missing columns: {sorted(missing)}")
        if len(frame) != expected_rows:
            raise ValueError(f"{role} prediction row count changed")
        if set(frame["protocol"].astype(str)) != set(protocols):
            raise ValueError(f"{role} protocol axis changed")
        if set(frame["method"].astype(str)) != set(METHODS):
            raise ValueError(f"{role} method axis changed")
        if frame.duplicated(["protocol", "method", "filename"]).any():
            raise ValueError(f"{role} prediction keys are duplicated")
        counts = frame.groupby(["protocol", "method"], observed=True).size()
        if len(counts) != len(protocols) * len(METHODS) or not counts.eq(45).all():
            raise ValueError(f"{role} protocol/method recording topology changed")
        probabilities = frame[
            ["probability_healthy", "probability_outer", "probability_inner"]
        ].to_numpy(dtype=float)
        if not np.isfinite(probabilities).all() or not np.allclose(
            probabilities.sum(axis=1), 1.0, atol=2e-6, rtol=0.0
        ):
            raise ValueError(f"{role} probabilities are invalid")

    metadata = primary[
        ["filename", "bearing_code", "specification_group", "load_w", "truth"]
    ].drop_duplicates()
    if len(metadata) != 45 or metadata["filename"].nunique() != 45:
        raise ValueError("primary recording metadata topology changed")
    if set(metadata["truth"].astype(str)) != set(CLASSES):
        raise ValueError("HUST truth axis changed")
    if metadata["bearing_code"].nunique() != 15:
        raise ValueError("HUST physical-bearing count changed")
    if set(metadata["specification_group"].astype(int)) != {4, 5, 6, 7, 8}:
        raise ValueError("HUST matched-specification axis changed")
    bearing_cells = metadata.groupby("bearing_code", observed=True).agg(
        recordings=("filename", "size"),
        loads=("load_w", "nunique"),
        truths=("truth", "nunique"),
        groups=("specification_group", "nunique"),
    )
    if not (
        bearing_cells["recordings"].eq(3).all()
        and bearing_cells["loads"].eq(3).all()
        and bearing_cells["truths"].eq(1).all()
        and bearing_cells["groups"].eq(1).all()
    ):
        raise ValueError("HUST physical-bearing hierarchy changed")
    group_cells = metadata.groupby(["specification_group", "truth"], observed=True)[
        "bearing_code"
    ].nunique()
    if len(group_cells) != 15 or not group_cells.eq(1).all():
        raise ValueError("matched-specification groups no longer contain one bearing per class")

    control_metadata = control[
        ["filename", "bearing_code", "specification_group", "load_w", "truth"]
    ].drop_duplicates()
    left = metadata.sort_values("filename").reset_index(drop=True)
    right = control_metadata.sort_values("filename").reset_index(drop=True)
    if not left.equals(right):
        raise ValueError("primary and control recording metadata differ")

    comparison_columns = [
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
    primary_crossed = (
        primary.loc[primary["protocol"] == "crossed_holdout", comparison_columns]
        .sort_values(["method", "filename"])
        .reset_index(drop=True)
    )
    control_crossed = (
        control.loc[control["protocol"] == "crossed_holdout", comparison_columns]
        .sort_values(["method", "filename"])
        .reset_index(drop=True)
    )
    if not primary_crossed.equals(control_crossed):
        raise ValueError(
            "control crossed predictions differ from the validated primary predictions"
        )


def _macro_f1(frame: pd.DataFrame) -> float:
    return float(
        f1_score(
            frame["truth"].astype(str),
            frame["prediction"].astype(str),
            labels=list(CLASSES),
            average="macro",
            zero_division=0,
        )
    )


def compute_influence_tables(
    primary: pd.DataFrame,
    control: pd.DataFrame,
) -> dict[str, pd.DataFrame]:
    """Recompute full and deletion effects without fitting or selecting a model."""

    _require_prediction_topology(primary, control)
    sources = {"primary": primary, "control": control}
    full_rows: list[dict[str, Any]] = []
    bearing_rows: list[dict[str, Any]] = []
    group_rows: list[dict[str, Any]] = []
    summary_rows: list[dict[str, Any]] = []

    for comparison, accessible_protocol, reference_protocol, source_name in COMPARISONS:
        source = sources[source_name]
        for method in METHODS:
            method_rows = source.loc[source["method"] == method]
            accessible = method_rows.loc[method_rows["protocol"] == accessible_protocol]
            reference = method_rows.loc[method_rows["protocol"] == reference_protocol]
            full_effect = _macro_f1(accessible) - _macro_f1(reference)
            full_rows.append(
                {
                    "comparison": comparison,
                    "method": method,
                    "accessible_protocol": accessible_protocol,
                    "reference_protocol": reference_protocol,
                    "recording_count": 45,
                    "effect_macro_f1": full_effect,
                }
            )

            method_bearing_rows: list[dict[str, Any]] = []
            for bearing_code in sorted(accessible["bearing_code"].astype(str).unique()):
                accessible_subset = accessible.loc[accessible["bearing_code"] != bearing_code]
                reference_subset = reference.loc[reference["bearing_code"] != bearing_code]
                effect = _macro_f1(accessible_subset) - _macro_f1(reference_subset)
                row = {
                    "comparison": comparison,
                    "method": method,
                    "omitted_bearing_code": bearing_code,
                    "omitted_truth": str(
                        accessible.loc[
                            accessible["bearing_code"] == bearing_code, "truth"
                        ].iloc[0]
                    ),
                    "remaining_recording_count": 42,
                    "effect_macro_f1": effect,
                    "influence_from_full": effect - full_effect,
                }
                method_bearing_rows.append(row)
                bearing_rows.append(row)

            method_group_rows: list[dict[str, Any]] = []
            for group in sorted(accessible["specification_group"].astype(int).unique()):
                accessible_subset = accessible.loc[accessible["specification_group"] != group]
                reference_subset = reference.loc[reference["specification_group"] != group]
                effect = _macro_f1(accessible_subset) - _macro_f1(reference_subset)
                row = {
                    "comparison": comparison,
                    "method": method,
                    "omitted_specification_group": int(group),
                    "remaining_recording_count": 36,
                    "effect_macro_f1": effect,
                    "influence_from_full": effect - full_effect,
                }
                method_group_rows.append(row)
                group_rows.append(row)

            bearing_effects = np.asarray(
                [float(row["effect_macro_f1"]) for row in method_bearing_rows]
            )
            bearing_influence = np.asarray(
                [float(row["influence_from_full"]) for row in method_bearing_rows]
            )
            group_effects = np.asarray(
                [float(row["effect_macro_f1"]) for row in method_group_rows]
            )
            group_influence = np.asarray(
                [float(row["influence_from_full"]) for row in method_group_rows]
            )
            summary_rows.append(
                {
                    "comparison": comparison,
                    "method": method,
                    "full_effect_macro_f1": full_effect,
                    "bearing_loo_minimum": float(bearing_effects.min()),
                    "bearing_loo_median": float(np.median(bearing_effects)),
                    "bearing_loo_maximum": float(bearing_effects.max()),
                    "bearing_loo_positive_count": int((bearing_effects > 0).sum()),
                    "bearing_loo_sign_stable": bool((bearing_effects > 0).all()),
                    "bearing_maximum_absolute_influence": float(
                        np.abs(bearing_influence).max()
                    ),
                    "group_loo_minimum": float(group_effects.min()),
                    "group_loo_median": float(np.median(group_effects)),
                    "group_loo_maximum": float(group_effects.max()),
                    "group_loo_positive_count": int((group_effects > 0).sum()),
                    "group_loo_sign_stable": bool((group_effects > 0).all()),
                    "group_maximum_absolute_influence": float(np.abs(group_influence).max()),
                }
            )

    return {
        "hust_influence_full_effects.csv": pd.DataFrame(full_rows),
        "hust_influence_leave_one_bearing.csv": pd.DataFrame(bearing_rows),
        "hust_influence_leave_one_group.csv": pd.DataFrame(group_rows),
        "hust_influence_summary.csv": pd.DataFrame(summary_rows),
    }


def run_hust_influence_audit(
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
    output_directory: Path,
) -> dict[str, Any]:
    """Run the frozen no-refit deletion audit and write deterministic artifacts."""

    plan_path = analysis_plan.resolve(strict=True)
    if sha256_file(plan_path) != analysis_plan_sha256:
        raise ValueError("analysis plan SHA-256 changed")
    primary, primary_hashes = _load_validated_predictions(
        summary_path=primary_summary,
        summary_sha256=primary_summary_sha256,
        expected_summary_status="one_shot_protocol_prospective_signal_unopened_before_seal",
        prediction_filename="recording_predictions.parquet",
        validation_path=primary_validation,
        validation_sha256=primary_validation_sha256,
        role="primary HUST",
    )
    control, control_hashes = _load_validated_predictions(
        summary_path=control_summary,
        summary_sha256=control_summary_sha256,
        expected_summary_status="outcome_blind_equal_source_volume_control",
        prediction_filename="combined_recording_predictions.parquet",
        validation_path=control_validation,
        validation_sha256=control_validation_sha256,
        role="equal-volume HUST",
    )
    tables = compute_influence_tables(primary, control)
    output_directory.mkdir(parents=True, exist_ok=True)
    output_hashes: dict[str, str] = {}
    for filename, frame in tables.items():
        path = output_directory / filename
        frame.to_csv(path, index=False, lineterminator="\n", float_format="%.12g")
        output_hashes[filename] = sha256_file(path)

    influence = tables["hust_influence_summary.csv"]
    findings = {
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
    summary = {
        "status": "posthoc_no_refit_physical_unit_influence_audit",
        "audit_version": AUDIT_VERSION,
        "evidence_role": "posthoc_sensitivity_not_confirmatory_inference",
        "refit_performed": False,
        "p_values_computed": False,
        "primary_endpoints_replaced": False,
        "design": {
            "comparisons": [item[0] for item in COMPARISONS],
            "methods": list(METHODS),
            "physical_bearings": 15,
            "matched_specification_groups": 5,
            "full_effect_rows": 18,
            "leave_one_bearing_rows": 270,
            "leave_one_group_rows": 90,
            "summary_rows": 18,
            "score": "pooled recording-level macro_f1",
        },
        "findings": findings,
        "input_sha256": {
            "analysis_plan": analysis_plan_sha256,
            "primary_summary": primary_hashes["summary"],
            "primary_validation": primary_hashes["validation"],
            "primary_recording_predictions": primary_hashes["recording_predictions"],
            "control_summary": control_hashes["summary"],
            "control_validation": control_hashes["validation"],
            "control_recording_predictions": control_hashes["recording_predictions"],
        },
        "output_sha256": output_hashes,
    }
    summary_path = output_directory / "hust_influence_audit_summary.json"
    summary_path.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    return summary
