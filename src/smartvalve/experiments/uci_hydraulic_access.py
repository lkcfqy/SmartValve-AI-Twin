"""Run the frozen UCI hydraulic target-access replication audit."""

from __future__ import annotations

import argparse
import json
from collections.abc import Sequence
from datetime import UTC, datetime
from hashlib import sha256
from itertools import combinations
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import sklearn
from sklearn.linear_model import Ridge
from sklearn.metrics import accuracy_score, confusion_matrix, f1_score
from sklearn.pipeline import Pipeline

from smartvalve.data.uci_hydraulic import (
    ARCHIVE_FILENAME,
    ARCHIVE_SHA256,
    CONTEXT_COLUMNS,
    CONTEXT_LEVELS,
    PHYSICAL_SENSORS,
    PRIMARY_REPETITIONS,
    SENSOR_FEATURES,
    VALVE_LABELS,
    extract_cycle_features,
)
from smartvalve.experiments.cranfield_baselines import (
    ESTIMATORS,
    _fit_classifier,
    classifier_for,
)
from smartvalve.experiments.cranfield_causal_audit import AUDIT_SEEDS

AUDIT_VERSION = "uci-hydraulic-access-audit-0.1.0"
PROTOCOLS = {
    "P0": "raw_no_target_reference",
    "P1": "source_polynomial_context_reference",
    "P2": "matched_target_context_reference",
}
LABELS = tuple(VALVE_LABELS[level] for level in sorted(VALVE_LABELS))
METADATA_COLUMNS = (
    "archive_row",
    "cooler",
    "valve",
    "pump",
    "accumulator",
    "stable",
    "repetition",
    "truth",
    "sensor_row",
    "context_id",
)
PRIMARY_METRICS = (
    "mean_fold_accuracy",
    "mean_fold_macro_f1",
    "worst_fold_macro_f1",
    "mean_fold_multiclass_brier",
    "mean_axis_ece",
    "max_context_sensitivity_tv",
    "mean_fault_sensitivity_tv",
    "max_control_ratio",
)


def _sha256(path: Path) -> str:
    digest = sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def feature_columns(frame: pd.DataFrame) -> list[str]:
    columns = [column for column in frame.columns if "__" in column]
    expected = len(PHYSICAL_SENSORS) * len(SENSOR_FEATURES)
    if len(columns) != expected:
        raise ValueError(f"expected {expected} primary features, found {len(columns)}")
    return columns


def validate_feature_matrix(frame: pd.DataFrame) -> list[str]:
    columns = feature_columns(frame)
    if len(frame) != 1440:
        raise ValueError(f"expected 1,440 selected cycles, found {len(frame)}")
    if frame["archive_row"].nunique() != len(frame):
        raise ValueError("feature matrix repeats an archive cycle")
    if frame["context_id"].nunique() != 36:
        raise ValueError("feature matrix does not contain 36 frozen contexts")
    expected_labels = {label: 360 for label in LABELS}
    if frame.groupby("truth").size().to_dict() != expected_labels:
        raise ValueError("feature matrix does not contain 360 cycles per valve class")
    if not np.isfinite(frame.loc[:, columns].to_numpy(dtype=float)).all():
        raise ValueError("feature matrix contains non-finite values")
    return columns


