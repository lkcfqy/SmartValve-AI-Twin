"""Validate a selective-evaluation package against its outcome-blind key manifest."""

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
from smartvalve.experiments.selective_expected_manifest import (
    KEY_SCHEMAS,
    MANIFEST_VERSION,
)

VALIDATION_VERSION = "selective-artifact-validation-0.1.0"
PROBABILITY_TOLERANCE = 2e-6
ARTIFACT_KEY_SETS = {
    "source_oof_predictions": "source_oof_predictions",
    "target_predictions": "target_predictions",
    "source_oof_ensemble_predictions": "source_oof_ensemble_predictions",
    "target_ensemble_predictions": "target_ensemble_predictions",
    "selection_decisions": "selection_decisions",
    "policies": "policies",
    "beta_selections": "beta_selections",
    "policy_metrics": "policy_metrics",
    "ranking_metrics": "ranking_metrics",
    "training_traces": "training_models",
    "reference_crosschecks": "reference_crosschecks",
}
PARQUET_ARTIFACTS = {
    "source_oof_predictions",
    "target_predictions",
    "source_oof_ensemble_predictions",
    "target_ensemble_predictions",
    "selection_decisions",
}


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
    path = directory / str(record["path"])
    if not path.is_file():
        raise FileNotFoundError(f"selective artifact is missing: {path}")
    if path.stat().st_size != int(record["bytes"]) or _sha256(path) != record["sha256"]:
        raise ValueError(f"selective artifact hash/size mismatch: {artifact_name}")
    return path


def _record_rows(
    value: pd.DataFrame | list[dict[str, Any]], columns: tuple[str, ...]
) -> list[tuple[Any, ...]]:
    if isinstance(value, pd.DataFrame):
        missing = sorted(set(columns) - set(value.columns))
        if missing:
            raise ValueError(f"artifact is missing key columns: {missing}")
        return list(value.loc[:, list(columns)].itertuples(index=False, name=None))
    rows = []
    for record in value:
        missing = sorted(set(columns) - set(record))
        if missing:
            raise ValueError(f"artifact record is missing key fields: {missing}")
        rows.append(tuple(record[column] for column in columns))
    return rows


def validate_expected_key_set(
    value: pd.DataFrame | list[dict[str, Any]],
    *,
    key_set_name: str,
    expected: dict[str, Any],
) -> dict[str, Any]:
    """Require exact schema, count and canonical key hash."""

    columns = KEY_SCHEMAS[key_set_name]
    if expected.get("columns") != list(columns):
        raise ValueError(f"expected manifest schema drift for {key_set_name}")
    observed = canonical_key_record(_record_rows(value, columns), columns)
    if observed != expected:
        raise ValueError(f"selective artifact key set differs for {key_set_name}")
    return observed


def _validate_recorded_count(
    record: dict[str, Any], observed_count: int, artifact_name: str
) -> None:
    count_fields = [
        key for key in record if key not in {"path", "bytes", "sha256"}
    ]
    if len(count_fields) != 1 or int(record[count_fields[0]]) != observed_count:
        raise ValueError(f"recorded artifact count differs for {artifact_name}")


def _validate_probabilities(frames: list[pd.DataFrame]) -> float:
    maximum_error = 0.0
    group_columns = ["dataset", "method", "seed", "fold_id"]
    for frame in frames:
        for _, group in frame.groupby(group_columns, sort=True, observed=True):
            columns = sorted(
                column
                for column in group
                if column.startswith("probability_") and group[column].notna().all()
            )
            if len(columns) < 2:
                raise ValueError("selective prediction group lacks active probabilities")
            probabilities = group[columns].to_numpy(dtype=float)
            if (
                not np.isfinite(probabilities).all()
                or np.any(probabilities < 0.0)
                or np.any(probabilities > 1.0)
            ):
                raise ValueError("selective prediction probabilities are invalid")
            error = float(np.max(np.abs(probabilities.sum(axis=1) - 1.0)))
            maximum_error = max(maximum_error, error)
    if maximum_error > PROBABILITY_TOLERANCE:
        raise ValueError("selective prediction probabilities are not normalized")
    return maximum_error


