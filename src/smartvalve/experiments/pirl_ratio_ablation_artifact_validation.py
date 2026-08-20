"""Validate a PIRL ratio ablation package against its outcome-blind manifest."""

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
from smartvalve.experiments.pirl_ratio_ablation_expected_manifest import (
    KEY_SCHEMAS,
    MANIFEST_VERSION,
)

VALIDATION_VERSION = "pirl-ratio-ablation-artifact-validation-0.1.0"
PROBABILITY_TOLERANCE = 2e-6


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
        raise ValueError(f"ablation artifact escapes output directory: {artifact_name}")
    if path.stat().st_size != int(record["bytes"]) or _sha256(path) != record["sha256"]:
        raise ValueError(f"ablation artifact hash/size mismatch: {artifact_name}")
    return path


def _key_record(
    value: pd.DataFrame | list[dict[str, Any]], key_set_name: str
) -> dict[str, Any]:
    columns = KEY_SCHEMAS[key_set_name]
    if isinstance(value, pd.DataFrame):
        missing = set(columns) - set(value.columns)
        if missing:
            raise ValueError(f"ablation predictions are missing keys: {sorted(missing)}")
        rows = value.loc[:, list(columns)].itertuples(index=False, name=None)
    else:
        if any(set(columns) - set(record) for record in value):
            raise ValueError("ablation trace is missing a frozen key")
        rows = (tuple(record[column] for column in columns) for record in value)
    return canonical_key_record(rows, columns)


def _maximum_probability_error(predictions: pd.DataFrame) -> float:
    maximum = 0.0
    for _, group in predictions.groupby(
        ["dataset", "method", "seed", "fold_id"], sort=True, observed=True
    ):
        columns = sorted(
            column
            for column in group
            if column.startswith("probability_") and group[column].notna().all()
        )
        if len(columns) < 2:
            raise ValueError("ablation prediction group lacks active probabilities")
        values = group[columns].to_numpy(dtype=float)
        if (
            not np.isfinite(values).all()
            or np.any(values < 0.0)
            or np.any(values > 1.0)
        ):
            raise ValueError("ablation probabilities are invalid")
        maximum = max(maximum, float(np.max(np.abs(values.sum(axis=1) - 1.0))))
    if maximum > PROBABILITY_TOLERANCE:
        raise ValueError("ablation probabilities are not normalized")
    return maximum


def validate_ablation_artifacts(
    *,
    ablation_output_directory: Path,
    expected_manifest: Path,
    expected_manifest_sha256: str,
    output: Path,
) -> dict[str, Any]:
    directory = ablation_output_directory.resolve(strict=True)
    expected_manifest = expected_manifest.resolve(strict=True)
    if _sha256(expected_manifest) != expected_manifest_sha256:
        raise ValueError("ablation expected-manifest SHA-256 mismatch")
    manifest = _read_json(expected_manifest)
    if manifest.get("manifest_version") != MANIFEST_VERSION:
        raise ValueError("ablation expected-manifest version changed")
    metrics_path = (directory / "metrics.json").resolve(strict=True)
    metrics = _read_json(metrics_path)
    for field in (
        "uci_feature_matrix_sha256",
        "protocol_document_sha256",
        "expected_manifest_sha256",
        "reference_hashes",
    ):
        expected = (
            expected_manifest_sha256
            if field == "expected_manifest_sha256"
            else manifest["input"][field]
        )
        if metrics["input"].get(field) != expected:
            raise ValueError(f"ablation metrics input drift: {field}")
    if (
        metrics["input"].get("paderborn_archive_contents_opened") is not False
        or manifest["input"].get("paderborn_archive_contents_opened") is not False
    ):
        raise ValueError("ablation package violates the Paderborn access boundary")

    predictions_path = _artifact_path(directory, metrics, "predictions")
    traces_path = _artifact_path(directory, metrics, "training_traces")
    predictions = pd.read_parquet(predictions_path)
    traces = _read_json(traces_path)
    if not isinstance(traces, list):
        raise ValueError("ablation training traces are not a list")
    if int(metrics["artifacts"]["predictions"]["rows"]) != len(predictions):
        raise ValueError("ablation prediction row count differs")
    if int(metrics["artifacts"]["training_traces"]["models"]) != len(traces):
        raise ValueError("ablation training-trace count differs")
    observed = {
        "target_predictions": _key_record(predictions, "target_predictions"),
        "training_models": _key_record(traces, "training_models"),
    }
    for name, record in observed.items():
        if record != manifest["expected_key_sets"][name]:
            raise ValueError(f"ablation artifact key set differs: {name}")
    probability_error = _maximum_probability_error(predictions)
    result = {
        "validation_version": VALIDATION_VERSION,
        "generated_at": datetime.now(UTC).isoformat(),
        "status": "passed_against_outcome_blind_ablation_manifest",
        "expected_manifest": {
            "path": str(expected_manifest),
            "sha256": expected_manifest_sha256,
        },
        "ablation_metrics": {
            "path": str(metrics_path),
            "sha256": _sha256(metrics_path),
        },
        "artifact_hashes": {
            "predictions": _sha256(predictions_path),
            "training_traces": _sha256(traces_path),
        },
        "observed_key_sets": observed,
        "maximum_probability_sum_error": probability_error,
        "paderborn_archive_contents_opened": False,
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
    parser.add_argument("--ablation-output-directory", type=Path, required=True)
    parser.add_argument("--expected-manifest", type=Path, required=True)
    parser.add_argument("--expected-manifest-sha256", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = validate_ablation_artifacts(
        ablation_output_directory=args.ablation_output_directory,
        expected_manifest=args.expected_manifest,
        expected_manifest_sha256=args.expected_manifest_sha256,
        output=args.output,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
