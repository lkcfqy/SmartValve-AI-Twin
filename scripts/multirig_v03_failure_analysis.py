#!/usr/bin/env python3
"""Reproduce the D0/D1/D2 failure audit and paired-scatter development probe.

Every target outcome consumed here is already observed.  Consequently, all
configuration comparisons emitted by this script are retrospective development
diagnostics and are prohibited from serving as confirmatory D3 evidence.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from itertools import combinations
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from sklearn.discriminant_analysis import LinearDiscriminantAnalysis
from sklearn.metrics import f1_score

from smartvalve.experiments.domain_data import (
    SourceOnlyFold,
    build_cranfield_folds,
    build_uci_folds,
)
from smartvalve.experiments.paderborn_domain import build_paderborn_model_folds
from smartvalve.experiments.paired_scatter_baseline import (
    fit_paired_scatter_projector,
)

SCHEMA_VERSION = "smartvalve-multirig-v03-failure-analysis-0.1.0"
SEEDS = (11, 23, 37, 53, 71)
METHODS = (
    "erm",
    "coral",
    "vrex",
    "groupdro",
    "dann",
    "lisa",
    "matchdg",
    "ccdg",
    "pirl",
)
LABELS = {
    "cranfield": ("normal", "lack_of_lubrication", "backlash"),
    "uci_hydraulic": (
        "close_to_failure",
        "severe_lag",
        "small_lag",
        "optimal",
    ),
    "paderborn": ("healthy", "outer", "inner"),
}
DEFAULT_HASHES = {
    "pirl_predictions": "a32e0b8bfa7d8a522fa7e26bb26e2ac6f4113d32e5a3589f2b5c106e6f69ed22",
    "neural_predictions": "7691980fbd47a209d79629c65bb3490ffc866645eec48f4c07509535fdfbe2d6",
    "paderborn_predictions": "5e3801e9df4636f180e85ccde060fade77422dfbcb65d5699bf7a93a49d9b400",
    "uci_features": "4359ce099e421cc9e55c65115d39f4a4c0463255f72f834a49d802fa6a038516",
    "paderborn_features": "c5caf0cfc408057ae4bfaebef37abdf597135620105ec62e17f3aece6800aff4",
}
PROBABILITY_COLUMNS = tuple(f"probability_{index}" for index in range(4))
PAIR_COMPONENTS = (4, 8, 16, 32, 64)
PAIR_RIDGES_K4 = (1e-6, 3e-6, 1e-5, 3e-5, 1e-4, 3e-4, 1e-3, 3e-3, 1e-2, 1e-1, 1.0)
BLEND_WEIGHTS = tuple(np.linspace(0.0, 1.0, 21).round(2))


@dataclass(frozen=True)
class FoldWithGlobalTarget:
    fold: SourceOnlyFold
    global_target_indices: np.ndarray


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _verify_input(path: Path, expected_sha256: str, *, role: str) -> str:
    if not path.is_file():
        raise FileNotFoundError(f"missing {role}: {path}")
    observed = _sha256(path)
    if observed != expected_sha256:
        raise ValueError(
            f"{role} SHA-256 changed: expected {expected_sha256}, observed {observed}"
        )
    return observed


def _write_json(path: Path, value: Any) -> None:
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _write_csv(path: Path, frame: pd.DataFrame) -> None:
    frame.to_csv(path, index=False, float_format="%.12g", lineterminator="\n")


def _macro_f1(truth: np.ndarray, probabilities: np.ndarray, class_count: int) -> float:
    predictions = np.argmax(probabilities, axis=1)
    return float(
        f1_score(
            truth,
            predictions,
            labels=np.arange(class_count),
            average="macro",
            zero_division=0,
        )
    )


def _canonical_prediction_frame(
    neural_path: Path,
    pirl_path: Path,
    paderborn_path: Path,
) -> pd.DataFrame:
    frames = [
        pd.read_parquet(neural_path),
        pd.read_parquet(pirl_path),
        pd.read_parquet(paderborn_path),
    ]
    records: list[pd.DataFrame] = []
    for source in frames:
        source = source.copy()
        source["method"] = source["method"].replace({"pirl_ratio": "pirl"})
        for dataset, labels in LABELS.items():
            subset = source.loc[source["dataset"].astype(str) == dataset].copy()
            if subset.empty:
                continue
            required = {
                "method",
                "seed",
                "fold_id",
                "row_index",
                "truth",
                *(f"probability_{label}" for label in labels),
            }
            missing = required - set(subset.columns)
            if missing:
                raise ValueError(
                    f"{dataset} predictions are missing columns: {sorted(missing)}"
                )
            label_index = {label: index for index, label in enumerate(labels)}
            encoded = subset["truth"].map(label_index)
            if encoded.isna().any():
                raise ValueError(f"{dataset} predictions contain an unexpected truth label")
            canonical = subset.loc[
                :, ["method", "seed", "fold_id", "row_index"]
            ].copy()
            canonical.insert(0, "dataset", dataset)
            canonical["truth"] = encoded.to_numpy(dtype=np.int64)
            for index, label in enumerate(labels):
                canonical[PROBABILITY_COLUMNS[index]] = subset[
                    f"probability_{label}"
                ].to_numpy(dtype=np.float64)
            for index in range(len(labels), len(PROBABILITY_COLUMNS)):
                canonical[PROBABILITY_COLUMNS[index]] = np.nan
            records.append(canonical)
    predictions = pd.concat(records, ignore_index=True)
    if set(predictions["method"].astype(str)) != set(METHODS):
        raise ValueError("the frozen nine-method prediction set changed")
    if set(predictions["seed"].astype(int)) != set(SEEDS):
        raise ValueError("the frozen five-seed prediction set changed")
    keys = ["dataset", "method", "seed", "fold_id", "row_index"]
    if predictions.duplicated(keys).any():
        raise ValueError("prediction inputs contain duplicate model/fold/row keys")
    for dataset, labels in LABELS.items():
        subset = predictions.loc[predictions["dataset"] == dataset]
        expected_methods = set(METHODS)
        if set(subset["method"].astype(str)) != expected_methods:
            raise ValueError(f"{dataset} does not contain all frozen methods")
        values = subset.loc[:, PROBABILITY_COLUMNS[: len(labels)]].to_numpy(dtype=float)
        if not np.isfinite(values).all():
            raise ValueError(f"{dataset} contains non-finite class probabilities")
        if float(np.max(np.abs(values.sum(axis=1) - 1.0))) > 2e-6:
            raise ValueError(f"{dataset} probabilities do not sum to one")
    return predictions.sort_values(keys, kind="stable").reset_index(drop=True)


def _seed_ensemble(predictions: pd.DataFrame) -> pd.DataFrame:
    keys = ["dataset", "method", "fold_id", "row_index", "truth"]
    ensemble = (
        predictions.groupby(keys, sort=True, observed=True)[list(PROBABILITY_COLUMNS)]
        .mean()
        .reset_index()
    )
    counts = predictions.groupby(keys, sort=False, observed=True)["seed"].nunique()
    if not (counts == len(SEEDS)).all():
        raise ValueError("a seed ensemble does not contain exactly five members")
    return ensemble


def _fold_and_pooled_metrics(
    rows: pd.DataFrame,
    *,
    method_column: str,
    evaluation_unit: str,
) -> pd.DataFrame:
    output = []
    for (dataset, method), group in rows.groupby(
        ["dataset", method_column], sort=True, observed=True
    ):
        class_count = len(LABELS[str(dataset)])
        probabilities = group.loc[
            :, PROBABILITY_COLUMNS[:class_count]
        ].to_numpy(dtype=float)
        fold_values = []
        for fold_id, fold in group.groupby("fold_id", sort=True, observed=True):
            fold_probabilities = fold.loc[
                :, PROBABILITY_COLUMNS[:class_count]
            ].to_numpy(dtype=float)
            value = _macro_f1(
                fold["truth"].to_numpy(dtype=int),
                fold_probabilities,
                class_count,
            )
            fold_values.append(value)
            output.append(
                {
                    "dataset": dataset,
                    "method": method,
                    "evaluation_unit": evaluation_unit,
                    "fold_id": fold_id,
                    "macro_f1": value,
                    "sample_count": len(fold),
                }
            )
        output.append(
            {
                "dataset": dataset,
                "method": method,
                "evaluation_unit": evaluation_unit,
                "fold_id": "__pooled__",
                "macro_f1": _macro_f1(
                    group["truth"].to_numpy(dtype=int),
                    probabilities,
                    class_count,
                ),
                "sample_count": len(group),
            }
        )
        output.append(
            {
                "dataset": dataset,
                "method": method,
                "evaluation_unit": evaluation_unit,
                "fold_id": "__mean_fold__",
                "macro_f1": float(np.mean(fold_values)),
                "sample_count": len(group),
            }
        )
        output.append(
            {
                "dataset": dataset,
                "method": method,
                "evaluation_unit": evaluation_unit,
                "fold_id": "__minimum_fold__",
                "macro_f1": float(np.min(fold_values)),
                "sample_count": len(group),
            }
        )
    return pd.DataFrame(output)


def _probability_tensor(
    ensemble: pd.DataFrame,
    *,
    dataset: str,
) -> tuple[pd.DataFrame, np.ndarray]:
    subset = ensemble.loc[ensemble["dataset"] == dataset]
    keys = ["fold_id", "row_index", "truth"]
    reference = (
        subset.loc[subset["method"] == METHODS[0], keys]
        .sort_values(keys, kind="stable")
        .reset_index(drop=True)
    )
    tensors = []
    class_count = len(LABELS[dataset])
    for method in METHODS:
        current = (
            subset.loc[subset["method"] == method]
            .sort_values(keys, kind="stable")
            .reset_index(drop=True)
        )
        if not current.loc[:, keys].equals(reference):
            raise ValueError(f"{dataset} method predictions do not share target keys")
        tensors.append(
            current.loc[:, PROBABILITY_COLUMNS[:class_count]].to_numpy(dtype=float)
        )
    return reference, np.stack(tensors, axis=0)


def _all_equal_weight_subsets(ensemble: pd.DataFrame) -> pd.DataFrame:
    records = []
    for dataset in LABELS:
        keys, tensor = _probability_tensor(ensemble, dataset=dataset)
        class_count = len(LABELS[dataset])
        truth = keys["truth"].to_numpy(dtype=int)
        folds = keys["fold_id"].astype(str).to_numpy()
        for count in range(1, len(METHODS) + 1):
            for indices in combinations(range(len(METHODS)), count):
                probabilities = tensor[list(indices)].mean(axis=0)
                fold_scores = [
                    _macro_f1(
                        truth[folds == fold_id],
                        probabilities[folds == fold_id],
                        class_count,
                    )
                    for fold_id in sorted(set(folds))
                ]
                records.append(
                    {
                        "dataset": dataset,
                        "subset": "+".join(METHODS[index] for index in indices),
                        "method_count": count,
                        "pooled_macro_f1": _macro_f1(
                            truth, probabilities, class_count
                        ),
                        "mean_fold_macro_f1": float(np.mean(fold_scores)),
                        "minimum_fold_macro_f1": float(np.min(fold_scores)),
                    }
                )
    frame = pd.DataFrame(records)
    aggregate = (
        frame.groupby(["subset", "method_count"], sort=True, observed=True)[
            [
                "pooled_macro_f1",
                "mean_fold_macro_f1",
                "minimum_fold_macro_f1",
            ]
        ]
        .mean()
        .reset_index()
    )
    aggregate.insert(0, "dataset", "mean_d0_d1_d2")
    return pd.concat((frame, aggregate), ignore_index=True)


def _standardized_lda_probabilities(
    source: np.ndarray,
    labels: np.ndarray,
    target: np.ndarray,
) -> np.ndarray:
    mean = source.mean(axis=0)
    raw_scale = source.std(axis=0, ddof=0)
    scale = np.where(raw_scale > 1e-12, raw_scale, 1.0)
    classifier = LinearDiscriminantAnalysis(solver="lsqr", shrinkage="auto")
    classifier.fit((source - mean) / scale, labels)
    expected_classes = np.arange(len(np.unique(labels)))
    if not np.array_equal(classifier.classes_, expected_classes):
        raise ValueError("raw shrinkage-LDA class order changed")
    return classifier.predict_proba((target - mean) / scale)


def _fold_collections(
    uci_features: pd.DataFrame,
    paderborn_features: pd.DataFrame,
) -> dict[str, list[FoldWithGlobalTarget]]:
    cranfield = [
        FoldWithGlobalTarget(fold=fold, global_target_indices=fold.target_indices)
        for fold in build_cranfield_folds()
    ]
    uci = [
        FoldWithGlobalTarget(fold=fold, global_target_indices=fold.target_indices)
        for fold in build_uci_folds(uci_features)
    ]
    paderborn = [
        FoldWithGlobalTarget(
            fold=model_fold.fold,
            global_target_indices=model_fold.target_global_indices,
        )
        for model_fold in build_paderborn_model_folds(paderborn_features)
    ]
    return {"cranfield": cranfield, "uci_hydraulic": uci, "paderborn": paderborn}


def _paired_scatter_probe(
    folds_by_dataset: dict[str, list[FoldWithGlobalTarget]],
) -> tuple[pd.DataFrame, pd.DataFrame]:
    prediction_records: list[pd.DataFrame] = []
    for dataset, fold_records in folds_by_dataset.items():
        class_count = len(LABELS[dataset])
        for record in fold_records:
            fold = record.fold
            maximum = min(max(PAIR_COMPONENTS), fold.source_features.shape[1])
            projector = fit_paired_scatter_projector(
                fold.source_features,
                fold.nuisance_pairs,
                fold.fault_pairs,
                max_components=maximum,
                ridge=1e-3,
            )
            configurations: dict[str, np.ndarray] = {
                "raw_shrinkage_lda": _standardized_lda_probabilities(
                    fold.source_features,
                    fold.source_labels,
                    fold.target_features,
                )
            }
            for count in PAIR_COMPONENTS:
                if count > maximum:
                    continue
                source_projection = projector.transform(
                    fold.source_features,
                    n_components=count,
                )
                target_projection = projector.transform(
                    fold.target_features,
                    n_components=count,
                )
                classifier = LinearDiscriminantAnalysis(solver="lsqr", shrinkage="auto")
                classifier.fit(source_projection, fold.source_labels)
                if not np.array_equal(classifier.classes_, np.arange(class_count)):
                    raise ValueError("paired-scatter LDA class order changed")
                configurations[f"paired_scatter_k{count}"] = classifier.predict_proba(
                    target_projection
                )
            for configuration, probabilities in configurations.items():
                rows = pd.DataFrame(
                    {
                        "dataset": dataset,
                        "configuration": configuration,
                        "fold_id": fold.fold_id,
                        "row_index": record.global_target_indices,
                        "truth": fold.target_labels,
                    }
                )
                for index in range(class_count):
                    rows[PROBABILITY_COLUMNS[index]] = probabilities[:, index]
                for index in range(class_count, len(PROBABILITY_COLUMNS)):
                    rows[PROBABILITY_COLUMNS[index]] = np.nan
                prediction_records.append(rows)
    predictions = pd.concat(prediction_records, ignore_index=True)
    metrics = _fold_and_pooled_metrics(
        predictions,
        method_column="configuration",
        evaluation_unit="retrospective_target_probe",
    )
    return predictions, metrics


def _paired_scatter_ridge_sensitivity(
    folds_by_dataset: dict[str, list[FoldWithGlobalTarget]],
) -> pd.DataFrame:
    """Evaluate a predeclared k=4 ridge grid as a target-aware stability audit."""

    prediction_records: list[pd.DataFrame] = []
    for dataset, fold_records in folds_by_dataset.items():
        class_count = len(LABELS[dataset])
        for ridge in PAIR_RIDGES_K4:
            configuration = f"paired_scatter_k4_ridge_{ridge:.0e}"
            for record in fold_records:
                fold = record.fold
                projector = fit_paired_scatter_projector(
                    fold.source_features,
                    fold.nuisance_pairs,
                    fold.fault_pairs,
                    max_components=4,
                    ridge=ridge,
                )
                source_projection = projector.transform(
                    fold.source_features,
                    n_components=4,
                )
                target_projection = projector.transform(
                    fold.target_features,
                    n_components=4,
                )
                classifier = LinearDiscriminantAnalysis(solver="lsqr", shrinkage="auto")
                classifier.fit(source_projection, fold.source_labels)
                if not np.array_equal(classifier.classes_, np.arange(class_count)):
                    raise ValueError("ridge-sensitivity LDA class order changed")
                probabilities = classifier.predict_proba(target_projection)
                rows = pd.DataFrame(
                    {
                        "dataset": dataset,
                        "configuration": configuration,
                        "ridge": ridge,
                        "fold_id": fold.fold_id,
                        "row_index": record.global_target_indices,
                        "truth": fold.target_labels,
                    }
                )
                for index in range(class_count):
                    rows[PROBABILITY_COLUMNS[index]] = probabilities[:, index]
                for index in range(class_count, len(PROBABILITY_COLUMNS)):
                    rows[PROBABILITY_COLUMNS[index]] = np.nan
                prediction_records.append(rows)
    predictions = pd.concat(prediction_records, ignore_index=True)
    metrics = _fold_and_pooled_metrics(
        predictions,
        method_column="configuration",
        evaluation_unit="retrospective_k4_ridge_sensitivity",
    )
    ridge_by_configuration = predictions.loc[
        :, ["configuration", "ridge"]
    ].drop_duplicates()
    metrics = metrics.merge(
        ridge_by_configuration,
        left_on="method",
        right_on="configuration",
        how="left",
        validate="many_to_one",
    ).drop(columns="configuration")
    aggregate_source = metrics.loc[
        metrics["fold_id"].isin(
            ["__pooled__", "__mean_fold__", "__minimum_fold__"]
        )
    ]
    aggregate = (
        aggregate_source.groupby(
            ["method", "ridge", "fold_id", "evaluation_unit"],
            sort=True,
            observed=True,
        )
        .agg(
            macro_f1=("macro_f1", "mean"),
            sample_count=("sample_count", "sum"),
        )
        .reset_index()
    )
    aggregate.insert(0, "dataset", "mean_d0_d1_d2")
    return pd.concat((metrics, aggregate), ignore_index=True)


def _score_probability_rows(
    keys: pd.DataFrame,
    probabilities: np.ndarray,
    *,
    class_count: int,
) -> tuple[float, float, float]:
    truth = keys["truth"].to_numpy(dtype=int)
    folds = keys["fold_id"].astype(str).to_numpy()
    fold_scores = [
        _macro_f1(
            truth[folds == fold_id],
            probabilities[folds == fold_id],
            class_count,
        )
        for fold_id in sorted(set(folds))
    ]
    return (
        _macro_f1(truth, probabilities, class_count),
        float(np.mean(fold_scores)),
        float(np.min(fold_scores)),
    )


def _paired_scatter_blends(
    ensemble: pd.DataFrame,
    probe_predictions: pd.DataFrame,
) -> pd.DataFrame:
    records = []
    for dataset in LABELS:
        class_count = len(LABELS[dataset])
        key_columns = ["fold_id", "row_index", "truth"]
        paired = (
            probe_predictions.loc[
                (probe_predictions["dataset"] == dataset)
                & (probe_predictions["configuration"] == "paired_scatter_k4")
            ]
            .sort_values(key_columns, kind="stable")
            .reset_index(drop=True)
        )
        paired_probabilities = paired.loc[
            :, PROBABILITY_COLUMNS[:class_count]
        ].to_numpy(dtype=float)
        for method in METHODS:
            neural = (
                ensemble.loc[
                    (ensemble["dataset"] == dataset)
                    & (ensemble["method"] == method)
                ]
                .sort_values(key_columns, kind="stable")
                .reset_index(drop=True)
            )
            if not neural.loc[:, key_columns].equals(paired.loc[:, key_columns]):
                raise ValueError(f"{dataset} paired-scatter/neural target keys differ")
            neural_probabilities = neural.loc[
                :, PROBABILITY_COLUMNS[:class_count]
            ].to_numpy(dtype=float)
            for weight in BLEND_WEIGHTS:
                probabilities = (
                    float(weight) * paired_probabilities
                    + (1.0 - float(weight)) * neural_probabilities
                )
                pooled, mean_fold, minimum_fold = _score_probability_rows(
                    neural,
                    probabilities,
                    class_count=class_count,
                )
                records.append(
                    {
                        "dataset": dataset,
                        "neural_method": method,
                        "paired_scatter_weight": float(weight),
                        "pooled_macro_f1": pooled,
                        "mean_fold_macro_f1": mean_fold,
                        "minimum_fold_macro_f1": minimum_fold,
                    }
                )
    frame = pd.DataFrame(records)
    aggregate = (
        frame.groupby(
            ["neural_method", "paired_scatter_weight"],
            sort=True,
            observed=True,
        )[
            [
                "pooled_macro_f1",
                "mean_fold_macro_f1",
                "minimum_fold_macro_f1",
            ]
        ]
        .mean()
        .reset_index()
    )
    aggregate.insert(0, "dataset", "mean_d0_d1_d2")
    return pd.concat((frame, aggregate), ignore_index=True)


def _metric_lookup(
    metrics: pd.DataFrame,
    *,
    dataset: str,
    method: str,
    fold_id: str,
) -> float:
    rows = metrics.loc[
        (metrics["dataset"] == dataset)
        & (metrics["method"] == method)
        & (metrics["fold_id"] == fold_id),
        "macro_f1",
    ]
    if len(rows) != 1:
        raise ValueError(f"metric key is not unique: {dataset}/{method}/{fold_id}")
    return float(rows.iloc[0])


def _best_record(frame: pd.DataFrame, value: str) -> dict[str, Any]:
    row = frame.sort_values(
        [value, "dataset", "subset"],
        ascending=[False, True, True],
        kind="stable",
    ).iloc[0]
    result: dict[str, Any] = {}
    for key, item in row.to_dict().items():
        if isinstance(item, np.integer):
            result[key] = int(item)
        elif isinstance(item, (np.floating, float)):
            result[key] = float(item)
        else:
            result[key] = item
    return result


def _analysis_summary(
    input_hashes: dict[str, str],
    method_metrics: pd.DataFrame,
    subset_metrics: pd.DataFrame,
    probe_metrics: pd.DataFrame,
    blend_metrics: pd.DataFrame,
    ridge_sensitivity: pd.DataFrame,
) -> dict[str, Any]:
    worst_folds = []
    ordinary_folds = method_metrics.loc[
        ~method_metrics["fold_id"].astype(str).str.startswith("__")
    ]
    for (dataset, method), group in ordinary_folds.groupby(
        ["dataset", "method"], sort=True, observed=True
    ):
        row = group.sort_values(
            ["macro_f1", "fold_id"], kind="stable"
        ).iloc[0]
        worst_folds.append(
            {
                "dataset": dataset,
                "method": method,
                "fold_id": row["fold_id"],
                "macro_f1": float(row["macro_f1"]),
            }
        )
    single_aggregate = subset_metrics.loc[
        (subset_metrics["dataset"] == "mean_d0_d1_d2")
        & (subset_metrics["method_count"] == 1)
    ]
    all_aggregate = subset_metrics.loc[
        subset_metrics["dataset"] == "mean_d0_d1_d2"
    ]
    paired_summary = {}
    normalized_probe = probe_metrics.rename(columns={"method": "configuration"})
    for dataset in LABELS:
        paired_summary[dataset] = {
            key: _metric_lookup(
                normalized_probe.rename(columns={"configuration": "method"}),
                dataset=dataset,
                method="paired_scatter_k4",
                fold_id=fold_id,
            )
            for key, fold_id in (
                ("pooled_macro_f1", "__pooled__"),
                ("mean_fold_macro_f1", "__mean_fold__"),
                ("minimum_fold_macro_f1", "__minimum_fold__"),
            )
        }
    aggregate_blends = blend_metrics.loc[
        blend_metrics["dataset"] == "mean_d0_d1_d2"
    ]
    best_blend_row = aggregate_blends.sort_values(
        ["minimum_fold_macro_f1", "pooled_macro_f1", "neural_method"],
        ascending=[False, False, True],
        kind="stable",
    ).iloc[0]
    ridge_aggregate = ridge_sensitivity.loc[
        (ridge_sensitivity["dataset"] == "mean_d0_d1_d2")
        & (ridge_sensitivity["fold_id"] == "__minimum_fold__")
    ]
    best_ridge_row = ridge_aggregate.sort_values(
        ["macro_f1", "ridge"],
        ascending=[False, True],
        kind="stable",
    ).iloc[0]
    ridge_values = ridge_aggregate.sort_values("ridge", kind="stable")
    return {
        "schema_version": SCHEMA_VERSION,
        "status": "retrospective_development_only",
        "confirmatory_use_prohibited": True,
        "inputs": input_hashes,
        "frozen_methods": list(METHODS),
        "frozen_seeds": list(SEEDS),
        "development_datasets": list(LABELS),
        "worst_seed_ensemble_fold_by_method": worst_folds,
        "equal_weight_ensemble_search": {
            "subsets_evaluated_per_dataset": 2 ** len(METHODS) - 1,
            "best_single_by_cross_dataset_mean_minimum_fold": _best_record(
                single_aggregate, "minimum_fold_macro_f1"
            ),
            "best_subset_by_cross_dataset_mean_minimum_fold": _best_record(
                all_aggregate, "minimum_fold_macro_f1"
            ),
        },
        "paired_scatter_k4": paired_summary,
        "paired_scatter_k4_ridge_sensitivity": {
            "target_outcome_informed": True,
            "confirmatory_use_prohibited": True,
            "grid": list(PAIR_RIDGES_K4),
            "best_cross_dataset_mean_minimum_fold": {
                "ridge": float(best_ridge_row["ridge"]),
                "macro_f1": float(best_ridge_row["macro_f1"]),
            },
            "cross_dataset_mean_minimum_fold_range": [
                float(ridge_values["macro_f1"].min()),
                float(ridge_values["macro_f1"].max()),
            ],
        },
        "best_fixed_probability_blend_by_cross_dataset_mean_minimum_fold": {
            key: (float(value) if isinstance(value, (float, np.floating)) else value)
            for key, value in best_blend_row.to_dict().items()
        },
        "interpretation": [
            "PIRL v0.2 does not establish a replicated closed-set or selective advantage.",
            (
                "Equal-weight method selection/ensembling does not remove the "
                "physical-group tail failure."
            ),
            (
                "The paired-scatter probe strongly repairs the UCI tail but lies "
                "on a cross-dataset Pareto front."
            ),
            (
                "The generalized-eigenvalue construction overlaps established "
                "discriminant and domain-invariant subspace methods and is therefore "
                "a baseline, not a novelty claim."
            ),
            (
                "Paderborn is development data for every method choice made after "
                "EXP-417; a fresh sealed D3 is mandatory for prospective evidence."
            ),
        ],
    }


def _expected_hash_arguments(parser: argparse.ArgumentParser) -> None:
    for role, value in DEFAULT_HASHES.items():
        parser.add_argument(
            f"--expected-{role.replace('_', '-')}-sha256",
            default=value,
        )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--neural-predictions", type=Path, required=True)
    parser.add_argument("--pirl-predictions", type=Path, required=True)
    parser.add_argument("--paderborn-predictions", type=Path, required=True)
    parser.add_argument("--uci-features", type=Path, required=True)
    parser.add_argument("--paderborn-features", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    _expected_hash_arguments(parser)
    return parser


def _iter_roles(arguments: argparse.Namespace) -> Iterable[tuple[str, Path, str]]:
    for role in DEFAULT_HASHES:
        yield (
            role,
            getattr(arguments, role),
            getattr(arguments, f"expected_{role}_sha256"),
        )


def main(argv: Sequence[str] | None = None) -> int:
    arguments = build_parser().parse_args(argv)
    arguments.output_dir.mkdir(parents=True, exist_ok=True)
    if any(arguments.output_dir.iterdir()):
        raise ValueError("output directory must be empty")
    input_hashes = {
        role: _verify_input(path, expected, role=role)
        for role, path, expected in _iter_roles(arguments)
    }
    predictions = _canonical_prediction_frame(
        arguments.neural_predictions,
        arguments.pirl_predictions,
        arguments.paderborn_predictions,
    )
    seed_ensemble = _seed_ensemble(predictions)
    method_metrics = _fold_and_pooled_metrics(
        seed_ensemble,
        method_column="method",
        evaluation_unit="five_seed_probability_ensemble",
    )
    subset_metrics = _all_equal_weight_subsets(seed_ensemble)
    uci_features = pd.read_parquet(arguments.uci_features)
    paderborn_features = pd.read_parquet(arguments.paderborn_features)
    folds = _fold_collections(uci_features, paderborn_features)
    probe_predictions, probe_metrics = _paired_scatter_probe(folds)
    ridge_sensitivity = _paired_scatter_ridge_sensitivity(folds)
    blend_metrics = _paired_scatter_blends(seed_ensemble, probe_predictions)
    summary = _analysis_summary(
        input_hashes,
        method_metrics,
        subset_metrics,
        probe_metrics,
        blend_metrics,
        ridge_sensitivity,
    )
    _write_csv(arguments.output_dir / "method_fold_metrics.csv", method_metrics)
    _write_csv(arguments.output_dir / "ensemble_subsets.csv", subset_metrics)
    _write_csv(arguments.output_dir / "paired_scatter_probe_metrics.csv", probe_metrics)
    _write_csv(
        arguments.output_dir / "paired_scatter_ridge_sensitivity.csv",
        ridge_sensitivity,
    )
    _write_csv(arguments.output_dir / "paired_scatter_blend_grid.csv", blend_metrics)
    _write_json(arguments.output_dir / "failure_analysis.json", summary)
    print(json.dumps(summary, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
