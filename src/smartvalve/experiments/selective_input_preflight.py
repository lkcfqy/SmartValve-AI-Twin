"""Outcome-aware D0/D1 input gate before the frozen selective refit begins."""

from __future__ import annotations

import argparse
import hashlib
import json
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np

from smartvalve.experiments.cranfield_causal_audit import AUDIT_SEEDS
from smartvalve.experiments.domain_data import (
    SourceOnlyFold,
    build_cranfield_folds,
    build_uci_folds,
)
from smartvalve.experiments.selective_prediction_run import (
    METHODS,
    LockedReferences,
    load_locked_references,
)

PREFLIGHT_VERSION = "selective-locked-input-preflight-0.1.0"
PROBABILITY_TOLERANCE = 2e-6


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _canonical_hash(records: list[tuple[str, str, int, str, int]]) -> str:
    payload = json.dumps(sorted(records), separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def validate_reference_prediction_topology(
    references: LockedReferences,
    datasets: dict[str, list[SourceOnlyFold]],
    *,
    methods: tuple[str, ...] = METHODS,
    seeds: tuple[int, ...] = AUDIT_SEEDS,
) -> dict[str, Any]:
    """Crosscheck every locked target row against the independently rebuilt folds."""

    predictions = references.predictions
    key_columns = ["dataset", "method", "seed", "fold_id", "row_index"]
    required = {
        *key_columns,
        "environment_id",
        "block_id",
        "truth",
        "prediction",
        "correct",
    }
    missing = sorted(required - set(predictions.columns))
    if missing:
        raise ValueError(f"locked prediction frame is missing columns: {missing}")
    if predictions.duplicated(key_columns).any():
        raise ValueError("locked prediction frame contains duplicate row keys")
    if not np.isfinite(predictions["seed"].to_numpy(dtype=float)).all():
        raise ValueError("locked prediction frame contains non-finite seeds")

    expected_group_keys = set()
    canonical_keys: list[tuple[str, str, int, str, int]] = []
    checked_groups = 0
    maximum_probability_sum_error = 0.0
    for dataset, folds in datasets.items():
        for method in methods:
            for seed in seeds:
                for fold in folds:
                    group_key = (dataset, method, int(seed), fold.fold_id)
                    expected_group_keys.add(group_key)
                    selector = (
                        (predictions["dataset"] == dataset)
                        & (predictions["method"] == method)
                        & (predictions["seed"] == int(seed))
                        & (predictions["fold_id"] == fold.fold_id)
                    )
                    group = predictions.loc[selector].sort_values("row_index", kind="stable")
                    expected_indices = np.sort(fold.target_indices.astype(np.int64))
                    observed_indices = group["row_index"].to_numpy(dtype=np.int64)
                    if not np.array_equal(observed_indices, expected_indices):
                        raise ValueError(f"locked target row indices differ for {group_key}")
                    expected_truth = np.asarray(
                        [fold.label_names[int(fold.labels[index])] for index in expected_indices]
                    )
                    if not np.array_equal(group["truth"].to_numpy(), expected_truth):
                        raise ValueError(f"locked target truth differs for {group_key}")
                    expected_environments = fold.environment_ids[expected_indices].astype(str)
                    expected_blocks = fold.block_ids[expected_indices].astype(str)
                    if not np.array_equal(
                        group["environment_id"].astype(str).to_numpy(),
                        expected_environments,
                    ):
                        raise ValueError(f"locked target environment differs for {group_key}")
                    if not np.array_equal(
                        group["block_id"].astype(str).to_numpy(), expected_blocks
                    ):
                        raise ValueError(f"locked physical block differs for {group_key}")
                    observed_correct = (
                        group["prediction"].astype(str).to_numpy()
                        == group["truth"].astype(str).to_numpy()
                    )
                    if not np.array_equal(
                        group["correct"].to_numpy(dtype=bool), observed_correct
                    ):
                        raise ValueError(f"locked correctness flag differs for {group_key}")
                    probability_columns = [
                        f"probability_{label}" for label in fold.label_names
                    ]
                    if any(column not in group for column in probability_columns):
                        raise ValueError(f"locked probabilities are incomplete for {group_key}")
                    probabilities = group[probability_columns].to_numpy(dtype=float)
                    if not np.isfinite(probabilities).all() or np.any(probabilities < 0.0):
                        raise ValueError(f"locked probabilities are invalid for {group_key}")
                    probability_error = float(
                        np.max(np.abs(probabilities.sum(axis=1) - 1.0))
                    )
                    maximum_probability_sum_error = max(
                        maximum_probability_sum_error, probability_error
                    )
                    if probability_error > PROBABILITY_TOLERANCE:
                        raise ValueError(
                            f"locked probabilities are not normalized for {group_key}"
                        )
                    canonical_keys.extend(
                        (dataset, method, int(seed), fold.fold_id, int(index))
                        for index in observed_indices
                    )
                    checked_groups += 1

    observed_group_keys = set(
        predictions[["dataset", "method", "seed", "fold_id"]]
        .drop_duplicates()
        .itertuples(index=False, name=None)
    )
    if observed_group_keys != expected_group_keys:
        raise ValueError("locked prediction groups differ from the frozen experiment design")
    expected_models = len(expected_group_keys)
    if set(references.model_state_sha256) != expected_group_keys:
        raise ValueError("locked model-state keys differ from the prediction groups")
    return {
        "groups": checked_groups,
        "model_states": expected_models,
        "prediction_rows": len(predictions),
        "prediction_key_sha256": _canonical_hash(canonical_keys),
        "maximum_probability_sum_error": maximum_probability_sum_error,
    }


def run_preflight(
    *,
    uci_feature_matrix: Path,
    expected_uci_feature_matrix_sha256: str,
    pirl_reference_directory: Path,
    dg_reference_directory: Path,
    expected_pirl_metrics_sha256: str,
    expected_dg_metrics_sha256: str,
    output: Path,
) -> dict[str, Any]:
    uci_feature_matrix = uci_feature_matrix.resolve(strict=True)
    observed_uci_hash = _sha256(uci_feature_matrix)
    if observed_uci_hash != expected_uci_feature_matrix_sha256:
        raise ValueError("UCI feature matrix differs from the frozen input")
    references = load_locked_references(
        pirl_reference_directory,
        dg_reference_directory,
        expected_pirl_metrics_sha256=expected_pirl_metrics_sha256,
        expected_dg_metrics_sha256=expected_dg_metrics_sha256,
    )
    datasets = {
        "cranfield": build_cranfield_folds(),
        "uci_hydraulic": build_uci_folds(uci_feature_matrix),
    }
    topology = validate_reference_prediction_topology(references, datasets)
    result = {
        "preflight_version": PREFLIGHT_VERSION,
        "generated_at": datetime.now(UTC).isoformat(),
        "status": "locked_selective_inputs_validated_before_refit",
        "inputs": {
            "uci_feature_matrix": str(uci_feature_matrix),
            "uci_feature_matrix_sha256": observed_uci_hash,
            "pirl_reference_directory": str(references.pirl_directory),
            "dg_reference_directory": str(references.dg_directory),
            "pirl_metrics_sha256": references.pirl_metrics_sha256,
            "dg_metrics_sha256": references.dg_metrics_sha256,
            "reference_artifact_hashes": references.artifact_hashes,
        },
        "configuration": {
            method: asdict(configuration)
            for method, configuration in references.configurations.items()
        },
        "topology": topology,
        "access_attestation": {
            "datasets": ["cranfield", "uci_hydraulic"],
            "target_outcomes_used_for_configuration_selection": False,
            "paderborn_archive_path_supplied": False,
            "paderborn_archive_contents_opened": False,
        },
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
    parser.add_argument("--uci-feature-matrix", type=Path, required=True)
    parser.add_argument("--uci-feature-matrix-sha256", required=True)
    parser.add_argument("--pirl-reference-directory", type=Path, required=True)
    parser.add_argument("--dg-reference-directory", type=Path, required=True)
    parser.add_argument("--pirl-metrics-sha256", required=True)
    parser.add_argument("--dg-metrics-sha256", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = run_preflight(
        uci_feature_matrix=args.uci_feature_matrix,
        expected_uci_feature_matrix_sha256=args.uci_feature_matrix_sha256,
        pirl_reference_directory=args.pirl_reference_directory,
        dg_reference_directory=args.dg_reference_directory,
        expected_pirl_metrics_sha256=args.pirl_metrics_sha256,
        expected_dg_metrics_sha256=args.dg_metrics_sha256,
        output=args.output,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
