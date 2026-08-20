"""Paired physical-block bootstrap for the frozen Cranfield reference audit."""

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
from sklearn.metrics import accuracy_score, f1_score

from smartvalve.experiments.cranfield_causal_audit import (
    AUDIT_SEEDS,
    BALANCED_RANDOM_GUESS_ACCURACY,
    LABELS,
    LOADS,
    MOTIONS,
    PROTOCOLS,
    calibration_metrics,
    control_metrics,
)

BOOTSTRAP_VERSION = "cranfield-paired-bootstrap-0.1.0"
BOOTSTRAP_REPLICATES = 2_000
BOOTSTRAP_SEED = 20_260_817
PERFORMANCE_METRICS = (
    "accuracy",
    "macro_f1",
    "worst_fold_accuracy",
    "worst_fold_macro_f1",
    "multiclass_brier",
    "ece_10_bin",
)
CONTROL_METRICS = (
    "nuisance_sensitivity_tv",
    "fault_sensitivity_tv",
    "control_ratio",
)
ALL_METRICS = PERFORMANCE_METRICS + CONTROL_METRICS
REQUIRED_COLUMNS = {
    "protocol",
    "seed",
    "motion",
    "load_kg",
    "repetition",
    "truth",
    "prediction",
    *(f"probability_{label}" for label in LABELS),
}


def _file_sha256(path: Path) -> str:
    digest = sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_and_validate_records(path: Path) -> pd.DataFrame:
    """Load the final EXP-010 records and reject incomplete or altered grids."""

    records = pd.read_csv(path)
    missing = REQUIRED_COLUMNS - set(records.columns)
    if missing:
        raise ValueError(f"missing required record columns: {sorted(missing)}")
    if set(records["protocol"]) != set(PROTOCOLS):
        raise ValueError("records must contain exactly P0, P1, and P2")
    if set(records["seed"].astype(int)) != set(AUDIT_SEEDS):
        raise ValueError("records do not contain the frozen five-seed grid")
    probability_columns = [f"probability_{label}" for label in LABELS]
    probabilities = records.loc[:, probability_columns].to_numpy(dtype=float)
    if not np.isfinite(probabilities).all():
        raise ValueError("records contain non-finite probabilities")
    if not np.allclose(probabilities.sum(axis=1), 1.0, atol=1e-9):
        raise ValueError("class probabilities do not sum to one")
    expected_keys = {
        (motion, load_kg, repetition, truth)
        for motion in MOTIONS
        for load_kg in LOADS
        for repetition in range(1, 11)
        for truth in LABELS
    }
    key_columns = ["motion", "load_kg", "repetition", "truth"]
    for protocol in PROTOCOLS:
        for seed in AUDIT_SEEDS:
            subset = records.loc[
                (records["protocol"] == protocol) & (records["seed"] == seed)
            ]
            keys = set(subset.loc[:, key_columns].itertuples(index=False, name=None))
            if keys != expected_keys or len(subset) != len(expected_keys):
                raise ValueError(f"incomplete or duplicate grid for {protocol}/seed={seed}")
    return records


def _performance_sample(records: pd.DataFrame, rng: np.random.Generator) -> pd.DataFrame:
    blocks: list[pd.DataFrame] = []
    for motion in MOTIONS:
        for load_kg in LOADS:
            stratum = records.loc[
                (records["motion"] == motion) & (records["load_kg"] == load_kg)
            ]
            repetitions = np.sort(stratum["repetition"].unique())
            sampled = rng.choice(repetitions, size=len(repetitions), replace=True)
            for draw_index, repetition in enumerate(sampled, start=1):
                block = stratum.loc[stratum["repetition"] == repetition].copy()
                block["bootstrap_draw"] = draw_index
                blocks.append(block)
    return pd.concat(blocks, ignore_index=True)


def _control_sample(records: pd.DataFrame, rng: np.random.Generator) -> pd.DataFrame:
    blocks: list[pd.DataFrame] = []
    for motion in MOTIONS:
        motion_records = records.loc[records["motion"] == motion]
        repetitions = np.sort(motion_records["repetition"].unique())
        sampled = rng.choice(repetitions, size=len(repetitions), replace=True)
        for draw_index, repetition in enumerate(sampled, start=1):
            block = motion_records.loc[motion_records["repetition"] == repetition].copy()
            block["original_repetition"] = block["repetition"]
            block["repetition"] = draw_index
            blocks.append(block)
    return pd.concat(blocks, ignore_index=True)


