"""Run the frozen PIRL-SORE versus ERM D0/D1 falsification screen."""

from __future__ import annotations

import argparse
import hashlib
import json
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path
from time import perf_counter
from typing import Any

import numpy as np
import pandas as pd
import torch

from smartvalve.experiments.cranfield_causal_audit import AUDIT_SEEDS
from smartvalve.experiments.domain_data import (
    SourceOnlyFold,
    build_cranfield_folds,
    build_uci_folds,
)
from smartvalve.experiments.pirl_sore import (
    TrainingConfig,
    configuration_record,
    fit_class_support,
    fit_fold,
    predict,
    risk_envelope_score,
    robust_class_distance,
)

SCREEN_VERSION = "pirl-sore-initial-screen-0.1.0"
METHODS = ("erm", "pirl_sore")
PROBABILITY_PREFIX = "probability_"
LOGIT_PREFIX = "logit_"
REPRESENTATION_PREFIX = "representation_"
AGGREGATE_METRICS = (
    "mean_fold_accuracy",
    "mean_fold_macro_f1",
    "worst_fold_macro_f1",
    "mean_fold_multiclass_brier",
    "mean_fold_aurc",
    "mean_fold_risk_at_50pct",
    "mean_source_representation_response_ratio",
    "mean_source_probability_response_ratio",
)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _macro_f1(truth: np.ndarray, prediction: np.ndarray, class_count: int) -> float:
    confusion = np.bincount(
        truth * class_count + prediction,
        minlength=class_count**2,
    ).reshape(class_count, class_count)
    true_positive = np.diag(confusion).astype(float)
    denominator = confusion.sum(axis=0) + confusion.sum(axis=1)
    class_f1 = np.divide(
        2 * true_positive,
        denominator,
        out=np.zeros_like(true_positive),
        where=denominator > 0,
    )
    return float(class_f1.mean())


def _multiclass_brier(
    truth: np.ndarray, probabilities: np.ndarray, class_count: int
) -> float:
    one_hot = np.eye(class_count, dtype=float)[truth]
    return float(np.mean(np.sum((probabilities - one_hot) ** 2, axis=1)))


def _risk_coverage(
    truth: np.ndarray,
    prediction: np.ndarray,
    scores: np.ndarray,
) -> tuple[float, float]:
    order = np.argsort(scores, kind="stable")
    errors = (prediction[order] != truth[order]).astype(float)
    cumulative_risk = np.cumsum(errors) / np.arange(1, len(errors) + 1)
    half_count = max(1, int(np.ceil(0.5 * len(errors))))
    return float(cumulative_risk.mean()), float(cumulative_risk[half_count - 1])


def _response(values: np.ndarray, pairs: np.ndarray, *, total_variation: bool) -> float:
    differences = np.abs(values[pairs[:, 0]] - values[pairs[:, 1]])
    if total_variation:
        return float((0.5 * differences.sum(axis=1)).mean())
    return float((differences**2).sum(axis=1).mean())


def _fold_metrics(
    fold: SourceOnlyFold,
    probabilities: np.ndarray,
    predictions: np.ndarray,
    scores: np.ndarray,
    *,
    nuisance_representation_response: float,
    fault_representation_response: float,
    nuisance_probability_response: float,
    fault_probability_response: float,
) -> dict[str, Any]:
    truth = fold.target_labels
    aurc, risk_at_half = _risk_coverage(truth, predictions, scores)
    return {
        "fold_id": fold.fold_id,
        "held_factor": fold.held_factor,
        "held_level": fold.held_level,
        "source_rows": len(fold.source_indices),
        "target_rows": len(fold.target_indices),
        "accuracy": float((predictions == truth).mean()),
        "macro_f1": _macro_f1(truth, predictions, len(fold.label_names)),
        "multiclass_brier": _multiclass_brier(
            truth, probabilities, len(fold.label_names)
        ),
        "aurc": aurc,
        "risk_at_50pct": risk_at_half,
        "source_nuisance_representation_response": nuisance_representation_response,
        "source_fault_representation_response": fault_representation_response,
        "source_representation_response_ratio": (
            nuisance_representation_response / fault_representation_response
        ),
        "source_nuisance_probability_response": nuisance_probability_response,
        "source_fault_probability_response": fault_probability_response,
        "source_probability_response_ratio": (
            nuisance_probability_response / fault_probability_response
        ),
    }


def _aggregate_folds(folds: list[dict[str, Any]]) -> dict[str, float]:
    def mean(name: str) -> float:
        return float(np.mean([fold[name] for fold in folds]))

    return {
        "mean_fold_accuracy": mean("accuracy"),
        "mean_fold_macro_f1": mean("macro_f1"),
        "worst_fold_macro_f1": float(min(fold["macro_f1"] for fold in folds)),
        "mean_fold_multiclass_brier": mean("multiclass_brier"),
        "mean_fold_aurc": mean("aurc"),
        "mean_fold_risk_at_50pct": mean("risk_at_50pct"),
        "mean_source_representation_response_ratio": mean(
            "source_representation_response_ratio"
        ),
        "mean_source_probability_response_ratio": mean(
            "source_probability_response_ratio"
        ),
    }


