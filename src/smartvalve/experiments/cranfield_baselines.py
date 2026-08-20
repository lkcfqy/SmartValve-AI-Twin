"""Classical estimator audit and operating-environment probe for Cranfield data."""

from __future__ import annotations

import argparse
import json
from collections.abc import Sequence
from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import sklearn
from sklearn.discriminant_analysis import LinearDiscriminantAnalysis
from sklearn.ensemble import ExtraTreesClassifier, HistGradientBoostingClassifier
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, confusion_matrix, f1_score
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.svm import SVC
from sklearn.utils.class_weight import compute_sample_weight

from smartvalve.experiments.cranfield_causal_audit import (
    AUDIT_SEEDS,
    LABELS,
    LOADS,
    MOTIONS,
    REPETITIONS,
    _aligned_probabilities,
    _fold_record,
    _numeric_summary,
    _protocol_summary,
    _relative_feature_frame,
    _seed_metrics,
    build_raw_matrix,
    protocol_feature_frame,
    raw_feature_columns,
)

BASELINE_VERSION = "cranfield-baselines-and-probe-0.1.0"
REPRESENTATIONS = ("P0", "P2")
ESTIMATORS = (
    "extra_trees",
    "logistic",
    "rbf_svm",
    "hist_gradient_boosting",
    "shrinkage_lda",
)


def _file_sha256(path: Path) -> str:
    digest = sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def classifier_for(estimator_name: str, seed: int) -> Pipeline:
    """Build one member of the frozen classical estimator suite."""

    median = SimpleImputer(strategy="median", keep_empty_features=True)
    if estimator_name == "extra_trees":
        steps = (
            ("imputer", median),
            (
                "estimator",
                ExtraTreesClassifier(
                    n_estimators=500,
                    min_samples_leaf=2,
                    max_features="sqrt",
                    class_weight="balanced",
                    random_state=seed,
                    n_jobs=-1,
                ),
            ),
        )
    elif estimator_name == "logistic":
        steps = (
            ("imputer", median),
            ("scaler", StandardScaler()),
            (
                "estimator",
                LogisticRegression(
                    C=1.0,
                    class_weight="balanced",
                    max_iter=5000,
                    random_state=seed,
                ),
            ),
        )
    elif estimator_name == "rbf_svm":
        steps = (
            ("imputer", median),
            ("scaler", StandardScaler()),
            (
                "estimator",
                SVC(
                    C=1.0,
                    gamma="scale",
                    class_weight="balanced",
                    probability=True,
                    random_state=seed,
                ),
            ),
        )
    elif estimator_name == "hist_gradient_boosting":
        steps = (
            ("imputer", median),
            (
                "estimator",
                HistGradientBoostingClassifier(
                    max_iter=200,
                    learning_rate=0.05,
                    max_leaf_nodes=15,
                    l2_regularization=1.0,
                    random_state=seed,
                ),
            ),
        )
    elif estimator_name == "shrinkage_lda":
        steps = (
            ("imputer", median),
            ("scaler", StandardScaler()),
            (
                "estimator",
                LinearDiscriminantAnalysis(solver="lsqr", shrinkage="auto"),
            ),
        )
    else:
        raise ValueError(f"unknown estimator: {estimator_name}")
    return Pipeline(steps)


def _fit_classifier(
    classifier: Pipeline,
    estimator_name: str,
    features: pd.DataFrame,
    truth: pd.Series,
) -> None:
    fit_parameters: dict[str, Any] = {}
    if estimator_name == "hist_gradient_boosting":
        fit_parameters["estimator__sample_weight"] = compute_sample_weight(
            class_weight="balanced", y=truth
        )
    classifier.fit(features, truth, **fit_parameters)


def _fault_feature_cache(
    raw: pd.DataFrame, feature_columns: Sequence[str]
) -> dict[tuple[str, str, int], tuple[pd.DataFrame, pd.Index, pd.Index, list[Any]]]:
    cache = {}
    for representation in REPRESENTATIONS:
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
                    raw,
                    representation,
                    motion_indices,
                    source_indices,
                    feature_columns,
                )
                cache[(representation, motion, held_out_load)] = (
                    features,
                    source_indices,
                    test_indices,
                    baseline_repetitions,
                )
    return cache