def write_feature_audit(output_directory: Path) -> dict[str, Any]:
    """Persist and fingerprint the frozen cohort before any classifier is fitted."""

    output_directory.mkdir(parents=True, exist_ok=True)
    matrix = extract_cycle_features()
    columns = validate_feature_matrix(matrix)
    path = output_directory / "feature_matrix.parquet"
    matrix.to_parquet(path, index=False)
    summary = {
        "audit_version": AUDIT_VERSION,
        "generated_at": datetime.now(UTC).isoformat(),
        "status": "feature integrity complete; no classifier fitted",
        "archive_filename": ARCHIVE_FILENAME,
        "archive_sha256": ARCHIVE_SHA256,
        "selected_cycles": len(matrix),
        "context_cells": int(matrix["context_id"].nunique()),
        "physical_blocks": int(
            matrix.groupby([*CONTEXT_COLUMNS, "repetition"]).ngroups
        ),
        "physical_sensors": [sensor.name for sensor in PHYSICAL_SENSORS],
        "raw_feature_count": len(columns),
        "nonfinite_feature_values": int(
            (~np.isfinite(matrix.loc[:, columns].to_numpy(dtype=float))).sum()
        ),
        "feature_matrix": {
            "path": path.name,
            "bytes": path.stat().st_size,
            "sha256": _sha256(path),
        },
    }
    (output_directory / "feature_audit.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return summary


def context_design(frame: pd.DataFrame) -> np.ndarray:
    """Map documented context severities to the frozen quadratic design."""

    cooler = (100.0 - frame["cooler"].to_numpy(dtype=float)) / 97.0
    pump = frame["pump"].to_numpy(dtype=float) / 2.0
    accumulator = (130.0 - frame["accumulator"].to_numpy(dtype=float)) / 40.0
    return np.column_stack(
        (
            cooler,
            pump,
            accumulator,
            cooler**2,
            pump**2,
            accumulator**2,
            cooler * pump,
            cooler * accumulator,
            pump * accumulator,
        )
    )


def fold_definitions() -> list[tuple[str, int]]:
    return [
        (factor, int(level))
        for factor in CONTEXT_COLUMNS
        for level in CONTEXT_LEVELS[factor]
    ]


def _relative_features(
    current: np.ndarray,
    reference: np.ndarray,
    columns: Sequence[str],
    index: pd.Index,
) -> pd.DataFrame:
    delta = current - reference
    relative = delta / (np.abs(reference) + 1e-6)
    values = np.empty((len(index), len(columns) * 2), dtype=float)
    values[:, 0::2] = delta
    values[:, 1::2] = relative
    result_columns = [
        name
        for feature in columns
        for name in (f"delta_{feature}", f"relative_{feature}")
    ]
    result = pd.DataFrame(values, index=index, columns=result_columns)
    if not np.isfinite(result.to_numpy(dtype=float)).all():
        raise ValueError("relative protocol features contain non-finite values")
    return result


def source_context_references(
    frame: pd.DataFrame,
    source_mask: pd.Series,
    columns: Sequence[str],
) -> np.ndarray:
    """Predict healthy references without reading any held-level sensor trajectory."""

    source = source_mask.to_numpy(dtype=bool)
    optimal = frame["truth"].to_numpy(dtype=object) == "optimal"
    values = frame.loc[:, list(columns)].to_numpy(dtype=float)
    design = context_design(frame)
    references = np.empty_like(values)
    all_source_optimal = source & optimal
    if all_source_optimal.sum() == 0:
        raise ValueError("P1 requires source optimal-valve cycles")
    final_model = Ridge(alpha=1.0, fit_intercept=True)
    final_model.fit(design[all_source_optimal], values[all_source_optimal])
    references[~source] = final_model.predict(design[~source])
    repetitions = frame["repetition"].to_numpy(dtype=int)
    for repetition in PRIMARY_REPETITIONS:
        training = all_source_optimal & (repetitions != repetition)
        rows = source & (repetitions == repetition)
        if training.sum() == 0 or rows.sum() == 0:
            raise ValueError("P1 repetition cross-fit has an empty training or prediction set")
        model = Ridge(alpha=1.0, fit_intercept=True)
        model.fit(design[training], values[training])
        references[rows] = model.predict(design[rows])
    if not np.isfinite(references).all():
        raise ValueError("P1 context model produced non-finite references")
    return references


def matched_context_references(
    frame: pd.DataFrame,
    columns: Sequence[str],
) -> tuple[np.ndarray, np.ndarray]:
    """Rotate to a distinct optimal cycle in the exact target context."""

    optimal = frame.loc[frame["truth"] == "optimal"]
    lookup = {
        (
            int(row["cooler"]),
            int(row["pump"]),
            int(row["accumulator"]),
            int(row["repetition"]),
        ): row.loc[list(columns)].to_numpy(dtype=float)
        for _, row in optimal.iterrows()
    }
    references = []
    baseline_repetitions = []
    for _, row in frame.iterrows():
        baseline = int(row["repetition"]) % len(PRIMARY_REPETITIONS) + 1
        key = (
            int(row["cooler"]),
            int(row["pump"]),
            int(row["accumulator"]),
            baseline,
        )
        if key not in lookup:
            raise ValueError(f"P2 is missing matched optimal reference {key}")
        references.append(lookup[key])
        baseline_repetitions.append(baseline)
    return np.vstack(references), np.asarray(baseline_repetitions, dtype=int)


def protocol_feature_frame(
    frame: pd.DataFrame,
    protocol: str,
    held_factor: str,
    held_level: int,
    columns: Sequence[str],
) -> tuple[pd.DataFrame, pd.Series, pd.Series, np.ndarray]:
    """Construct one fold without estimator fitting or target-label selection."""

    if held_factor not in CONTEXT_COLUMNS:
        raise ValueError(f"unknown held factor: {held_factor}")
    source_mask = frame[held_factor] != held_level
    test_mask = ~source_mask
    if source_mask.sum() == 0 or test_mask.sum() == 0:
        raise ValueError("outer fold has an empty source or target partition")
    current = frame.loc[:, list(columns)].to_numpy(dtype=float)
    if protocol == "P0":
        features = pd.DataFrame(current, index=frame.index, columns=list(columns))
        baseline_repetitions = np.full(len(frame), -1, dtype=int)
    elif protocol == "P1":
        reference = source_context_references(frame, source_mask, columns)
        features = _relative_features(current, reference, columns, frame.index)
        baseline_repetitions = np.full(len(frame), -1, dtype=int)
    elif protocol == "P2":
        reference, baseline_repetitions = matched_context_references(frame, columns)
        features = _relative_features(current, reference, columns, frame.index)
    else:
        raise ValueError(f"unknown protocol: {protocol}")
    if set(frame.loc[source_mask, held_factor]) & set(frame.loc[test_mask, held_factor]):
        raise ValueError("held context level leaked into the source partition")
    return features, source_mask, test_mask, baseline_repetitions


def _aligned_probabilities(classifier: Pipeline, features: pd.DataFrame) -> np.ndarray:
    probabilities = classifier.predict_proba(features)
    estimator = classifier.named_steps["estimator"]
    aligned = np.zeros((len(features), len(LABELS)), dtype=float)
    for source_column, label in enumerate(estimator.classes_):
        aligned[:, LABELS.index(str(label))] = probabilities[:, source_column]
    return aligned


def _multiclass_brier(truth: Sequence[str], probabilities: np.ndarray) -> float:
    truth_values = np.asarray(truth, dtype=object)
    one_hot = np.column_stack([truth_values == label for label in LABELS]).astype(float)
    return float(np.mean(np.sum((probabilities - one_hot) ** 2, axis=1)))


def _ece(truth: Sequence[str], probabilities: np.ndarray, *, bins: int = 10) -> float:
    truth_values = np.asarray(truth, dtype=object)
    confidence = probabilities.max(axis=1)
    prediction = np.asarray(LABELS, dtype=object)[probabilities.argmax(axis=1)]
    correct = prediction == truth_values
    bin_ids = np.minimum((confidence * bins).astype(int), bins - 1)
    result = 0.0
    for bin_id in range(bins):
        mask = bin_ids == bin_id
        if mask.any():
            result += float(mask.mean()) * abs(
                float(correct[mask].mean()) - float(confidence[mask].mean())
            )
    return result


def _mean_pairwise_tv(records: pd.DataFrame, groups: Sequence[str]) -> tuple[float, int]:
    probability_columns = [f"probability_{label}" for label in LABELS]
    distances = []
    for _, group in records.groupby(list(groups), sort=False):
        values = group.loc[:, probability_columns].to_numpy(dtype=float)
        for left, right in combinations(values, 2):
            distances.append(float(0.5 * np.abs(left - right).sum()))
    if not distances:
        raise ValueError("matched control has no probability pairs")
    return float(np.mean(distances)), len(distances)


def _axis_controls(records: pd.DataFrame, factor: str) -> dict[str, float | int]:
    other_context = [column for column in CONTEXT_COLUMNS if column != factor]
    nuisance, nuisance_pairs = _mean_pairwise_tv(
        records,
        (*other_context, "truth", "repetition"),
    )
    fault, fault_pairs = _mean_pairwise_tv(
        records,
        (*CONTEXT_COLUMNS, "repetition"),
    )
    return {
        "context_sensitivity_tv": nuisance,
        "fault_sensitivity_tv": fault,
        "control_ratio": nuisance / fault if fault > 0 else float("inf"),
        "context_pairs": nuisance_pairs,
        "fault_pairs": fault_pairs,
    }


def _numeric_summary(values: Sequence[float]) -> dict[str, float]:
    array = np.asarray(values, dtype=float)
    return {
        "mean": float(array.mean()),
        "sample_std": float(array.std(ddof=1)) if len(array) > 1 else 0.0,
        "minimum": float(array.min()),
        "maximum": float(array.max()),
    }


def _seed_metrics(records: pd.DataFrame) -> dict[str, Any]:
    folds = []
    for held_factor, held_level in fold_definitions():
        fold = records.loc[
            (records["held_factor"] == held_factor)
            & (records["held_level"] == held_level)
        ]
        truth = fold["truth"].to_numpy(dtype=object)
        prediction = fold["prediction"].to_numpy(dtype=object)
        probabilities = fold.loc[
            :, [f"probability_{label}" for label in LABELS]
        ].to_numpy(dtype=float)
        folds.append(
            {
                "held_factor": held_factor,
                "held_level": held_level,
                "test_cycles": len(fold),
                "accuracy": float(accuracy_score(truth, prediction)),
                "macro_f1": float(
                    f1_score(
                        truth,
                        prediction,
                        labels=list(LABELS),
                        average="macro",
                        zero_division=0,
                    )
                ),
                "multiclass_brier": _multiclass_brier(truth, probabilities),
            }
        )
    axes = {}
    for factor in CONTEXT_COLUMNS:
        axis = records.loc[records["held_factor"] == factor]
        if len(axis) != 1440:
            raise ValueError(f"axis {factor} does not contain each primary cycle exactly once")
        truth = axis["truth"].to_numpy(dtype=object)
        prediction = axis["prediction"].to_numpy(dtype=object)
        probabilities = axis.loc[
            :, [f"probability_{label}" for label in LABELS]
        ].to_numpy(dtype=float)
        matrix = confusion_matrix(truth, prediction, labels=list(LABELS))
        axes[factor] = {
            "accuracy": float(accuracy_score(truth, prediction)),
            "macro_f1": float(
                f1_score(
                    truth,
                    prediction,
                    labels=list(LABELS),
                    average="macro",
                    zero_division=0,
                )
            ),
            "multiclass_brier": _multiclass_brier(truth, probabilities),
            "ece_10_bin": _ece(truth, probabilities),
            "confusion_matrix": {
                truth_label: {
                    predicted_label: int(matrix[row, column])
                    for column, predicted_label in enumerate(LABELS)
                }
                for row, truth_label in enumerate(LABELS)
            },
            **_axis_controls(axis, factor),
        }
    return {
        "mean_fold_accuracy": float(np.mean([item["accuracy"] for item in folds])),
        "mean_fold_macro_f1": float(np.mean([item["macro_f1"] for item in folds])),
        "worst_fold_macro_f1": float(np.min([item["macro_f1"] for item in folds])),
        "mean_fold_multiclass_brier": float(
            np.mean([item["multiclass_brier"] for item in folds])
        ),
        "mean_axis_ece": float(np.mean([axes[factor]["ece_10_bin"] for factor in axes])),
        "max_context_sensitivity_tv": float(
            np.max([axes[factor]["context_sensitivity_tv"] for factor in axes])
        ),
        "mean_fault_sensitivity_tv": float(
            np.mean([axes[factor]["fault_sensitivity_tv"] for factor in axes])
        ),
        "max_control_ratio": float(
            np.max([axes[factor]["control_ratio"] for factor in axes])
        ),
        "folds": folds,
        "axes": axes,
    }


def _summarize(seed_results: Sequence[dict[str, Any]]) -> dict[str, Any]:
    summary = {
        metric: _numeric_summary([float(item[metric]) for item in seed_results])
        for metric in PRIMARY_METRICS
    }
    summary["folds"] = []
    for held_factor, held_level in fold_definitions():
        matching = [
            fold
            for result in seed_results
            for fold in result["folds"]
            if fold["held_factor"] == held_factor and fold["held_level"] == held_level
        ]
        summary["folds"].append(
            {
                "held_factor": held_factor,
                "held_level": held_level,
                **{
                    metric: _numeric_summary([float(item[metric]) for item in matching])
                    for metric in ("accuracy", "macro_f1", "multiclass_brier")
                },
            }
        )
    return summary


def _paired_comparisons(results: dict[str, Any]) -> dict[str, Any]:
    comparisons: dict[str, Any] = {}
    for estimator_name in results:
        estimator_results = results[estimator_name]
        estimator_comparisons = {}
        for left, right in (("P1", "P0"), ("P2", "P0"), ("P2", "P1")):
            left_by_seed = {
                int(item["seed"]): item for item in estimator_results[left]["per_seed"]
            }
            right_by_seed = {
                int(item["seed"]): item for item in estimator_results[right]["per_seed"]
            }
            shared = sorted(set(left_by_seed) & set(right_by_seed))
            estimator_comparisons[f"{left}_minus_{right}"] = {
                "shared_seeds": shared,
                **{
                    metric: _numeric_summary(
                        [
                            float(left_by_seed[seed][metric])
                            - float(right_by_seed[seed][metric])
                            for seed in shared
                        ]
                    )
                    for metric in PRIMARY_METRICS
                },
            }
        comparisons[estimator_name] = estimator_comparisons
    return comparisons


def _render_report(metrics: dict[str, Any]) -> str:
    lines = [
        "# UCI hydraulic target-access audit",
        "",
        f"- Version: `{AUDIT_VERSION}`",
        "- Status: frozen point estimates; physical-block bootstrap is a subsequent run.",
        f"- Selected cycles: {metrics['dataset']['selected_cycles']}",
        f"- Primary raw features: {metrics['configuration']['raw_feature_count']}",
        "",
        "| Estimator | Protocol | Mean-fold macro F1 | Worst-fold F1 | Brier | Max ratio |",
        "|---|---|---:|---:|---:|---:|",
    ]
    for estimator_name, estimator_results in metrics["results"].items():
        for protocol, result in estimator_results.items():
            summary = result["summary"]
            lines.append(
                "| "
                + " | ".join(
                    (
                        estimator_name,
                        protocol,
                        (
                            f"{summary['mean_fold_macro_f1']['mean']:.4f} ± "
                            f"{summary['mean_fold_macro_f1']['sample_std']:.4f}"
                        ),
                        (
                            f"{summary['worst_fold_macro_f1']['mean']:.4f} ± "
                            f"{summary['worst_fold_macro_f1']['sample_std']:.4f}"
                        ),
                        (
                            f"{summary['mean_fold_multiclass_brier']['mean']:.4f} ± "
                            f"{summary['mean_fold_multiclass_brier']['sample_std']:.4f}"
                        ),
                        (
                            f"{summary['max_control_ratio']['mean']:.4f} ± "
                            f"{summary['max_control_ratio']['sample_std']:.4f}"
                        ),
                    )
                )
                + " |"
            )
    lines.extend(
        (
            "",
            "P0 reads no target-context trajectory. P1 reads context metadata but fits its",
            "healthy reference from source levels only. P2 reads a different optimal-valve cycle",
            "from the exact held-out context and is therefore target calibration, not pure DG.",
            "",
            "No cross-rig replication claim is made until the paired physical-block bootstrap.",
        )
    )
    return "\n".join(lines) + "\n"


def run_audit(
    output_directory: Path,
    *,
    estimators: Sequence[str] = ESTIMATORS,
    seeds: Sequence[int] = AUDIT_SEEDS,
    feature_matrix_path: Path | None = None,
) -> dict[str, Any]:
    invalid_estimators = set(estimators) - set(ESTIMATORS)
    if invalid_estimators:
        raise ValueError(f"unknown estimators: {sorted(invalid_estimators)}")
    if not seeds:
        raise ValueError("at least one seed is required")
    output_directory.mkdir(parents=True, exist_ok=True)
    matrix = (
        pd.read_parquet(feature_matrix_path)
        if feature_matrix_path is not None
        else extract_cycle_features()
    )
    columns = validate_feature_matrix(matrix)
    feature_path = output_directory / "feature_matrix.parquet"
    matrix.to_parquet(feature_path, index=False)
    fold_cache = {
        (protocol, factor, level): protocol_feature_frame(
            matrix,
            protocol,
            factor,
            level,
            columns,
        )
        for protocol in PROTOCOLS
        for factor, level in fold_definitions()
    }
    all_records: list[pd.DataFrame] = []
    results: dict[str, Any] = {}
    for estimator_name in estimators:
        estimator_results: dict[str, Any] = {}
        for protocol in PROTOCOLS:
            seed_results = []
            for seed in seeds:
                seed_records = []
                for held_factor, held_level in fold_definitions():
                    features, source_mask, test_mask, baseline_repetitions = fold_cache[
                        (protocol, held_factor, held_level)
                    ]
                    classifier = classifier_for(estimator_name, int(seed))
                    _fit_classifier(
                        classifier,
                        estimator_name,
                        features.loc[source_mask],
                        matrix.loc[source_mask, "truth"],
                    )
                    test_features = features.loc[test_mask]
                    prediction = classifier.predict(test_features)
                    probabilities = np.round(
                        _aligned_probabilities(classifier, test_features),
                        12,
                    )
                    records = matrix.loc[test_mask, list(METADATA_COLUMNS)].copy()
                    records.insert(0, "protocol", protocol)
                    records.insert(1, "protocol_name", PROTOCOLS[protocol])
                    records.insert(2, "estimator", estimator_name)
                    records.insert(3, "seed", int(seed))
                    records.insert(4, "held_factor", held_factor)
                    records.insert(5, "held_level", held_level)
                    records["baseline_repetition"] = baseline_repetitions[test_mask]
                    records["prediction"] = prediction
                    records["correct"] = prediction == records["truth"].to_numpy(dtype=object)
                    records["confidence"] = probabilities.max(axis=1)
                    for column, label in enumerate(LABELS):
                        records[f"probability_{label}"] = probabilities[:, column]
                    seed_records.append(records)
                combined = pd.concat(seed_records, ignore_index=True)
                seed_results.append({"seed": int(seed), **_seed_metrics(combined)})
                all_records.append(combined)
            estimator_results[protocol] = {
                "per_seed": seed_results,
                "summary": _summarize(seed_results),
            }
        results[estimator_name] = estimator_results
    records = pd.concat(all_records, ignore_index=True)
    records_path = output_directory / "records.parquet"
    records.to_parquet(records_path, index=False)
    metrics: dict[str, Any] = {
        "audit_version": AUDIT_VERSION,
        "generated_at": datetime.now(UTC).isoformat(),
        "protocol_document": "research/protocols/uci_hydraulic_access_v0.1.md",
        "status": "point estimates; bootstrap pending",
        "dataset": {
            "name": "UCI Condition Monitoring of Hydraulic Systems",
            "doi": "10.24432/C5CW21",
            "license": "CC BY 4.0",
            "archive_filename": ARCHIVE_FILENAME,
            "archive_sha256": ARCHIVE_SHA256,
            "archive_cycles": 2205,
            "selected_cycles": len(matrix),
            "physical_blocks": 360,
            "context_cells": int(matrix["context_id"].nunique()),
            "excluded_surplus_stable_optimal_cycles": 9,
        },
        "configuration": {
            "protocols": list(PROTOCOLS),
            "protocol_names": PROTOCOLS,
            "estimators": list(estimators),
            "seeds": [int(seed) for seed in seeds],
            "outer_folds": [
                {"held_factor": factor, "held_level": level}
                for factor, level in fold_definitions()
            ],
            "physical_sensors": [sensor.name for sensor in PHYSICAL_SENSORS],
            "sensor_features": list(SENSOR_FEATURES),
            "raw_feature_count": len(columns),
            "relative_feature_count": len(columns) * 2,
            "library_version": f"scikit-learn {sklearn.__version__}",
        },
        "artifacts": {
            "feature_matrix": {
                "path": feature_path.name,
                "bytes": feature_path.stat().st_size,
                "sha256": _sha256(feature_path),
            },
            "records": {
                "path": records_path.name,
                "bytes": records_path.stat().st_size,
                "sha256": _sha256(records_path),
                "rows": len(records),
            },
        },
        "results": results,
        "paired_seed_comparisons": _paired_comparisons(results),
        "claim_boundary": [
            "No external replication claim is made before the paired block bootstrap.",
            "P2 is target-context calibration, not target-free domain generalization.",
            (
                "Other component states are label-preserving context for valve diagnosis, "
                "not harmless."
            ),
            "The UCI rig is independent of Cranfield but is not a factory population.",
        ],
    }
    metrics_path = output_directory / "metrics.json"
    metrics_path.write_text(
        json.dumps(metrics, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    (output_directory / "report.md").write_text(_render_report(metrics), encoding="utf-8")
    return metrics


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-directory", type=Path, required=True)
    parser.add_argument("--estimators", nargs="+", choices=ESTIMATORS, default=list(ESTIMATORS))
    parser.add_argument("--seeds", nargs="+", type=int, default=list(AUDIT_SEEDS))
    parser.add_argument("--feature-matrix", type=Path)
    parser.add_argument("--features-only", action="store_true")
    args = parser.parse_args()
    if args.features_only:
        summary = write_feature_audit(args.output_directory)
        print(json.dumps(summary, ensure_ascii=False, indent=2))
        return
    metrics = run_audit(
        args.output_directory,
        estimators=args.estimators,
        seeds=args.seeds,
        feature_matrix_path=args.feature_matrix,
    )
    print(json.dumps(metrics["artifacts"], ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