def _numeric_summary(values: list[float]) -> dict[str, float]:
    array = np.asarray(values, dtype=float)
    return {
        "mean": float(array.mean()),
        "sample_std": float(array.std(ddof=1)) if len(array) > 1 else 0.0,
        "minimum": float(array.min()),
        "maximum": float(array.max()),
    }


def _method_summary(seed_results: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        metric: _numeric_summary(
            [result["aggregate"][metric] for result in seed_results]
        )
        for metric in AGGREGATE_METRICS
    }


def _prediction_records(
    fold: SourceOnlyFold,
    *,
    method: str,
    seed: int,
    logits: np.ndarray,
    probabilities: np.ndarray,
    predictions: np.ndarray,
    representations: np.ndarray,
    support_distance: np.ndarray,
    scores: np.ndarray,
) -> pd.DataFrame:
    target = fold.target_indices
    result = pd.DataFrame(
        {
            "dataset": fold.dataset,
            "method": method,
            "seed": seed,
            "fold_id": fold.fold_id,
            "held_factor": fold.held_factor,
            "held_level": fold.held_level,
            "row_index": target,
            "environment_id": fold.target_environments,
            "block_id": fold.block_ids[target],
            "truth": [fold.label_names[value] for value in fold.target_labels],
            "prediction": [fold.label_names[value] for value in predictions],
            "correct": predictions == fold.target_labels,
            "confidence": probabilities.max(axis=1),
            "msp_uncertainty": 1.0 - probabilities.max(axis=1),
            "robust_class_support_distance": support_distance,
            "risk_envelope_score_beta_0_25": scores,
        }
    )
    for index, label in enumerate(fold.label_names):
        result[f"{PROBABILITY_PREFIX}{label}"] = probabilities[:, index]
        result[f"{LOGIT_PREFIX}{label}"] = logits[:, index]
    for index in range(representations.shape[1]):
        result[f"{REPRESENTATION_PREFIX}{index:02d}"] = representations[:, index]
    return result


def _fit_one(
    fold: SourceOnlyFold,
    method: str,
    seed: int,
    *,
    device: str,
    epochs: int,
    base_config: TrainingConfig | None = None,
) -> tuple[dict[str, Any], pd.DataFrame, dict[str, Any]]:
    config = replace(
        base_config or TrainingConfig(),
        method=method,
        epochs=epochs,
        seed=seed,
    )
    if device.startswith("cuda"):
        torch.cuda.reset_peak_memory_stats(0)
    started = perf_counter()
    fitted = fit_fold(fold, config, device=device)
    fit_seconds = perf_counter() - started
    peak_memory = (
        int(torch.cuda.max_memory_allocated(0)) if device.startswith("cuda") else None
    )
    source = predict(fitted, fold.source_features)
    target = predict(fitted, fold.target_features)
    support = fit_class_support(
        source.representations,
        fold.source_labels,
        class_count=len(fold.label_names),
    )
    scores = risk_envelope_score(
        target.probabilities,
        target.representations,
        support,
        beta=0.25,
    )
    support_distance = robust_class_distance(
        target.representations, support
    ).min(axis=1)
    nuisance_representation = _response(
        source.representations, fold.nuisance_pairs, total_variation=False
    )
    fault_representation = _response(
        source.representations, fold.fault_pairs, total_variation=False
    )
    nuisance_probability = _response(
        source.probabilities, fold.nuisance_pairs, total_variation=True
    )
    fault_probability = _response(
        source.probabilities, fold.fault_pairs, total_variation=True
    )
    if min(fault_representation, fault_probability) <= 0:
        raise ValueError("fitted model has a zero source fault response")
    metrics = _fold_metrics(
        fold,
        target.probabilities,
        target.predictions,
        scores,
        nuisance_representation_response=nuisance_representation,
        fault_representation_response=fault_representation,
        nuisance_probability_response=nuisance_probability,
        fault_probability_response=fault_probability,
    )
    metrics.update(
        {
            "fit_seconds": fit_seconds,
            "peak_memory_bytes": peak_memory,
            "model_state_sha256": fitted.state_sha256,
        }
    )
    records = _prediction_records(
        fold,
        method=method,
        seed=seed,
        logits=target.logits,
        probabilities=target.probabilities,
        predictions=target.predictions,
        representations=target.representations,
        support_distance=support_distance,
        scores=scores,
    )
    trace = {
        "dataset": fold.dataset,
        "fold_id": fold.fold_id,
        "method": method,
        "seed": seed,
        "configuration": configuration_record(config),
        "effective_intervention_weight": config.effective_loss_weights()[0],
        "effective_worst_environment_weight": config.effective_loss_weights()[1],
        "model_state_sha256": fitted.state_sha256,
        "history": fitted.history,
    }
    return metrics, records, trace


