"""Locked component attribution for the selected PIRL response-ratio method."""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict, replace
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
from smartvalve.experiments.pirl_ablation import _seed_aggregates
from smartvalve.experiments.pirl_development import (
    AGGREGATE_METRICS,
    _aggregate_folds,
    _fit_one,
    _method_summary,
    _numeric_summary,
    _sha256,
)
from smartvalve.experiments.pirl_sore import TrainingConfig

ABLATION_VERSION = "pirl-ratio-component-ablation-0.2.0"
REFERENCE_HASHES = {
    "metrics.json": "90bf71655ef2dbee9ab46ba2cb614f4c100d4553b6b4e94ffe5db140e21f72f7",
    "predictions.parquet": (
        "a32e0b8bfa7d8a522fa7e26bb26e2ac6f4113d32e5a3589f2b5c106e6f69ed22"
    ),
    "tuning_traces.json": (
        "a2eff73fc2b84de1c551bb022c75ca4d700defeacb034a0d830d9dbb2e35724f"
    ),
    "final_training_traces.json": (
        "d84aca64c937ffce91d608f8b0b2dd90eaf621785ef927404a895c84b465834d"
    ),
}
ABLATION_ARMS = ("same_arch_erm", "ratio_only", "margin_only")
EXPECTED_MANIFEST_VERSION = "pirl-ratio-ablation-expected-key-manifest-0.1.0"
EXPECTED_MODEL_COUNT = 195
EXPECTED_PREDICTION_COUNT = 67_500


def _validate_hash(path: Path, expected: str, label: str) -> str:
    observed = _sha256(path)
    if observed != expected:
        raise ValueError(
            f"{label} SHA-256 mismatch: expected {expected}, observed {observed}"
        )
    return observed


def validate_execution_authorization(
    *,
    uci_feature_matrix: Path,
    uci_feature_matrix_sha256: str,
    protocol_document: Path,
    protocol_sha256: str,
    expected_manifest: Path,
    expected_manifest_sha256: str,
    reference_directory: Path,
) -> dict[str, str]:
    """Require exact frozen inputs and outcome-blind topology before fitting."""

    paths = {
        "uci_feature_matrix": uci_feature_matrix.resolve(strict=True),
        "protocol_document": protocol_document.resolve(strict=True),
        "expected_manifest": expected_manifest.resolve(strict=True),
    }
    expected_hashes = {
        "uci_feature_matrix": uci_feature_matrix_sha256,
        "protocol_document": protocol_sha256,
        "expected_manifest": expected_manifest_sha256,
    }
    observed = {
        name: _validate_hash(path, expected_hashes[name], name)
        for name, path in paths.items()
    }
    protocol_text = paths["protocol_document"].read_text(encoding="utf-8")
    for value in (
        uci_feature_matrix_sha256,
        *REFERENCE_HASHES.values(),
        "195 model keys",
        "67,500",
    ):
        if value not in protocol_text:
            raise ValueError(f"PIRL ratio ablation protocol does not freeze {value}")

    manifest = json.loads(paths["expected_manifest"].read_text(encoding="utf-8"))
    if manifest.get("manifest_version") != EXPECTED_MANIFEST_VERSION:
        raise ValueError("PIRL ratio ablation expected-manifest version changed")
    manifest_input = manifest.get("input", {})
    expected_input = {
        "uci_feature_matrix_sha256": uci_feature_matrix_sha256,
        "protocol_document_sha256": protocol_sha256,
        "reference_hashes": REFERENCE_HASHES,
        "paderborn_archive_contents_opened": False,
    }
    for field, expected in expected_input.items():
        if manifest_input.get(field) != expected:
            raise ValueError(f"PIRL ratio ablation manifest input drift: {field}")
    if (
        Path(str(manifest_input.get("uci_feature_matrix", ""))).resolve()
        != paths["uci_feature_matrix"]
        or Path(str(manifest_input.get("protocol_document", ""))).resolve()
        != paths["protocol_document"]
        or Path(str(manifest_input.get("reference_directory", ""))).resolve()
        != reference_directory.resolve(strict=True)
    ):
        raise ValueError("PIRL ratio ablation manifest paths differ from the requested run")
    configuration = manifest.get("configuration", {})
    if (
        configuration.get("arms") != list(ABLATION_ARMS)
        or configuration.get("seeds") != list(AUDIT_SEEDS)
        or configuration.get("epochs") != 300
    ):
        raise ValueError("PIRL ratio ablation manifest configuration changed")
    key_sets = manifest.get("expected_key_sets", {})
    if (
        key_sets.get("training_models", {}).get("count") != EXPECTED_MODEL_COUNT
        or key_sets.get("target_predictions", {}).get("count")
        != EXPECTED_PREDICTION_COUNT
    ):
        raise ValueError("PIRL ratio ablation manifest topology count changed")
    return {
        **observed,
        "uci_feature_matrix_path": str(paths["uci_feature_matrix"]),
        "protocol_document_path": str(paths["protocol_document"]),
        "expected_manifest_path": str(paths["expected_manifest"]),
    }


