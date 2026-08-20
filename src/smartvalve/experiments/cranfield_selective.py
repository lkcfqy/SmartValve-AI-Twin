"""Source-only selective prediction over Cranfield leave-one-load-out folds."""

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
from sklearn.ensemble import ExtraTreesClassifier
from sklearn.impute import SimpleImputer
from sklearn.metrics import f1_score
from sklearn.pipeline import Pipeline

from smartvalve.experiments.cranfield_causal_audit import (
    AUDIT_SEEDS,
    LABELS,
    LOADS,
    MOTIONS,
    _aligned_probabilities,
    build_raw_matrix,
    protocol_feature_frame,
    raw_feature_columns,
)

SELECTIVE_VERSION = "cranfield-source-selective-0.1.0"
CONFORMAL_ALPHA = 0.10
SUPPORT_RATIO_THRESHOLD = 1.0
POLICIES = (
    "none",
    "source_ood_conformal",
    "metadata_support",
    "hybrid",
)
SUMMARY_METRICS = (
    "coverage",
    "selective_accuracy",
    "macro_f1_abstention_as_error",
    "accepted_errors",
    "error_detection_recall",
    "correct_rejection_rate",
    "worst_nonempty_fold_selective_accuracy",
    "trap_minus40_accepted_errors",
)


def _file_sha256(path: Path) -> str:
    digest = sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def conformal_quantile(scores: Sequence[float], alpha: float = CONFORMAL_ALPHA) -> float:
    """Finite-sample split-conformal upper quantile."""

    values = np.asarray(scores, dtype=float)
    if len(values) == 0 or not np.isfinite(values).all():
        raise ValueError("conformal scores must be finite and non-empty")
    if not 0.0 < alpha < 1.0:
        raise ValueError("alpha must lie strictly between zero and one")
    rank = min(len(values), int(np.ceil((len(values) + 1) * (1.0 - alpha))))
    return float(np.sort(values)[rank - 1])


def metadata_support_ratio(target_load: int, source_loads: Sequence[int]) -> float:
    """Measure extrapolation distance in units of the source-load span."""

    ordered = sorted(int(load) for load in source_loads)
    if len(ordered) != 2 or ordered[0] == ordered[1]:
        raise ValueError("metadata support requires two distinct source loads")
    span = ordered[1] - ordered[0]
    if ordered[0] <= target_load <= ordered[1]:
        return 0.0
    distance = ordered[0] - target_load if target_load < ordered[0] else target_load - ordered[1]
    return float(distance / span)


