"""Paired physical-block bootstrap for the frozen UCI hydraulic access audit."""

from __future__ import annotations

import argparse
import json
from collections.abc import Sequence
from datetime import UTC, datetime
from hashlib import sha256
from itertools import combinations, product
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from smartvalve.data.uci_hydraulic import (
    CONTEXT_COLUMNS,
    CONTEXT_LEVELS,
    PRIMARY_REPETITIONS,
)
from smartvalve.experiments.cranfield_baselines import ESTIMATORS
from smartvalve.experiments.cranfield_causal_audit import AUDIT_SEEDS
from smartvalve.experiments.uci_hydraulic_access import LABELS, PROTOCOLS

BOOTSTRAP_VERSION = "uci-hydraulic-paired-bootstrap-0.1.0"
BOOTSTRAP_REPLICATES = 2_000
BOOTSTRAP_SEED = 20_260_818
PERFORMANCE_METRICS = (
    "mean_fold_accuracy",
    "mean_fold_macro_f1",
    "worst_fold_macro_f1",
    "mean_fold_multiclass_brier",
    "mean_axis_ece",
)
CONTROL_METRICS = (
    "max_context_sensitivity_tv",
    "mean_fault_sensitivity_tv",
    "max_control_ratio",
)
ALL_METRICS = PERFORMANCE_METRICS + CONTROL_METRICS
CONTEXTS = tuple(product(*(CONTEXT_LEVELS[column] for column in CONTEXT_COLUMNS)))
PROBABILITY_COLUMNS = tuple(f"probability_{label}" for label in LABELS)
EXPECTED_RECORD_ROWS = (
    len(ESTIMATORS)
    * len(PROTOCOLS)
    * len(AUDIT_SEEDS)
    * len(CONTEXT_COLUMNS)
    * len(CONTEXTS)
    * len(PRIMARY_REPETITIONS)
    * len(LABELS)
)
REQUIRED_COLUMNS = {
    "archive_row",
    "protocol",
    "estimator",
    "seed",
    "held_factor",
    "held_level",
    *CONTEXT_COLUMNS,
    "repetition",
    "truth",
    "baseline_repetition",
    "prediction",
    *PROBABILITY_COLUMNS,
}


def _file_sha256(path: Path) -> str:
    digest = sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_and_validate_records(path: Path) -> pd.DataFrame:
    """Load EXP-110 predictions and reject an altered or incomplete factorial."""

    records = pd.read_parquet(path)
    missing = REQUIRED_COLUMNS - set(records.columns)
    if missing:
        raise ValueError(f"missing required record columns: {sorted(missing)}")
    if len(records) != EXPECTED_RECORD_ROWS:
        raise ValueError(
            f"expected {EXPECTED_RECORD_ROWS:,} prediction rows, found {len(records):,}"
        )
    frozen_sets = (
        ("protocol", set(PROTOCOLS)),
        ("estimator", set(ESTIMATORS)),
        ("seed", set(AUDIT_SEEDS)),
        ("held_factor", set(CONTEXT_COLUMNS)),
        ("truth", set(LABELS)),
        ("prediction", set(LABELS)),
    )
    for column, expected in frozen_sets:
        actual = set(records[column])
        if actual != expected:
            raise ValueError(f"{column} grid differs from frozen values")
    probabilities = records.loc[:, PROBABILITY_COLUMNS].to_numpy(dtype=float)
    if not np.isfinite(probabilities).all():
        raise ValueError("records contain non-finite probabilities")
    if not np.allclose(probabilities.sum(axis=1), 1.0, atol=5e-10):
        raise ValueError("class probabilities do not sum to one")
    for factor in CONTEXT_COLUMNS:
        rows = records["held_factor"] == factor
        if not (
            records.loc[rows, "held_level"].to_numpy(dtype=int)
            == records.loc[rows, factor].to_numpy(dtype=int)
        ).all():
            raise ValueError(f"held levels do not match the {factor} context column")
    p2 = records["protocol"] == "P2"
    expected_baseline = records["repetition"].to_numpy(dtype=int) % 10 + 1
    if not (
        records.loc[p2, "baseline_repetition"].to_numpy(dtype=int) == expected_baseline[p2]
    ).all():
        raise ValueError("P2 baseline repetitions do not follow the frozen rotation")
    if not (records.loc[~p2, "baseline_repetition"].to_numpy(dtype=int) == -1).all():
        raise ValueError("P0/P1 unexpectedly record a target baseline")
    group_columns = ["estimator", "protocol", "seed", "held_factor"]
    sizes = records.groupby(group_columns, observed=True).size()
    expected_groups = (
        len(ESTIMATORS) * len(PROTOCOLS) * len(AUDIT_SEEDS) * len(CONTEXT_COLUMNS)
    )
    if len(sizes) != expected_groups or not (sizes == 1440).all():
        raise ValueError("estimator/protocol/seed/axis cells are incomplete")
    if records.duplicated([*group_columns, "archive_row"]).any():
        raise ValueError("a frozen cycle is duplicated within an axis prediction grid")
    truth_counts = records.groupby([*group_columns, "truth"], observed=True).size()
    if not (truth_counts == 360).all():
        raise ValueError("an axis prediction grid is not balanced across valve states")
    return records


