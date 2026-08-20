"""Audit Cranfield fault predictions under three healthy-reference access policies.

The experiment changes only the information available for feature construction while preserving
the motion-specific leave-one-load-out split and ExtraTrees estimator family. It is a falsification
audit for nuisance sensitivity, not proof that any representation is causal.
"""

from __future__ import annotations

import argparse
import json
from collections.abc import Iterable, Sequence
from datetime import UTC, datetime
from itertools import combinations
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import sklearn
from sklearn.ensemble import ExtraTreesClassifier
from sklearn.impute import SimpleImputer
from sklearn.metrics import (
    accuracy_score,
    confusion_matrix,
    f1_score,
    precision_recall_fscore_support,
)
from sklearn.pipeline import Pipeline

from smartvalve.config import project_root
from smartvalve.data.cranfield import load_cranfield_frame
from smartvalve.data.external import cache_directory
from smartvalve.experiments.cranfield_benchmark import (
    FILES,
    LABELS,
    LOADS,
    MOTIONS,
    REPETITIONS,
    _file_sha256,
    _raw_features,
)

AUDIT_VERSION = "cranfield-reference-audit-0.1.1"
AUDIT_SEEDS = (11, 23, 37, 53, 71)
PROTOCOLS = {
    "P0": "raw_no_target_reference",
    "P1": "source_linear_healthy_reference",
    "P2": "matched_target_healthy_reference",
}
METADATA_COLUMNS = ("motion", "load_kg", "repetition", "truth")
SUMMARY_METRICS = (
    "accuracy",
    "macro_f1",
    "worst_fold_macro_f1",
    "multiclass_brier",
    "ece_10_bin",
    "maximum_calibration_error",
    "mean_confidence",
    "nuisance_sensitivity_tv",
    "fault_sensitivity_tv",
    "control_ratio",
)
BALANCED_RANDOM_GUESS_ACCURACY = 1.0 / len(LABELS)


def build_raw_matrix() -> pd.DataFrame:
    """Extract one row of raw interpretable features for each complete physical trial."""

    rows: list[dict[str, Any]] = []
    for motion in MOTIONS:
        for label, filename in FILES.items():
            for load_kg in LOADS:
                for repetition in REPETITIONS:
                    frame = load_cranfield_frame(
                        filename,
                        motion=motion,
                        load_kg=load_kg,
                        repetition=repetition,
                    )
                    rows.append(
                        {
                            "motion": motion,
                            "load_kg": load_kg,
                            "repetition": repetition,
                            "truth": label,
                            **_raw_features(frame),
                        }
                    )
    return pd.DataFrame(rows)


def raw_feature_columns(raw: pd.DataFrame) -> list[str]:
    """Return raw feature names in their frozen extraction order."""

    metadata = set(METADATA_COLUMNS)
    return [column for column in raw.columns if column not in metadata]


def source_linear_reference(
    raw: pd.DataFrame,
    source_indices: Sequence[int] | pd.Index,
    row_index: int,
    feature_columns: Sequence[str],
) -> np.ndarray:
    """Predict a row's healthy reference from source-load normal trials only.

    The mean healthy feature at each of the two source loads defines a line evaluated at the row's
    known load. A normal source row is excluded from its own load mean, giving a leave-one-trial-out
    training reference. Target-load rows can never enter the reference pool.
    """

    source = raw.loc[list(source_indices)]
    healthy = source.loc[source["truth"] == "normal"]
    row = raw.loc[row_index]
    if row_index in healthy.index:
        healthy = healthy.drop(index=row_index)
    means = healthy.groupby("load_kg", sort=True)[list(feature_columns)].mean()
    if len(means) != 2:
        raise ValueError("P1 requires healthy trials from exactly two source loads")
    source_loads = means.index.to_numpy(dtype=float)
    values = means.to_numpy(dtype=float)
    load_span = source_loads[1] - source_loads[0]
    if load_span == 0:
        raise ValueError("P1 source loads must be distinct")
    weight = (float(row["load_kg"]) - source_loads[0]) / load_span
    return values[0] + weight * (values[1] - values[0])


