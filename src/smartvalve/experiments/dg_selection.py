"""Source-only selection and final D0/D1 evaluation of neural DG baselines."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from dataclasses import asdict, replace
from datetime import UTC, datetime
from pathlib import Path
from time import perf_counter
from typing import Any

import numpy as np
import pandas as pd
import torch

from smartvalve.experiments.cranfield_causal_audit import AUDIT_SEEDS
from smartvalve.experiments.dg_training import (
    BASELINE_METHODS,
    BaselineConfig,
    configuration_record,
    fit_dg_fold,
    predict_dg,
)
from smartvalve.experiments.domain_data import (
    SourceOnlyFold,
    build_cranfield_folds,
    build_uci_folds,
)
from smartvalve.experiments.inner_splits import (
    build_inner_splits,
    materialize_inner_fold,
)
from smartvalve.experiments.pirl_ablation import _seed_aggregates
from smartvalve.experiments.pirl_development import (
    AGGREGATE_METRICS,
    _aggregate_folds,
    _fold_metrics,
    _macro_f1,
    _method_summary,
    _multiclass_brier,
    _numeric_summary,
    _prediction_records,
    _response,
    _sha256,
)
from smartvalve.experiments.pirl_sore import (
    fit_class_support,
    risk_envelope_score,
    robust_class_distance,
)

SELECTION_VERSION = "neural-dg-source-selection-0.1.0"
SELECTION_SEED = 11
SELECTION_TOLERANCE = 0.01
REPRESENTATION_DIMS = (32, 64)
PENALTY_WEIGHTS = (0.1, 0.5, 1.0)
GROUPDRO_STEP_SIZES = (0.01, 0.1, 1.0)


def _number(value: float) -> str:
    return str(value).replace(".", "p")


def candidate_id(config: BaselineConfig) -> str:
    base = f"{config.method}_r{config.representation_dim}"
    if config.method == "erm":
        return base
    if config.method == "groupdro":
        return f"{base}_q{_number(config.groupdro_step_size)}"
    return f"{base}_w{_number(config.penalty_weight)}"


def candidate_grid(method: str) -> tuple[BaselineConfig, ...]:
    if method not in BASELINE_METHODS:
        raise ValueError(f"unsupported DG baseline: {method}")
    candidates = []
    if method == "erm":
        candidates = [
            BaselineConfig(
                method=method,
                representation_dim=dimension,
                penalty_weight=0.0,
                epochs=300,
                seed=SELECTION_SEED,
            )
            for dimension in REPRESENTATION_DIMS
        ]
    elif method == "groupdro":
        candidates = [
            BaselineConfig(
                method=method,
                representation_dim=dimension,
                penalty_weight=0.0,
                groupdro_step_size=step_size,
                epochs=300,
                seed=SELECTION_SEED,
            )
            for dimension in REPRESENTATION_DIMS
            for step_size in GROUPDRO_STEP_SIZES
        ]
    else:
        candidates = [
            BaselineConfig(
                method=method,
                representation_dim=dimension,
                penalty_weight=weight,
                dann_coefficient=1.0,
                ccdg_temperature=0.7,
                epochs=300,
                seed=SELECTION_SEED,
            )
            for dimension in REPRESENTATION_DIMS
            for weight in PENALTY_WEIGHTS
        ]
    output = tuple(candidates)
    if len({candidate_id(config) for config in output}) != len(output):
        raise AssertionError("DG candidate identifiers are not unique")
    return output


def _inner_oof(
    outer_fold: SourceOnlyFold,
    config: BaselineConfig,
    *,
    device: str,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    row_count = len(outer_fold.source_indices)
    class_count = len(outer_fold.label_names)
    probabilities = np.full((row_count, class_count), np.nan, dtype=float)
    traces = []
    for split in build_inner_splits(outer_fold):
        inner_fold = materialize_inner_fold(outer_fold, split)
        started = perf_counter()
        fitted = fit_dg_fold(inner_fold, config, device=device)
        fit_seconds = perf_counter() - started
        validation = predict_dg(fitted, inner_fold.target_features)
        probabilities[split.validation_indices] = validation.probabilities
        traces.append(
            {
                "dataset": outer_fold.dataset,
                "outer_fold_id": outer_fold.fold_id,
                "inner_split_id": split.split_id,
                "candidate_id": candidate_id(config),
                "configuration": configuration_record(config),
                "fit_seconds": fit_seconds,
                "model_state_sha256": fitted.state_sha256,
                "auxiliary_state_sha256": fitted.auxiliary_state_sha256,
                "history": fitted.history,
            }
        )
        print(
            json.dumps(
                {
                    "event": "dg_inner_fit_complete",
                    "dataset": outer_fold.dataset,
                    "outer_fold_id": outer_fold.fold_id,
                    "inner_split_id": split.split_id,
                    "candidate_id": candidate_id(config),
                    "fit_seconds": fit_seconds,
                    "model_state_sha256": fitted.state_sha256,
                }
            ),
            flush=True,
        )
    if not np.isfinite(probabilities).all():
        raise ValueError("DG source OOF probability matrix is incomplete")
    truth = outer_fold.source_labels
    predictions = probabilities.argmax(axis=1)
    environment_f1 = [
        _macro_f1(
            truth[outer_fold.source_environments == environment],
            predictions[outer_fold.source_environments == environment],
            class_count,
        )
        for environment in np.unique(outer_fold.source_environments)
    ]
    nuisance = _response(
        probabilities, outer_fold.nuisance_pairs, total_variation=True
    )
    fault = _response(
        probabilities, outer_fold.fault_pairs, total_variation=True
    )
    if fault <= 0:
        raise ValueError("DG source OOF fault probability response is zero")
    return (
        {
            "method": config.method,
            "dataset": outer_fold.dataset,
            "outer_fold_id": outer_fold.fold_id,
            "candidate_id": candidate_id(config),
            "source_oof_macro_f1": _macro_f1(
                truth, predictions, class_count
            ),
            "source_oof_worst_environment_macro_f1": float(
                min(environment_f1)
            ),
            "source_oof_multiclass_brier": _multiclass_brier(
                truth, probabilities, class_count
            ),
            "source_oof_nuisance_probability_response": nuisance,
            "source_oof_fault_probability_response": fault,
            "source_oof_probability_response_ratio": nuisance / fault,
        },
        traces,
    )


def select_outer_candidate(
    candidate_metrics: list[dict[str, Any]],
    *,
    tolerance: float = SELECTION_TOLERANCE,
) -> dict[str, Any]:
    if not candidate_metrics or tolerance < 0:
        raise ValueError("outer DG selection requires candidates and a valid tolerance")
    keys = {
        (
            str(candidate["method"]),
            str(candidate["dataset"]),
            str(candidate["outer_fold_id"]),
        )
        for candidate in candidate_metrics
    }
    if len(keys) != 1:
        raise ValueError("outer DG selection cannot mix methods or folds")
    best_worst_f1 = max(
        float(candidate["source_oof_worst_environment_macro_f1"])
        for candidate in candidate_metrics
    )
    eligible = [
        candidate
        for candidate in candidate_metrics
        if float(candidate["source_oof_worst_environment_macro_f1"])
        + tolerance
        + 1e-12
        >= best_worst_f1
    ]
    selected = min(
        eligible,
        key=lambda candidate: (
            -float(candidate["source_oof_macro_f1"]),
            float(candidate["source_oof_multiclass_brier"]),
            str(candidate["candidate_id"]),
        ),
    )
    return {
        "method": selected["method"],
        "dataset": selected["dataset"],
        "outer_fold_id": selected["outer_fold_id"],
        "best_source_oof_worst_environment_macro_f1": best_worst_f1,
        "tolerance": tolerance,
        "eligible_candidates": sorted(
            str(candidate["candidate_id"]) for candidate in eligible
        ),
        "selected_candidate_id": selected["candidate_id"],
        "selected_metrics": {
            key: value
            for key, value in selected.items()
            if key.startswith("source_oof_")
        },
    }


def _ordinal_ranks(
    values: dict[str, float],
    *,
    lower_is_better: bool,
) -> dict[str, int]:
    ordered = sorted(
        values,
        key=lambda key: (
            values[key] if lower_is_better else -values[key],
            key,
        ),
    )
    return {candidate: rank for rank, candidate in enumerate(ordered, start=1)}


def select_common_candidate(
    outer_selections: list[dict[str, Any]],
    candidate_metrics: list[dict[str, Any]],
) -> dict[str, Any]:
    if not outer_selections or not candidate_metrics:
        raise ValueError("common DG selection requires decisions and metrics")
    methods = {str(row["method"]) for row in candidate_metrics}
    if len(methods) != 1 or {
        str(row["method"]) for row in outer_selections
    } != methods:
        raise ValueError("common DG selection must contain exactly one method")
    counts = Counter(
        str(selection["selected_candidate_id"])
        for selection in outer_selections
    )
    maximum = max(counts.values())
    contenders = sorted(
        candidate for candidate, count in counts.items() if count == maximum
    )
    rank_names = {
        "worst_f1": ("source_oof_worst_environment_macro_f1", False),
        "macro_f1": ("source_oof_macro_f1", False),
        "brier": ("source_oof_multiclass_brier", True),
    }
    ranks: dict[str, dict[str, list[int]]] = {
        name: {candidate: [] for candidate in contenders}
        for name in rank_names
    }
    fold_keys = sorted(
        {
            (str(row["dataset"]), str(row["outer_fold_id"]))
            for row in candidate_metrics
        }
    )
    for dataset, fold_id in fold_keys:
        rows = [
            row
            for row in candidate_metrics
            if row["dataset"] == dataset and row["outer_fold_id"] == fold_id
        ]
        for rank_name, (metric_name, lower_is_better) in rank_names.items():
            fold_ranks = _ordinal_ranks(
                {
                    str(row["candidate_id"]): float(row[metric_name])
                    for row in rows
                },
                lower_is_better=lower_is_better,
            )
            for candidate in contenders:
                ranks[rank_name][candidate].append(fold_ranks[candidate])
    selected = min(
        contenders,
        key=lambda candidate: (
            float(np.mean(ranks["worst_f1"][candidate])),
            float(np.mean(ranks["macro_f1"][candidate])),
            float(np.mean(ranks["brier"][candidate])),
            candidate,
        ),
    )
    return {
        "method": next(iter(methods)),
        "selected_candidate_id": selected,
        "selection_counts": dict(sorted(counts.items())),
        "modal_count": maximum,
        "modal_contenders": contenders,
        "tie_break_mean_worst_f1_rank": {
            candidate: float(np.mean(values))
            for candidate, values in ranks["worst_f1"].items()
        },
        "tie_break_mean_macro_f1_rank": {
            candidate: float(np.mean(values))
            for candidate, values in ranks["macro_f1"].items()
        },
        "tie_break_mean_brier_rank": {
            candidate: float(np.mean(values))
            for candidate, values in ranks["brier"].items()
        },
    }


def _fit_one(
    fold: SourceOnlyFold,
    config: BaselineConfig,
    seed: int,
    *,
    device: str,
) -> tuple[dict[str, Any], pd.DataFrame, dict[str, Any]]:
    final_config = replace(config, seed=seed)
    if device.startswith("cuda"):
        torch.cuda.reset_peak_memory_stats(0)
    started = perf_counter()
    fitted = fit_dg_fold(fold, final_config, device=device)
    fit_seconds = perf_counter() - started
    peak_memory = (
        int(torch.cuda.max_memory_allocated(0))
        if device.startswith("cuda")
        else None
    )
    source = predict_dg(fitted, fold.source_features)
    target = predict_dg(fitted, fold.target_features)
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
        raise ValueError("DG fitted model has a zero source fault response")
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
            "auxiliary_state_sha256": fitted.auxiliary_state_sha256,
        }
    )
    records = _prediction_records(
        fold,
        method=config.method,
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
        "method": config.method,
        "seed": seed,
        "candidate_id": candidate_id(config),
        "configuration": configuration_record(final_config),
        "model_state_sha256": fitted.state_sha256,
        "auxiliary_state_sha256": fitted.auxiliary_state_sha256,
        "history": fitted.history,
    }
    return metrics, records, trace


def _paired_against_tuned_erm(
    results: dict[str, dict[str, dict[str, Any]]],
) -> dict[str, Any]:
    output = {}
    for dataset, methods in results.items():
        erm = _seed_aggregates(methods["erm"])
        output[dataset] = {}
        for method, method_result in methods.items():
            if method == "erm":
                continue
            current = _seed_aggregates(method_result)
            output[dataset][f"{method}_minus_erm"] = {
                metric: _numeric_summary(
                    [
                        current[int(seed)][metric] - erm[int(seed)][metric]
                        for seed in AUDIT_SEEDS
                    ]
                )
                for metric in AGGREGATE_METRICS
            }
    return output


def _artifact(path: Path, **counts: int) -> dict[str, Any]:
    return {
        "path": path.name,
        **counts,
        "bytes": path.stat().st_size,
        "sha256": _sha256(path),
    }


def run_selection(
    uci_feature_matrix: Path,
    output_directory: Path,
    *,
    device: str = "cuda:0",
) -> dict[str, Any]:
    if device.startswith("cuda"):
        if not torch.cuda.is_available():
            raise RuntimeError("formal DG selection requires validated CUDA")
        torch.cuda.init()
    datasets = {
        "cranfield": build_cranfield_folds(),
        "uci_hydraulic": build_uci_folds(uci_feature_matrix),
    }
    grids = {method: candidate_grid(method) for method in BASELINE_METHODS}
    candidate_metrics = []
    tuning_traces = []
    outer_selections = []
    common_selections = {}
    selected_configs = {}
    for method in BASELINE_METHODS:
        method_metrics = []
        for folds in datasets.values():
            for fold in folds:
                fold_metrics = []
                for config in grids[method]:
                    metrics, traces = _inner_oof(
                        fold, config, device=device
                    )
                    fold_metrics.append(metrics)
                    method_metrics.append(metrics)
                    candidate_metrics.append(metrics)
                    tuning_traces.extend(traces)
                outer_selections.append(
                    select_outer_candidate(fold_metrics)
                )
        method_outer = [
            row for row in outer_selections if row["method"] == method
        ]
        common = select_common_candidate(method_outer, method_metrics)
        configurations = {
            candidate_id(config): config for config in grids[method]
        }
        selected = configurations[common["selected_candidate_id"]]
        selected_configs[method] = selected
        common_selections[method] = {
            **common,
            "configuration": configuration_record(selected),
        }

    records = []
    final_traces = []
    results: dict[str, dict[str, dict[str, Any]]] = {}
    for dataset, folds in datasets.items():
        results[dataset] = {}
        for method in BASELINE_METHODS:
            seed_results = []
            for seed in AUDIT_SEEDS:
                fold_results = []
                for fold in folds:
                    metrics, prediction_records, trace = _fit_one(
                        fold,
                        selected_configs[method],
                        int(seed),
                        device=device,
                    )
                    fold_results.append(metrics)
                    records.append(prediction_records)
                    final_traces.append(trace)
                    print(
                        json.dumps(
                            {
                                "event": "dg_final_fit_complete",
                                "dataset": dataset,
                                "method": method,
                                "seed": int(seed),
                                "fold_id": fold.fold_id,
                                "candidate_id": candidate_id(
                                    selected_configs[method]
                                ),
                                "macro_f1": metrics["macro_f1"],
                                "fit_seconds": metrics["fit_seconds"],
                                "model_state_sha256": metrics[
                                    "model_state_sha256"
                                ],
                            }
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
    predictions_path = output_directory / "predictions.parquet"
    predictions = pd.concat(records, ignore_index=True)
    predictions.to_parquet(predictions_path, index=False)
    candidate_path = output_directory / "candidate_metrics.parquet"
    pd.DataFrame(candidate_metrics).to_parquet(candidate_path, index=False)
    tuning_path = output_directory / "tuning_traces.json"
    tuning_path.write_text(
        json.dumps(tuning_traces, ensure_ascii=False, indent=2, allow_nan=False)
        + "\n",
        encoding="utf-8",
    )
    final_path = output_directory / "final_training_traces.json"
    final_path.write_text(
        json.dumps(final_traces, ensure_ascii=False, indent=2, allow_nan=False)
        + "\n",
        encoding="utf-8",
    )
    metrics = {
        "selection_version": SELECTION_VERSION,
        "generated_at": datetime.now(UTC).isoformat(),
        "protocol_document": (
            "research/protocols/neural_dg_selection_v0.1.md"
        ),
        "input": {
            "uci_feature_matrix": str(uci_feature_matrix.resolve()),
            "uci_feature_matrix_sha256": _sha256(uci_feature_matrix),
            "paderborn_archive_contents_opened": False,
        },
        "configuration": {
            "methods": list(BASELINE_METHODS),
            "selection_seed": SELECTION_SEED,
            "selection_tolerance": SELECTION_TOLERANCE,
            "final_seeds": list(AUDIT_SEEDS),
            "epochs": 300,
            "device": device,
            "candidate_count": sum(len(grid) for grid in grids.values()),
            "candidate_grids": {
                method: [
                    {
                        "candidate_id": candidate_id(config),
                        "configuration": asdict(config),
                    }
                    for config in grid
                ]
                for method, grid in grids.items()
            },
        },
        "outer_selections": outer_selections,
        "common_selections": common_selections,
        "results": results,
        "paired_against_tuned_erm": _paired_against_tuned_erm(results),
        "artifacts": {
            "predictions": _artifact(
                predictions_path, rows=len(predictions)
            ),
            "candidate_metrics": _artifact(
                candidate_path, rows=len(candidate_metrics)
            ),
            "tuning_traces": _artifact(
                tuning_path, models=len(tuning_traces)
            ),
            "final_training_traces": _artifact(
                final_path, models=len(final_traces)
            ),
        },
    }
    (output_directory / "metrics.json").write_text(
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
    result = run_selection(
        args.uci_feature_matrix,
        args.output_directory,
        device=args.device,
    )
    print(json.dumps(result["common_selections"], ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