def _tensorize_records(records: pd.DataFrame) -> tuple[np.ndarray, np.ndarray]:
    """Convert the validated table to estimator/protocol/seed/axis/context/block tensors."""

    shape = (
        len(ESTIMATORS),
        len(PROTOCOLS),
        len(AUDIT_SEEDS),
        len(CONTEXT_COLUMNS),
        len(CONTEXTS),
        len(PRIMARY_REPETITIONS),
        len(LABELS),
    )
    probabilities = np.full((*shape, len(LABELS)), np.nan, dtype=float)
    predictions = np.full(shape, -1, dtype=np.int8)
    mappings = (
        {value: index for index, value in enumerate(ESTIMATORS)},
        {value: index for index, value in enumerate(PROTOCOLS)},
        {value: index for index, value in enumerate(AUDIT_SEEDS)},
        {value: index for index, value in enumerate(CONTEXT_COLUMNS)},
        {value: index for index, value in enumerate(CONTEXTS)},
        {value: index for index, value in enumerate(PRIMARY_REPETITIONS)},
        {value: index for index, value in enumerate(LABELS)},
    )
    context_values = list(records.loc[:, CONTEXT_COLUMNS].itertuples(index=False, name=None))
    index = (
        records["estimator"].map(mappings[0]).to_numpy(dtype=int),
        records["protocol"].map(mappings[1]).to_numpy(dtype=int),
        records["seed"].map(mappings[2]).to_numpy(dtype=int),
        records["held_factor"].map(mappings[3]).to_numpy(dtype=int),
        np.fromiter((mappings[4][value] for value in context_values), dtype=int),
        records["repetition"].map(mappings[5]).to_numpy(dtype=int),
        records["truth"].map(mappings[6]).to_numpy(dtype=int),
    )
    probabilities[index] = records.loc[:, PROBABILITY_COLUMNS].to_numpy(dtype=float)
    predictions[index] = records["prediction"].map(mappings[6]).to_numpy(dtype=np.int8)
    if not np.isfinite(probabilities).all() or (predictions < 0).any():
        raise ValueError("prediction tensor is incomplete")
    return probabilities, predictions


def _sample_tensors(
    probabilities: np.ndarray,
    predictions: np.ndarray,
    choices: np.ndarray,
) -> tuple[np.ndarray, np.ndarray]:
    sampled_probabilities = np.empty_like(probabilities)
    sampled_predictions = np.empty_like(predictions)
    for context_index in range(len(CONTEXTS)):
        repetitions = choices[context_index]
        sampled_probabilities[..., context_index, :, :, :] = probabilities[
            ..., context_index, repetitions, :, :
        ]
        sampled_predictions[..., context_index, :, :] = predictions[
            ..., context_index, repetitions, :
        ]
    return sampled_probabilities, sampled_predictions


def _macro_f1(truth: np.ndarray, prediction: np.ndarray) -> float:
    class_count = len(LABELS)
    confusion = np.bincount(
        truth.ravel() * class_count + prediction.ravel(),
        minlength=class_count**2,
    ).reshape(class_count, class_count)
    true_positive = np.diag(confusion).astype(float)
    denominator = confusion.sum(axis=0) + confusion.sum(axis=1)
    class_f1 = np.divide(
        2.0 * true_positive,
        denominator,
        out=np.zeros_like(true_positive),
        where=denominator > 0,
    )
    return float(class_f1.mean())