def _load_reference(directory: Path) -> dict[str, Any]:
    for filename, expected in REFERENCE_HASHES.items():
        path = directory / filename
        if not path.is_file():
            raise FileNotFoundError(f"missing locked EXP-330 artifact: {path}")
        actual = _sha256(path)
        if actual != expected:
            raise ValueError(
                f"EXP-330 {filename} hash mismatch: expected {expected}, observed {actual}"
            )
    metrics = json.loads((directory / "metrics.json").read_text(encoding="utf-8"))
    gate = metrics.get("gate_decision", {})
    if not gate.get("mechanism_gate_passed") or not gate.get("efficacy_gate_passed"):
        raise ValueError("locked EXP-330 did not pass both development gates")
    if metrics["common_selection"]["selected_candidate_id"] != "r64_l1p0_m0p5":
        raise ValueError("locked EXP-330 selected candidate differs from the protocol")
    return metrics


def ablation_configurations(
    selected: TrainingConfig,
) -> dict[str, TrainingConfig]:
    """Change exactly the component declared by each frozen arm."""

    if selected.method != "pirl_ratio":
        raise ValueError("component ablation requires a selected pirl_ratio configuration")
    configurations = {
        "same_arch_erm": replace(selected, method="erm"),
        "ratio_only": replace(
            selected,
            method="pirl_ratio",
            ratio_term_weight=1.0,
            fault_margin_weight=0.0,
        ),
        "margin_only": replace(
            selected,
            method="pirl_ratio",
            ratio_term_weight=0.0,
            fault_margin_weight=1.0,
        ),
    }
    for configuration in configurations.values():
        configuration.validate()
    return configurations


def _paired_comparisons(
    reference: dict[str, Any],
    results: dict[str, dict[str, dict[str, Any]]],
) -> dict[str, Any]:
    comparisons = {}
    for dataset, arms in results.items():
        full = _seed_aggregates(reference["results"][dataset])
        same_arch_erm = _seed_aggregates(arms["same_arch_erm"])
        comparisons[dataset] = {}
        for arm, result in arms.items():
            current = _seed_aggregates(result)
            comparisons[dataset][f"{arm}_minus_full"] = {
                metric: _numeric_summary(
                    [
                        current[int(seed)][metric] - full[int(seed)][metric]
                        for seed in AUDIT_SEEDS
                    ]
                )
                for metric in AGGREGATE_METRICS
            }
            if arm != "same_arch_erm":
                comparisons[dataset][f"{arm}_minus_same_arch_erm"] = {
                    metric: _numeric_summary(
                        [
                            current[int(seed)][metric]
                            - same_arch_erm[int(seed)][metric]
                            for seed in AUDIT_SEEDS
                        ]
                    )
                    for metric in AGGREGATE_METRICS
                }
    return comparisons


def _component_summary(
    reference: dict[str, Any],
    results: dict[str, dict[str, dict[str, Any]]],
) -> dict[str, Any]:
    output = {}
    for dataset, arms in results.items():
        full = reference["results"][dataset]["summary"]
        output[dataset] = {}
        for arm, result in arms.items():
            summary = result["summary"]
            output[dataset][arm] = {
                "full_minus_arm_mean_fold_macro_f1": float(
                    full["mean_fold_macro_f1"]["mean"]
                    - summary["mean_fold_macro_f1"]["mean"]
                ),
                "full_minus_arm_worst_fold_macro_f1": float(
                    full["worst_fold_macro_f1"]["mean"]
                    - summary["worst_fold_macro_f1"]["mean"]
                ),
                "full_minus_arm_source_representation_response_ratio": float(
                    full["mean_source_representation_response_ratio"]["mean"]
                    - summary[
                        "mean_source_representation_response_ratio"
                    ]["mean"]
                ),
                "full_minus_arm_source_probability_response_ratio": float(
                    full["mean_source_probability_response_ratio"]["mean"]
                    - summary["mean_source_probability_response_ratio"]["mean"]
                ),
            }
    return output


