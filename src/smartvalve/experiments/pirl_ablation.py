"""Run the frozen PIRL-SORE component-attribution ablation."""

from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pandas as pd
import torch

from smartvalve.experiments.cranfield_causal_audit import AUDIT_SEEDS
from smartvalve.experiments.domain_data import (
    build_cranfield_folds,
    build_uci_folds,
)
from smartvalve.experiments.pirl_development import (
    AGGREGATE_METRICS,
    _aggregate_folds,
    _fit_one,
    _method_summary,
    _numeric_summary,
    _sha256,
)

ABLATION_VERSION = "pirl-sore-component-ablation-0.1.0"
NEW_METHODS = ("worst_erm", "pirl_only")
REFERENCE_HASHES = {
    "metrics.json": "2909e32f19aa4b9beb5c28da821c1fd3e8b4e6670691eb64e03a21a5c9182ebf",
    "predictions.parquet": (
        "a80a93ef58aef8a135fe53dde3ed00a6255b350c3d766d5236e7e9555e02fa13"
    ),
    "training_traces.json": (
        "c0f0002b577e446e3f7a38cb5296d55bd02a31591de7c7f404e88691c2ad2302"
    ),
}


def _load_reference(directory: Path) -> dict[str, Any]:
    for name, expected in REFERENCE_HASHES.items():
        path = directory / name
        if not path.is_file():
            raise FileNotFoundError(f"missing locked EXP-320 reference: {path}")
        actual = _sha256(path)
        if actual != expected:
            raise ValueError(
                f"EXP-320 {name} hash mismatch: expected {expected}, got {actual}"
            )
    return json.loads((directory / "metrics.json").read_text(encoding="utf-8"))


def _seed_aggregates(method_result: dict[str, Any]) -> dict[int, dict[str, float]]:
    return {
        int(result["seed"]): result["aggregate"]
        for result in method_result["seed_results"]
    }