def _ece(truth: np.ndarray, probabilities: np.ndarray, *, bins: int = 10) -> float:
    confidence = probabilities.max(axis=-1)
    correct = probabilities.argmax(axis=-1) == truth
    bin_ids = np.minimum((confidence * bins).astype(int), bins - 1)
    result = 0.0
    for bin_id in range(bins):
        mask = bin_ids == bin_id
        if np.any(mask):
            result += float(mask.mean()) * abs(
                float(correct[mask].mean()) - float(confidence[mask].mean())
            )
    return result


def _performance_metric_tensor(
    probabilities: np.ndarray,
    predictions: np.ndarray,
    choices: np.ndarray,
) -> np.ndarray:
    sampled_probabilities, sampled_predictions = _sample_tensors(
        probabilities, predictions, choices
    )
    result = np.empty(
        (len(ESTIMATORS), len(PROTOCOLS), len(AUDIT_SEEDS), len(PERFORMANCE_METRICS)),
        dtype=float,
    )
    context_array = np.asarray(CONTEXTS, dtype=int)
    truth_template = np.arange(len(LABELS), dtype=np.int8)
    for estimator_index in range(len(ESTIMATORS)):
        for protocol_index in range(len(PROTOCOLS)):
            for seed_index in range(len(AUDIT_SEEDS)):
                fold_accuracy: list[float] = []
                fold_macro_f1: list[float] = []
                fold_brier: list[float] = []
                axis_ece: list[float] = []
                for axis_index, factor in enumerate(CONTEXT_COLUMNS):
                    axis_probabilities = sampled_probabilities[
                        estimator_index, protocol_index, seed_index, axis_index
                    ]
                    axis_predictions = sampled_predictions[
                        estimator_index, protocol_index, seed_index, axis_index
                    ]
                    axis_truth = np.broadcast_to(truth_template, axis_predictions.shape)
                    axis_ece.append(_ece(axis_truth, axis_probabilities))
                    for level in CONTEXT_LEVELS[factor]:
                        context_rows = context_array[:, axis_index] == level
                        fold_prediction = axis_predictions[context_rows]
                        fold_probability = axis_probabilities[context_rows]
                        fold_truth = axis_truth[context_rows]
                        fold_accuracy.append(float((fold_prediction == fold_truth).mean()))
                        fold_macro_f1.append(_macro_f1(fold_truth, fold_prediction))
                        one_hot = np.eye(len(LABELS), dtype=float)[fold_truth]
                        fold_brier.append(
                            float(np.mean(np.sum((fold_probability - one_hot) ** 2, axis=-1)))
                        )
                result[estimator_index, protocol_index, seed_index] = (
                    float(np.mean(fold_accuracy)),
                    float(np.mean(fold_macro_f1)),
                    float(np.min(fold_macro_f1)),
                    float(np.mean(fold_brier)),
                    float(np.mean(axis_ece)),
                )
    return result


def _control_choices(rng: np.random.Generator) -> np.ndarray:
    """Synchronize block draws across levels of each tested context factor."""

    choices = np.empty(
        (len(CONTEXT_COLUMNS), len(CONTEXTS), len(PRIMARY_REPETITIONS)), dtype=int
    )
    for axis_index in range(len(CONTEXT_COLUMNS)):
        other_axes = [index for index in range(len(CONTEXT_COLUMNS)) if index != axis_index]
        other_levels = product(*(CONTEXT_LEVELS[CONTEXT_COLUMNS[index]] for index in other_axes))
        for fixed_values in other_levels:
            context_indices = [
                index
                for index, context in enumerate(CONTEXTS)
                if all(
                    context[axis] == value
                    for axis, value in zip(other_axes, fixed_values, strict=True)
                )
            ]
            draws = rng.integers(
                0, len(PRIMARY_REPETITIONS), size=len(PRIMARY_REPETITIONS)
            )
            choices[axis_index, context_indices] = draws
    return choices


def _sample_axis_probabilities(
    probabilities: np.ndarray,
    axis_index: int,
    choices: np.ndarray,
) -> np.ndarray:
    axis = probabilities[:, :, :, axis_index]
    sampled = np.empty_like(axis)
    for context_index in range(len(CONTEXTS)):
        sampled[..., context_index, :, :, :] = axis[
            ..., context_index, choices[context_index], :, :
        ]
    return sampled


