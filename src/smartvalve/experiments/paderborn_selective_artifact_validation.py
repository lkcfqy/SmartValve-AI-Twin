"""Validate sealed Paderborn selective artifacts against the frozen key manifest."""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from smartvalve.experiments.dg_expected_manifest import canonical_key_record
from smartvalve.experiments.paderborn_selective_expected_manifest import (
    KEY_SCHEMAS,
    MANIFEST_VERSION,
)
from smartvalve.experiments.selective_evaluation import (
    ENSEMBLE_SCORE_COLUMNS,
    INDIVIDUAL_SCORE_COLUMNS,
)
from smartvalve.experiments.selective_scores import (
    energy_uncertainty,
    ensemble_jensen_shannon,
    maximum_softmax_uncertainty,
    negative_max_logit,
    normalized_predictive_entropy,
    pnorm_normalized_max_logit,
)

VALIDATION_VERSION = "paderborn-selective-artifact-validation-0.1.0"
VALIDATION_STATUS = "passed_against_sealed_paderborn_selective_manifest"
EVALUATION_STATUS = "sealed_paderborn_source_oof_selective_evaluation_complete"
PROBABILITY_TOLERANCE = 2e-6
OUTCOME_FIELDS = {
    "truth",
    "correct",
    "component",
    "damage_extent",
    "damage_origin",
    "accuracy",
    "selective_risk",
    "accepted_errors",
    "error_detection_recall",
    "correct_rejection_rate",
}
ARTIFACT_KEY_SETS = {
    "source_oof_predictions": "source_oof_predictions",
    "target_predictions": "target_predictions",
    "compound_predictions": "compound_predictions",
    "source_oof_ensemble_predictions": "source_oof_ensemble_predictions",
    "target_ensemble_predictions": "target_ensemble_predictions",
    "compound_ensemble_predictions": "compound_ensemble_predictions",
    "policies": "policies",
    "beta_selections": "beta_selections",
    "policy_metrics": "policy_metrics",
    "ranking_metrics": "ranking_metrics",
    "selection_decisions": "selection_decisions",
    "compound_decisions": "compound_decisions",
    "compound_policy_metrics": "compound_policy_metrics",
    "training_traces": "training_models",
}
PARQUET_ARTIFACTS = {
    "source_oof_predictions",
    "target_predictions",
    "compound_predictions",
    "source_oof_ensemble_predictions",
    "target_ensemble_predictions",
    "compound_ensemble_predictions",
    "selection_decisions",
    "compound_decisions",
}


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _artifact_path(directory: Path, metrics: dict[str, Any], artifact_name: str) -> Path:
    record = metrics.get("artifacts", {}).get(artifact_name)
    if not isinstance(record, dict):
        raise ValueError(f"Paderborn selective metrics omit {artifact_name}")
    path = (directory / str(record.get("path", ""))).resolve(strict=True)
    if directory != path and directory not in path.parents:
        raise ValueError(f"Paderborn selective artifact escapes output directory: {artifact_name}")
    if path.stat().st_size != int(record.get("bytes", -1)):
        raise ValueError(f"Paderborn selective artifact size differs: {artifact_name}")
    if _sha256(path) != record.get("sha256"):
        raise ValueError(f"Paderborn selective artifact hash differs: {artifact_name}")
    return path


def _key_record(value: pd.DataFrame | list[dict[str, Any]], name: str) -> dict[str, Any]:
    columns = KEY_SCHEMAS[name]
    if isinstance(value, pd.DataFrame):
        missing = set(columns) - set(value)
        if missing:
            raise ValueError(f"Paderborn selective artifact is missing keys: {sorted(missing)}")
        rows = value.loc[:, list(columns)].itertuples(index=False, name=None)
    else:
        if any(set(columns) - set(record) for record in value):
            raise ValueError("Paderborn selective JSON artifact is missing a frozen key")
        rows = (tuple(record[column] for column in columns) for record in value)
    return canonical_key_record(rows, columns)


def _validate_recorded_count(
    record: dict[str, Any], observed_count: int, artifact_name: str
) -> None:
    count_fields = [key for key in record if key not in {"path", "bytes", "sha256"}]
    if len(count_fields) != 1 or int(record[count_fields[0]]) != observed_count:
        raise ValueError(f"Paderborn selective count differs: {artifact_name}")