def _run_fault_classifiers(
    raw: pd.DataFrame,
    feature_columns: Sequence[str],
    seeds: Sequence[int],
) -> tuple[pd.DataFrame, dict[str, Any]]:
    cache = _fault_feature_cache(raw, feature_columns)
    all_records: list[pd.DataFrame] = []
    results: dict[str, Any] = {}
    for representation in REPRESENTATIONS:
        representation_results: dict[str, Any] = {}
        for estimator_name in ESTIMATORS:
            seed_results: list[dict[str, Any]] = []
            for seed in seeds:
                seed_records: list[pd.DataFrame] = []
                fold_metrics: list[dict[str, Any]] = []
                for motion in MOTIONS:
                    for held_out_load in LOADS:
                        features, source_indices, test_indices, baseline_repetitions = cache[
                            (representation, motion, held_out_load)
                        ]
                        classifier = classifier_for(estimator_name, int(seed))
                        _fit_classifier(
                            classifier,
                            estimator_name,
                            features.loc[source_indices],
                            raw.loc[source_indices, "truth"],
                        )
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
                                "accuracy": float(
                                    accuracy_score(test_truth, predictions)
                                ),
                                "macro_f1": float(
                                    f1_score(
                                        test_truth,
                                        predictions,
                                        labels=list(LABELS),
                                        average="macro",
                                        zero_division=0,
                                    )
                                ),
                                "predicted_class_counts": {
                                    label: int((predictions == label).sum())
                                    for label in LABELS
                                },
                            }
                        )
                        baseline_by_index = dict(
                            zip(features.index, baseline_repetitions, strict=True)
                        )
                        fold_records = _fold_record(
                            raw,
                            test_indices,
                            representation,
                            int(seed),
                            [baseline_by_index[index] for index in test_indices],
                            predictions,
                            probabilities,
                        )
                        fold_records.insert(0, "estimator", estimator_name)
                        seed_records.append(fold_records)
                combined = pd.concat(seed_records, ignore_index=True)
                seed_results.append(
                    {"seed": int(seed), **_seed_metrics(combined, fold_metrics)}
                )
                all_records.append(combined)
            representation_results[estimator_name] = {
                "per_seed": seed_results,
                "summary": _protocol_summary(seed_results),
            }
        results[representation] = representation_results
    return pd.concat(all_records, ignore_index=True), results


def _model_independence(fault_results: dict[str, Any]) -> dict[str, Any]:
    """Identify folds at chance or worse for every seed in multiple P0 families."""

    all_seed_failures: dict[str, list[dict[str, Any]]] = {}
    fold_to_estimators: dict[tuple[str, int], list[str]] = {}
    for estimator_name in ESTIMATORS:
        summary = fault_results["P0"][estimator_name]["summary"]
        failed_folds = [
            {
                "motion": fold["motion"],
                "held_out_load_kg": int(fold["held_out_load_kg"]),
            }
            for fold in summary["folds"]
            if len(fold["chance_level_or_worse_seeds"]) == len(AUDIT_SEEDS)
        ]
        all_seed_failures[estimator_name] = failed_folds
        for fold in failed_folds:
            key = (str(fold["motion"]), int(fold["held_out_load_kg"]))
            fold_to_estimators.setdefault(key, []).append(estimator_name)
    corroborated_folds = [
        {
            "motion": motion,
            "held_out_load_kg": load_kg,
            "estimators": estimators,
            "estimator_count": len(estimators),
        }
        for (motion, load_kg), estimators in sorted(fold_to_estimators.items())
        if len(estimators) >= 3
    ]
    return {
        "criterion": (
            "same P0 fold has accuracy at or below 1/3 for every seed in at least "
            "three estimator families"
        ),
        "all_seed_chance_folds_by_estimator": all_seed_failures,
        "corroborated_folds": corroborated_folds,
        "criterion_met": bool(corroborated_folds),
    }


