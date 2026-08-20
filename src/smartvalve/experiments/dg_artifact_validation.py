"""Validate completed neural-DG artifacts against the outcome-blind manifest."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from smartvalve.experiments.dg_expected_manifest import (
    KEY_SCHEMAS,
    MANIFEST_VERSION,
    canonical_key_record,
)
from smartvalve.experiments.dg_selection import (
    SELECTION_SEED,
    SELECTION_TOLERANCE,
    SELECTION_VERSION,
    select_common_candidate,
    select_outer_candidate,
)
from smartvalve.experiments.dg_training import BASELINE_METHODS, BaselineConfig

VALIDATION_VERSION = "neural-dg-artifact-validation-0.1.0"
HASH_PATTERN = re.compile(r"^[0-9a-f]{64}$")
PROBABILITY_TOLERANCE = 2e-6
REPRESENTATION_NORM_TOLERANCE = 2e-5
CANDIDATE_NUMERIC_COLUMNS = (
    "source_oof_macro_f1",
    "source_oof_worst_environment_macro_f1",
    "source_oof_multiclass_brier",
    "source_oof_nuisance_probability_response",
    "source_oof_fault_probability_response",
    "source_oof_probability_response_ratio",
)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n",
        encoding="utf-8",
    )


def _artifact_path(
    output_directory: Path,
    record: dict[str, Any],
    *,
    count_name: str,
    observed_count: int,
) -> Path:
    path = (output_directory / str(record.get("path", ""))).resolve()
    if path.parent != output_directory.resolve() or not path.is_file():
        raise ValueError("DG artifact path is missing or escapes its output directory")
    if path.stat().st_size != int(record.get("bytes", -1)):
        raise ValueError(f"DG artifact byte count changed: {path.name}")
    if _sha256(path) != record.get("sha256"):
        raise ValueError(f"DG artifact SHA-256 mismatch: {path.name}")
    if int(record.get(count_name, -1)) != observed_count:
        raise ValueError(f"DG artifact {count_name} count mismatch: {path.name}")
    return path


def _key_record_from_frame(frame: pd.DataFrame, name: str) -> dict[str, Any]:
    columns = KEY_SCHEMAS[name]
    missing = set(columns) - set(frame.columns)
    if missing:
        raise ValueError(f"DG {name} is missing key columns: {sorted(missing)}")
    return canonical_key_record(
        frame.loc[:, columns].itertuples(index=False, name=None), columns
    )


def _assert_expected_key_record(
    name: str,
    actual: dict[str, Any],
    manifest: dict[str, Any],
) -> None:
    expected = manifest["expected_key_sets"].get(name)
    if actual != expected:
        raise ValueError(
            f"DG {name} topology differs from the outcome-blind manifest: "
            f"expected={expected}, observed={actual}"
        )


def validate_candidate_values(frame: pd.DataFrame) -> dict[str, float]:
    missing = set(CANDIDATE_NUMERIC_COLUMNS) - set(frame.columns)
    if missing:
        raise ValueError(f"DG candidate metrics are missing: {sorted(missing)}")
    values = frame.loc[:, CANDIDATE_NUMERIC_COLUMNS].to_numpy(dtype=float)
    if not np.isfinite(values).all():
        raise ValueError("DG candidate metrics contain non-finite values")
    for column in (
        "source_oof_macro_f1",
        "source_oof_worst_environment_macro_f1",
    ):
        if not frame[column].between(0, 1).all():
            raise ValueError(f"DG candidate {column} is outside [0, 1]")
    if not frame["source_oof_multiclass_brier"].between(0, 2).all():
        raise ValueError("DG candidate Brier score is outside [0, 2]")
    nuisance = frame["source_oof_nuisance_probability_response"].to_numpy(
        dtype=float
    )
    fault = frame["source_oof_fault_probability_response"].to_numpy(dtype=float)
    ratio = frame["source_oof_probability_response_ratio"].to_numpy(dtype=float)
    if np.any(nuisance < 0) or np.any(fault <= 0):
        raise ValueError("DG candidate probability responses are invalid")
    maximum_ratio_error = float(np.max(np.abs(ratio - nuisance / fault)))
    if maximum_ratio_error > 1e-10:
        raise ValueError("DG candidate response ratio is internally inconsistent")
    return {"maximum_probability_response_ratio_error": maximum_ratio_error}


def _validate_history(trace: dict[str, Any], epochs: int) -> None:
    history = trace.get("history")
    expected_checkpoints = sorted({0, epochs - 1, *range(24, epochs, 25)})
    expected_epochs = [checkpoint + 1 for checkpoint in expected_checkpoints]
    if not isinstance(history, list) or [row.get("epoch") for row in history] != (
        expected_epochs
    ):
        raise ValueError("DG training history checkpoints are incomplete")
    numeric = []
    for row in history:
        numeric.extend(
            float(value)
            for key, value in row.items()
            if key != "epoch"
        )
    if not np.isfinite(np.asarray(numeric, dtype=float)).all():
        raise ValueError("DG training history contains non-finite values")


def _validate_trace(
    trace: dict[str, Any],
    *,
    expected_configuration: dict[str, Any],
) -> None:
    configuration = trace.get("configuration")
    if configuration != expected_configuration:
        raise ValueError("DG trace configuration differs from the frozen grid")
    model_hash = trace.get("model_state_sha256")
    if not isinstance(model_hash, str) or not HASH_PATTERN.fullmatch(model_hash):
        raise ValueError("DG trace has an invalid model-state hash")
    method = str(configuration["method"])
    auxiliary_hash = trace.get("auxiliary_state_sha256")
    if method == "dann":
        if not isinstance(auxiliary_hash, str) or not HASH_PATTERN.fullmatch(
            auxiliary_hash
        ):
            raise ValueError("DANN trace has no valid discriminator-state hash")
    elif auxiliary_hash is not None:
        raise ValueError("non-DANN trace unexpectedly has an auxiliary-state hash")
    _validate_history(trace, int(configuration["epochs"]))


def _validate_tuning_traces(
    traces: list[dict[str, Any]],
    manifest: dict[str, Any],
) -> dict[str, Any]:
    grid_lookup = {
        (method, row["candidate_id"]): row["configuration"]
        for method, rows in manifest["configuration"]["candidate_grids"].items()
        for row in rows
    }
    key_rows = []
    for trace in traces:
        configuration = trace.get("configuration")
        if not isinstance(configuration, dict):
            raise ValueError("DG tuning trace has no configuration")
        method = str(configuration.get("method"))
        identifier = str(trace.get("candidate_id"))
        expected = grid_lookup.get((method, identifier))
        if expected is None:
            raise ValueError("DG tuning trace is outside the frozen candidate grid")
        _validate_trace(trace, expected_configuration=expected)
        if float(trace.get("fit_seconds", 0)) <= 0:
            raise ValueError("DG tuning trace has a nonpositive fit time")
        key_rows.append(
            (
                method,
                str(trace["dataset"]),
                str(trace["outer_fold_id"]),
                identifier,
                str(trace["inner_split_id"]),
            )
        )
    record = canonical_key_record(key_rows, KEY_SCHEMAS["tuning_models"])
    _assert_expected_key_record("tuning_models", record, manifest)
    return record


def _validate_selections(
    candidate_metrics: pd.DataFrame,
    metrics: dict[str, Any],
    manifest: dict[str, Any],
) -> dict[str, str]:
    outer = metrics.get("outer_selections")
    common = metrics.get("common_selections")
    if not isinstance(outer, list) or not isinstance(common, dict):
        raise ValueError("DG metrics are missing selection decisions")
    outer_frame = pd.DataFrame(outer)
    outer_record = _key_record_from_frame(outer_frame, "outer_selections")
    _assert_expected_key_record("outer_selections", outer_record, manifest)
    outer_index = {
        (str(row["method"]), str(row["dataset"]), str(row["outer_fold_id"])): row
        for row in outer
    }
    for key, group in candidate_metrics.groupby(
        ["method", "dataset", "outer_fold_id"], sort=True, observed=True
    ):
        rows = group.to_dict(orient="records")
        recomputed = select_outer_candidate(rows, tolerance=SELECTION_TOLERANCE)
        recorded = outer_index[tuple(str(value) for value in key)]
        for field in (
            "selected_candidate_id",
            "eligible_candidates",
            "tolerance",
        ):
            if recorded[field] != recomputed[field]:
                raise ValueError(f"DG outer selection recomputation changed {field}")
        if not np.isclose(
            float(recorded["best_source_oof_worst_environment_macro_f1"]),
            float(recomputed["best_source_oof_worst_environment_macro_f1"]),
            atol=1e-12,
            rtol=0,
        ):
            raise ValueError("DG outer selection best score is inconsistent")

    selected: dict[str, str] = {}
    for method in BASELINE_METHODS:
        method_metrics = candidate_metrics.loc[
            candidate_metrics["method"] == method
        ].to_dict(orient="records")
        method_outer = [row for row in outer if row["method"] == method]
        recomputed = select_common_candidate(method_outer, method_metrics)
        recorded = common.get(method)
        if not isinstance(recorded, dict):
            raise ValueError(f"DG common selection is missing method {method}")
        for field in (
            "selected_candidate_id",
            "selection_counts",
            "modal_count",
            "modal_contenders",
        ):
            if recorded[field] != recomputed[field]:
                raise ValueError(f"DG common selection recomputation changed {field}")
        identifier = str(recorded["selected_candidate_id"])
        expected_configuration = next(
            row["configuration"]
            for row in manifest["configuration"]["candidate_grids"][method]
            if row["candidate_id"] == identifier
        )
        if recorded.get("configuration") != expected_configuration:
            raise ValueError("DG common configuration differs from its selected candidate")
        selected[method] = identifier
    if set(common) != set(BASELINE_METHODS):
        raise ValueError("DG common selections contain an unexpected method")
    return selected


def _validate_final_traces(
    traces: list[dict[str, Any]],
    metrics: dict[str, Any],
    manifest: dict[str, Any],
) -> dict[tuple[str, str, int, str], str]:
    common = metrics["common_selections"]
    key_rows = []
    state_hashes = {}
    for trace in traces:
        method = str(trace["method"])
        seed = int(trace["seed"])
        expected = replace(
            BaselineConfig(**common[method]["configuration"]), seed=seed
        )
        expected_configuration = expected.__dict__.copy()
        _validate_trace(trace, expected_configuration=expected_configuration)
        if trace.get("candidate_id") != common[method]["selected_candidate_id"]:
            raise ValueError("DG final trace does not use the common candidate")
        key = (
            str(trace["dataset"]),
            method,
            seed,
            str(trace["fold_id"]),
        )
        if key in state_hashes:
            raise ValueError("DG final traces contain a duplicate model key")
        state_hashes[key] = str(trace["model_state_sha256"])
        key_rows.append(key)
    record = canonical_key_record(key_rows, KEY_SCHEMAS["final_models"])
    _assert_expected_key_record("final_models", record, manifest)
    return state_hashes


def validate_prediction_values(
    predictions: pd.DataFrame,
    common_selections: dict[str, Any],
) -> dict[str, float]:
    required = {
        "dataset",
        "method",
        "seed",
        "fold_id",
        "row_index",
        "truth",
        "prediction",
        "correct",
        "confidence",
        "robust_class_support_distance",
        "risk_envelope_score_beta_0_25",
    }
    missing = required - set(predictions.columns)
    if missing:
        raise ValueError(f"DG predictions are missing columns: {sorted(missing)}")
    probability_columns = [
        column for column in predictions.columns if column.startswith("probability_")
    ]
    logit_columns = [
        column for column in predictions.columns if column.startswith("logit_")
    ]
    representation_columns = sorted(
        column for column in predictions.columns if column.startswith("representation_")
    )
    if not probability_columns or not logit_columns or not representation_columns:
        raise ValueError("DG predictions omit probability, logit or representation columns")
    max_probability_sum_error = 0.0
    max_softmax_error = 0.0
    max_representation_norm_error = 0.0
    for (dataset, method), group in predictions.groupby(
        ["dataset", "method"], sort=True, observed=True
    ):
        del dataset
        relevant_probability = [
            column for column in probability_columns if group[column].notna().all()
        ]
        if any(
            group[column].notna().any() and column not in relevant_probability
            for column in probability_columns
        ):
            raise ValueError("DG probability column is only partially populated")
        labels = [column.removeprefix("probability_") for column in relevant_probability]
        relevant_logits = [f"logit_{label}" for label in labels]
        if not relevant_probability or not set(relevant_logits).issubset(logit_columns):
            raise ValueError("DG probability and logit label schemas differ")
        probabilities = group.loc[:, relevant_probability].to_numpy(dtype=float)
        logits = group.loc[:, relevant_logits].to_numpy(dtype=float)
        if not np.isfinite(probabilities).all() or not np.isfinite(logits).all():
            raise ValueError("DG predictions contain non-finite probabilities or logits")
        if np.any(probabilities < 0) or np.any(probabilities > 1):
            raise ValueError("DG prediction probabilities are outside [0, 1]")
        probability_sum_error = float(
            np.max(np.abs(probabilities.sum(axis=1) - 1.0))
        )
        max_probability_sum_error = max(
            max_probability_sum_error, probability_sum_error
        )
        if probability_sum_error > PROBABILITY_TOLERANCE:
            raise ValueError("DG prediction probabilities are not normalized")
        shifted = logits - logits.max(axis=1, keepdims=True)
        softmax = np.exp(shifted)
        softmax /= softmax.sum(axis=1, keepdims=True)
        softmax_error = float(np.max(np.abs(softmax - probabilities)))
        max_softmax_error = max(max_softmax_error, softmax_error)
        if softmax_error > PROBABILITY_TOLERANCE:
            raise ValueError("DG stored logits do not reproduce stored probabilities")
        predicted_labels = np.asarray(labels, dtype=object)[probabilities.argmax(axis=1)]
        if not np.array_equal(predicted_labels, group["prediction"].to_numpy()):
            raise ValueError("DG stored prediction differs from probability argmax")
        if not np.array_equal(
            group["correct"].to_numpy(dtype=bool),
            group["prediction"].to_numpy() == group["truth"].to_numpy(),
        ):
            raise ValueError("DG stored correctness flag is inconsistent")
        if not np.allclose(
            group["confidence"].to_numpy(dtype=float),
            probabilities.max(axis=1),
            atol=PROBABILITY_TOLERANCE,
            rtol=0,
        ):
            raise ValueError("DG stored confidence differs from maximum probability")

        dimension = int(common_selections[str(method)]["configuration"]["representation_dim"])
        expected_representation = [f"representation_{index:02d}" for index in range(dimension)]
        if not set(expected_representation).issubset(representation_columns):
            raise ValueError("DG predictions omit selected representation dimensions")
        representation = group.loc[:, expected_representation].to_numpy(dtype=float)
        if not np.isfinite(representation).all():
            raise ValueError("DG selected representation contains non-finite values")
        unused = [
            column
            for column in representation_columns
            if column not in expected_representation
        ]
        if unused and group.loc[:, unused].notna().any().any():
            raise ValueError("DG method populates dimensions beyond its selected representation")
        norm_error = float(
            np.max(np.abs(np.linalg.norm(representation, axis=1) - 1.0))
        )
        max_representation_norm_error = max(
            max_representation_norm_error, norm_error
        )
        if norm_error > REPRESENTATION_NORM_TOLERANCE:
            raise ValueError("DG representations are not unit normalized")
    diagnostics = predictions.loc[
        :, ["robust_class_support_distance", "risk_envelope_score_beta_0_25"]
    ].to_numpy(dtype=float)
    if not np.isfinite(diagnostics).all() or np.any(diagnostics < 0):
        raise ValueError("DG target diagnostic scores are invalid")
    return {
        "maximum_probability_sum_error": max_probability_sum_error,
        "maximum_softmax_probability_error": max_softmax_error,
        "maximum_representation_norm_error": max_representation_norm_error,
    }


def _validate_prediction_topology(
    predictions: pd.DataFrame,
    manifest: dict[str, Any],
) -> dict[str, Any]:
    prediction_record = _key_record_from_frame(predictions, "target_predictions")
    _assert_expected_key_record("target_predictions", prediction_record, manifest)
    provenance_columns = KEY_SCHEMAS["target_provenance"]
    identity_columns = ("dataset", "fold_id", "row_index")
    grouped = predictions.groupby(list(identity_columns), sort=False, observed=True)
    if (
        grouped[list(provenance_columns[3:])].nunique(dropna=False) != 1
    ).any().any():
        raise ValueError("DG target provenance changes across paired methods or seeds")
    expected_repetitions = len(BASELINE_METHODS) * 5
    if not grouped.size().eq(expected_repetitions).all():
        raise ValueError("DG target rows do not contain every paired method and seed")
    provenance = predictions.loc[:, provenance_columns].drop_duplicates(
        list(identity_columns)
    )
    provenance_record = _key_record_from_frame(provenance, "target_provenance")
    _assert_expected_key_record("target_provenance", provenance_record, manifest)
    return {
        "prediction_keys": prediction_record,
        "physical_provenance": provenance_record,
    }


def validate_artifacts(
    dg_output_directory: Path,
    expected_manifest_path: Path,
    *,
    expected_manifest_sha256: str,
) -> dict[str, Any]:
    manifest_hash = _sha256(expected_manifest_path)
    if manifest_hash != expected_manifest_sha256:
        raise ValueError("DG expected-manifest hash differs from the audit lock")
    manifest = _read_json(expected_manifest_path)
    if manifest.get("manifest_version") != MANIFEST_VERSION:
        raise ValueError("DG expected manifest has an unexpected version")
    metrics_path = dg_output_directory / "metrics.json"
    metrics = _read_json(metrics_path)
    if metrics.get("selection_version") != SELECTION_VERSION:
        raise ValueError("DG metrics have an unexpected selection version")
    configuration = metrics.get("configuration", {})
    expected_configuration = manifest["configuration"]
    if configuration.get("methods") != expected_configuration["methods"]:
        raise ValueError("DG metrics change the frozen method order")
    if configuration.get("candidate_count") != expected_configuration["candidate_count"]:
        raise ValueError("DG metrics change the candidate count")
    if configuration.get("candidate_grids") != expected_configuration["candidate_grids"]:
        raise ValueError("DG metrics change the candidate grids")
    if configuration.get("selection_seed") != SELECTION_SEED:
        raise ValueError("DG metrics change the selection seed")
    if configuration.get("selection_tolerance") != SELECTION_TOLERANCE:
        raise ValueError("DG metrics change the selection tolerance")
    if configuration.get("final_seeds") != expected_configuration["seeds"]:
        raise ValueError("DG metrics change the final seeds")
    if configuration.get("epochs") != 300 or not str(
        configuration.get("device", "")
    ).startswith("cuda"):
        raise ValueError("DG metrics change the training budget or validated device")
    if metrics.get("input", {}).get("uci_feature_matrix_sha256") != manifest[
        "input"
    ]["uci_feature_matrix_sha256"]:
        raise ValueError("DG metrics use a different UCI feature matrix")
    if metrics.get("input", {}).get("paderborn_archive_contents_opened") is not False:
        raise ValueError("DG metrics do not preserve the Paderborn access seal")

    records = metrics.get("artifacts", {})
    candidate_record = records.get("candidate_metrics", {})
    tuning_record = records.get("tuning_traces", {})
    final_record = records.get("final_training_traces", {})
    prediction_record = records.get("predictions", {})
    candidate_path = dg_output_directory / str(candidate_record.get("path", ""))
    tuning_path = dg_output_directory / str(tuning_record.get("path", ""))
    final_path = dg_output_directory / str(final_record.get("path", ""))
    predictions_path = dg_output_directory / str(prediction_record.get("path", ""))
    candidate_metrics = pd.read_parquet(candidate_path)
    tuning_traces = _read_json(tuning_path)
    final_traces = _read_json(final_path)
    predictions = pd.read_parquet(predictions_path)
    _artifact_path(
        dg_output_directory,
        candidate_record,
        count_name="rows",
        observed_count=len(candidate_metrics),
    )
    _artifact_path(
        dg_output_directory,
        tuning_record,
        count_name="models",
        observed_count=len(tuning_traces),
    )
    _artifact_path(
        dg_output_directory,
        final_record,
        count_name="models",
        observed_count=len(final_traces),
    )
    _artifact_path(
        dg_output_directory,
        prediction_record,
        count_name="rows",
        observed_count=len(predictions),
    )

    candidate_key_record = _key_record_from_frame(
        candidate_metrics, "candidate_metrics"
    )
    _assert_expected_key_record("candidate_metrics", candidate_key_record, manifest)
    candidate_diagnostics = validate_candidate_values(candidate_metrics)
    tuning_key_record = _validate_tuning_traces(tuning_traces, manifest)
    selected = _validate_selections(candidate_metrics, metrics, manifest)
    state_hashes = _validate_final_traces(
        final_traces, metrics, manifest
    )
    topology = _validate_prediction_topology(predictions, manifest)
    prediction_diagnostics = validate_prediction_values(
        predictions, metrics["common_selections"]
    )
    return {
        "validation_version": VALIDATION_VERSION,
        "generated_at": datetime.now(UTC).isoformat(),
        "passed": True,
        "inputs": {
            "dg_metrics": str(metrics_path.resolve()),
            "dg_metrics_sha256": _sha256(metrics_path),
            "expected_manifest": str(expected_manifest_path.resolve()),
            "expected_manifest_sha256": manifest_hash,
        },
        "selected_candidates": selected,
        "counts": {
            "candidate_metrics": len(candidate_metrics),
            "tuning_models": len(tuning_traces),
            "outer_selections": len(metrics["outer_selections"]),
            "final_models": len(state_hashes),
            "target_predictions": len(predictions),
            "physical_target_rows": topology["physical_provenance"]["count"],
        },
        "key_records": {
            "candidate_metrics": candidate_key_record,
            "tuning_models": tuning_key_record,
            "final_models": canonical_key_record(
                state_hashes, KEY_SCHEMAS["final_models"]
            ),
            **topology,
        },
        "numeric_diagnostics": {
            **candidate_diagnostics,
            **prediction_diagnostics,
        },
        "artifact_hashes": {
            name: record["sha256"] for name, record in records.items()
        },
        "paderborn_archive_contents_opened": False,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dg-output-directory", type=Path, required=True)
    parser.add_argument("--expected-manifest", type=Path, required=True)
    parser.add_argument("--expected-manifest-sha256", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = validate_artifacts(
        args.dg_output_directory,
        args.expected_manifest,
        expected_manifest_sha256=args.expected_manifest_sha256,
    )
    _write_json(args.output, result)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