def _control_metric_tensor(probabilities: np.ndarray, choices: np.ndarray) -> np.ndarray:
    context_tv = []
    fault_tv = []
    ratios = []
    truth_pairs = tuple(combinations(range(len(LABELS)), 2))
    for axis_index in range(len(CONTEXT_COLUMNS)):
        sampled = _sample_axis_probabilities(probabilities, axis_index, choices[axis_index])
        other_axes = [index for index in range(len(CONTEXT_COLUMNS)) if index != axis_index]
        context_pairs = []
        other_levels = product(*(CONTEXT_LEVELS[CONTEXT_COLUMNS[index]] for index in other_axes))
        for fixed_values in other_levels:
            context_indices = [
                index
                for index, context in enumerate(CONTEXTS)
                if all(
                    context[axis] == value
                    for axis, value in zip(other_axes, fixed_values, strict=True)
                )
            ]
            context_pairs.extend(combinations(context_indices, 2))
        nuisance_distances = [
            0.5
            * np.abs(sampled[..., left, :, :, :] - sampled[..., right, :, :, :]).sum(
                axis=-1
            )
            for left, right in context_pairs
        ]
        nuisance = np.stack(nuisance_distances, axis=-1).mean(axis=(-3, -2, -1))
        fault_distances = [
            0.5 * np.abs(sampled[..., left, :] - sampled[..., right, :]).sum(axis=-1)
            for left, right in truth_pairs
        ]
        fault = np.stack(fault_distances, axis=-1).mean(axis=(-3, -2, -1))
        ratio = np.divide(
            nuisance,
            fault,
            out=np.full_like(nuisance, np.nan),
            where=fault > 0,
        )
        context_tv.append(nuisance)
        fault_tv.append(fault)
        ratios.append(ratio)
    stacked_context = np.stack(context_tv, axis=-1)
    stacked_fault = np.stack(fault_tv, axis=-1)
    stacked_ratios = np.stack(ratios, axis=-1)
    return np.stack(
        (
            stacked_context.max(axis=-1),
            stacked_fault.mean(axis=-1),
            stacked_ratios.max(axis=-1),
        ),
        axis=-1,
    )


def _all_metric_tensor(
    probabilities: np.ndarray,
    predictions: np.ndarray,
    performance_choices: np.ndarray,
    control_choices: np.ndarray,
) -> np.ndarray:
    return np.concatenate(
        (
            _performance_metric_tensor(probabilities, predictions, performance_choices),
            _control_metric_tensor(probabilities, control_choices),
        ),
        axis=-1,
    )


def _interval(point_estimate: float, values: Sequence[float]) -> dict[str, float]:
    array = np.asarray(values, dtype=float)
    if len(array) == 0 or not np.isfinite(array).all():
        raise ValueError("bootstrap distribution must be finite and non-empty")
    return {
        "point_estimate": float(point_estimate),
        "bootstrap_mean": float(array.mean()),
        "bootstrap_standard_error": float(array.std(ddof=1)) if len(array) > 1 else 0.0,
        "ci95_low": float(np.quantile(array, 0.025)),
        "ci95_high": float(np.quantile(array, 0.975)),
    }


def _summaries(point: np.ndarray, replicates: pd.DataFrame) -> dict[str, Any]:
    results: dict[str, Any] = {}
    for estimator_index, estimator in enumerate(ESTIMATORS):
        results[estimator] = {}
        for protocol_index, protocol in enumerate(PROTOCOLS):
            rows = replicates.loc[
                (replicates["estimator"] == estimator) & (replicates["protocol"] == protocol)
            ]
            results[estimator][protocol] = {
                metric: _interval(
                    point[estimator_index, protocol_index, metric_index], rows[metric]
                )
                for metric_index, metric in enumerate(ALL_METRICS)
            }
    return results