def probe_feature_frame(
    raw: pd.DataFrame,
    representation: str,
    motion: str,
    held_out_repetition: int,
    feature_columns: Sequence[str],
) -> tuple[pd.DataFrame, list[int | None]]:
    """Build probe features without reading the held-out repetition as a reference."""

    row_indices = raw.index[raw["motion"] == motion]
    current = raw.loc[row_indices, list(feature_columns)].to_numpy(dtype=float)
    if representation == "P0":
        return (
            pd.DataFrame(current, index=row_indices, columns=list(feature_columns)),
            [None] * len(row_indices),
        )
    if representation != "P2":
        raise ValueError(f"unknown probe representation: {representation}")
    healthy = raw.loc[
        (raw["motion"] == motion)
        & (raw["truth"] == "normal")
        & (raw["repetition"] != held_out_repetition)
    ]
    references: list[np.ndarray] = []
    baseline_repetitions: list[int] = []
    for row_index in row_indices:
        row = raw.loc[row_index]
        candidates = healthy.loc[
            (healthy["load_kg"] == row["load_kg"])
            & (healthy["repetition"] != row["repetition"])
        ].sort_values("repetition")
        if candidates.empty:
            raise ValueError("P2 probe requires a train-only healthy reference")
        later = candidates.loc[candidates["repetition"] > row["repetition"]]
        reference = later.iloc[0] if not later.empty else candidates.iloc[0]
        references.append(reference.loc[list(feature_columns)].to_numpy(dtype=float))
        baseline_repetitions.append(int(reference["repetition"]))
    features = _relative_feature_frame(
        current,
        np.vstack(references),
        feature_columns,
        row_indices,
    ).replace([np.inf, -np.inf], np.nan)
    return features, baseline_repetitions


def _aligned_load_probabilities(
    classifier: Pipeline, features: pd.DataFrame
) -> np.ndarray:
    probabilities = classifier.predict_proba(features)
    estimator = classifier.named_steps["estimator"]
    aligned = np.zeros((len(features), len(LOADS)), dtype=float)
    for source_column, load_kg in enumerate(estimator.classes_):
        aligned[:, LOADS.index(int(load_kg))] = probabilities[:, source_column]
    return aligned


def _probe_seed_metrics(records: pd.DataFrame) -> dict[str, Any]:
    truth = records["truth_load_kg"].to_numpy(dtype=int)
    prediction = records["predicted_load_kg"].to_numpy(dtype=int)
    matrix = confusion_matrix(truth, prediction, labels=list(LOADS))
    per_motion = {}
    for motion in MOTIONS:
        subset = records.loc[records["motion"] == motion]
        per_motion[motion] = {
            "accuracy": float(
                accuracy_score(subset["truth_load_kg"], subset["predicted_load_kg"])
            ),
            "macro_f1": float(
                f1_score(
                    subset["truth_load_kg"],
                    subset["predicted_load_kg"],
                    labels=list(LOADS),
                    average="macro",
                    zero_division=0,
                )
            ),
        }
    return {
        "accuracy": float(accuracy_score(truth, prediction)),
        "macro_f1": float(
            f1_score(
                truth,
                prediction,
                labels=list(LOADS),
                average="macro",
                zero_division=0,
            )
        ),
        "confusion_matrix": {
            str(truth_load): {
                str(predicted_load): int(matrix[row, column])
                for column, predicted_load in enumerate(LOADS)
            }
            for row, truth_load in enumerate(LOADS)
        },
        "per_motion": per_motion,
    }


def _probe_summary(seed_results: Sequence[dict[str, Any]]) -> dict[str, Any]:
    return {
        "accuracy": _numeric_summary(item["accuracy"] for item in seed_results),
        "macro_f1": _numeric_summary(item["macro_f1"] for item in seed_results),
        "per_motion": {
            motion: {
                metric: _numeric_summary(
                    item["per_motion"][motion][metric] for item in seed_results
                )
                for metric in ("accuracy", "macro_f1")
            }
            for motion in MOTIONS
        },
    }