def _classifier(seed: int) -> Pipeline:
    return Pipeline(
        (
            ("imputer", SimpleImputer(strategy="median", keep_empty_features=True)),
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
    )


def _source_ood_scores(
    raw: pd.DataFrame,
    features: pd.DataFrame,
    motion: str,
    source_loads: Sequence[int],
    seed: int,
) -> np.ndarray:
    scores: list[np.ndarray] = []
    for calibration_load in source_loads:
        fit_load = next(load for load in source_loads if load != calibration_load)
        fit_indices = raw.index[
            (raw["motion"] == motion) & (raw["load_kg"] == fit_load)
        ]
        calibration_indices = raw.index[
            (raw["motion"] == motion) & (raw["load_kg"] == calibration_load)
        ]
        classifier = _classifier(seed)
        classifier.fit(features.loc[fit_indices], raw.loc[fit_indices, "truth"])
        probabilities = np.round(
            _aligned_probabilities(classifier, features.loc[calibration_indices]), 12
        )
        truth_indices = np.asarray(
            [LABELS.index(label) for label in raw.loc[calibration_indices, "truth"]], dtype=int
        )
        scores.append(1.0 - probabilities[np.arange(len(calibration_indices)), truth_indices])
    return np.concatenate(scores)


def _fold_base_records(
    raw: pd.DataFrame,
    features: pd.DataFrame,
    motion: str,
    held_out_load: int,
    seed: int,
) -> pd.DataFrame:
    source_loads = [load for load in LOADS if load != held_out_load]
    source_indices = raw.index[
        (raw["motion"] == motion) & (raw["load_kg"].isin(source_loads))
    ]
    test_indices = raw.index[
        (raw["motion"] == motion) & (raw["load_kg"] == held_out_load)
    ]
    calibration_scores = _source_ood_scores(
        raw, features, motion, source_loads, seed
    )
    quantile = conformal_quantile(calibration_scores)
    classifier = _classifier(seed)
    classifier.fit(features.loc[source_indices], raw.loc[source_indices, "truth"])
    base_prediction = classifier.predict(features.loc[test_indices])
    probabilities = np.round(
        _aligned_probabilities(classifier, features.loc[test_indices]), 12
    )
    included = 1.0 - probabilities <= quantile + 1e-12
    cardinality = included.sum(axis=1)
    singleton_label = np.full(len(test_indices), "", dtype=object)
    singleton_rows = np.flatnonzero(cardinality == 1)
    if len(singleton_rows):
        singleton_label[singleton_rows] = np.asarray(LABELS, dtype=object)[
            included[singleton_rows].argmax(axis=1)
        ]
    support_ratio = metadata_support_ratio(held_out_load, source_loads)
    records = raw.loc[
        test_indices, ["motion", "load_kg", "repetition", "truth"]
    ].copy()
    records.insert(0, "seed", seed)
    records["base_prediction"] = base_prediction
    records["base_correct"] = records["truth"].to_numpy(dtype=object) == base_prediction
    records["confidence"] = probabilities.max(axis=1)
    for class_index, label in enumerate(LABELS):
        records[f"probability_{label}"] = probabilities[:, class_index]
    records["conformal_quantile"] = quantile
    records["conformal_set_size"] = cardinality
    records["conformal_singleton_label"] = singleton_label
    records["metadata_support_ratio"] = support_ratio
    records["metadata_supported"] = support_ratio <= SUPPORT_RATIO_THRESHOLD
    return records


def _apply_policy(base_records: pd.DataFrame, policy: str) -> pd.DataFrame:
    records = base_records.copy()
    conformal_accept = records["conformal_set_size"] == 1
    metadata_accept = records["metadata_supported"].astype(bool)
    if policy == "none":
        accepted = np.ones(len(records), dtype=bool)
        prediction = records["base_prediction"].to_numpy(dtype=object)
    elif policy == "source_ood_conformal":
        accepted = conformal_accept.to_numpy(dtype=bool)
        prediction = records["conformal_singleton_label"].to_numpy(dtype=object)
    elif policy == "metadata_support":
        accepted = metadata_accept.to_numpy(dtype=bool)
        prediction = records["base_prediction"].to_numpy(dtype=object)
    elif policy == "hybrid":
        accepted = (conformal_accept & metadata_accept).to_numpy(dtype=bool)
        prediction = records["conformal_singleton_label"].to_numpy(dtype=object)
    else:
        raise ValueError(f"unknown selection policy: {policy}")
    records.insert(0, "policy", policy)
    records["accepted"] = accepted
    records["selective_prediction"] = np.where(accepted, prediction, "abstain")
    records["selective_correct"] = accepted & (
        prediction == records["truth"].to_numpy(dtype=object)
    )
    return records


def selection_metrics(records: pd.DataFrame) -> dict[str, Any]:
    accepted = records["accepted"].to_numpy(dtype=bool)
    truth = records["truth"].to_numpy(dtype=object)
    prediction = records["selective_prediction"].to_numpy(dtype=object)
    base_correct = records["base_correct"].to_numpy(dtype=bool)
    accepted_correct = accepted & (prediction == truth)
    accepted_count = int(accepted.sum())
    selective_accuracy = (
        float(accepted_correct.sum() / accepted_count) if accepted_count else None
    )
    base_errors = ~base_correct
    fold_results: list[dict[str, Any]] = []
    for motion in MOTIONS:
        for load_kg in LOADS:
            fold = records.loc[
                (records["motion"] == motion) & (records["load_kg"] == load_kg)
            ]
            if fold.empty:
                continue
            fold_accepted = fold["accepted"].to_numpy(dtype=bool)
            fold_correct = fold["selective_correct"].to_numpy(dtype=bool)
            fold_accepted_count = int(fold_accepted.sum())
            fold_results.append(
                {
                    "motion": motion,
                    "held_out_load_kg": load_kg,
                    "coverage": float(fold_accepted.mean()),
                    "selective_accuracy": (
                        float(fold_correct.sum() / fold_accepted_count)
                        if fold_accepted_count
                        else None
                    ),
                    "accepted_errors": int((fold_accepted & ~fold_correct).sum()),
                    "base_errors": int((~fold["base_correct"].to_numpy(dtype=bool)).sum()),
                }
            )
    nonempty_accuracies = [
        float(fold["selective_accuracy"])
        for fold in fold_results
        if fold["selective_accuracy"] is not None
    ]
    trap_minus40 = next(
        fold
        for fold in fold_results
        if fold["motion"] == "trap" and fold["held_out_load_kg"] == -40
    )
    return {
        "coverage": float(accepted.mean()),
        "abstention_rate": float((~accepted).mean()),
        "selective_accuracy": selective_accuracy,
        "macro_f1_abstention_as_error": float(
            f1_score(
                truth,
                prediction,
                labels=list(LABELS),
                average="macro",
                zero_division=0,
            )
        ),
        "accepted_predictions": accepted_count,
        "accepted_errors": int((accepted & ~accepted_correct).sum()),
        "error_detection_recall": (
            float(((~accepted) & base_errors).sum() / base_errors.sum())
            if base_errors.any()
            else 0.0
        ),
        "correct_rejection_rate": (
            float(((~accepted) & base_correct).sum() / base_correct.sum())
            if base_correct.any()
            else 0.0
        ),
        "worst_nonempty_fold_selective_accuracy": (
            min(nonempty_accuracies) if nonempty_accuracies else None
        ),
        "zero_coverage_folds": [
            {
                "motion": fold["motion"],
                "held_out_load_kg": fold["held_out_load_kg"],
            }
            for fold in fold_results
            if fold["coverage"] == 0.0
        ],
        "trap_minus40_accepted_errors": int(trap_minus40["accepted_errors"]),
        "folds": fold_results,
    }


def _summary(seed_results: Sequence[dict[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for metric in SUMMARY_METRICS:
        values = np.asarray(
            [item[metric] for item in seed_results if item[metric] is not None], dtype=float
        )
        result[metric] = (
            {
                "mean": float(values.mean()),
                "sample_std": float(values.std(ddof=1)) if len(values) > 1 else 0.0,
                "min": float(values.min()),
                "max": float(values.max()),
            }
            if len(values)
            else None
        )
    result["zero_coverage_folds"] = sorted(
        {
            (fold["motion"], int(fold["held_out_load_kg"]))
            for item in seed_results
            for fold in item["zero_coverage_folds"]
        }
    )
    return result


def _coverage_risk_curve(base_records: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for seed in AUDIT_SEEDS:
        records = base_records.loc[base_records["seed"] == seed].sort_values(
            ["confidence", "motion", "load_kg", "repetition"],
            ascending=[False, True, True, True],
            kind="stable",
        )
        errors = (~records["base_correct"].to_numpy(dtype=bool)).astype(int)
        cumulative_errors = np.cumsum(errors)
        for accepted_count in range(1, len(records) + 1):
            rows.append(
                {
                    "seed": seed,
                    "accepted_count": accepted_count,
                    "coverage": accepted_count / len(records),
                    "selective_risk": cumulative_errors[accepted_count - 1] / accepted_count,
                    "confidence_threshold": float(
                        records.iloc[accepted_count - 1]["confidence"]
                    ),
                }
            )
    return pd.DataFrame(rows)


def _equivalence_check(base_records: pd.DataFrame, reference_path: Path) -> dict[str, Any]:
    reference = pd.read_csv(reference_path)
    reference = reference.loc[reference["protocol"] == "P0"].copy()
    key_columns = ["seed", "motion", "load_kg", "repetition", "truth"]
    probability_columns = [f"probability_{label}" for label in LABELS]
    merged = base_records.merge(
        reference.loc[
            :, [*key_columns, "prediction", *probability_columns]
        ],
        on=key_columns,
        suffixes=("_new", "_reference"),
        validate="one_to_one",
    )
    categorical_identical = bool(
        (
            merged["base_prediction"].to_numpy(dtype=object)
            == merged["prediction"].to_numpy(dtype=object)
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
    if not categorical_identical or maximum_difference > 1e-12:
        raise ValueError("EXP-012 base predictions do not reproduce final EXP-010 P0")
    return {
        "reference_path": str(reference_path.resolve()),
        "reference_sha256": _file_sha256(reference_path),
        "rows_compared": len(merged),
        "categorical_predictions_identical": categorical_identical,
        "maximum_probability_absolute_difference": maximum_difference,
    }


def _render_report(metrics: dict[str, Any]) -> str:
    lines = [
        "# Cranfield source-only selective prediction",
        "",
        f"- Version: `{SELECTIVE_VERSION}`",
        f"- Conformal alpha: {CONFORMAL_ALPHA}",
        f"- Metadata support threshold: {SUPPORT_RATIO_THRESHOLD}",
        "",
        "| Policy | Coverage | Selective accuracy | F1 (abstention=error) "
        "| Error recall | Accepted errors | trap/-40 errors |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for policy in POLICIES:
        summary = metrics["results"][policy]["summary"]

        display = {
            metric: (
                "NA"
                if summary[metric] is None
                else (
                    f"{summary[metric]['mean']:.4f} ± "
                    f"{summary[metric]['sample_std']:.4f}"
                )
            )
            for metric in SUMMARY_METRICS
        }

        lines.append(
            "| "
            + " | ".join(
                (
                    policy,
                    display["coverage"],
                    display["selective_accuracy"],
                    display["macro_f1_abstention_as_error"],
                    display["error_detection_recall"],
                    display["accepted_errors"],
                    display["trap_minus40_accepted_errors"],
                )
            )
            + " |"
        )
    lines.extend(
        (
            "",
            "The support gate uses only the known target load and the two source-load values.",
            "The conformal gate is calibrated from source-to-source held-load predictions only.",
            "Zero-coverage folds remain explicit and are never scored as perfect "
            "selective accuracy.",
            "",
        )
    )
    return "\n".join(lines)


def run_selective_experiment(
    output_directory: Path,
    *,
    reference_records: Path | None = None,
    seeds: Sequence[int] = AUDIT_SEEDS,
) -> dict[str, Any]:
    if tuple(seeds) != AUDIT_SEEDS:
        raise ValueError("EXP-012 requires the frozen five-seed sequence")
    raw = build_raw_matrix()
    feature_columns = raw_feature_columns(raw)
    motion_features: dict[str, pd.DataFrame] = {}
    for motion in MOTIONS:
        motion_indices = raw.index[raw["motion"] == motion]
        source_indices = motion_indices
        features, _ = protocol_feature_frame(
            raw, "P0", motion_indices, source_indices, feature_columns
        )
        motion_features[motion] = features
    base_parts: list[pd.DataFrame] = []
    for seed in seeds:
        for motion in MOTIONS:
            for held_out_load in LOADS:
                base_parts.append(
                    _fold_base_records(
                        raw,
                        motion_features[motion],
                        motion,
                        held_out_load,
                        int(seed),
                    )
                )
    base_records = pd.concat(base_parts, ignore_index=True)
    equivalence = (
        _equivalence_check(base_records, reference_records)
        if reference_records is not None
        else None
    )
    policy_records = pd.concat(
        [_apply_policy(base_records, policy) for policy in POLICIES], ignore_index=True
    )
    policy_results: dict[str, Any] = {}
    for policy in POLICIES:
        seed_results: list[dict[str, Any]] = []
        for seed in seeds:
            records = policy_records.loc[
                (policy_records["policy"] == policy) & (policy_records["seed"] == seed)
            ]
            seed_results.append({"seed": int(seed), **selection_metrics(records)})
        policy_results[policy] = {
            "per_seed": seed_results,
            "summary": _summary(seed_results),
        }
    coverage_risk = _coverage_risk_curve(base_records)
    metrics: dict[str, Any] = {
        "selective_version": SELECTIVE_VERSION,
        "generated_at": datetime.now(UTC).isoformat(),
        "protocol_document": "research/protocols/cranfield_selective_v0.1.md",
        "status": "post-EXP-010 exploratory source-only selection",
        "configuration": {
            "seeds": list(seeds),
            "protocol": "P0 raw features, motion-specific leave-one-load-out",
            "conformal_alpha": CONFORMAL_ALPHA,
            "metadata_support_ratio_threshold": SUPPORT_RATIO_THRESHOLD,
            "estimator": "frozen EXP-010 ExtraTrees with train-only median imputation",
            "library_version": f"scikit-learn {sklearn.__version__}",
        },
        "base_equivalence": equivalence,
        "results": policy_results,
        "limitations": [
            "This protocol was designed after observing the EXP-010 trap/-40 failure.",
            "Source-to-source conformal calibration does not guarantee target-load coverage.",
            "The metadata support threshold is an engineering envelope, not a learned causal law.",
            "Rejecting an entire environment can improve safety while sacrificing useful coverage.",
            "Results remain single-rig and do not establish between-asset selective risk.",
        ],
    }
    output_directory.mkdir(parents=True, exist_ok=True)
    policy_records.to_csv(output_directory / "records.csv", index=False)
    coverage_risk.to_csv(output_directory / "coverage_risk_curve.csv", index=False)
    (output_directory / "metrics.json").write_text(
        json.dumps(metrics, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8"
    )
    (output_directory / "report.md").write_text(_render_report(metrics), encoding="utf-8")
    return metrics


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-directory", type=Path, required=True)
    parser.add_argument("--reference-records", type=Path)
    args = parser.parse_args()
    result = run_selective_experiment(
        args.output_directory, reference_records=args.reference_records
    )
    print(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False))


if __name__ == "__main__":
    main()
