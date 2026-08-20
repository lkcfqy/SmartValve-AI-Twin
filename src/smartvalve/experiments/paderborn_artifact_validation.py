"""Validate one-shot Paderborn artifacts against the sealed metadata-only manifest."""

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
from smartvalve.experiments.paderborn_expected_manifest import (
    KEY_SCHEMAS,
    MANIFEST_VERSION,
)

VALIDATION_VERSION = "paderborn-prospective-artifact-validation-0.1.0"
PROBABILITY_TOLERANCE = 2e-6
REPRESENTATION_TOLERANCE = 2e-6


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _artifact_path(
    directory: Path, metrics: dict[str, Any], artifact_name: str
) -> Path:
    record = metrics["artifacts"][artifact_name]
    path = (directory / str(record["path"])).resolve(strict=True)
    if directory != path and directory not in path.parents:
        raise ValueError(f"Paderborn artifact escapes output directory: {artifact_name}")
    if path.stat().st_size != int(record["bytes"]) or _sha256(path) != record["sha256"]:
        raise ValueError(f"Paderborn artifact hash/size mismatch: {artifact_name}")
    return path


def _key_record(
    value: pd.DataFrame | list[dict[str, Any]], name: str
) -> dict[str, Any]:
    columns = KEY_SCHEMAS[name]
    if isinstance(value, pd.DataFrame):
        missing = set(columns) - set(value)
        if missing:
            raise ValueError(f"Paderborn artifact is missing keys: {sorted(missing)}")
        rows = value.loc[:, list(columns)].itertuples(index=False, name=None)
    else:
        if any(set(columns) - set(record) for record in value):
            raise ValueError("Paderborn JSON artifact is missing a frozen key")
        rows = (tuple(record[column] for column in columns) for record in value)
    return canonical_key_record(rows, columns)


def _validate_numeric_predictions(
    predictions: pd.DataFrame,
    expected_dimensions: dict[str, int],
    *,
    outcomes_released: bool,
) -> dict[str, Any]:
    required = {
        "prediction",
        "confidence",
        "robust_class_support_distance",
    }
    missing = required - set(predictions)
    if missing:
        raise ValueError(f"Paderborn prediction diagnostics are missing: {sorted(missing)}")
    if outcomes_released and not {"truth", "correct"}.issubset(predictions.columns):
        raise ValueError("Paderborn primary predictions omit released outcomes")
    if not outcomes_released and {"truth", "correct"} & set(predictions):
        raise ValueError("Paderborn compound predictions expose a forced outcome field")
    maximum_probability_error = 0.0
    maximum_representation_error = 0.0
    maximum_confidence_error = 0.0
    for (method, _, _), group in predictions.groupby(
        ["method", "seed", "fold_id"], sort=True, observed=True
    ):
        probability_columns = sorted(
            column
            for column in group
            if column.startswith("probability_") and group[column].notna().all()
        )
        probabilities = group[probability_columns].to_numpy(dtype=float)
        if (
            len(probability_columns) != 3
            or not np.isfinite(probabilities).all()
            or np.any(probabilities < 0.0)
            or np.any(probabilities > 1.0)
        ):
            raise ValueError("Paderborn probabilities have an invalid schema")
        maximum_probability_error = max(
            maximum_probability_error,
            float(np.max(np.abs(probabilities.sum(axis=1) - 1.0))),
        )
        labels = [column.removeprefix("probability_") for column in probability_columns]
        prediction = np.asarray(
            [labels[index] for index in probabilities.argmax(axis=1)], dtype=str
        )
        if not np.array_equal(prediction, group["prediction"].to_numpy(dtype=str)):
            raise ValueError("Paderborn prediction differs from probability argmax")
        confidence_error = float(
            np.max(
                np.abs(
                    probabilities.max(axis=1)
                    - group["confidence"].to_numpy(dtype=float)
                )
            )
        )
        maximum_confidence_error = max(
            maximum_confidence_error, confidence_error
        )
        logit_columns = sorted(
            column
            for column in group
            if column.startswith("logit_") and group[column].notna().all()
        )
        if (
            len(logit_columns) != 3
            or [column.removeprefix("logit_") for column in logit_columns] != labels
            or not np.isfinite(group[logit_columns].to_numpy(dtype=float)).all()
        ):
            raise ValueError("Paderborn logits have an invalid schema")
        distances = group["robust_class_support_distance"].to_numpy(dtype=float)
        if not np.isfinite(distances).all() or np.any(distances < 0.0):
            raise ValueError("Paderborn class-support distances are invalid")
        if outcomes_released:
            correct = prediction == group["truth"].to_numpy(dtype=str)
            if not np.array_equal(correct, group["correct"].to_numpy(dtype=bool)):
                raise ValueError("Paderborn correctness flag changed")
        representation_columns = sorted(
            column
            for column in group
            if column.startswith("representation_") and group[column].notna().all()
        )
        if len(representation_columns) != expected_dimensions[str(method)]:
            raise ValueError(f"Paderborn representation dimension differs for {method}")
        representations = group[representation_columns].to_numpy(dtype=float)
        if not np.isfinite(representations).all():
            raise ValueError("Paderborn representations contain non-finite values")
        maximum_representation_error = max(
            maximum_representation_error,
            float(np.max(np.abs(np.linalg.norm(representations, axis=1) - 1.0))),
        )
    if maximum_probability_error > PROBABILITY_TOLERANCE:
        raise ValueError("Paderborn probabilities are not normalized")
    if maximum_confidence_error > PROBABILITY_TOLERANCE:
        raise ValueError("Paderborn confidence differs from maximum probability")
    if maximum_representation_error > REPRESENTATION_TOLERANCE:
        raise ValueError("Paderborn representations are not unit normalized")
    return {
        "maximum_probability_sum_error": maximum_probability_error,
        "maximum_confidence_error": maximum_confidence_error,
        "maximum_representation_norm_error": maximum_representation_error,
    }