def _paired_differences(
    results: dict[str, dict[str, dict[str, Any]]]
) -> dict[str, Any]:
    output = {}
    for dataset, methods in results.items():
        erm = {
            int(result["seed"]): result["aggregate"]
            for result in methods["erm"]["seed_results"]
        }
        pirl = {
            int(result["seed"]): result["aggregate"]
            for result in methods["pirl_sore"]["seed_results"]
        }
        output[dataset] = {
            metric: {
                **_numeric_summary(
                    [pirl[seed][metric] - erm[seed][metric] for seed in AUDIT_SEEDS]
                ),
                "direction": "higher_is_better"
                if metric
                in {
                    "mean_fold_accuracy",
                    "mean_fold_macro_f1",
                    "worst_fold_macro_f1",
                }
                else "lower_is_better",
            }
            for metric in AGGREGATE_METRICS
        }
    return output


def run_screen(
    uci_feature_matrix: Path,
    output_directory: Path,
    *,
    device: str = "cuda:0",
    epochs: int = 300,
    seeds: tuple[int, ...] = AUDIT_SEEDS,
) -> dict[str, Any]:
    if tuple(seeds) != tuple(AUDIT_SEEDS):
        raise ValueError("formal screen requires the five frozen seeds")
    if epochs != 300:
        raise ValueError("formal screen requires 300 frozen epochs")
    if device.startswith("cuda"):
        if not torch.cuda.is_available():
            raise RuntimeError("formal screen requires the validated CUDA environment")
        torch.cuda.init()
    datasets = {
        "cranfield": build_cranfield_folds(),
        "uci_hydraulic": build_uci_folds(uci_feature_matrix),
    }
    all_records = []
    traces = []
    results: dict[str, dict[str, dict[str, Any]]] = {}
    for dataset, folds in datasets.items():
        results[dataset] = {}
        for method in METHODS:
            seed_results = []
            for seed in seeds:
                fold_results = []
                for fold in folds:
                    metrics, records, trace = _fit_one(
                        fold,
                        method,
                        int(seed),
                        device=device,
                        epochs=epochs,
                    )
                    fold_results.append(metrics)
                    all_records.append(records)
                    traces.append(trace)
                    print(
                        json.dumps(
                            {
                                "event": "fit_complete",
                                "dataset": dataset,
                                "method": method,
                                "seed": int(seed),
                                "fold_id": fold.fold_id,
                                "macro_f1": metrics["macro_f1"],
                                "fit_seconds": metrics["fit_seconds"],
                                "model_state_sha256": metrics["model_state_sha256"],
                            },
                            ensure_ascii=False,
                        ),
                        flush=True,
                    )
                seed_results.append(
                    {
                        "seed": int(seed),
                        "folds": fold_results,
                        "aggregate": _aggregate_folds(fold_results),
                    }
                )
            results[dataset][method] = {
                "seed_results": seed_results,
                "summary": _method_summary(seed_results),
            }

    output_directory.mkdir(parents=True, exist_ok=True)
    records_path = output_directory / "predictions.parquet"
    records_frame = pd.concat(all_records, ignore_index=True)
    records_frame.to_parquet(records_path, index=False)
    traces_path = output_directory / "training_traces.json"
    traces_path.write_text(
        json.dumps(traces, ensure_ascii=False, indent=2, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    metrics: dict[str, Any] = {
        "screen_version": SCREEN_VERSION,
        "generated_at": datetime.now(UTC).isoformat(),
        "protocol_document": "research/protocols/pirl_sore_screen_v0.1.md",
        "configuration": {
            "methods": list(METHODS),
            "seeds": list(seeds),
            "epochs": epochs,
            "device": device,
            "risk_envelope_beta": 0.25,
            "target_risk_at_50pct_is_diagnostic_only": True,
        },
        "input": {
            "uci_feature_matrix": str(uci_feature_matrix.resolve()),
            "uci_feature_matrix_sha256": _sha256(uci_feature_matrix),
            "paderborn_archive_contents_opened": False,
        },
        "results": results,
        "paired_pirl_minus_erm": _paired_differences(results),
        "artifacts": {
            "predictions": {
                "path": records_path.name,
                "rows": len(records_frame),
                "bytes": records_path.stat().st_size,
                "sha256": _sha256(records_path),
            },
            "training_traces": {
                "path": traces_path.name,
                "models": len(traces),
                "bytes": traces_path.stat().st_size,
                "sha256": _sha256(traces_path),
            },
        },
    }
    metrics_path = output_directory / "metrics.json"
    metrics_path.write_text(
        json.dumps(metrics, ensure_ascii=False, indent=2, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    return metrics


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--uci-feature-matrix", type=Path, required=True)
    parser.add_argument("--output-directory", type=Path, required=True)
    parser.add_argument("--device", default="cuda:0")
    args = parser.parse_args()
    result = run_screen(
        args.uci_feature_matrix,
        args.output_directory,
        device=args.device,
    )
    print(json.dumps(result["artifacts"], ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