def _active_columns(frame: pd.DataFrame, prefix: str) -> list[str]:
    columns = sorted(
        column for column in frame if column.startswith(prefix) and frame[column].notna().all()
    )
    if len(columns) != 3:
        raise ValueError(f"Paderborn selective group has {len(columns)} active {prefix}")
    return columns


def _validate_prediction_frame(
    frame: pd.DataFrame,
    *,
    ensemble: bool,
    compound: bool,
) -> float:
    required = {
        "dataset",
        "method",
        "seed",
        "fold_id",
        "row_index",
        "prediction",
        "confidence",
        "robust_class_support_distance",
    }
    score_columns = ENSEMBLE_SCORE_COLUMNS if ensemble else INDIVIDUAL_SCORE_COLUMNS
    required.update(score_columns.values())
    missing = required - set(frame)
    if missing:
        raise ValueError(f"Paderborn selective prediction fields are missing: {sorted(missing)}")
    if compound and OUTCOME_FIELDS & set(frame):
        raise ValueError("Paderborn compound predictions expose a forced outcome field")
    if not compound and not {"truth", "correct"}.issubset(frame.columns):
        raise ValueError("Paderborn primary predictions omit released outcomes")
    expected_dataset = "paderborn_compound" if compound else "paderborn"
    if set(frame["dataset"].astype(str)) != {expected_dataset}:
        raise ValueError("Paderborn selective prediction dataset identifier changed")
    score_values = frame.loc[:, list(score_columns.values())].to_numpy(dtype=float)
    distances = frame["robust_class_support_distance"].to_numpy(dtype=float)
    confidences = frame["confidence"].to_numpy(dtype=float)
    if (
        not np.isfinite(score_values).all()
        or not np.isfinite(distances).all()
        or np.any(distances < 0.0)
        or not np.isfinite(confidences).all()
        or np.any(confidences < 0.0)
        or np.any(confidences > 1.0)
    ):
        raise ValueError("Paderborn selective prediction diagnostics are invalid")
    maximum_error = 0.0
    for _, group in frame.groupby(
        ["dataset", "method", "seed", "fold_id"], sort=True, observed=True
    ):
        probability_columns = _active_columns(group, "probability_")
        probabilities = group.loc[:, probability_columns].to_numpy(dtype=float)
        if (
            not np.isfinite(probabilities).all()
            or np.any(probabilities < 0.0)
            or np.any(probabilities > 1.0)
        ):
            raise ValueError("Paderborn selective probabilities are invalid")
        maximum_error = max(
            maximum_error,
            float(np.max(np.abs(probabilities.sum(axis=1) - 1.0))),
        )
        labels = [column.removeprefix("probability_") for column in probability_columns]
        predicted = np.asarray([labels[index] for index in probabilities.argmax(axis=1)], dtype=str)
        if not np.array_equal(predicted, group["prediction"].to_numpy(dtype=str)):
            raise ValueError("Paderborn selective predictions differ from argmax")
        if (
            np.max(np.abs(probabilities.max(axis=1) - group["confidence"].to_numpy(dtype=float)))
            > PROBABILITY_TOLERANCE
        ):
            raise ValueError("Paderborn selective confidence differs from probability")
        if not compound:
            expected_correct = predicted == group["truth"].to_numpy(dtype=str)
            if not np.array_equal(expected_correct, group["correct"].to_numpy(dtype=bool)):
                raise ValueError("Paderborn selective correctness flag changed")
        expected_scores = {
            "score_msp": maximum_softmax_uncertainty(probabilities),
            "score_predictive_entropy": normalized_predictive_entropy(probabilities),
            "score_robust_class_support": group["robust_class_support_distance"].to_numpy(
                dtype=float
            ),
        }
        if not ensemble:
            logit_columns = _active_columns(group, "logit_")
            probability_labels = [
                column.removeprefix("probability_") for column in probability_columns
            ]
            logit_labels = [column.removeprefix("logit_") for column in logit_columns]
            if probability_labels != logit_labels:
                raise ValueError("Paderborn selective probability/logit labels differ")
            if not np.isfinite(group.loc[:, logit_columns].to_numpy(dtype=float)).all():
                raise ValueError("Paderborn selective logits are invalid")
            logits = group.loc[:, logit_columns].to_numpy(dtype=float)
            expected_scores.update(
                {
                    "score_energy_t1": energy_uncertainty(logits),
                    "score_negative_max_logit": negative_max_logit(logits),
                    "score_pnorm_max_logit_p2": pnorm_normalized_max_logit(logits, order=2.0),
                }
            )
        for column, expected_values in expected_scores.items():
            if not np.allclose(
                group[column].to_numpy(dtype=float),
                expected_values,
                rtol=0.0,
                atol=PROBABILITY_TOLERANCE,
            ):
                raise ValueError(f"Paderborn selective derived score changed: {column}")
    if maximum_error > PROBABILITY_TOLERANCE:
        raise ValueError("Paderborn selective probabilities are not normalized")
    return maximum_error