def _performance_metrics(records: pd.DataFrame) -> dict[str, float]:
    truth = records["truth"].to_numpy(dtype=object)
    prediction = records["prediction"].to_numpy(dtype=object)
    probabilities = records.loc[
        :, [f"probability_{label}" for label in LABELS]
    ].to_numpy(dtype=float)
    one_hot = np.column_stack([truth == label for label in LABELS]).astype(float)
    fold_accuracy: list[float] = []
    fold_macro_f1: list[float] = []
    for motion in MOTIONS:
        for load_kg in LOADS:
            fold = records.loc[
                (records["motion"] == motion) & (records["load_kg"] == load_kg)
            ]
            fold_accuracy.append(float(accuracy_score(fold["truth"], fold["prediction"])))
            fold_macro_f1.append(
                float(
                    f1_score(
                        fold["truth"],
                        fold["prediction"],
                        labels=list(LABELS),
                        average="macro",
                    )
                )
            )
    return {
        "accuracy": float(accuracy_score(truth, prediction)),
        "macro_f1": float(f1_score(truth, prediction, labels=list(LABELS), average="macro")),
        "worst_fold_accuracy": min(fold_accuracy),
        "worst_fold_macro_f1": min(fold_macro_f1),
        "multiclass_brier": float(np.mean(np.sum((probabilities - one_hot) ** 2, axis=1))),
        "ece_10_bin": float(calibration_metrics(truth, probabilities)["ece_10_bin"]),
    }


def _seed_averaged_metrics(
    performance_records: pd.DataFrame,
    control_records: pd.DataFrame,
) -> dict[str, dict[str, float]]:
    results: dict[str, dict[str, float]] = {}
    for protocol in PROTOCOLS:
        by_seed: list[dict[str, float]] = []
        for seed in AUDIT_SEEDS:
            performance = performance_records.loc[
                (performance_records["protocol"] == protocol)
                & (performance_records["seed"] == seed)
            ]
            controls = control_records.loc[
                (control_records["protocol"] == protocol)
                & (control_records["seed"] == seed)
            ]
            control_result = control_metrics(controls)
            by_seed.append(
                {
                    **_performance_metrics(performance),
                    **{
                        metric: float(control_result[metric])
                        for metric in CONTROL_METRICS
                    },
                }
            )
        results[protocol] = {
            metric: float(np.mean([seed_result[metric] for seed_result in by_seed]))
            for metric in ALL_METRICS
        }
    return results


def _tensorize_records(records: pd.DataFrame) -> tuple[np.ndarray, np.ndarray]:
    """Convert the validated prediction grid to P/S/M/L/R/C/K tensors."""

    shape = (
        len(PROTOCOLS),
        len(AUDIT_SEEDS),
        len(MOTIONS),
        len(LOADS),
        10,
        len(LABELS),
    )
    probabilities = np.full((*shape, len(LABELS)), np.nan, dtype=float)
    predictions = np.full(shape, -1, dtype=np.int8)
    protocol_index = {protocol: index for index, protocol in enumerate(PROTOCOLS)}
    seed_index = {seed: index for index, seed in enumerate(AUDIT_SEEDS)}
    motion_index = {motion: index for index, motion in enumerate(MOTIONS)}
    load_index = {load: index for index, load in enumerate(LOADS)}
    label_index = {label: index for index, label in enumerate(LABELS)}
    probability_columns = [f"probability_{label}" for label in LABELS]
    for _, row in records.iterrows():
        index = (
            protocol_index[str(row["protocol"])],
            seed_index[int(row["seed"])],
            motion_index[str(row["motion"])],
            load_index[int(row["load_kg"])],
            int(row["repetition"]) - 1,
            label_index[str(row["truth"])],
        )
        probabilities[index] = row[probability_columns].to_numpy(dtype=float)
        predictions[index] = label_index[str(row["prediction"])]
    if not np.isfinite(probabilities).all() or (predictions < 0).any():
        raise ValueError("prediction tensor is incomplete")
    return probabilities, predictions


