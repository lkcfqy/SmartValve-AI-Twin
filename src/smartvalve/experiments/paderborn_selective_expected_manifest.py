"""Metadata-only expected topology for sealed Paderborn selective evaluation."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

import numpy as np

from smartvalve.data.paderborn_features import main_signal_feature_names
from smartvalve.experiments.cranfield_causal_audit import AUDIT_SEEDS
from smartvalve.experiments.dg_expected_manifest import canonical_key_record
from smartvalve.experiments.inner_splits import build_inner_splits
from smartvalve.experiments.paderborn_domain import build_paderborn_model_folds
from smartvalve.experiments.paderborn_expected_manifest import metadata_only_indices
from smartvalve.experiments.selective_evaluation import (
    COVERAGE_LEVELS,
    MINIMUM_SOURCE_ENVIRONMENT_COVERAGE,
)
from smartvalve.experiments.selective_expected_manifest import (
    ENSEMBLE_SCORE_NAMES,
    ENSEMBLE_SEED,
    INDIVIDUAL_SCORE_NAMES,
)
from smartvalve.experiments.selective_prediction_run import METHODS

MANIFEST_VERSION = "paderborn-selective-expected-key-manifest-0.2.0"
KEY_SCHEMAS = {
    "source_oof_predictions": ("dataset", "method", "seed", "fold_id", "row_index"),
    "target_predictions": ("dataset", "method", "seed", "fold_id", "row_index"),
    "compound_predictions": (
        "dataset",
        "method",
        "seed",
        "fold_id",
        "row_index",
    ),
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
    "compound_ensemble_predictions": (
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
    "compound_decisions": (
        "dataset",
        "method",
        "seed",
        "fold_id",
        "score_name",
        "nominal_source_coverage",
        "row_index",
    ),
    "compound_policy_metrics": (
        "dataset",
        "method",
        "seed",
        "fold_id",
        "score_name",
        "nominal_source_coverage",
    ),
    "training_models": (
        "dataset",
        "method",
        "seed",
        "fold_id",
        "inner_split_id",
    ),
}


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _policy_keys(
    group: tuple[str, str, int, str], score_names: tuple[str, ...]
) -> list[tuple[Any, ...]]:
    return [
        (*group, score_name, float(coverage))
        for score_name in score_names
        for coverage in COVERAGE_LEVELS
    ]


def _metadata_only_model_folds():
    primary, compound = metadata_only_indices()
    for index, feature_name in enumerate(main_signal_feature_names()):
        primary[feature_name] = (np.arange(len(primary), dtype=np.float32) + index) % 17
    return build_paderborn_model_folds(primary), compound


def build_expected_paderborn_selective_manifest(
    *,
    protocol_document: str,
    protocol_document_sha256: str,
    base_expected_manifest: str,
    base_expected_manifest_sha256: str,
    methods: tuple[str, ...] = METHODS,
    seeds: tuple[int, ...] = AUDIT_SEEDS,
) -> dict[str, Any]:
    model_folds, compound = _metadata_only_model_folds()
    rows: dict[str, list[tuple[Any, ...]]] = {name: [] for name in KEY_SCHEMAS}
    compound_indices = compound["full_row_index"].to_numpy(dtype=int)
    fold_records = []
    for model_fold in model_folds:
        fold = model_fold.fold
        inner_ids = tuple(split.split_id for split in build_inner_splits(fold))
        if len(inner_ids) != 3 or len(set(inner_ids)) != 3:
            raise ValueError("Paderborn selective design requires three inner splits")
        fold_records.append(
            {
                "fold_id": fold.fold_id,
                "source_rows": len(fold.source_indices),
                "target_rows": len(fold.target_indices),
                "compound_rows": len(compound_indices),
                "inner_split_ids": list(inner_ids),
            }
        )
        for method in methods:
            ensemble = ("paderborn", method, ENSEMBLE_SEED, fold.fold_id)
            rows["source_oof_ensemble_predictions"].extend(
                (*ensemble, int(row_index)) for row_index in fold.source_indices
            )
            rows["target_ensemble_predictions"].extend(
                (*ensemble, int(row_index)) for row_index in model_fold.target_global_indices
            )
            compound_ensemble = (
                "paderborn_compound",
                method,
                ENSEMBLE_SEED,
                fold.fold_id,
            )
            rows["compound_ensemble_predictions"].extend(
                (*compound_ensemble, int(row_index)) for row_index in compound_indices
            )
            ensemble_policies = _policy_keys(ensemble, ENSEMBLE_SCORE_NAMES)
            rows["policies"].extend(ensemble_policies)
            rows["policy_metrics"].extend(ensemble_policies)
            rows["compound_policy_metrics"].extend(
                ("paderborn_compound", *policy[1:]) for policy in ensemble_policies
            )
            rows["beta_selections"].append(ensemble)
            rows["ranking_metrics"].extend(
                (*ensemble, score_name) for score_name in ENSEMBLE_SCORE_NAMES
            )
            rows["selection_decisions"].extend(
                (*policy, int(row_index))
                for policy in ensemble_policies
                for row_index in model_fold.target_global_indices
            )
            rows["compound_decisions"].extend(
                ("paderborn_compound", *policy[1:], int(row_index))
                for policy in ensemble_policies
                for row_index in compound_indices
            )
            for seed in seeds:
                group = ("paderborn", method, int(seed), fold.fold_id)
                compound_group = (
                    "paderborn_compound",
                    method,
                    int(seed),
                    fold.fold_id,
                )
                rows["source_oof_predictions"].extend(
                    (*group, int(row_index)) for row_index in fold.source_indices
                )
                rows["target_predictions"].extend(
                    (*group, int(row_index)) for row_index in model_fold.target_global_indices
                )
                rows["compound_predictions"].extend(
                    (*compound_group, int(row_index)) for row_index in compound_indices
                )
                policies = _policy_keys(group, INDIVIDUAL_SCORE_NAMES)
                rows["policies"].extend(policies)
                rows["policy_metrics"].extend(policies)
                rows["compound_policy_metrics"].extend(
                    ("paderborn_compound", *policy[1:]) for policy in policies
                )
                rows["beta_selections"].append(group)
                rows["ranking_metrics"].extend(
                    (*group, score_name) for score_name in INDIVIDUAL_SCORE_NAMES
                )
                rows["selection_decisions"].extend(
                    (*policy, int(row_index))
                    for policy in policies
                    for row_index in model_fold.target_global_indices
                )
                rows["compound_decisions"].extend(
                    ("paderborn_compound", *policy[1:], int(row_index))
                    for policy in policies
                    for row_index in compound_indices
                )
                rows["training_models"].extend((*group, inner_id) for inner_id in inner_ids)
    return {
        "manifest_version": MANIFEST_VERSION,
        "role": (
            "metadata-only expected Paderborn selective topology; contains no signal "
            "feature, fitted model, score, threshold, prediction or outcome"
        ),
        "input": {
            "protocol_document": protocol_document,
            "protocol_document_sha256": protocol_document_sha256,
            "base_expected_manifest": base_expected_manifest,
            "base_expected_manifest_sha256": base_expected_manifest_sha256,
            "paderborn_archive_contents_opened_before_manifest": True,
            "structural_exclusion_informed": True,
            "signal_features_used_to_define_topology": False,
            "model_outcomes_inspected_before_manifest": False,
        },
        "configuration": {
            "methods": list(methods),
            "seeds": [int(seed) for seed in seeds],
            "ensemble_seed": ENSEMBLE_SEED,
            "outer_folds": len(model_folds),
            "inner_partitions_per_fold": 3,
            "coverage_levels": list(COVERAGE_LEVELS),
            "minimum_source_environment_coverage": (MINIMUM_SOURCE_ENVIRONMENT_COVERAGE),
            "individual_score_names": list(INDIVIDUAL_SCORE_NAMES),
            "ensemble_score_names": list(ENSEMBLE_SCORE_NAMES),
            "compound_forced_ground_truth_defined": False,
        },
        "folds": fold_records,
        "expected_key_sets": {
            name: canonical_key_record(values, KEY_SCHEMAS[name]) for name, values in rows.items()
        },
    }


def run_manifest(
    *,
    protocol_document: Path,
    expected_protocol_sha256: str,
    base_expected_manifest: Path,
    expected_base_manifest_sha256: str,
    output: Path,
) -> dict[str, Any]:
    protocol_document = protocol_document.resolve(strict=True)
    base_expected_manifest = base_expected_manifest.resolve(strict=True)
    if _sha256(protocol_document) != expected_protocol_sha256:
        raise ValueError("Paderborn selective protocol hash changed")
    if _sha256(base_expected_manifest) != expected_base_manifest_sha256:
        raise ValueError("Paderborn base expected-manifest hash changed")
    protocol_text = protocol_document.read_text(encoding="utf-8")
    for value in ("frozen", "720", "347,850", "1,382,400"):
        if value not in protocol_text:
            raise ValueError(f"Paderborn protocol does not freeze {value}")
    base = json.loads(base_expected_manifest.read_text(encoding="utf-8"))
    base_input = base.get("input", {})
    if (
        base_input.get("signal_features_used_to_define_topology") is not False
        or base_input.get("model_outcomes_inspected_before_manifest") is not False
    ):
        raise ValueError("Paderborn base manifest violates the prospective boundary")
    manifest = build_expected_paderborn_selective_manifest(
        protocol_document=str(protocol_document),
        protocol_document_sha256=expected_protocol_sha256,
        base_expected_manifest=str(base_expected_manifest),
        base_expected_manifest_sha256=expected_base_manifest_sha256,
    )
    output = output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--protocol-document", type=Path, required=True)
    parser.add_argument("--protocol-sha256", required=True)
    parser.add_argument("--base-expected-manifest", type=Path, required=True)
    parser.add_argument("--base-expected-manifest-sha256", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = run_manifest(
        protocol_document=args.protocol_document,
        expected_protocol_sha256=args.protocol_sha256,
        base_expected_manifest=args.base_expected_manifest,
        expected_base_manifest_sha256=args.base_expected_manifest_sha256,
        output=args.output,
    )
    print(json.dumps(result["expected_key_sets"], ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