def _validate_decisions(frame: pd.DataFrame, *, compound: bool) -> None:
    required = {"score", "threshold", "accepted", "prediction"}
    missing = required - set(frame)
    if missing:
        raise ValueError(f"Paderborn selective decisions omit {sorted(missing)}")
    numeric = frame.loc[:, ["score", "threshold"]].to_numpy(dtype=float)
    if (
        not np.isfinite(numeric).all()
        or frame["accepted"].isna().any()
        or not pd.api.types.is_bool_dtype(frame["accepted"])
    ):
        raise ValueError("Paderborn selective decisions contain invalid values")
    if compound and OUTCOME_FIELDS & set(frame):
        raise ValueError("Paderborn compound decisions expose a forced outcome field")
    expected_dataset = "paderborn_compound" if compound else "paderborn"
    if set(frame["dataset"].astype(str)) != {expected_dataset}:
        raise ValueError("Paderborn selective decision dataset identifier changed")


def _validate_ensemble_against_members(
    members: pd.DataFrame, ensemble: pd.DataFrame
) -> dict[str, float]:
    """Reconstruct every fixed ensemble from its sealed individual predictions."""

    group_columns = ["dataset", "method", "fold_id"]
    identity_columns = [*group_columns, "row_index"]
    if members.duplicated([*identity_columns, "seed"]).any():
        raise ValueError("Paderborn selective ensemble members contain duplicate keys")
    if ensemble.duplicated(identity_columns).any() or not ensemble["seed"].eq(-1).all():
        raise ValueError("Paderborn selective ensemble identities are invalid")
    if "ensemble_size" not in ensemble:
        raise ValueError("Paderborn selective ensemble omits its member count")
    ensemble_groups = {
        key: group.sort_values("row_index", kind="stable")
        for key, group in ensemble.groupby(group_columns, sort=True, observed=True)
    }
    maximum_probability_difference = 0.0
    maximum_distance_difference = 0.0
    maximum_js_difference = 0.0
    for key, group in members.groupby(group_columns, sort=True, observed=True):
        if key not in ensemble_groups:
            raise ValueError("Paderborn selective ensemble has no matching member group")
        seeds = tuple(sorted(int(value) for value in group["seed"].unique()))
        if not seeds:
            raise ValueError("Paderborn selective ensemble has no members")
        probability_columns = _active_columns(group, "probability_")
        member_probabilities = []
        member_distances = []
        reference_rows = None
        for seed in seeds:
            member = group.loc[group["seed"] == seed].sort_values("row_index", kind="stable")
            if reference_rows is None:
                reference_rows = member[identity_columns].reset_index(drop=True)
            elif not member[identity_columns].reset_index(drop=True).equals(reference_rows):
                raise ValueError("Paderborn selective ensemble member rows do not align")
            member_probabilities.append(member.loc[:, probability_columns].to_numpy(dtype=float))
            member_distances.append(member["robust_class_support_distance"].to_numpy(dtype=float))
        stacked_probabilities = np.stack(member_probabilities)
        expected_probabilities = stacked_probabilities.mean(axis=0)
        expected_distances = np.stack(member_distances).mean(axis=0)
        observed = ensemble_groups.pop(key)
        if reference_rows is None or not observed[identity_columns].reset_index(drop=True).equals(
            reference_rows
        ):
            raise ValueError("Paderborn selective ensemble rows differ from members")
        if not observed["ensemble_size"].eq(len(seeds)).all():
            raise ValueError("Paderborn selective ensemble member count changed")
        observed_probability_columns = _active_columns(observed, "probability_")
        if observed_probability_columns != probability_columns:
            raise ValueError("Paderborn selective ensemble probability schema changed")
        maximum_probability_difference = max(
            maximum_probability_difference,
            float(
                np.max(
                    np.abs(
                        observed.loc[:, probability_columns].to_numpy(dtype=float)
                        - expected_probabilities
                    )
                )
            ),
        )
        maximum_distance_difference = max(
            maximum_distance_difference,
            float(
                np.max(
                    np.abs(
                        observed["robust_class_support_distance"].to_numpy(dtype=float)
                        - expected_distances
                    )
                )
            ),
        )
        expected_js = ensemble_jensen_shannon(stacked_probabilities)
        maximum_js_difference = max(
            maximum_js_difference,
            float(
                np.max(
                    np.abs(
                        observed["score_ensemble_jensen_shannon"].to_numpy(dtype=float)
                        - expected_js
                    )
                )
            ),
        )
    if ensemble_groups:
        raise ValueError("Paderborn selective ensemble has groups without members")
    if (
        max(
            maximum_probability_difference,
            maximum_distance_difference,
            maximum_js_difference,
        )
        > PROBABILITY_TOLERANCE
    ):
        raise ValueError("Paderborn selective ensemble reconstruction differs")
    return {
        "maximum_probability_difference": maximum_probability_difference,
        "maximum_support_distance_difference": maximum_distance_difference,
        "maximum_jensen_shannon_difference": maximum_js_difference,
    }


