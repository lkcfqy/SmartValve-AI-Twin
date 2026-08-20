"""Outcome-blind expected-key manifest for the frozen selective experiment."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from smartvalve.experiments.cranfield_causal_audit import AUDIT_SEEDS
from smartvalve.experiments.dg_expected_manifest import canonical_key_record
from smartvalve.experiments.domain_data import (
    SourceOnlyFold,
    build_cranfield_folds,
    build_uci_folds,
)
from smartvalve.experiments.inner_splits import build_inner_splits
from smartvalve.experiments.selective_evaluation import (
    BETA_CANDIDATES,
    COVERAGE_LEVELS,
    ENSEMBLE_SCORE_COLUMNS,
    INDIVIDUAL_SCORE_COLUMNS,
    MINIMUM_SOURCE_ENVIRONMENT_COVERAGE,
)
from smartvalve.experiments.selective_input_preflight import _sha256
from smartvalve.experiments.selective_prediction_run import METHODS

MANIFEST_VERSION = "selective-expected-key-manifest-0.1.0"
ENSEMBLE_SEED = -1
INDIVIDUAL_SCORE_NAMES = (*INDIVIDUAL_SCORE_COLUMNS, "risk_envelope")
ENSEMBLE_SCORE_NAMES = (*ENSEMBLE_SCORE_COLUMNS, "ensemble_risk_envelope")
KEY_SCHEMAS = {
    "source_oof_predictions": ("dataset", "method", "seed", "fold_id", "row_index"),
    "target_predictions": ("dataset", "method", "seed", "fold_id", "row_index"),
    "source_oof_ensemble_predictions": (
        "dataset",
        "method",
        "seed",
        "fold_id",
        "row_index",
    ),
    "target_ensemble_predictions": (
        "dataset",
        "method",
        "seed",
        "fold_id",
        "row_index",
    ),
    "policies": (
        "dataset",
        "method",
        "seed",
        "fold_id",
        "score_name",
        "nominal_source_coverage",
    ),
    "beta_selections": ("dataset", "method", "seed", "fold_id"),
    "policy_metrics": (
        "dataset",
        "method",
        "seed",
        "fold_id",
        "score_name",
        "nominal_source_coverage",
    ),
    "ranking_metrics": ("dataset", "method", "seed", "fold_id", "score_name"),
    "selection_decisions": (
        "dataset",
        "method",
        "seed",
        "fold_id",
        "score_name",
        "nominal_source_coverage",
        "row_index",
    ),
    "training_models": (
        "dataset",
        "method",
        "seed",
        "fold_id",
        "inner_split_id",
    ),
    "reference_crosschecks": ("dataset", "method", "seed", "fold_id"),
}


def _policy_keys(
    *,
    dataset: str,
    method: str,
    seed: int,
    fold_id: str,
    score_names: tuple[str, ...],
) -> list[tuple[Any, ...]]:
    return [
        (dataset, method, seed, fold_id, score_name, float(coverage))
        for score_name in score_names
        for coverage in COVERAGE_LEVELS
    ]


def build_expected_selective_manifest(
    datasets: dict[str, list[SourceOnlyFold]],
    *,
    uci_feature_matrix: str,
    uci_feature_matrix_sha256: str,
    pirl_metrics_sha256: str,
    dg_metrics_sha256: str,
) -> dict[str, Any]:
    if set(datasets) != {"cranfield", "uci_hydraulic"}:
        raise ValueError("selective manifest requires exactly Cranfield and UCI Hydraulic")
    rows: dict[str, list[tuple[Any, ...]]] = {name: [] for name in KEY_SCHEMAS}
    fold_records = []
    for dataset, folds in datasets.items():
        for fold in folds:
            fold.validate()
            if fold.dataset != dataset:
                raise ValueError("selective manifest fold is assigned to the wrong dataset")
            inner_ids = tuple(split.split_id for split in build_inner_splits(fold))
            if len(inner_ids) != 4 or len(set(inner_ids)) != 4:
                raise ValueError("selective manifest requires four unique inner partitions")
            fold_records.append(
                {
                    "dataset": dataset,
                    "fold_id": fold.fold_id,
                    "source_rows": len(fold.source_indices),
                    "target_rows": len(fold.target_indices),
                    "inner_split_ids": list(inner_ids),
                }
            )
            for method in METHODS:
                ensemble_group = (dataset, method, ENSEMBLE_SEED, fold.fold_id)
                rows["source_oof_ensemble_predictions"].extend(
                    (*ensemble_group, int(row_index))
                    for row_index in fold.source_indices
                )
                rows["target_ensemble_predictions"].extend(
                    (*ensemble_group, int(row_index))
                    for row_index in fold.target_indices
                )
                ensemble_policies = _policy_keys(
                    dataset=dataset,
                    method=method,
                    seed=ENSEMBLE_SEED,
                    fold_id=fold.fold_id,
                    score_names=ENSEMBLE_SCORE_NAMES,
                )
                rows["policies"].extend(ensemble_policies)
                rows["policy_metrics"].extend(ensemble_policies)
                rows["beta_selections"].append(ensemble_group)
                rows["ranking_metrics"].extend(
                    (*ensemble_group, score_name)
                    for score_name in ENSEMBLE_SCORE_NAMES
                )
                rows["selection_decisions"].extend(
                    (*policy, int(row_index))
                    for policy in ensemble_policies
                    for row_index in fold.target_indices
                )
                for seed in AUDIT_SEEDS:
                    group = (dataset, method, int(seed), fold.fold_id)
                    rows["source_oof_predictions"].extend(
                        (*group, int(row_index)) for row_index in fold.source_indices
                    )
                    rows["target_predictions"].extend(
                        (*group, int(row_index)) for row_index in fold.target_indices
                    )
                    policies = _policy_keys(
                        dataset=dataset,
                        method=method,
                        seed=int(seed),
                        fold_id=fold.fold_id,
                        score_names=INDIVIDUAL_SCORE_NAMES,
                    )
                    rows["policies"].extend(policies)
                    rows["policy_metrics"].extend(policies)
                    rows["beta_selections"].append(group)
                    rows["ranking_metrics"].extend(
                        (*group, score_name)
                        for score_name in INDIVIDUAL_SCORE_NAMES
                    )
                    rows["selection_decisions"].extend(
                        (*policy, int(row_index))
                        for policy in policies
                        for row_index in fold.target_indices
                    )
                    rows["training_models"].extend(
                        (*group, inner_id) for inner_id in inner_ids
                    )
                    rows["training_models"].append((*group, None))
                    rows["reference_crosschecks"].append(group)

    key_records = {
        name: canonical_key_record(values, KEY_SCHEMAS[name])
        for name, values in rows.items()
    }
    return {
        "manifest_version": MANIFEST_VERSION,
        "role": "outcome-blind expected selective topology; contains no selective score or result",
        "input": {
            "uci_feature_matrix": uci_feature_matrix,
            "uci_feature_matrix_sha256": uci_feature_matrix_sha256,
            "pirl_metrics_sha256": pirl_metrics_sha256,
            "dg_metrics_sha256": dg_metrics_sha256,
            "paderborn_archive_contents_opened": False,
        },
        "configuration": {
            "methods": list(METHODS),
            "seeds": list(AUDIT_SEEDS),
            "ensemble_seed": ENSEMBLE_SEED,
            "ensemble_size": len(AUDIT_SEEDS),
            "inner_partitions_per_fold": 4,
            "individual_score_names": list(INDIVIDUAL_SCORE_NAMES),
            "ensemble_score_names": list(ENSEMBLE_SCORE_NAMES),
            "coverage_levels": list(COVERAGE_LEVELS),
            "minimum_source_environment_coverage": (
                MINIMUM_SOURCE_ENVIRONMENT_COVERAGE
            ),
            "beta_candidates": list(BETA_CANDIDATES),
        },
        "folds": fold_records,
        "expected_key_sets": key_records,
    }


def run_manifest(
    *,
    uci_feature_matrix: Path,
    expected_uci_feature_matrix_sha256: str,
    pirl_metrics_sha256: str,
    dg_metrics_sha256: str,
    output: Path,
) -> dict[str, Any]:
    observed_uci_hash = _sha256(uci_feature_matrix)
    if observed_uci_hash != expected_uci_feature_matrix_sha256:
        raise ValueError("UCI feature matrix hash differs from the frozen input")
    manifest = build_expected_selective_manifest(
        {
            "cranfield": build_cranfield_folds(),
            "uci_hydraulic": build_uci_folds(uci_feature_matrix),
        },
        uci_feature_matrix=str(uci_feature_matrix.resolve()),
        uci_feature_matrix_sha256=observed_uci_hash,
        pirl_metrics_sha256=pirl_metrics_sha256,
        dg_metrics_sha256=dg_metrics_sha256,
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--uci-feature-matrix", type=Path, required=True)
    parser.add_argument("--uci-feature-matrix-sha256", required=True)
    parser.add_argument("--pirl-metrics-sha256", required=True)
    parser.add_argument("--dg-metrics-sha256", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = run_manifest(
        uci_feature_matrix=args.uci_feature_matrix,
        expected_uci_feature_matrix_sha256=args.uci_feature_matrix_sha256,
        pirl_metrics_sha256=args.pirl_metrics_sha256,
        dg_metrics_sha256=args.dg_metrics_sha256,
        output=args.output,
    )
    print(json.dumps(result["expected_key_sets"], ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
