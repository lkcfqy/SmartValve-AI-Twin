"""Outcome-blind expected-key manifest for the frozen neural-DG experiment."""

from __future__ import annotations

import argparse
import hashlib
import json
from collections.abc import Iterable
from dataclasses import asdict
from pathlib import Path
from typing import Any

import numpy as np

from smartvalve.experiments.cranfield_causal_audit import AUDIT_SEEDS
from smartvalve.experiments.dg_selection import candidate_grid, candidate_id
from smartvalve.experiments.dg_training import BASELINE_METHODS
from smartvalve.experiments.domain_data import (
    SourceOnlyFold,
    build_cranfield_folds,
    build_uci_folds,
)
from smartvalve.experiments.inner_splits import build_inner_splits

MANIFEST_VERSION = "neural-dg-expected-key-manifest-0.1.0"
KEY_SCHEMAS = {
    "candidate_metrics": (
        "method",
        "dataset",
        "outer_fold_id",
        "candidate_id",
    ),
    "tuning_models": (
        "method",
        "dataset",
        "outer_fold_id",
        "candidate_id",
        "inner_split_id",
    ),
    "outer_selections": ("method", "dataset", "outer_fold_id"),
    "final_models": ("dataset", "method", "seed", "fold_id"),
    "target_predictions": (
        "dataset",
        "method",
        "seed",
        "fold_id",
        "row_index",
    ),
    "target_provenance": (
        "dataset",
        "fold_id",
        "row_index",
        "environment_id",
        "block_id",
        "truth",
    ),
}


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _canonical_value(value: Any) -> str | int | float | bool | None:
    if isinstance(value, np.generic):
        value = value.item()
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    return str(value)


def canonical_key_record(
    rows: Iterable[tuple[Any, ...]],
    columns: tuple[str, ...],
) -> dict[str, Any]:
    """Hash a named key set independently of producer row order."""

    normalized = [tuple(_canonical_value(value) for value in row) for row in rows]
    if any(len(row) != len(columns) for row in normalized):
        raise ValueError("key row width differs from its frozen schema")
    if len(normalized) != len(set(normalized)):
        raise ValueError("expected-key manifest contains a duplicate key")
    normalized.sort(key=lambda row: tuple(str(value) for value in row))
    digest = hashlib.sha256()
    for row in normalized:
        digest.update(
            json.dumps(
                row,
                ensure_ascii=False,
                separators=(",", ":"),
                allow_nan=False,
            ).encode("utf-8")
        )
        digest.update(b"\n")
    return {
        "columns": list(columns),
        "count": len(normalized),
        "sha256": digest.hexdigest(),
    }


def build_expected_manifest(
    datasets: dict[str, list[SourceOnlyFold]],
    *,
    uci_feature_matrix: str,
    uci_feature_matrix_sha256: str,
) -> dict[str, Any]:
    if set(datasets) != {"cranfield", "uci_hydraulic"}:
        raise ValueError("DG manifest requires exactly Cranfield and UCI Hydraulic")
    grids = {method: candidate_grid(method) for method in BASELINE_METHODS}
    candidate_keys = []
    tuning_keys = []
    selection_keys = []
    final_keys = []
    prediction_keys = []
    provenance_keys = []
    fold_records = []
    for dataset, folds in datasets.items():
        if not folds:
            raise ValueError(f"DG manifest dataset {dataset} has no folds")
        for fold in folds:
            fold.validate()
            if fold.dataset != dataset:
                raise ValueError("DG manifest fold is assigned to the wrong dataset")
            inner_ids = tuple(split.split_id for split in build_inner_splits(fold))
            if len(inner_ids) != 4 or len(set(inner_ids)) != 4:
                raise ValueError("DG manifest requires four unique source-only inner splits")
            fold_records.append(
                {
                    "dataset": dataset,
                    "fold_id": fold.fold_id,
                    "source_rows": len(fold.source_indices),
                    "target_rows": len(fold.target_indices),
                    "inner_split_ids": list(inner_ids),
                }
            )
            for row_index, environment, block_id, truth_index in zip(
                fold.target_indices,
                fold.target_environments,
                fold.block_ids[fold.target_indices],
                fold.target_labels,
                strict=True,
            ):
                provenance_keys.append(
                    (
                        dataset,
                        fold.fold_id,
                        int(row_index),
                        str(environment),
                        str(block_id),
                        fold.label_names[int(truth_index)],
                    )
                )
            for method in BASELINE_METHODS:
                selection_keys.append((method, dataset, fold.fold_id))
                for config in grids[method]:
                    identifier = candidate_id(config)
                    candidate_keys.append(
                        (method, dataset, fold.fold_id, identifier)
                    )
                    tuning_keys.extend(
                        (
                            method,
                            dataset,
                            fold.fold_id,
                            identifier,
                            inner_id,
                        )
                        for inner_id in inner_ids
                    )
                for seed in AUDIT_SEEDS:
                    final_keys.append(
                        (dataset, method, int(seed), fold.fold_id)
                    )
                    prediction_keys.extend(
                        (
                            dataset,
                            method,
                            int(seed),
                            fold.fold_id,
                            int(row_index),
                        )
                        for row_index in fold.target_indices
                    )
    key_rows = {
        "candidate_metrics": candidate_keys,
        "tuning_models": tuning_keys,
        "outer_selections": selection_keys,
        "final_models": final_keys,
        "target_predictions": prediction_keys,
        "target_provenance": provenance_keys,
    }
    key_records = {
        name: canonical_key_record(rows, KEY_SCHEMAS[name])
        for name, rows in key_rows.items()
    }
    return {
        "manifest_version": MANIFEST_VERSION,
        "role": "outcome-blind expected topology; contains no model score or prediction",
        "input": {
            "uci_feature_matrix": uci_feature_matrix,
            "uci_feature_matrix_sha256": uci_feature_matrix_sha256,
            "paderborn_archive_contents_opened": False,
        },
        "configuration": {
            "methods": list(BASELINE_METHODS),
            "seeds": list(AUDIT_SEEDS),
            "candidate_count": sum(len(grid) for grid in grids.values()),
            "candidate_grids": {
                method: [
                    {
                        "candidate_id": candidate_id(config),
                        "configuration": asdict(config),
                    }
                    for config in grid
                ]
                for method, grid in grids.items()
            },
        },
        "folds": fold_records,
        "expected_key_sets": key_records,
    }


def run_manifest(
    uci_feature_matrix: Path,
    output_path: Path,
    *,
    expected_uci_sha256: str,
) -> dict[str, Any]:
    observed_hash = _sha256(uci_feature_matrix)
    if observed_hash != expected_uci_sha256:
        raise ValueError("UCI feature matrix hash differs from the frozen input")
    manifest = build_expected_manifest(
        {
            "cranfield": build_cranfield_folds(),
            "uci_hydraulic": build_uci_folds(uci_feature_matrix),
        },
        uci_feature_matrix=str(uci_feature_matrix.resolve()),
        uci_feature_matrix_sha256=observed_hash,
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--uci-feature-matrix", type=Path, required=True)
    parser.add_argument("--uci-feature-matrix-sha256", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = run_manifest(
        args.uci_feature_matrix,
        args.output,
        expected_uci_sha256=args.uci_feature_matrix_sha256,
    )
    print(json.dumps(result["expected_key_sets"], ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