def _paired_comparisons(point: np.ndarray, replicates: pd.DataFrame) -> dict[str, Any]:
    results: dict[str, Any] = {}
    protocol_index = {protocol: index for index, protocol in enumerate(PROTOCOLS)}
    for estimator_index, estimator in enumerate(ESTIMATORS):
        estimator_rows = replicates.loc[replicates["estimator"] == estimator]
        results[estimator] = {}
        for left, right in (("P1", "P0"), ("P2", "P0"), ("P2", "P1")):
            left_rows = estimator_rows.loc[
                estimator_rows["protocol"] == left
            ].set_index("replicate")
            right_rows = estimator_rows.loc[
                estimator_rows["protocol"] == right
            ].set_index("replicate")
            results[estimator][f"{left}_minus_{right}"] = {}
            for metric_index, metric in enumerate(ALL_METRICS):
                differences = left_rows[metric] - right_rows[metric]
                interval = _interval(
                    point[estimator_index, protocol_index[left], metric_index]
                    - point[estimator_index, protocol_index[right], metric_index],
                    differences,
                )
                interval["resolved_away_from_zero"] = bool(
                    interval["ci95_low"] > 0 or interval["ci95_high"] < 0
                )
                results[estimator][f"{left}_minus_{right}"][metric] = interval
    return results


def _replication_assessment(comparisons: dict[str, Any]) -> dict[str, Any]:
    c1_estimators = []
    c2_estimators = []
    for estimator in ESTIMATORS:
        p1 = comparisons[estimator]["P1_minus_P0"]
        p2 = comparisons[estimator]["P2_minus_P0"]
        p1_f1 = p1["mean_fold_macro_f1"]
        p2_f1 = p2["mean_fold_macro_f1"]
        p2_brier = p2["mean_fold_multiclass_brier"]
        if p1_f1["ci95_high"] < 0:
            c1_estimators.append(estimator)
        if (
            p2_f1["ci95_low"] <= 0 <= p2_f1["ci95_high"]
            and p2_brier["ci95_low"] > 0
        ):
            c2_estimators.append(estimator)
    return {
        "C1_source_context_reference_harms_macro_f1": {
            "supporting_estimators": c1_estimators,
            "support_count": len(c1_estimators),
            "model_independent": len(c1_estimators) >= 3,
        },
        "C2_matched_target_reference_no_f1_gain_and_worse_brier": {
            "supporting_estimators": c2_estimators,
            "support_count": len(c2_estimators),
            "model_independent": len(c2_estimators) >= 3,
        },
    }


def _format_interval(result: dict[str, float]) -> str:
    return (
        f"{result['point_estimate']:.4f} "
        f"[{result['ci95_low']:.4f}, {result['ci95_high']:.4f}]"
    )


def _render_report(metrics: dict[str, Any]) -> str:
    lines = [
        "# UCI hydraulic paired block-bootstrap results",
        "",
        f"- Version: `{BOOTSTRAP_VERSION}`",
        f"- Replicates: {metrics['configuration']['replicates']}",
        f"- RNG seed: {metrics['configuration']['seed']}",
        "- Intervals: paired percentile 95% confidence intervals",
        "",
        "| Estimator | Protocol | Mean-fold macro F1 | Worst-fold F1 | Brier ↓ | Max ratio ↓ |",
        "|---|---|---:|---:|---:|---:|",
    ]
    for estimator in ESTIMATORS:
        for protocol in PROTOCOLS:
            result = metrics["results"][estimator][protocol]
            lines.append(
                "| "
                + " | ".join(
                    (
                        estimator,
                        protocol,
                        _format_interval(result["mean_fold_macro_f1"]),
                        _format_interval(result["worst_fold_macro_f1"]),
                        _format_interval(result["mean_fold_multiclass_brier"]),
                        _format_interval(result["max_control_ratio"]),
                    )
                )
                + " |"
            )
    lines.extend(("", "## Frozen replication decisions", ""))
    for claim, result in metrics["replication_assessment"].items():
        supporters = ", ".join(result["supporting_estimators"]) or "none"
        lines.append(
            f"- `{claim}`: {result['support_count']}/5 ({supporters}); "
            f"model-independent={result['model_independent']}"
        )
    lines.extend(
        (
            "",
            "Performance resampling is stratified within each exact context. Matched-control",
            "resampling synchronizes repetition draws across levels of the tested factor. Model",
            "seeds are averaged and never treated as physical replicates.",
            "",
        )
    )
    return "\n".join(lines)