def _relative_feature_frame(
    current: np.ndarray,
    reference: np.ndarray,
    feature_columns: Sequence[str],
    index: pd.Index,
) -> pd.DataFrame:
    delta = current - reference
    relative = delta / (np.abs(reference) + 1e-6)
    values = np.empty((len(index), len(feature_columns) * 2), dtype=float)
    values[:, 0::2] = delta
    values[:, 1::2] = relative
    columns = [
        name
        for feature in feature_columns
        for name in (f"delta_{feature}", f"relative_{feature}")
    ]
    return pd.DataFrame(values, index=index, columns=columns)


def _matched_target_references(
    raw: pd.DataFrame,
    row_indices: pd.Index,
    feature_columns: Sequence[str],
) -> tuple[np.ndarray, list[int]]:
    normal = raw.loc[raw["truth"] == "normal"]
    lookup = {
        (str(row["motion"]), int(row["load_kg"]), int(row["repetition"])): row[
            list(feature_columns)
        ].to_numpy(dtype=float)
        for _, row in normal.iterrows()
    }
    references: list[np.ndarray] = []
    baseline_repetitions: list[int] = []
    for row_index in row_indices:
        row = raw.loc[row_index]
        baseline_repetition = int(row["repetition"]) % len(REPETITIONS) + 1
        key = (str(row["motion"]), int(row["load_kg"]), baseline_repetition)
        references.append(lookup[key])
        baseline_repetitions.append(baseline_repetition)
    return np.vstack(references), baseline_repetitions


def protocol_feature_frame(
    raw: pd.DataFrame,
    protocol: str,
    row_indices: pd.Index,
    source_indices: pd.Index,
    feature_columns: Sequence[str],
) -> tuple[pd.DataFrame, list[int | None]]:
    """Construct fold-specific features without fitting an estimator or imputer."""

    current = raw.loc[row_indices, list(feature_columns)].to_numpy(dtype=float)
    if protocol == "P0":
        features = pd.DataFrame(current, index=row_indices, columns=list(feature_columns))
        baseline_repetitions: list[int | None] = [None] * len(row_indices)
    elif protocol == "P1":
        references = np.vstack(
            [
                source_linear_reference(raw, source_indices, int(index), feature_columns)
                for index in row_indices
            ]
        )
        features = _relative_feature_frame(current, references, feature_columns, row_indices)
        baseline_repetitions = [None] * len(row_indices)
    elif protocol == "P2":
        references, matched_repetitions = _matched_target_references(
            raw, row_indices, feature_columns
        )
        features = _relative_feature_frame(current, references, feature_columns, row_indices)
        baseline_repetitions = list(matched_repetitions)
    else:
        raise ValueError(f"unknown protocol: {protocol}")
    return features.replace([np.inf, -np.inf], np.nan), baseline_repetitions


def calibration_metrics(
    truth: Sequence[str], probabilities: np.ndarray, *, bins: int = 10
) -> dict[str, float]:
    """Compute confidence calibration diagnostics using equal-width bins."""

    truth_array = np.asarray(truth, dtype=object)
    confidence = probabilities.max(axis=1)
    predicted = np.asarray(LABELS, dtype=object)[probabilities.argmax(axis=1)]
    correct = predicted == truth_array
    bin_ids = np.minimum((confidence * bins).astype(int), bins - 1)
    weighted_error = 0.0
    maximum_error = 0.0
    for bin_id in range(bins):
        mask = bin_ids == bin_id
        if not np.any(mask):
            continue
        gap = abs(float(correct[mask].mean()) - float(confidence[mask].mean()))
        weighted_error += float(mask.mean()) * gap
        maximum_error = max(maximum_error, gap)
    return {
        "ece_10_bin": weighted_error,
        "maximum_calibration_error": maximum_error,
        "mean_confidence": float(confidence.mean()),
    }