def validate_paderborn_artifacts(
    *,
    paderborn_output_directory: Path,
    expected_manifest: Path,
    expected_manifest_sha256: str,
    output: Path,
) -> dict[str, Any]:
    directory = paderborn_output_directory.resolve(strict=True)
    expected_manifest = expected_manifest.resolve(strict=True)
    if _sha256(expected_manifest) != expected_manifest_sha256:
        raise ValueError("Paderborn expected-manifest SHA-256 mismatch")
    manifest = _read_json(expected_manifest)
    if manifest.get("manifest_version") != MANIFEST_VERSION:
        raise ValueError("Paderborn expected-manifest version changed")
    metrics_path = (directory / "metrics.json").resolve(strict=True)
    metrics = _read_json(metrics_path)
    if metrics.get("status") != "one_shot_paderborn_prospective_evaluation_complete":
        raise ValueError("Paderborn prospective evaluation did not complete")
    if metrics["input"].get("expected_manifest_sha256") != expected_manifest_sha256:
        raise ValueError("Paderborn metrics reference a different expected manifest")
    for field in (
        "protocol_document_sha256",
        "split_manifest_sha256",
        "model_fold_manifest_sha256",
    ):
        metrics_field = (
            "frozen_protocol_sha256"
            if field == "protocol_document_sha256"
            else field
        )
        if metrics["input"].get(metrics_field) != manifest["input"].get(field):
            raise ValueError(f"Paderborn metrics input drift: {field}")
    access = metrics.get("access_attestation", {})
    if (
        access.get("paderborn_model_outcomes_emitted_only_after_all_fits") is not True
        or access.get("configuration_reselection_performed") is not False
        or access.get("target_labels_used_for_fitting_selection_or_stopping") is not False
        or access.get("quarantine_rows_exposed_to_trainer") is not False
        or access.get("compound_forced_ground_truth_defined") is not False
        or access.get("compound_accuracy_computed") is not False
    ):
        raise ValueError("Paderborn evaluation access attestation changed")

    paths = {
        name: _artifact_path(directory, metrics, name)
        for name in (
            "predictions",
            "compound_predictions",
            "fold_metrics",
            "training_traces",
        )
    }
    predictions = pd.read_parquet(paths["predictions"])
    compound = pd.read_parquet(paths["compound_predictions"])
    fold_metrics = _read_json(paths["fold_metrics"])
    traces = _read_json(paths["training_traces"])
    if not isinstance(fold_metrics, list) or not isinstance(traces, list):
        raise ValueError("Paderborn JSON artifacts have an invalid type")
    values: dict[str, pd.DataFrame | list[dict[str, Any]]] = {
        "target_predictions": predictions,
        "compound_predictions": compound,
        "fold_metrics": fold_metrics,
        "training_models": traces,
    }
    observed = {
        name: _key_record(value, name) for name, value in values.items()
    }
    for name, record in observed.items():
        if record != manifest["expected_key_sets"][name]:
            raise ValueError(f"Paderborn artifact key set differs: {name}")
    recorded_counts = {
        "predictions": ("rows", len(predictions)),
        "compound_predictions": ("rows", len(compound)),
        "fold_metrics": ("folds", len(fold_metrics)),
        "training_traces": ("models", len(traces)),
    }
    for name, (field, count) in recorded_counts.items():
        if int(metrics["artifacts"][name][field]) != count:
            raise ValueError(f"Paderborn recorded count differs: {name}")
    if {"truth", "correct", "component", "damage_extent", "damage_origin"} & set(
        compound
    ):
        raise ValueError("Paderborn compound artifact exposes a forced outcome field")
    expected_dimensions = {
        method: int(configuration["representation_dim"])
        for method, configuration in metrics["configuration"][
            "method_configurations"
        ].items()
    }
    numeric = _validate_numeric_predictions(
        predictions, expected_dimensions, outcomes_released=True
    )
    compound_numeric = _validate_numeric_predictions(
        compound, expected_dimensions, outcomes_released=False
    )
    result = {
        "validation_version": VALIDATION_VERSION,
        "generated_at": datetime.now(UTC).isoformat(),
        "status": "passed_against_sealed_metadata_only_paderborn_manifest",
        "expected_manifest": {
            "path": str(expected_manifest),
            "sha256": expected_manifest_sha256,
        },
        "paderborn_metrics": {
            "path": str(metrics_path),
            "sha256": _sha256(metrics_path),
        },
        "artifact_hashes": {name: _sha256(path) for name, path in paths.items()},
        "observed_key_sets": observed,
        "closed_set_numeric_integrity": numeric,
        "compound_numeric_integrity": compound_numeric,
        "compound_forced_ground_truth_defined": False,
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
    parser.add_argument("--paderborn-output-directory", type=Path, required=True)
    parser.add_argument("--expected-manifest", type=Path, required=True)
    parser.add_argument("--expected-manifest-sha256", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = validate_paderborn_artifacts(
        paderborn_output_directory=args.paderborn_output_directory,
        expected_manifest=args.expected_manifest,
        expected_manifest_sha256=args.expected_manifest_sha256,
        output=args.output,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