def _run_environment_probe(
    raw: pd.DataFrame,
    feature_columns: Sequence[str],
    seeds: Sequence[int],
) -> tuple[pd.DataFrame, dict[str, Any]]:
    feature_cache = {
        (representation, motion, held_out_repetition): probe_feature_frame(
            raw,
            representation,
            motion,
            held_out_repetition,
            feature_columns,
        )
        for representation in REPRESENTATIONS
        for motion in MOTIONS
        for held_out_repetition in REPETITIONS
    }
    all_records: list[pd.DataFrame] = []
    results: dict[str, Any] = {}
    for representation in REPRESENTATIONS:
        seed_results: list[dict[str, Any]] = []
        for seed in seeds:
            seed_records: list[pd.DataFrame] = []
            for motion in MOTIONS:
                for held_out_repetition in REPETITIONS:
                    features, baseline_repetitions = feature_cache[
                        (representation, motion, held_out_repetition)
                    ]
                    train_indices = raw.index[
                        (raw["motion"] == motion)
                        & (raw["repetition"] != held_out_repetition)
                    ]
                    test_indices = raw.index[
                        (raw["motion"] == motion)
                        & (raw["repetition"] == held_out_repetition)
                    ]
                    classifier = classifier_for("extra_trees", int(seed))
                    classifier.fit(
                        features.loc[train_indices],
                        raw.loc[train_indices, "load_kg"],
                    )
                    predictions = classifier.predict(features.loc[test_indices]).astype(int)
                    probabilities = np.round(
                        _aligned_load_probabilities(
                            classifier, features.loc[test_indices]
                        ),
                        12,
                    )
                    baseline_by_index = dict(
                        zip(features.index, baseline_repetitions, strict=True)
                    )
                    records = raw.loc[
                        test_indices,
                        ["motion", "load_kg", "repetition", "truth"],
                    ].rename(
                        columns={"load_kg": "truth_load_kg", "truth": "fault_state"}
                    )
                    records.insert(0, "representation", representation)
                    records.insert(1, "seed", int(seed))
                    records["held_out_repetition"] = held_out_repetition
                    records["baseline_repetition"] = [
                        baseline_by_index[index]
                        if baseline_by_index[index] is not None
                        else ""
                        for index in test_indices
                    ]
                    records["predicted_load_kg"] = predictions
                    records["correct"] = (
                        records["truth_load_kg"].to_numpy(dtype=int) == predictions
                    )
                    records["confidence"] = probabilities.max(axis=1)
                    for column, load_kg in enumerate(LOADS):
                        records[f"probability_load_{load_kg}"] = probabilities[:, column]
                    seed_records.append(records)
            combined = pd.concat(seed_records, ignore_index=True)
            seed_results.append(
                {"seed": int(seed), **_probe_seed_metrics(combined)}
            )
            all_records.append(combined)
        results[representation] = {
            "per_seed": seed_results,
            "summary": _probe_summary(seed_results),
        }
    return pd.concat(all_records, ignore_index=True), results


def _equivalence_check(fault_records: pd.DataFrame, reference_path: Path) -> dict[str, Any]:
    reference = pd.read_csv(reference_path)
    reference = reference.loc[reference["protocol"].isin(REPRESENTATIONS)].copy()
    candidate = fault_records.loc[fault_records["estimator"] == "extra_trees"].copy()
    keys = ["protocol", "seed", "motion", "load_kg", "repetition", "truth"]
    probability_columns = [f"probability_{label}" for label in LABELS]
    merged = candidate.merge(
        reference.loc[:, [*keys, "prediction", *probability_columns]],
        on=keys,
        suffixes=("_new", "_reference"),
        validate="one_to_one",
    )
    predictions_identical = bool(
        (
            merged["prediction_new"].to_numpy(dtype=object)
            == merged["prediction_reference"].to_numpy(dtype=object)
        ).all()
    )
    maximum_difference = max(
        float(
            np.abs(
                merged[f"{column}_new"].to_numpy(dtype=float)
                - merged[f"{column}_reference"].to_numpy(dtype=float)
            ).max()
        )
        for column in probability_columns
    )
    if len(merged) != 1800 or not predictions_identical or maximum_difference > 1e-12:
        raise ValueError("EXP-020 ExtraTrees does not reproduce final EXP-010 P0/P2")
    return {
        "reference_path": str(reference_path.resolve()),
        "reference_sha256": _file_sha256(reference_path),
        "rows_compared": len(merged),
        "categorical_predictions_identical": predictions_identical,
        "maximum_probability_absolute_difference": maximum_difference,
    }


def _display(summary: dict[str, Any], metric: str) -> str:
    return f"{summary[metric]['mean']:.4f} ± {summary[metric]['sample_std']:.4f}"