def _validate_source_only_records(
    loaded: dict[str, pd.DataFrame | list[dict[str, Any]]],
) -> None:
    for name in ("policies", "beta_selections"):
        records = loaded[name]
        if not isinstance(records, list) or any(
            str(record.get("dataset")) != "paderborn" for record in records
        ):
            raise ValueError("Paderborn thresholds/betas were not source-only records")
    metrics = loaded["compound_policy_metrics"]
    if not isinstance(metrics, list):
        raise ValueError("Paderborn compound policy metrics have an invalid type")
    for record in metrics:
        if str(record.get("dataset")) != "paderborn_compound":
            raise ValueError("Paderborn compound policy metric dataset changed")
        if record.get("accuracy_reported") is not False:
            raise ValueError("Paderborn compound policy metric reports accuracy")
        if OUTCOME_FIELDS & set(record):
            raise ValueError("Paderborn compound policy metric contains outcome diagnostics")


def _validated_base_references(
    selective_metrics: dict[str, Any],
) -> tuple[pd.DataFrame, pd.DataFrame]:
    inputs = selective_metrics.get("input", {})
    required = {
        "base_output_directory",
        "base_validation",
        "base_validation_sha256",
        "base_metrics_sha256",
    }
    missing = required - set(inputs)
    if missing:
        raise ValueError(f"Paderborn selective metrics omit base references: {sorted(missing)}")
    base_directory = Path(str(inputs["base_output_directory"])).resolve(strict=True)
    base_metrics_path = (base_directory / "metrics.json").resolve(strict=True)
    if base_directory != base_metrics_path.parent:
        raise ValueError("Paderborn base metrics escape their output directory")
    if _sha256(base_metrics_path) != inputs["base_metrics_sha256"]:
        raise ValueError("Paderborn base metrics changed before selective validation")
    base_metrics = _read_json(base_metrics_path)
    base_validation_path = Path(str(inputs["base_validation"])).resolve(strict=True)
    if _sha256(base_validation_path) != inputs["base_validation_sha256"]:
        raise ValueError("Paderborn base validation changed")
    base_validation = _read_json(base_validation_path)
    if (
        base_validation.get("status") != "passed_against_sealed_metadata_only_paderborn_manifest"
        or base_validation.get("paderborn_metrics", {}).get("sha256")
        != inputs["base_metrics_sha256"]
    ):
        raise ValueError("Paderborn selective inputs lack a valid base evaluation")
    frames = []
    for name in ("predictions", "compound_predictions"):
        record = base_metrics.get("artifacts", {}).get(name)
        if not isinstance(record, dict):
            raise ValueError(f"Paderborn base metrics omit {name}")
        path = (base_directory / str(record.get("path", ""))).resolve(strict=True)
        if base_directory != path and base_directory not in path.parents:
            raise ValueError("Paderborn base artifact escapes its output directory")
        if (
            path.stat().st_size != int(record.get("bytes", -1))
            or _sha256(path) != record.get("sha256")
            or base_validation.get("artifact_hashes", {}).get(name) != record.get("sha256")
        ):
            raise ValueError(f"Paderborn validated base artifact changed: {name}")
        frames.append(pd.read_parquet(path))
    return frames[0], frames[1]


