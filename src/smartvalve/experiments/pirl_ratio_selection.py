"""Source-only selection and final D0/D1 evaluation of PIRL response-ratio v0.2."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from dataclasses import asdict
from datetime import UTC, datetime
from itertools import product
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
from smartvalve.experiments.inner_splits import (
    build_inner_splits,
    materialize_inner_fold,
)
from smartvalve.experiments.pirl_ablation import (
    REFERENCE_HASHES,
    _load_reference,
    _seed_aggregates,
)
from smartvalve.experiments.pirl_development import (
    AGGREGATE_METRICS,
    _aggregate_folds,
    _fit_one,
    _macro_f1,
    _method_summary,
    _multiclass_brier,
    _numeric_summary,
    _response,
    _sha256,
)
from smartvalve.experiments.pirl_sore import (
    TrainingConfig,
    fit_fold,
    predict,
)

SELECTION_VERSION = "pirl-ratio-source-selection-0.2.0"
SELECTION_SEED = 11
SELECTION_TOLERANCE = 0.01


def candidate_id(config: TrainingConfig) -> str:
    def number(value: float) -> str:
        return str(value).replace(".", "p")

    return (
        f"r{config.representation_dim}"
        f"_l{number(config.intervention_weight)}"
        f"_m{number(config.fault_margin)}"
    )


def candidate_grid() -> tuple[TrainingConfig, ...]:
    candidates = []
    for representation_dim, weight, margin in product(
        (32, 64),
        (0.1, 0.5, 1.0),
        (0.5, 1.0),
    ):
        candidates.append(
            TrainingConfig(
                method="pirl_ratio",
                representation_dim=representation_dim,
                intervention_weight=weight,
                worst_environment_weight=0.0,
                fault_margin=margin,
                fault_margin_weight=1.0,
                response_epsilon=1e-4,
                epochs=300,
                seed=SELECTION_SEED,
            )
        )
    return tuple(candidates)


def _inner_oof(
    outer_fold: SourceOnlyFold,
    config: TrainingConfig,
    *,
    device: str,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    row_count = len(outer_fold.source_indices)
    class_count = len(outer_fold.label_names)
    probabilities = np.full((row_count, class_count), np.nan, dtype=float)
    traces = []
    training_ratios = []
    for split in build_inner_splits(outer_fold):
        inner_fold = materialize_inner_fold(outer_fold, split)
        started = perf_counter()
        fitted = fit_fold(inner_fold, config, device=device)
        elapsed = perf_counter() - started
        validation = predict(fitted, inner_fold.target_features)
        probabilities[split.validation_indices] = validation.probabilities
        final = fitted.history[-1]
        training_ratios.append(
            final["nuisance_response"] / final["fault_response"]
        )
        trace = {
            "dataset": outer_fold.dataset,
            "outer_fold_id": outer_fold.fold_id,
            "inner_split_id": split.split_id,
            "candidate_id": candidate_id(config),
            "configuration": asdict(config),
            "fit_seconds": elapsed,
            "model_state_sha256": fitted.state_sha256,
            "history": fitted.history,
        }
        traces.append(trace)
        print(
            json.dumps(
                {
                    "event": "inner_fit_complete",
                    "dataset": outer_fold.dataset,
                    "outer_fold_id": outer_fold.fold_id,
                    "inner_split_id": split.split_id,
                    "candidate_id": candidate_id(config),
                    "fit_seconds": elapsed,
                    "model_state_sha256": fitted.state_sha256,
                }
            ),
            flush=True,
        )
    if not np.isfinite(probabilities).all():
        raise ValueError("source OOF probability matrix is incomplete")
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
        raise ValueError("source OOF fault probability response is zero")
    return (
        {
            "dataset": outer_fold.dataset,
            "outer_fold_id": outer_fold.fold_id,
            "candidate_id": candidate_id(config),
            "configuration": asdict(config),
            "source_oof_macro_f1": _macro_f1(
                truth, predictions, class_count
            ),
            "source_oof_worst_environment_macro_f1": float(min(environment_f1)),
            "source_oof_multiclass_brier": _multiclass_brier(
                truth, probabilities, class_count
            ),
            "source_oof_nuisance_probability_response": nuisance,
            "source_oof_fault_probability_response": fault,
            "source_oof_probability_response_ratio": nuisance / fault,
            "mean_inner_training_representation_response_ratio": float(
                np.mean(training_ratios)
            ),
        },
        traces,
    )


def select_outer_candidate(
    candidate_metrics: list[dict[str, Any]],
    *,
    tolerance: float = SELECTION_TOLERANCE,
) -> dict[str, Any]:
    if not candidate_metrics or tolerance < 0:
        raise ValueError("outer selection requires candidates and a nonnegative tolerance")
    best_f1 = max(
        float(candidate["source_oof_macro_f1"])
        for candidate in candidate_metrics
    )
    eligible = [
        candidate
        for candidate in candidate_metrics
        if float(candidate["source_oof_macro_f1"]) + tolerance + 1e-12
        >= best_f1
    ]
    selected = min(
        eligible,
        key=lambda candidate: (
            float(candidate["source_oof_probability_response_ratio"]),
            float(candidate["source_oof_multiclass_brier"]),
            str(candidate["candidate_id"]),
        ),
    )
    return {
        "dataset": selected["dataset"],
        "outer_fold_id": selected["outer_fold_id"],
        "best_source_oof_macro_f1": best_f1,
        "tolerance": tolerance,
        "eligible_candidates": sorted(
            str(candidate["candidate_id"]) for candidate in eligible
        ),
        "selected_candidate_id": selected["candidate_id"],
        "selected_metrics": {
            key: value
            for key, value in selected.items()
            if key.startswith("source_oof_")
            or key == "mean_inner_training_representation_response_ratio"
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
        raise ValueError("common selection requires outer decisions and candidate metrics")
    counts = Counter(
        str(selection["selected_candidate_id"]) for selection in outer_selections
    )
    maximum = max(counts.values())
    contenders = sorted(
        candidate for candidate, count in counts.items() if count == maximum
    )
    f1_ranks: dict[str, list[int]] = {candidate: [] for candidate in contenders}
    ratio_ranks: dict[str, list[int]] = {candidate: [] for candidate in contenders}
    fold_keys = sorted(
        {
            (str(metric["dataset"]), str(metric["outer_fold_id"]))
            for metric in candidate_metrics
        }
    )
    for dataset, fold_id in fold_keys:
        rows = [
            metric
            for metric in candidate_metrics
            if metric["dataset"] == dataset and metric["outer_fold_id"] == fold_id
        ]
        f1 = {
            str(row["candidate_id"]): float(row["source_oof_macro_f1"])
            for row in rows
        }
        ratio = {
            str(row["candidate_id"]): float(
                row["source_oof_probability_response_ratio"]
            )
            for row in rows
        }
        fold_f1_ranks = _ordinal_ranks(f1, lower_is_better=False)
        fold_ratio_ranks = _ordinal_ranks(ratio, lower_is_better=True)
        for candidate in contenders:
            f1_ranks[candidate].append(fold_f1_ranks[candidate])
            ratio_ranks[candidate].append(fold_ratio_ranks[candidate])
    selected = min(
        contenders,
        key=lambda candidate: (
            float(np.mean(f1_ranks[candidate])),
            float(np.mean(ratio_ranks[candidate])),
            candidate,
        ),
    )
    return {
        "selected_candidate_id": selected,
        "selection_counts": dict(sorted(counts.items())),
        "modal_count": maximum,
        "modal_contenders": contenders,
        "tie_break_mean_f1_rank": {
            candidate: float(np.mean(ranks))
            for candidate, ranks in f1_ranks.items()
        },
        "tie_break_mean_ratio_rank": {
            candidate: float(np.mean(ranks))
            for candidate, ranks in ratio_ranks.items()
        },
    }


def _paired_against_erm(
    reference: dict[str, Any],
    results: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    output = {}
    for dataset, method_result in results.items():
        erm = _seed_aggregates(reference["results"][dataset]["erm"])
        current = _seed_aggregates(method_result)
        output[dataset] = {
            metric: _numeric_summary(
                [
                    current[seed][metric] - erm[seed][metric]
                    for seed in AUDIT_SEEDS
                ]
            )
            for metric in AGGREGATE_METRICS
        }
    return output


def _gate_decision(
    reference: dict[str, Any],
    results: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    representation_improved = {}
    probability_improved = {}
    worst_f1_change = {}
    mean_f1_change = {}
    for dataset, method_result in results.items():
        erm = reference["results"][dataset]["erm"]["summary"]
        summary = method_result["summary"]
        representation_improved[dataset] = bool(
            summary["mean_source_representation_response_ratio"]["mean"]
            < erm["mean_source_representation_response_ratio"]["mean"]
        )
        probability_improved[dataset] = bool(
            summary["mean_source_probability_response_ratio"]["mean"]
            < erm["mean_source_probability_response_ratio"]["mean"]
        )
        worst_f1_change[dataset] = float(
            summary["worst_fold_macro_f1"]["mean"]
            - erm["worst_fold_macro_f1"]["mean"]
        )
        mean_f1_change[dataset] = float(
            summary["mean_fold_macro_f1"]["mean"]
            - erm["mean_fold_macro_f1"]["mean"]
        )
    mechanism = all(representation_improved.values()) and all(
        probability_improved.values()
    )
    efficacy = any(change > 0 for change in worst_f1_change.values()) and all(
        change >= -0.02 for change in mean_f1_change.values()
    )
    return {
        "representation_response_ratio_improved": representation_improved,
        "probability_response_ratio_improved": probability_improved,
        "worst_fold_macro_f1_change": worst_f1_change,
        "mean_fold_macro_f1_change": mean_f1_change,
        "mechanism_gate_passed": mechanism,
        "efficacy_gate_passed": efficacy,
        "advance_to_strong_baselines": mechanism and efficacy,
    }


def run_selection(
    uci_feature_matrix: Path,
    reference_directory: Path,
    output_directory: Path,
    *,
    device: str = "cuda:0",
) -> dict[str, Any]:
    reference = _load_reference(reference_directory)
    if device.startswith("cuda"):
        if not torch.cuda.is_available():
            raise RuntimeError("v0.2 selection requires the validated CUDA environment")
        torch.cuda.init()
    datasets = {
        "cranfield": build_cranfield_folds(),
        "uci_hydraulic": build_uci_folds(uci_feature_matrix),
    }
    candidates = candidate_grid()
    metrics_by_fold: dict[tuple[str, str], list[dict[str, Any]]] = {}
    candidate_metrics = []
    tuning_traces = []
    for dataset, folds in datasets.items():
        for fold in folds:
            rows = []
            for config in candidates:
                metrics, traces = _inner_oof(fold, config, device=device)
                rows.append(metrics)
                candidate_metrics.append(metrics)
                tuning_traces.extend(traces)
            metrics_by_fold[(dataset, fold.fold_id)] = rows
    outer_selections = [
        select_outer_candidate(metrics_by_fold[key])
        for key in sorted(metrics_by_fold)
    ]
    common_selection = select_common_candidate(
        outer_selections, candidate_metrics
    )
    configurations = {candidate_id(config): config for config in candidates}
    selected_config = configurations[common_selection["selected_candidate_id"]]

    final_records = []
    final_traces = []
    results: dict[str, dict[str, Any]] = {}
    for dataset, folds in datasets.items():
        seed_results = []
        for seed in AUDIT_SEEDS:
            fold_results = []
            for fold in folds:
                metrics, records, trace = _fit_one(
                    fold,
                    "pirl_ratio",
                    int(seed),
                    device=device,
                    epochs=300,
                    base_config=selected_config,
                )
                fold_results.append(metrics)
                final_records.append(records)
                final_traces.append(trace)
                print(
                    json.dumps(
                        {
                            "event": "final_fit_complete",
                            "dataset": dataset,
                            "seed": int(seed),
                            "fold_id": fold.fold_id,
                            "candidate_id": candidate_id(selected_config),
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
        results[dataset] = {
            "seed_results": seed_results,
            "summary": _method_summary(seed_results),
        }

    output_directory.mkdir(parents=True, exist_ok=True)
    predictions_path = output_directory / "predictions.parquet"
    predictions = pd.concat(final_records, ignore_index=True)
    predictions.to_parquet(predictions_path, index=False)
    tuning_path = output_directory / "tuning_traces.json"
    tuning_path.write_text(
        json.dumps(tuning_traces, ensure_ascii=False, indent=2, allow_nan=False)
        + "\n",
        encoding="utf-8",
    )
    final_trace_path = output_directory / "final_training_traces.json"
    final_trace_path.write_text(
        json.dumps(final_traces, ensure_ascii=False, indent=2, allow_nan=False)
        + "\n",
        encoding="utf-8",
    )
    metrics = {
        "selection_version": SELECTION_VERSION,
        "generated_at": datetime.now(UTC).isoformat(),
        "protocol_document": "research/protocols/pirl_ratio_selection_v0.2.md",
        "input": {
            "uci_feature_matrix": str(uci_feature_matrix.resolve()),
            "uci_feature_matrix_sha256": _sha256(uci_feature_matrix),
            "reference_directory": str(reference_directory.resolve()),
            "reference_hashes": REFERENCE_HASHES,
            "paderborn_archive_contents_opened": False,
        },
        "configuration": {
            "selection_seed": SELECTION_SEED,
            "selection_tolerance": SELECTION_TOLERANCE,
            "candidate_count": len(candidates),
            "candidates": [
                {
                    "candidate_id": candidate_id(config),
                    "configuration": asdict(config),
                }
                for config in candidates
            ],
            "final_seeds": list(AUDIT_SEEDS),
            "device": device,
        },
        "candidate_metrics": candidate_metrics,
        "outer_selections": outer_selections,
        "common_selection": {
            **common_selection,
            "configuration": asdict(selected_config),
        },
        "results": results,
        "paired_pirl_ratio_minus_erm": _paired_against_erm(
            reference, results
        ),
        "gate_decision": _gate_decision(reference, results),
        "artifacts": {
            "predictions": {
                "path": predictions_path.name,
                "rows": len(predictions),
                "bytes": predictions_path.stat().st_size,
                "sha256": _sha256(predictions_path),
            },
            "tuning_traces": {
                "path": tuning_path.name,
                "models": len(tuning_traces),
                "bytes": tuning_path.stat().st_size,
                "sha256": _sha256(tuning_path),
            },
            "final_training_traces": {
                "path": final_trace_path.name,
                "models": len(final_traces),
                "bytes": final_trace_path.stat().st_size,
                "sha256": _sha256(final_trace_path),
            },
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
    parser.add_argument("--reference-directory", type=Path, required=True)
    parser.add_argument("--output-directory", type=Path, required=True)
    parser.add_argument("--device", default="cuda:0")
    args = parser.parse_args()
    result = run_selection(
        args.uci_feature_matrix,
        args.reference_directory,
        args.output_directory,
        device=args.device,
    )
    print(json.dumps(result["gate_decision"], ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