def _render_report(metrics: dict[str, Any]) -> str:
    lines = [
        "# Cranfield classical baselines and environment probe",
        "",
        f"- Version: `{BASELINE_VERSION}`",
        "- Fault task: six motion-specific leave-one-load-out folds.",
        "- Probe task: leave-one-repetition-out load prediction within motion.",
        "",
        "## Fault classification",
        "",
        (
            "| Representation | Estimator | Macro F1 | Worst-fold F1 | Brier ↓ | "
            "Control ratio ↓ |"
        ),
        "|---|---|---:|---:|---:|---:|",
    ]
    fault_results = metrics["fault_classification"]["results"]
    for representation in REPRESENTATIONS:
        for estimator_name in ESTIMATORS:
            summary = fault_results[representation][estimator_name]["summary"]
            lines.append(
                "| "
                + " | ".join(
                    (
                        representation,
                        estimator_name,
                        _display(summary, "macro_f1"),
                        _display(summary, "worst_fold_macro_f1"),
                        _display(summary, "multiclass_brier"),
                        _display(summary, "control_ratio"),
                    )
                )
                + " |"
            )
    lines.extend(
        (
            "",
            "## Operating-environment prediction probe",
            "",
            "| Representation | Load macro F1 | trap macro F1 | sin macro F1 |",
            "|---|---:|---:|---:|",
        )
    )
    probe_results = metrics["environment_probe"]["results"]
    for representation in REPRESENTATIONS:
        summary = probe_results[representation]["summary"]
        lines.append(
            "| "
            + " | ".join(
                (
                    representation,
                    _display(summary, "macro_f1"),
                    _display(summary["per_motion"]["trap"], "macro_f1"),
                    _display(summary["per_motion"]["sin"], "macro_f1"),
                )
            )
            + " |"
        )
    lines.extend(
        (
            "",
            "High load predictability is a shortcut diagnostic, not causal attribution.",
            "P2 explicitly uses same-load healthy references and is not pure DG.",
            "",
        )
    )
    return "\n".join(lines)


def run_baselines(
    output_directory: Path,
    *,
    reference_records: Path | None = None,
    seeds: Sequence[int] = AUDIT_SEEDS,
) -> dict[str, Any]:
    if tuple(seeds) != AUDIT_SEEDS:
        raise ValueError("EXP-020 requires the frozen five-seed sequence")
    raw = build_raw_matrix()
    feature_columns = raw_feature_columns(raw)
    fault_records, fault_results = _run_fault_classifiers(
        raw, feature_columns, seeds
    )
    equivalence = (
        _equivalence_check(fault_records, reference_records)
        if reference_records is not None
        else None
    )
    probe_records, probe_results = _run_environment_probe(
        raw, feature_columns, seeds
    )
    metrics: dict[str, Any] = {
        "baseline_version": BASELINE_VERSION,
        "generated_at": datetime.now(UTC).isoformat(),
        "protocol_document": "research/protocols/cranfield_baselines_v0.1.md",
        "configuration": {
            "representations": list(REPRESENTATIONS),
            "estimators": list(ESTIMATORS),
            "seeds": list(seeds),
            "library_version": f"scikit-learn {sklearn.__version__}",
        },
        "fault_classification": {
            "outer_split": "motion-specific leave-one-load-out",
            "base_equivalence": equivalence,
            "results": fault_results,
            "model_independence": _model_independence(fault_results),
        },
        "environment_probe": {
            "outer_split": "within-motion leave-one-repetition-out",
            "held_out_repetition_used_as_reference": False,
            "results": probe_results,
        },
        "limitations": [
            "The fixed estimator suite is broad but not exhaustive.",
            "All physical trials are from one actuator rig.",
            "P2 reads a same-load healthy trajectory and is not domain generalization.",
            "Load predictability diagnoses retained nuisance information but not classifier use.",
            (
                "Estimator comparisons use fixed defaults rather than target-selected "
                "hyperparameters."
            ),
        ],
    }
    output_directory.mkdir(parents=True, exist_ok=True)
    fault_records.to_csv(output_directory / "fault_records.csv", index=False)
    probe_records.to_csv(output_directory / "probe_records.csv", index=False)
    (output_directory / "metrics.json").write_text(
        json.dumps(metrics, ensure_ascii=False, indent=2, allow_nan=False),
        encoding="utf-8",
    )
    (output_directory / "report.md").write_text(
        _render_report(metrics), encoding="utf-8"
    )
    return metrics


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-directory", type=Path, required=True)
    parser.add_argument("--reference-records", type=Path)
    args = parser.parse_args()
    result = run_baselines(
        args.output_directory, reference_records=args.reference_records
    )
    print(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False))


if __name__ == "__main__":
    main()