def _validate_base_projection(reference: pd.DataFrame, observed: pd.DataFrame) -> dict[str, int]:
    """Require selective scoring to preserve every validated base field exactly."""

    methods = set(observed["method"].astype(str))
    reference = reference.loc[reference["method"].astype(str).isin(methods)].copy()
    keys = ["dataset", "method", "seed", "fold_id", "row_index"]
    reference = reference.sort_values(keys, kind="stable").reset_index(drop=True)
    observed = observed.sort_values(keys, kind="stable").reset_index(drop=True)
    if len(reference) != len(observed) or not reference[keys].equals(observed[keys]):
        raise ValueError("Paderborn selective rows differ from validated base predictions")
    missing = set(reference) - set(observed)
    if missing:
        raise ValueError(f"Paderborn selective projection drops base fields: {sorted(missing)}")
    for column in reference:
        expected = reference[column]
        actual = observed[column]
        if pd.api.types.is_numeric_dtype(expected):
            if not np.array_equal(expected.to_numpy(), actual.to_numpy(), equal_nan=True):
                raise ValueError(f"Paderborn selective projection changes base field {column}")
        elif not expected.astype("string").equals(actual.astype("string")):
            raise ValueError(f"Paderborn selective projection changes base field {column}")
    return {"rows": len(reference), "preserved_columns": len(reference.columns)}