def _mean_pairwise_total_variation(
    records: pd.DataFrame, group_columns: Sequence[str]
) -> tuple[float, int]:
    probability_columns = [f"probability_{label}" for label in LABELS]
    distances: list[float] = []
    for _, group in records.groupby(list(group_columns), sort=False):
        probabilities = group.loc[:, probability_columns].to_numpy(dtype=float)
        for left, right in combinations(probabilities, 2):
            distances.append(float(0.5 * np.abs(left - right).sum()))
    if not distances:
        raise ValueError("control metric requires at least one matched pair")
    return float(np.mean(distances)), len(distances)


def control_metrics(records: pd.DataFrame) -> dict[str, float | int | bool | None]:
    """Compare label-preserving load changes with fault-state changes."""

    nuisance, nuisance_pairs = _mean_pairwise_total_variation(
        records, ("motion", "truth", "repetition")
    )
    fault, fault_pairs = _mean_pairwise_total_variation(
        records, ("motion", "load_kg", "repetition")
    )
    ratio = nuisance / fault if fault > 0 else None
    return {
        "nuisance_sensitivity_tv": nuisance,
        "fault_sensitivity_tv": fault,
        "control_ratio": ratio,
        "negative_control_pass": bool(ratio is not None and ratio < 1.0),
        "nuisance_pairs": nuisance_pairs,
        "fault_pairs": fault_pairs,
    }


def _aligned_probabilities(classifier: Pipeline, features: pd.DataFrame) -> np.ndarray:
    raw_probabilities = classifier.predict_proba(features)
    estimator = classifier.named_steps["estimator"]
    aligned = np.zeros((len(features), len(LABELS)), dtype=float)
    for source_column, label in enumerate(estimator.classes_):
        aligned[:, LABELS.index(str(label))] = raw_probabilities[:, source_column]
    return aligned


def _fold_record(
    raw: pd.DataFrame,
    test_indices: pd.Index,
    protocol: str,
    seed: int,
    baseline_repetitions: Sequence[int | None],
    predictions: np.ndarray,
    probabilities: np.ndarray,
) -> pd.DataFrame:
    records = raw.loc[test_indices, list(METADATA_COLUMNS)].copy()
    records.insert(0, "protocol_name", PROTOCOLS[protocol])
    records.insert(0, "protocol", protocol)
    records.insert(2, "seed", seed)
    records["baseline_repetition"] = [
        repetition if repetition is not None else "" for repetition in baseline_repetitions
    ]
    records["prediction"] = predictions
    records["correct"] = records["truth"].to_numpy(dtype=object) == predictions
    records["confidence"] = probabilities.max(axis=1)
    for column, label in enumerate(LABELS):
        records[f"probability_{label}"] = probabilities[:, column]
    return records