def _macro_f1_from_indices(truth: np.ndarray, prediction: np.ndarray) -> float:
    class_count = len(LABELS)
    confusion = np.bincount(
        truth.ravel() * class_count + prediction.ravel(),
        minlength=class_count**2,
    ).reshape(class_count, class_count)
    true_positive = np.diag(confusion).astype(float)
    predicted_count = confusion.sum(axis=0).astype(float)
    true_count = confusion.sum(axis=1).astype(float)
    denominator = predicted_count + true_count
    class_f1 = np.divide(
        2.0 * true_positive,
        denominator,
        out=np.zeros_like(true_positive),
        where=denominator > 0,
    )
    return float(class_f1.mean())


def _numeric_performance_metrics(
    probabilities: np.ndarray, predictions: np.ndarray
) -> np.ndarray:
    """Return PERFORMANCE_METRICS for one sampled protocol/seed tensor."""

    truth = np.broadcast_to(
        np.arange(len(LABELS), dtype=np.int8)[None, None, None, :],
        predictions.shape,
    )
    fold_accuracy: list[float] = []
    fold_macro_f1: list[float] = []
    for motion_index in range(len(MOTIONS)):
        for load_index in range(len(LOADS)):
            fold_truth = truth[motion_index, load_index]
            fold_prediction = predictions[motion_index, load_index]
            fold_accuracy.append(float((fold_truth == fold_prediction).mean()))
            fold_macro_f1.append(
                _macro_f1_from_indices(fold_truth, fold_prediction)
            )
    one_hot = np.eye(len(LABELS), dtype=float)[truth]
    confidence = probabilities.max(axis=-1)
    calibration_correct = probabilities.argmax(axis=-1) == truth
    bin_ids = np.minimum((confidence * 10).astype(int), 9)
    ece = 0.0
    for bin_id in range(10):
        mask = bin_ids == bin_id
        if np.any(mask):
            ece += float(mask.mean()) * abs(
                float(calibration_correct[mask].mean()) - float(confidence[mask].mean())
            )
    return np.asarray(
        (
            float((predictions == truth).mean()),
            _macro_f1_from_indices(truth, predictions),
            min(fold_accuracy),
            min(fold_macro_f1),
            float(np.mean(np.sum((probabilities - one_hot) ** 2, axis=-1))),
            ece,
        ),
        dtype=float,
    )


def _sample_performance_tensors(
    probabilities: np.ndarray,
    predictions: np.ndarray,
    choices: np.ndarray,
) -> tuple[np.ndarray, np.ndarray]:
    sampled_probabilities = np.empty_like(probabilities)
    sampled_predictions = np.empty_like(predictions)
    for motion_index in range(len(MOTIONS)):
        for load_index in range(len(LOADS)):
            repetitions = choices[motion_index, load_index]
            sampled_probabilities[:, :, motion_index, load_index] = probabilities[
                :, :, motion_index, load_index, repetitions
            ]
            sampled_predictions[:, :, motion_index, load_index] = predictions[
                :, :, motion_index, load_index, repetitions
            ]
    return sampled_probabilities, sampled_predictions


def _performance_metric_tensor(
    probabilities: np.ndarray,
    predictions: np.ndarray,
    choices: np.ndarray,
) -> np.ndarray:
    sampled_probabilities, sampled_predictions = _sample_performance_tensors(
        probabilities, predictions, choices
    )
    result = np.empty(
        (len(PROTOCOLS), len(AUDIT_SEEDS), len(PERFORMANCE_METRICS)), dtype=float
    )
    for protocol_index in range(len(PROTOCOLS)):
        for seed_index in range(len(AUDIT_SEEDS)):
            result[protocol_index, seed_index] = _numeric_performance_metrics(
                sampled_probabilities[protocol_index, seed_index],
                sampled_predictions[protocol_index, seed_index],
            )
    return result