def run_bootstrap(
    records_path: Path,
    output_directory: Path,
    *,
    replicates: int = BOOTSTRAP_REPLICATES,
    seed: int = BOOTSTRAP_SEED,
) -> dict[str, Any]:
    if replicates < 1:
        raise ValueError("replicates must be positive")
    records_path = records_path.resolve()
    records = load_and_validate_records(records_path)
    probabilities, predictions = _tensorize_records(records)
    identity_performance = np.broadcast_to(
        np.arange(len(PRIMARY_REPETITIONS)),
        (len(CONTEXTS), len(PRIMARY_REPETITIONS)),
    )
    identity_control = np.broadcast_to(
        np.arange(len(PRIMARY_REPETITIONS)),
        (len(CONTEXT_COLUMNS), len(CONTEXTS), len(PRIMARY_REPETITIONS)),
    )
    point_by_seed = _all_metric_tensor(
        probabilities,
        predictions,
        identity_performance,
        identity_control,
    )
    point = point_by_seed.mean(axis=2)
    performance_rng = np.random.default_rng(seed)
    control_rng = np.random.default_rng(seed + 1)
    replicate_rows: list[dict[str, Any]] = []
    for replicate in range(replicates):
        performance_choices = performance_rng.integers(
            0,
            len(PRIMARY_REPETITIONS),
            size=(len(CONTEXTS), len(PRIMARY_REPETITIONS)),
        )
        control_choices = _control_choices(control_rng)
        values = _all_metric_tensor(
            probabilities,
            predictions,
            performance_choices,
            control_choices,
        ).mean(axis=2)
        for estimator_index, estimator in enumerate(ESTIMATORS):
            for protocol_index, protocol in enumerate(PROTOCOLS):
                replicate_rows.append(
                    {
                        "replicate": replicate,
                        "estimator": estimator,
                        "protocol": protocol,
                        **{
                            metric: float(values[estimator_index, protocol_index, index])
                            for index, metric in enumerate(ALL_METRICS)
                        },
                    }
                )
    replicate_frame = pd.DataFrame(replicate_rows)
    results = _summaries(point, replicate_frame)
    comparisons = _paired_comparisons(point, replicate_frame)
    metrics: dict[str, Any] = {
        "bootstrap_version": BOOTSTRAP_VERSION,
        "generated_at": datetime.now(UTC).isoformat(),
        "protocol_document": "research/protocols/uci_hydraulic_bootstrap_v0.1.md",
        "input": {
            "records_path": str(records_path),
            "records_sha256": _file_sha256(records_path),
            "rows": len(records),
            "estimators": list(ESTIMATORS),
            "protocols": list(PROTOCOLS),
            "seeds": list(AUDIT_SEEDS),
        },
        "configuration": {
            "replicates": replicates,
            "seed": seed,
            "interval": "paired percentile 95%",
            "performance_sampling": "ten complete blocks within each of 36 contexts",
            "control_sampling": "factor-matched synchronized complete-block draws",
            "model_seed_treatment": "average within replicate",
        },
        "results": results,
        "paired_comparisons": comparisons,
        "replication_assessment": _replication_assessment(comparisons),
        "limitations": [
            "Intervals are conditional on the frozen cohort, features and five model seeds.",
            "Ten blocks per context limit tail precision.",
            "These access-audit intervals do not test a new SmartValve method.",
            "Multi-dataset primary method comparisons require a separately frozen correction.",
        ],
    }
    output_directory.mkdir(parents=True, exist_ok=True)
    replicate_path = output_directory / "bootstrap_replicates.parquet"
    replicate_frame.to_parquet(replicate_path, index=False)
    metrics["artifacts"] = {
        "replicates": {
            "path": replicate_path.name,
            "bytes": replicate_path.stat().st_size,
            "sha256": _file_sha256(replicate_path),
            "rows": len(replicate_frame),
        }
    }
    (output_directory / "metrics.json").write_text(
        json.dumps(metrics, ensure_ascii=False, indent=2, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    (output_directory / "report.md").write_text(_render_report(metrics), encoding="utf-8")
    return metrics


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--records", type=Path, required=True)
    parser.add_argument("--output-directory", type=Path, required=True)
    parser.add_argument("--replicates", type=int, default=BOOTSTRAP_REPLICATES)
    parser.add_argument("--seed", type=int, default=BOOTSTRAP_SEED)
    args = parser.parse_args()
    result = run_bootstrap(
        args.records,
        args.output_directory,
        replicates=args.replicates,
        seed=args.seed,
    )
    print(json.dumps(result["artifacts"], ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