def _paired_comparisons(
    reference: dict[str, Any],
    new_results: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    comparisons = {}
    for dataset, methods in new_results.items():
        comparisons[dataset] = {}
        for method, result in methods.items():
            current = _seed_aggregates(result)
            for reference_method in ("erm", "pirl_sore"):
                locked = _seed_aggregates(
                    reference["results"][dataset][reference_method]
                )
                comparisons[dataset][f"{method}_minus_{reference_method}"] = {
                    metric: _numeric_summary(
                        [
                            current[seed][metric] - locked[seed][metric]
                            for seed in AUDIT_SEEDS
                        ]
                    )
                    for metric in AGGREGATE_METRICS
                }
    return comparisons


def _mean_metric(
    method_result: dict[str, Any],
    metric: str,
) -> float:
    return float(method_result["summary"][metric]["mean"])


def _attribution_decision(
    reference: dict[str, Any],
    new_results: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    uci_reference = reference["results"]["uci_hydraulic"]
    uci_new = new_results["uci_hydraulic"]
    metric = "mean_fold_macro_f1"
    erm_value = _mean_metric(uci_reference["erm"], metric)
    full_value = _mean_metric(uci_reference["pirl_sore"], metric)
    worst_value = _mean_metric(uci_new["worst_erm"], metric)
    pirl_only_value = _mean_metric(uci_new["pirl_only"], metric)
    full_gain = full_value - erm_value
    worst_recovery = (worst_value - erm_value) / full_gain if full_gain > 0 else None
    pirl_recovery = (
        (pirl_only_value - erm_value) / full_gain if full_gain > 0 else None
    )
    attributed_to_worst = bool(
        worst_recovery is not None
        and pirl_recovery is not None
        and worst_recovery >= 0.8
        and pirl_recovery < 0.2
    )

    response_improved = {}
    worst_f1_improved = {}
    mean_f1_change = {}
    for dataset in ("cranfield", "uci_hydraulic"):
        locked_erm = reference["results"][dataset]["erm"]
        pirl_only = new_results[dataset]["pirl_only"]
        response_improved[dataset] = bool(
            _mean_metric(
                pirl_only, "mean_source_representation_response_ratio"
            )
            < _mean_metric(
                locked_erm, "mean_source_representation_response_ratio"
            )
        )
        worst_f1_improved[dataset] = bool(
            _mean_metric(pirl_only, "worst_fold_macro_f1")
            > _mean_metric(locked_erm, "worst_fold_macro_f1")
        )
        mean_f1_change[dataset] = (
            _mean_metric(pirl_only, "mean_fold_macro_f1")
            - _mean_metric(locked_erm, "mean_fold_macro_f1")
        )
    mechanism_supported = bool(
        all(response_improved.values())
        and any(worst_f1_improved.values())
        and all(change >= -0.02 for change in mean_f1_change.values())
    )
    return {
        "uci_full_minus_erm_mean_macro_f1": full_gain,
        "uci_worst_erm_recovery_fraction": worst_recovery,
        "uci_pirl_only_recovery_fraction": pirl_recovery,
        "full_gain_attributed_primarily_to_worst_environment_term": (
            attributed_to_worst
        ),
        "pirl_only_response_ratio_improved": response_improved,
        "pirl_only_worst_fold_macro_f1_improved": worst_f1_improved,
        "pirl_only_mean_fold_macro_f1_change": mean_f1_change,
        "current_intervention_hinge_mechanistically_supported": (
            mechanism_supported
        ),
        "headline_current_hinge_rejected": not mechanism_supported,
    }


def run_ablation(
    uci_feature_matrix: Path,
    reference_directory: Path,
    output_directory: Path,
    *,
    device: str = "cuda:0",
) -> dict[str, Any]:
    reference = _load_reference(reference_directory)
    if device.startswith("cuda"):
        if not torch.cuda.is_available():
            raise RuntimeError("frozen ablation requires the validated CUDA environment")
        torch.cuda.init()
    datasets = {
        "cranfield": build_cranfield_folds(),
        "uci_hydraulic": build_uci_folds(uci_feature_matrix),
    }
    records = []
    traces = []
    results: dict[str, dict[str, Any]] = {}
    for dataset, folds in datasets.items():
        results[dataset] = {}
        for method in NEW_METHODS:
            seed_results = []
            for seed in AUDIT_SEEDS:
                fold_results = []
                for fold in folds:
                    metrics, prediction_records, trace = _fit_one(
                        fold,
                        method,
                        int(seed),
                        device=device,
                        epochs=300,
                    )
                    fold_results.append(metrics)
                    records.append(prediction_records)
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
    records_path = output_directory / "predictions.parquet"
    records_frame = pd.concat(records, ignore_index=True)
    records_frame.to_parquet(records_path, index=False)
    traces_path = output_directory / "training_traces.json"
    traces_path.write_text(
        json.dumps(traces, ensure_ascii=False, indent=2, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    comparisons = _paired_comparisons(reference, results)
    metrics = {
        "ablation_version": ABLATION_VERSION,
        "generated_at": datetime.now(UTC).isoformat(),
        "protocol_document": (
            "research/protocols/pirl_component_ablation_v0.1.md"
        ),
        "configuration": {
            "new_methods": list(NEW_METHODS),
            "locked_reference_methods": ["erm", "pirl_sore"],
            "seeds": list(AUDIT_SEEDS),
            "epochs": 300,
            "device": device,
        },
        "input": {
            "uci_feature_matrix": str(uci_feature_matrix.resolve()),
            "uci_feature_matrix_sha256": _sha256(uci_feature_matrix),
            "reference_directory": str(reference_directory.resolve()),
            "reference_hashes": REFERENCE_HASHES,
            "paderborn_archive_contents_opened": False,
        },
        "results": results,
        "paired_comparisons": comparisons,
        "attribution_decision": _attribution_decision(reference, results),
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
    result = run_ablation(
        args.uci_feature_matrix,
        args.reference_directory,
        args.output_directory,
        device=args.device,
    )
    print(json.dumps(result["attribution_decision"], ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