def validate_paderborn_selective_artifacts(
    *,
    selective_output_directory: Path,
    expected_manifest: Path,
    expected_manifest_sha256: str,
    output: Path,
) -> dict[str, Any]:
    """Independently validate the complete Paderborn selective output package."""

    directory = selective_output_directory.resolve(strict=True)
    expected_manifest = expected_manifest.resolve(strict=True)
    manifest_hash = _sha256(expected_manifest)
    if manifest_hash != expected_manifest_sha256:
        raise ValueError("Paderborn selective expected-manifest SHA-256 mismatch")
    manifest = _read_json(expected_manifest)
    if manifest.get("manifest_version") != MANIFEST_VERSION:
        raise ValueError("Paderborn selective expected-manifest version changed")
    manifest_input = manifest.get("input", {})
    if (
        manifest_input.get("signal_features_used_to_define_topology") is not False
        or manifest_input.get("model_outcomes_inspected_before_manifest") is not False
    ):
        raise ValueError("Paderborn selective manifest violates the access boundary")
    metrics_path = (directory / "metrics.json").resolve(strict=True)
    metrics = _read_json(metrics_path)
    if metrics.get("status") != EVALUATION_STATUS:
        raise ValueError("Paderborn selective evaluation did not complete")
    if metrics.get("input", {}).get("expected_manifest_sha256") != manifest_hash:
        raise ValueError("Paderborn selective metrics reference another manifest")
    for field in ("protocol_document_sha256", "base_expected_manifest_sha256"):
        if metrics["input"].get(field) != manifest["input"].get(field):
            raise ValueError(f"Paderborn selective metrics input drift: {field}")
    access = metrics.get("access_attestation", {})
    if (
        access.get("all_thresholds_and_betas_selected_from_source_oof_only") is not True
        or access.get("target_coverage_used_for_threshold_selection") is not False
        or access.get("target_labels_used_for_threshold_selection") is not False
        or access.get("configuration_reselection_performed") is not False
        or access.get("compound_forced_ground_truth_defined") is not False
        or access.get("compound_accuracy_computed") is not False
    ):
        raise ValueError("Paderborn selective access attestation changed")

    loaded: dict[str, pd.DataFrame | list[dict[str, Any]]] = {}
    paths: dict[str, Path] = {}
    observed_key_sets = {}
    for artifact_name, key_set_name in ARTIFACT_KEY_SETS.items():
        path = _artifact_path(directory, metrics, artifact_name)
        value = pd.read_parquet(path) if artifact_name in PARQUET_ARTIFACTS else _read_json(path)
        if not isinstance(value, (pd.DataFrame, list)):
            raise ValueError(f"Paderborn selective artifact has invalid type: {artifact_name}")
        _validate_recorded_count(metrics["artifacts"][artifact_name], len(value), artifact_name)
        observed = _key_record(value, key_set_name)
        if observed != manifest["expected_key_sets"][key_set_name]:
            raise ValueError(f"Paderborn selective artifact key set differs: {artifact_name}")
        loaded[artifact_name] = value
        paths[artifact_name] = path
        observed_key_sets[key_set_name] = observed

    probability_errors = {}
    prediction_specs = {
        "source_oof_predictions": (False, False),
        "target_predictions": (False, False),
        "compound_predictions": (False, True),
        "source_oof_ensemble_predictions": (True, False),
        "target_ensemble_predictions": (True, False),
        "compound_ensemble_predictions": (True, True),
    }
    for name, (ensemble, compound) in prediction_specs.items():
        frame = loaded[name]
        if not isinstance(frame, pd.DataFrame):
            raise AssertionError("Paderborn selective prediction is not tabular")
        probability_errors[name] = _validate_prediction_frame(
            frame, ensemble=ensemble, compound=compound
        )
    for name, compound in (
        ("selection_decisions", False),
        ("compound_decisions", True),
    ):
        frame = loaded[name]
        if not isinstance(frame, pd.DataFrame):
            raise AssertionError("Paderborn selective decisions are not tabular")
        _validate_decisions(frame, compound=compound)
    _validate_source_only_records(loaded)
    base_target, base_compound = _validated_base_references(metrics)
    target_projection = loaded["target_predictions"]
    compound_projection = loaded["compound_predictions"]
    if not isinstance(target_projection, pd.DataFrame) or not isinstance(
        compound_projection, pd.DataFrame
    ):
        raise AssertionError("Paderborn selective base projections are not tabular")
    base_projection = {
        "target": _validate_base_projection(base_target, target_projection),
        "compound": _validate_base_projection(base_compound, compound_projection),
    }
    ensemble_reconstruction = {}
    for scope in ("source_oof", "target", "compound"):
        members = loaded[f"{scope}_predictions"]
        ensemble = loaded[f"{scope}_ensemble_predictions"]
        if not isinstance(members, pd.DataFrame) or not isinstance(ensemble, pd.DataFrame):
            raise AssertionError("Paderborn selective ensemble inputs are not tabular")
        ensemble_reconstruction[scope] = _validate_ensemble_against_members(members, ensemble)

    result = {
        "validation_version": VALIDATION_VERSION,
        "generated_at": datetime.now(UTC).isoformat(),
        "status": VALIDATION_STATUS,
        "expected_manifest": {
            "path": str(expected_manifest),
            "sha256": manifest_hash,
        },
        "selective_metrics": {
            "path": str(metrics_path),
            "sha256": _sha256(metrics_path),
        },
        "observed_key_sets": observed_key_sets,
        "artifact_hashes": {name: _sha256(path) for name, path in paths.items()},
        "maximum_probability_sum_error": max(probability_errors.values()),
        "probability_sum_errors": probability_errors,
        "ensemble_reconstruction": ensemble_reconstruction,
        "validated_base_projection": base_projection,
        "source_only_policy_selection": True,
        "compound_forced_ground_truth_defined": False,
        "compound_accuracy_computed": False,
    }
    output = output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_suffix(output.suffix + ".tmp")
    temporary.write_text(
        json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    temporary.replace(output)
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--selective-output-directory", type=Path, required=True)
    parser.add_argument("--expected-manifest", type=Path, required=True)
    parser.add_argument("--expected-manifest-sha256", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = validate_paderborn_selective_artifacts(
        selective_output_directory=args.selective_output_directory,
        expected_manifest=args.expected_manifest,
        expected_manifest_sha256=args.expected_manifest_sha256,
        output=args.output,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