def validate_selective_artifacts(
    *,
    selective_output_directory: Path,
    expected_manifest_path: Path,
    expected_manifest_sha256: str,
    output: Path,
) -> dict[str, Any]:
    directory = selective_output_directory.resolve(strict=True)
    expected_manifest_path = expected_manifest_path.resolve(strict=True)
    manifest_hash = _sha256(expected_manifest_path)
    if manifest_hash != expected_manifest_sha256:
        raise ValueError("selective expected-manifest SHA-256 mismatch")
    manifest = _read_json(expected_manifest_path)
    if manifest.get("manifest_version") != MANIFEST_VERSION:
        raise ValueError("selective expected manifest has an unexpected version")
    metrics_path = directory / "metrics.json"
    metrics = _read_json(metrics_path)
    expected_input = manifest["input"]
    for field in (
        "uci_feature_matrix_sha256",
        "pirl_metrics_sha256",
        "dg_metrics_sha256",
    ):
        if metrics["input"][field] != expected_input[field]:
            raise ValueError(f"selective metrics input drift: {field}")
    if (
        expected_input.get("paderborn_archive_contents_opened") is not False
        or metrics["input"].get("paderborn_archive_contents_opened") is not False
    ):
        raise ValueError("selective package does not preserve the Paderborn access boundary")

    loaded: dict[str, pd.DataFrame | list[dict[str, Any]]] = {}
    observed_key_sets = {}
    artifact_hashes = {}
    for artifact_name, key_set_name in ARTIFACT_KEY_SETS.items():
        path = _artifact_path(directory, metrics, artifact_name)
        value = (
            pd.read_parquet(path)
            if artifact_name in PARQUET_ARTIFACTS
            else _read_json(path)
        )
        if not isinstance(value, (pd.DataFrame, list)):
            raise ValueError(f"selective artifact has unexpected type: {artifact_name}")
        loaded[artifact_name] = value
        observed_count = len(value)
        _validate_recorded_count(
            metrics["artifacts"][artifact_name], observed_count, artifact_name
        )
        observed_key_sets[key_set_name] = validate_expected_key_set(
            value,
            key_set_name=key_set_name,
            expected=manifest["expected_key_sets"][key_set_name],
        )
        artifact_hashes[artifact_name] = _sha256(path)

    probability_error = _validate_probabilities(
        [
            loaded["source_oof_predictions"],
            loaded["target_predictions"],
            loaded["source_oof_ensemble_predictions"],
            loaded["target_ensemble_predictions"],
        ]
    )
    decisions = loaded["selection_decisions"]
    if not isinstance(decisions, pd.DataFrame):
        raise AssertionError("selection decisions unexpectedly are not tabular")
    if decisions[["score", "threshold"]].isna().any().any() or not np.isfinite(
        decisions[["score", "threshold"]].to_numpy(dtype=float)
    ).all():
        raise ValueError("selection decisions contain non-finite score/threshold values")
    if decisions["accepted"].isna().any():
        raise ValueError("selection decisions contain missing acceptance values")

    integrity = metrics["integrity"]
    expected_crosschecks = manifest["expected_key_sets"]["reference_crosschecks"][
        "count"
    ]
    if int(integrity["reference_crosschecks"]) != int(expected_crosschecks):
        raise ValueError("selective reference-crosscheck count differs")
    if integrity.get("all_final_model_state_hashes_exact") is not True:
        raise ValueError("selective final model-state hashes were not exact")
    if (
        float(integrity["maximum_absolute_probability_difference"])
        > PROBABILITY_TOLERANCE
    ):
        raise ValueError("selective final probability crosscheck exceeds tolerance")
    topology = integrity["prediction_topology"]
    if int(topology["source_oof_rows"]) != len(loaded["source_oof_predictions"]):
        raise ValueError("selective source topology count differs")
    if int(topology["target_rows"]) != len(loaded["target_predictions"]):
        raise ValueError("selective target topology count differs")

    result = {
        "validation_version": VALIDATION_VERSION,
        "generated_at": datetime.now(UTC).isoformat(),
        "status": "passed_against_outcome_blind_selective_manifest",
        "expected_manifest": {
            "path": str(expected_manifest_path),
            "sha256": manifest_hash,
        },
        "selective_metrics": {
            "path": str(metrics_path),
            "sha256": _sha256(metrics_path),
        },
        "observed_key_sets": observed_key_sets,
        "artifact_hashes": artifact_hashes,
        "maximum_probability_sum_error": probability_error,
        "reference_crosschecks": int(integrity["reference_crosschecks"]),
        "maximum_absolute_reference_probability_difference": float(
            integrity["maximum_absolute_probability_difference"]
        ),
        "paderborn_archive_contents_opened": False,
    }
    output = output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_suffix(output.suffix + ".tmp")
    temporary.write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
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
    result = validate_selective_artifacts(
        selective_output_directory=args.selective_output_directory,
        expected_manifest_path=args.expected_manifest,
        expected_manifest_sha256=args.expected_manifest_sha256,
        output=args.output,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