def _control_metric_tensor(probabilities: np.ndarray, choices: np.ndarray) -> np.ndarray:
    sampled = np.empty_like(probabilities)
    for motion_index in range(len(MOTIONS)):
        repetitions = choices[motion_index]
        for load_index in range(len(LOADS)):
            sampled[:, :, motion_index, load_index] = probabilities[
                :, :, motion_index, load_index, repetitions
            ]
    nuisance_distances = []
    for left, right in ((0, 1), (0, 2), (1, 2)):
        nuisance_distances.append(
            0.5 * np.abs(sampled[:, :, :, left] - sampled[:, :, :, right]).sum(axis=-1)
        )
    nuisance = np.stack(nuisance_distances, axis=-1).mean(axis=(2, 3, 4, 5))
    fault_distances = []
    for left, right in ((0, 1), (0, 2), (1, 2)):
        fault_distances.append(
            0.5 * np.abs(sampled[..., left, :] - sampled[..., right, :]).sum(axis=-1)
        )
    fault = np.stack(fault_distances, axis=-1).mean(axis=(2, 3, 4, 5))
    ratio = np.divide(
        nuisance,
        fault,
        out=np.full_like(nuisance, np.nan),
        where=fault > 0,
    )
    return np.stack((nuisance, fault, ratio), axis=-1)


def _tensor_results(
    probabilities: np.ndarray,
    predictions: np.ndarray,
    performance_choices: np.ndarray,
    control_choices: np.ndarray,
) -> dict[str, dict[str, float]]:
    performance = _performance_metric_tensor(
        probabilities, predictions, performance_choices
    )
    controls = _control_metric_tensor(probabilities, control_choices)
    results: dict[str, dict[str, float]] = {}
    for protocol_index, protocol in enumerate(PROTOCOLS):
        values = np.concatenate(
            (performance[protocol_index], controls[protocol_index]), axis=1
        ).mean(axis=0)
        results[protocol] = {
            metric: float(values[index]) for index, metric in enumerate(ALL_METRICS)
        }
    return results


def _interval(point_estimate: float, values: Sequence[float]) -> dict[str, float]:
    array = np.asarray(values, dtype=float)
    if not np.isfinite(array).all() or len(array) == 0:
        raise ValueError("bootstrap distribution must be finite and non-empty")
    return {
        "point_estimate": float(point_estimate),
        "bootstrap_mean": float(array.mean()),
        "bootstrap_standard_error": float(array.std(ddof=1)) if len(array) > 1 else 0.0,
        "ci95_low": float(np.quantile(array, 0.025)),
        "ci95_high": float(np.quantile(array, 0.975)),
    }


def _comparison_summary(
    point_results: dict[str, dict[str, float]],
    replicate_frame: pd.DataFrame,
) -> dict[str, Any]:
    comparisons: dict[str, Any] = {}
    for left, right in (("P1", "P0"), ("P2", "P0"), ("P2", "P1")):
        left_rows = replicate_frame.loc[replicate_frame["protocol"] == left].set_index(
            "replicate"
        )
        right_rows = replicate_frame.loc[replicate_frame["protocol"] == right].set_index(
            "replicate"
        )
        metrics: dict[str, Any] = {}
        for metric in ALL_METRICS:
            differences = left_rows[metric] - right_rows[metric]
            interval = _interval(
                point_results[left][metric] - point_results[right][metric], differences
            )
            interval["resolved_away_from_zero"] = bool(
                interval["ci95_low"] > 0 or interval["ci95_high"] < 0
            )
            metrics[metric] = interval
        comparisons[f"{left}_minus_{right}"] = metrics
    return comparisons


def _format_interval(result: dict[str, float]) -> str:
    return (
        f"{result['point_estimate']:.4f} "
        f"[{result['ci95_low']:.4f}, {result['ci95_high']:.4f}]"
    )