def _seed_metrics(
    records: pd.DataFrame, fold_metrics: list[dict[str, Any]]
) -> dict[str, Any]:
    truth = records["truth"].to_numpy(dtype=object)
    prediction = records["prediction"].to_numpy(dtype=object)
    probabilities = records.loc[
        :, [f"probability_{label}" for label in LABELS]
    ].to_numpy(dtype=float)
    one_hot = np.column_stack([truth == label for label in LABELS]).astype(float)
    precision, recall, class_f1, support = precision_recall_fscore_support(
        truth, prediction, labels=list(LABELS), zero_division=0
    )
    confusion_values = confusion_matrix(truth, prediction, labels=list(LABELS))
    controls = control_metrics(records)
    chance_level_folds = [
        {
            "motion": str(fold["motion"]),
            "held_out_load_kg": int(fold["held_out_load_kg"]),
            "accuracy": float(fold["accuracy"]),
            "macro_f1": float(fold["macro_f1"]),
        }
        for fold in fold_metrics
        if float(fold["accuracy"]) <= BALANCED_RANDOM_GUESS_ACCURACY + 1e-12
    ]
    result: dict[str, Any] = {
        "accuracy": float(accuracy_score(truth, prediction)),
        "macro_f1": float(f1_score(truth, prediction, labels=list(LABELS), average="macro")),
        "worst_fold_macro_f1": min(float(fold["macro_f1"]) for fold in fold_metrics),
        "multiclass_brier": float(np.mean(np.sum((probabilities - one_hot) ** 2, axis=1))),
        **calibration_metrics(truth, probabilities),
        **controls,
        "chance_level_or_worse_folds": chance_level_folds,
        "worst_fold_chance_failure": bool(chance_level_folds),
        "falsification_triggered": bool(
            not controls["negative_control_pass"] or chance_level_folds
        ),
        "per_class": {
            label: {
                "precision": float(precision[index]),
                "recall": float(recall[index]),
                "f1": float(class_f1[index]),
                "support": int(support[index]),
            }
            for index, label in enumerate(LABELS)
        },
        "confusion_matrix": {
            truth_label: {
                predicted_label: int(confusion_values[row, column])
                for column, predicted_label in enumerate(LABELS)
            }
            for row, truth_label in enumerate(LABELS)
        },
        "folds": fold_metrics,
    }
    return result


def _numeric_summary(values: Iterable[float]) -> dict[str, float]:
    array = np.asarray(list(values), dtype=float)
    return {
        "mean": float(array.mean()),
        "sample_std": float(array.std(ddof=1)) if len(array) > 1 else 0.0,
        "min": float(array.min()),
        "max": float(array.max()),
    }


def _protocol_summary(seed_results: Sequence[dict[str, Any]]) -> dict[str, Any]:
    summary = {
        metric: _numeric_summary(
            float(result[metric]) for result in seed_results if result[metric] is not None
        )
        for metric in SUMMARY_METRICS
    }
    summary["negative_control_ratio_failed_seeds"] = [
        int(result["seed"]) for result in seed_results if not result["negative_control_pass"]
    ]
    summary["worst_fold_chance_failed_seeds"] = [
        int(result["seed"]) for result in seed_results if result["worst_fold_chance_failure"]
    ]
    summary["falsification_triggered_seeds"] = [
        int(result["seed"]) for result in seed_results if result["falsification_triggered"]
    ]
    fold_summaries: list[dict[str, Any]] = []
    for motion in MOTIONS:
        for held_out_load in LOADS:
            matching_folds = [
                fold
                for result in seed_results
                for fold in result["folds"]
                if fold["motion"] == motion and fold["held_out_load_kg"] == held_out_load
            ]
            fold_summaries.append(
                {
                    "motion": motion,
                    "held_out_load_kg": held_out_load,
                    "accuracy": _numeric_summary(
                        float(fold["accuracy"]) for fold in matching_folds
                    ),
                    "macro_f1": _numeric_summary(
                        float(fold["macro_f1"]) for fold in matching_folds
                    ),
                    "chance_level_or_worse_seeds": [
                        int(result["seed"])
                        for result in seed_results
                        for fold in result["folds"]
                        if fold["motion"] == motion
                        and fold["held_out_load_kg"] == held_out_load
                        and float(fold["accuracy"])
                        <= BALANCED_RANDOM_GUESS_ACCURACY + 1e-12
                    ],
                }
            )
    summary["folds"] = fold_summaries
    return summary


def _paired_comparisons(results: dict[str, dict[str, Any]]) -> dict[str, Any]:
    comparisons: dict[str, Any] = {}
    for left, right in (("P1", "P0"), ("P2", "P0"), ("P2", "P1")):
        if left not in results or right not in results:
            continue
        left_by_seed = {item["seed"]: item for item in results[left]["per_seed"]}
        right_by_seed = {item["seed"]: item for item in results[right]["per_seed"]}
        shared_seeds = sorted(set(left_by_seed) & set(right_by_seed))
        comparison: dict[str, Any] = {"shared_seeds": shared_seeds}
        for metric in (
            "macro_f1",
            "worst_fold_macro_f1",
            "multiclass_brier",
            "nuisance_sensitivity_tv",
            "fault_sensitivity_tv",
            "control_ratio",
        ):
            comparison[metric] = _numeric_summary(
                float(left_by_seed[seed][metric]) - float(right_by_seed[seed][metric])
                for seed in shared_seeds
            )
        comparisons[f"{left}_minus_{right}"] = comparison
    return comparisons