def run_ablation(
    uci_feature_matrix: Path,
    reference_directory: Path,
    output_directory: Path,
    *,
    uci_feature_matrix_sha256: str,
    protocol_document: Path,
    protocol_sha256: str,
    expected_manifest: Path,
    expected_manifest_sha256: str,
    device: str = "cuda:0",
) -> dict[str, Any]:
    authorization = validate_execution_authorization(
        uci_feature_matrix=uci_feature_matrix,
        uci_feature_matrix_sha256=uci_feature_matrix_sha256,
        protocol_document=protocol_document,
        protocol_sha256=protocol_sha256,
        expected_manifest=expected_manifest,
        expected_manifest_sha256=expected_manifest_sha256,
        reference_directory=reference_directory,
    )
    uci_feature_matrix = Path(authorization["uci_feature_matrix_path"])
    reference_directory = reference_directory.resolve(strict=True)
    reference = _load_reference(reference_directory)
    selected = TrainingConfig(
        **reference["common_selection"]["configuration"]
    )
    configurations = ablation_configurations(selected)
    if device.startswith("cuda"):
        if not torch.cuda.is_available():
            raise RuntimeError("formal v0.2 ablation requires validated CUDA")
        torch.cuda.init()
    datasets = {
        "cranfield": build_cranfield_folds(),
        "uci_hydraulic": build_uci_folds(uci_feature_matrix),
    }
    records = []
    traces = []
    results: dict[str, dict[str, dict[str, Any]]] = {}
    for dataset, folds in datasets.items():
        results[dataset] = {}
        for arm in ABLATION_ARMS:
            configuration = configurations[arm]
            seed_results = []
            for seed in AUDIT_SEEDS:
                fold_results = []
                for fold in folds:
                    metrics, prediction_records, trace = _fit_one(
                        fold,
                        configuration.method,
                        int(seed),
                        device=device,
                        epochs=300,
                        base_config=configuration,
                    )
                    prediction_records["method"] = arm
                    trace["training_method"] = trace["method"]
                    trace["method"] = arm
                    fold_results.append(metrics)
                    records.append(prediction_records)
                    traces.append(trace)
                    print(
                        json.dumps(
                            {
                                "event": "pirl_ratio_ablation_fit_complete",
                                "dataset": dataset,
                                "arm": arm,
                                "training_method": configuration.method,
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
            results[dataset][arm] = {
                "seed_results": seed_results,
                "summary": _method_summary(seed_results),
            }
    output_directory.mkdir(parents=True, exist_ok=True)
    predictions_path = output_directory / "predictions.parquet"
    predictions = pd.concat(records, ignore_index=True, sort=False)
    predictions.to_parquet(predictions_path, index=False)
    traces_path = output_directory / "training_traces.json"
    traces_path.write_text(
        json.dumps(traces, ensure_ascii=False, indent=2, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    comparisons = _paired_comparisons(reference, results)
    metrics = {
        "ablation_version": ABLATION_VERSION,
        "generated_at": datetime.now(UTC).isoformat(),
        "protocol_document": "research/protocols/pirl_ratio_ablation_v0.2.md",
        "input": {
            "uci_feature_matrix": str(uci_feature_matrix.resolve()),
            "uci_feature_matrix_sha256": authorization["uci_feature_matrix"],
            "reference_directory": str(reference_directory.resolve()),
            "reference_hashes": REFERENCE_HASHES,
            "protocol_document": authorization["protocol_document_path"],
            "protocol_document_sha256": authorization["protocol_document"],
            "expected_manifest": authorization["expected_manifest_path"],
            "expected_manifest_sha256": authorization["expected_manifest"],
            "paderborn_archive_contents_opened": False,
        },
        "configuration": {
            "locked_full": asdict(selected),
            "ablation_arms": {
                arm: asdict(configuration)
                for arm, configuration in configurations.items()
            },
            "seeds": list(AUDIT_SEEDS),
            "epochs": 300,
            "device": device,
        },
        "locked_full_results": reference["results"],
        "results": results,
        "paired_comparisons": comparisons,
        "component_summary": _component_summary(reference, results),
        "artifacts": {
            "predictions": {
                "path": predictions_path.name,
                "rows": len(predictions),
                "bytes": predictions_path.stat().st_size,
                "sha256": _sha256(predictions_path),
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
    parser.add_argument("--uci-feature-matrix-sha256", required=True)
    parser.add_argument("--reference-directory", type=Path, required=True)
    parser.add_argument("--protocol-document", type=Path, required=True)
    parser.add_argument("--protocol-sha256", required=True)
    parser.add_argument("--expected-manifest", type=Path, required=True)
    parser.add_argument("--expected-manifest-sha256", required=True)
    parser.add_argument("--output-directory", type=Path, required=True)
    parser.add_argument("--device", default="cuda:0")
    args = parser.parse_args()
    result = run_ablation(
        args.uci_feature_matrix,
        args.reference_directory,
        args.output_directory,
        uci_feature_matrix_sha256=args.uci_feature_matrix_sha256,
        protocol_document=args.protocol_document,
        protocol_sha256=args.protocol_sha256,
        expected_manifest=args.expected_manifest,
        expected_manifest_sha256=args.expected_manifest_sha256,
        device=args.device,
    )
    print(json.dumps(result["component_summary"], ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