def _render_report(metrics: dict[str, Any]) -> str:
    lines = [
        "# Cranfield paired block-bootstrap results",
        "",
        f"- Version: `{BOOTSTRAP_VERSION}`",
        f"- Replicates: {metrics['configuration']['replicates']}",
        f"- RNG seed: {metrics['configuration']['seed']}",
        "- Intervals: paired percentile 95% confidence intervals",
        "",
        "| Protocol | Macro F1 | Worst-fold F1 | Brier ↓ | Control ratio ↓ |",
        "|---|---:|---:|---:|---:|",
    ]
    for protocol in PROTOCOLS:
        result = metrics["results"][protocol]
        lines.append(
            "| "
            + " | ".join(
                (
                    f"{protocol} `{PROTOCOLS[protocol]}`",
                    _format_interval(result["macro_f1"]),
                    _format_interval(result["worst_fold_macro_f1"]),
                    _format_interval(result["multiclass_brier"]),
                    _format_interval(result["control_ratio"]),
                )
            )
            + " |"
        )
    lines.extend(("", "## Paired macro-F1 differences", ""))
    for comparison, result in metrics["paired_comparisons"].items():
        interval = result["macro_f1"]
        lines.append(
            f"- `{comparison}`: {_format_interval(interval)}; "
            f"resolved={interval['resolved_away_from_zero']}"
        )
    lines.extend(
        (
            "",
            "Performance intervals resample three-state physical blocks within each motion/load",
            "fold. Control intervals use synchronized repetition draws across loads to preserve",
            "the negative-control matching topology. Seeds are averaged, not treated as physical",
            "replicates.",
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
    """Generate paired performance and control bootstrap distributions."""

    if replicates < 1:
        raise ValueError("replicates must be positive")
    records_path = records_path.resolve()
    records = load_and_validate_records(records_path)
    probabilities, predictions = _tensorize_records(records)
    repetition_count = probabilities.shape[4]
    identity_performance = np.broadcast_to(
        np.arange(repetition_count),
        (len(MOTIONS), len(LOADS), repetition_count),
    )
    identity_control = np.broadcast_to(
        np.arange(repetition_count), (len(MOTIONS), repetition_count)
    )
    point_results = _tensor_results(
        probabilities,
        predictions,
        identity_performance,
        identity_control,
    )
    performance_rng = np.random.default_rng(seed)
    control_rng = np.random.default_rng(seed + 1)
    replicate_rows: list[dict[str, Any]] = []
    for replicate in range(replicates):
        performance_choices = performance_rng.integers(
            0,
            repetition_count,
            size=(len(MOTIONS), len(LOADS), repetition_count),
        )
        control_choices = control_rng.integers(
            0,
            repetition_count,
            size=(len(MOTIONS), repetition_count),
        )
        replicate_results = _tensor_results(
            probabilities,
            predictions,
            performance_choices,
            control_choices,
        )
        for protocol, result in replicate_results.items():
            replicate_rows.append(
                {"replicate": replicate, "protocol": protocol, **result}
            )
    replicate_frame = pd.DataFrame(replicate_rows)
    results = {
        protocol: {
            metric: _interval(
                point_results[protocol][metric],
                replicate_frame.loc[replicate_frame["protocol"] == protocol, metric],
            )
            for metric in ALL_METRICS
        }
        for protocol in PROTOCOLS
    }
    for protocol in PROTOCOLS:
        values = replicate_frame.loc[
            replicate_frame["protocol"] == protocol, "worst_fold_accuracy"
        ]
        results[protocol]["chance_failure_probability"] = float(
            (values <= BALANCED_RANDOM_GUESS_ACCURACY + 1e-12).mean()
        )
    metrics: dict[str, Any] = {
        "bootstrap_version": BOOTSTRAP_VERSION,
        "generated_at": datetime.now(UTC).isoformat(),
        "protocol_document": "research/protocols/cranfield_bootstrap_v0.1.md",
        "input": {
            "records_path": str(records_path),
            "records_sha256": _file_sha256(records_path),
            "rows": len(records),
            "protocols": list(PROTOCOLS),
            "seeds": list(AUDIT_SEEDS),
        },
        "configuration": {
            "replicates": replicates,
            "seed": seed,
            "interval": "percentile 95%",
            "performance_sampling": "stratified (motion, load, repetition) three-state blocks",
            "control_sampling": "motion-stratified synchronized repetition clusters across loads",
        },
        "results": results,
        "paired_comparisons": _comparison_summary(
            point_results, replicate_frame
        ),
        "limitations": [
            "Intervals quantify physical-block uncertainty conditional on five fixed model seeds.",
            "Only ten repetition blocks are available in each motion/load fold.",
            "Percentile intervals do not correct the paired comparison family for multiplicity.",
            "Single-rig repetitions do not quantify between-asset variation.",
        ],
    }
    output_directory.mkdir(parents=True, exist_ok=True)
    replicate_frame.to_csv(output_directory / "bootstrap_replicates.csv", index=False)
    (output_directory / "metrics.json").write_text(
        json.dumps(metrics, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8"
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
    print(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False))


if __name__ == "__main__":
    main()