def _render_report(metrics: dict[str, Any]) -> str:
    lines = [
        "# Cranfield healthy-reference access audit",
        "",
        f"- Version: `{AUDIT_VERSION}`",
        f"- Seeds: `{metrics['configuration']['seeds']}`",
        "- Status: pre-registered point estimates; block-bootstrap uncertainty is EXP-011.",
        "",
        (
            "| Protocol | Macro F1 | Worst-fold F1 | Brier ↓ | Nuisance TV ↓ | "
            "Fault TV ↑ | Ratio ↓ | Triggered seeds |"
        ),
        "|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for protocol in metrics["configuration"]["protocols"]:
        summary = metrics["results"][protocol]["summary"]
        display = {
            metric: f"{summary[metric]['mean']:.4f} ± {summary[metric]['sample_std']:.4f}"
            for metric in SUMMARY_METRICS
        }

        lines.append(
            "| "
            + " | ".join(
                (
                    f"{protocol} `{PROTOCOLS[protocol]}`",
                    display["macro_f1"],
                    display["worst_fold_macro_f1"],
                    display["multiclass_brier"],
                    display["nuisance_sensitivity_tv"],
                    display["fault_sensitivity_tv"],
                    display["control_ratio"],
                    str(summary["falsification_triggered_seeds"]),
                )
            )
            + " |"
        )
    lines.extend(
        (
            "",
            "P0 reads no healthy target trace. P1 predicts a load-conditioned healthy reference",
            "from source normal trials only. P2 explicitly reads a different normal repetition at",
            "the held-out load and therefore represents target-condition calibration, not pure DG.",
            "",
            (
                "The control ratio is mean label-preserving load sensitivity divided by mean "
                "fault-state"
            ),
            "sensitivity. A ratio at or above one triggers the pre-registered falsification rule.",
            "Repetition-matched runs are not individual counterfactuals.",
            (
                "The second falsification rule triggers when any balanced three-class fold has "
                "accuracy at or below the 1/3 random-guess level."
            ),
            "",
        )
    )
    return "\n".join(lines)


def run_audit(
    output_directory: Path | None = None,
    *,
    seeds: Sequence[int] = AUDIT_SEEDS,
    protocols: Sequence[str] = tuple(PROTOCOLS),
) -> dict[str, Any]:
    """Run the frozen six-fold audit and persist predictions plus transparent metrics."""

    invalid_protocols = set(protocols) - set(PROTOCOLS)
    if invalid_protocols:
        raise ValueError(f"unknown protocols: {sorted(invalid_protocols)}")
    if not seeds:
        raise ValueError("at least one random seed is required")
    output_directory = output_directory or (
        project_root() / "artifacts" / "research" / "cranfield_reference_audit"
    )
    raw = build_raw_matrix()
    feature_columns = raw_feature_columns(raw)
    raw_values = raw.loc[:, feature_columns].to_numpy(dtype=float)
    nonfinite_by_feature = {
        feature: int((~np.isfinite(raw_values[:, column])).sum())
        for column, feature in enumerate(feature_columns)
        if (~np.isfinite(raw_values[:, column])).any()
    }

    fold_cache: dict[tuple[str, str, int], tuple[pd.DataFrame, pd.Index, pd.Index, list[Any]]] = {}
    for protocol in protocols:
        for motion in MOTIONS:
            motion_indices = raw.index[raw["motion"] == motion]
            for held_out_load in LOADS:
                source_indices = raw.index[
                    (raw["motion"] == motion) & (raw["load_kg"] != held_out_load)
                ]
                test_indices = raw.index[
                    (raw["motion"] == motion) & (raw["load_kg"] == held_out_load)
                ]
                features, baseline_repetitions = protocol_feature_frame(
                    raw, protocol, motion_indices, source_indices, feature_columns
                )
                fold_cache[(protocol, motion, held_out_load)] = (
                    features,
                    source_indices,
                    test_indices,
                    baseline_repetitions,
                )

    all_records: list[pd.DataFrame] = []
    protocol_results: dict[str, dict[str, Any]] = {}
    for protocol in protocols:
        seed_results: list[dict[str, Any]] = []
        for seed in seeds:
            seed_records: list[pd.DataFrame] = []
            fold_metrics: list[dict[str, Any]] = []
            for motion in MOTIONS:
                for held_out_load in LOADS:
                    features, source_indices, test_indices, baseline_repetitions = fold_cache[
                        (protocol, motion, held_out_load)
                    ]
                    classifier = Pipeline(
                        (
                            (
                                "imputer",
                                SimpleImputer(strategy="median", keep_empty_features=True),
                            ),
                            (
                                "estimator",
                                ExtraTreesClassifier(
                                    n_estimators=500,
                                    min_samples_leaf=2,
                                    max_features="sqrt",
                                    class_weight="balanced",
                                    random_state=int(seed),
                                    n_jobs=-1,
                                ),
                            ),
                        )
                    )
                    classifier.fit(features.loc[source_indices], raw.loc[source_indices, "truth"])
                    predictions = classifier.predict(features.loc[test_indices])
                    probabilities = np.round(
                        _aligned_probabilities(classifier, features.loc[test_indices]), 12
                    )
                    test_truth = raw.loc[test_indices, "truth"]
                    fold_metrics.append(
                        {
                            "motion": motion,
                            "held_out_load_kg": held_out_load,
                            "training_trials": len(source_indices),
                            "test_trials": len(test_indices),
                            "feature_count": features.shape[1],
                            "nonfinite_training_values_imputed": int(
                                features.loc[source_indices].isna().sum().sum()
                            ),
                            "nonfinite_test_values_imputed": int(
                                features.loc[test_indices].isna().sum().sum()
                            ),
                            "accuracy": float(accuracy_score(test_truth, predictions)),
                            "macro_f1": float(
                                f1_score(
                                    test_truth,
                                    predictions,
                                    labels=list(LABELS),
                                    average="macro",
                                )
                            ),
                            "predicted_class_counts": {
                                label: int((predictions == label).sum()) for label in LABELS
                            },
                        }
                    )
                    baseline_by_index = dict(zip(features.index, baseline_repetitions, strict=True))
                    fold_records = _fold_record(
                        raw,
                        test_indices,
                        protocol,
                        int(seed),
                        [baseline_by_index[index] for index in test_indices],
                        predictions,
                        probabilities,
                    )
                    seed_records.append(fold_records)
            combined_seed_records = pd.concat(seed_records, ignore_index=True)
            result = {
                "seed": int(seed),
                **_seed_metrics(combined_seed_records, fold_metrics),
            }
            seed_results.append(result)
            all_records.append(combined_seed_records)
        protocol_results[protocol] = {
            "name": PROTOCOLS[protocol],
            "target_healthy_trajectory_access": protocol == "P2",
            "feature_count": fold_cache[(protocol, MOTIONS[0], LOADS[0])][0].shape[1],
            "per_seed": seed_results,
            "summary": _protocol_summary(seed_results),
        }

    records = pd.concat(all_records, ignore_index=True)
    cache = cache_directory()
    metrics: dict[str, Any] = {
        "audit_version": AUDIT_VERSION,
        "generated_at": datetime.now(UTC).isoformat(),
        "protocol_document": "research/protocols/cranfield_audit_v0.1.md",
        "status": "pre-registered point estimates; EXP-011 bootstrap intervals pending",
        "dataset": {
            "name": "Cranfield Real Linear Actuator Rig",
            "citation_url": "https://doi.org/10.17862/cranfield.rd.5097649",
            "license": "CC BY 4.0",
            "trials": len(raw),
            "motions": list(MOTIONS),
            "loads_kgf": list(LOADS),
            "classes": list(LABELS),
            "repetitions_per_cell": len(REPETITIONS),
            "input_sha256": {
                filename: _file_sha256(cache / filename) for filename in FILES.values()
            },
        },
        "configuration": {
            "protocols": list(protocols),
            "protocol_names": {protocol: PROTOCOLS[protocol] for protocol in protocols},
            "seeds": [int(seed) for seed in seeds],
            "folds_per_seed": len(MOTIONS) * len(LOADS),
            "outer_split": "motion-specific leave-one-load-out",
            "estimator": (
                "median train-only imputation; ExtraTreesClassifier(n_estimators=500, "
                "min_samples_leaf=2, max_features='sqrt', class_weight='balanced')"
            ),
            "library_version": f"scikit-learn {sklearn.__version__}",
            "P1_reference": (
                "line through per-load healthy feature means from the two source loads; "
                "normal training rows use leave-one-trial-out means"
            ),
            "P2_reference": (
                "different normal repetition from the same motion and load, rotated 1..10"
            ),
        },
        "missingness": {
            "raw_nonfinite_total": int((~np.isfinite(raw_values)).sum()),
            "raw_nonfinite_by_feature": nonfinite_by_feature,
            "policy": "replace non-finite transformed values with NaN; median fitted on train only",
        },
        "metric_definitions": {
            "multiclass_brier": "mean over trials of sum_k (p_k - 1[y=k])^2",
            "ece_10_bin": "confidence ECE with ten equal-width bins",
            "nuisance_sensitivity_tv": (
                "mean pairwise total variation across loads within "
                "(motion, truth, repetition)"
            ),
            "fault_sensitivity_tv": (
                "mean pairwise total variation across fault states within "
                "(motion, load, repetition)"
            ),
            "control_ratio": "nuisance_sensitivity_tv / fault_sensitivity_tv; lower is better",
            "worst_fold_chance_failure": (
                "true when any balanced three-class fold has accuracy <= 1/3; this implements "
                "the pre-registered chance-level stopping criterion"
            ),
        },
        "results": protocol_results,
        "paired_comparisons": _paired_comparisons(protocol_results),
        "limitations": [
            "Point estimates precede the pre-registered block-bootstrap uncertainty run EXP-011.",
            "All trials come from one electromechanical actuator rig, not independent assets.",
            "P1 fits a linear load response from only two source loads and may extrapolate.",
            (
                "Nuisance-control pairs use each load's own leave-one-load-out model, so the "
                "distance includes both load and source-training-set changes."
            ),
            "Tree-vote probabilities are not post-hoc calibrated.",
            "Matched repetition indices are experimental groups, not individual counterfactuals.",
            (
                "P2 is deployment with target-condition healthy calibration, not pure domain "
                "generalization."
            ),
        ],
    }
    output_directory.mkdir(parents=True, exist_ok=True)
    records.to_csv(output_directory / "records.csv", index=False)
    (output_directory / "metrics.json").write_text(
        json.dumps(metrics, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8"
    )
    (output_directory / "report.md").write_text(_render_report(metrics), encoding="utf-8")
    return metrics


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-directory", type=Path)
    parser.add_argument("--seeds", nargs="+", type=int, default=list(AUDIT_SEEDS))
    parser.add_argument("--protocols", nargs="+", choices=tuple(PROTOCOLS), default=list(PROTOCOLS))
    args = parser.parse_args()
    result = run_audit(args.output_directory, seeds=args.seeds, protocols=args.protocols)
    print(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False))


if __name__ == "__main__":
    main()
