"""Re-fit locked PIRL/ERM models for source-OOF selective evaluation."""

from __future__ import annotations

import argparse
import hashlib
import json
from dataclasses import asdict, dataclass, replace
from datetime import UTC, datetime
from pathlib import Path
from time import perf_counter
from typing import Any

import numpy as np
import pandas as pd
import torch

from smartvalve.experiments.cranfield_causal_audit import AUDIT_SEEDS
from smartvalve.experiments.dg_training import (
    BaselineConfig,
    fit_dg_fold,
    predict_dg,
)
from smartvalve.experiments.domain_data import (
    SourceOnlyFold,
    build_cranfield_folds,
    build_uci_folds,
)
from smartvalve.experiments.inner_splits import (
    InnerSplit,
    build_inner_splits,
    materialize_inner_fold,
)
from smartvalve.experiments.pirl_sore import (
    PredictionBundle,
    TrainingConfig,
    fit_class_support,
    fit_fold,
    predict,
    robust_class_distance,
)
from smartvalve.experiments.selective_evaluation import (
    SELECTIVE_EVALUATION_VERSION,
    analyze_ensemble_predictions,
    analyze_individual_predictions,
)

RUN_VERSION = "locked-pirl-erm-source-oof-selective-0.1.0"
METHODS = ("erm", "pirl_ratio")
REFERENCE_ABSOLUTE_TOLERANCE = 2e-6
PREFLIGHT_STATUS = "locked_selective_inputs_validated_before_refit"
EXPECTED_MANIFEST_VERSION = "selective-expected-key-manifest-0.1.0"


@dataclass(frozen=True)
class LockedReferences:
    pirl_directory: Path
    dg_directory: Path
    pirl_metrics_sha256: str
    dg_metrics_sha256: str
    configurations: dict[str, BaselineConfig | TrainingConfig]
    predictions: pd.DataFrame
    model_state_sha256: dict[tuple[str, str, int, str], str]
    artifact_hashes: dict[str, str]


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _validate_hash(path: Path, expected: str, label: str) -> str:
    actual = _sha256(path)
    if actual != expected:
        raise ValueError(f"{label} SHA-256 mismatch: expected {expected}, observed {actual}")
    return actual


def validate_execution_authorization(
    *,
    uci_feature_matrix: Path,
    uci_feature_matrix_sha256: str,
    pirl_reference_directory: Path,
    dg_reference_directory: Path,
    pirl_metrics_sha256: str,
    dg_metrics_sha256: str,
    protocol_document: Path,
    protocol_sha256: str,
    input_preflight: Path,
    input_preflight_sha256: str,
    expected_manifest: Path,
    expected_manifest_sha256: str,
) -> dict[str, str]:
    """Require the frozen protocol and both pre-run gates before any GPU fit."""

    paths = {
        "uci_feature_matrix": uci_feature_matrix.resolve(strict=True),
        "protocol_document": protocol_document.resolve(strict=True),
        "input_preflight": input_preflight.resolve(strict=True),
        "expected_manifest": expected_manifest.resolve(strict=True),
    }
    expected_hashes = {
        "uci_feature_matrix": uci_feature_matrix_sha256,
        "protocol_document": protocol_sha256,
        "input_preflight": input_preflight_sha256,
        "expected_manifest": expected_manifest_sha256,
    }
    observed_hashes = {
        name: _validate_hash(path, expected_hashes[name], name)
        for name, path in paths.items()
    }
    protocol_text = paths["protocol_document"].read_text(encoding="utf-8")
    for frozen_value in (
        "frozen v0.1",
        uci_feature_matrix_sha256,
        pirl_metrics_sha256,
        dg_metrics_sha256,
    ):
        if frozen_value not in protocol_text:
            raise ValueError(f"selective protocol does not freeze {frozen_value}")

    preflight = _read_json(paths["input_preflight"])
    if preflight.get("status") != PREFLIGHT_STATUS:
        raise ValueError("selective input preflight did not pass")
    preflight_inputs = preflight.get("inputs", {})
    expected_inputs = {
        "uci_feature_matrix_sha256": uci_feature_matrix_sha256,
        "pirl_metrics_sha256": pirl_metrics_sha256,
        "dg_metrics_sha256": dg_metrics_sha256,
    }
    for field, expected in expected_inputs.items():
        if preflight_inputs.get(field) != expected:
            raise ValueError(f"selective preflight input drift: {field}")
    if (
        Path(str(preflight_inputs.get("uci_feature_matrix", ""))).resolve()
        != paths["uci_feature_matrix"]
        or Path(str(preflight_inputs.get("pirl_reference_directory", ""))).resolve()
        != pirl_reference_directory.resolve()
        or Path(str(preflight_inputs.get("dg_reference_directory", ""))).resolve()
        != dg_reference_directory.resolve()
    ):
        raise ValueError("selective preflight paths differ from the requested run")
    access = preflight.get("access_attestation", {})
    if (
        access.get("target_outcomes_used_for_configuration_selection") is not False
        or access.get("paderborn_archive_path_supplied") is not False
        or access.get("paderborn_archive_contents_opened") is not False
    ):
        raise ValueError("selective preflight violates the access boundary")

    manifest = _read_json(paths["expected_manifest"])
    if manifest.get("manifest_version") != EXPECTED_MANIFEST_VERSION:
        raise ValueError("selective expected-manifest version changed")
    manifest_inputs = manifest.get("input", {})
    for field, expected in expected_inputs.items():
        if manifest_inputs.get(field) != expected:
            raise ValueError(f"selective expected-manifest input drift: {field}")
    if manifest_inputs.get("paderborn_archive_contents_opened") is not False:
        raise ValueError("selective expected manifest violates the Paderborn boundary")
    return observed_hashes


def _artifact_path(
    directory: Path,
    metrics: dict[str, Any],
    artifact_name: str,
) -> Path:
    record = metrics["artifacts"][artifact_name]
    path = directory / str(record["path"])
    _validate_hash(path, str(record["sha256"]), artifact_name)
    return path


def _trace_index(
    traces: list[dict[str, Any]],
    *,
    expected_method: str,
) -> dict[tuple[str, str, int, str], str]:
    output = {}
    for trace in traces:
        method = str(trace.get("method", expected_method))
        if method != expected_method:
            continue
        key = (
            str(trace["dataset"]),
            method,
            int(trace["seed"]),
            str(trace["fold_id"]),
        )
        if key in output:
            raise ValueError(f"duplicate reference training trace: {key}")
        output[key] = str(trace["model_state_sha256"])
    return output


def load_locked_references(
    pirl_directory: Path,
    dg_directory: Path,
    *,
    expected_pirl_metrics_sha256: str,
    expected_dg_metrics_sha256: str,
) -> LockedReferences:
    """Load only hash-locked, source-selected configurations and predictions."""

    pirl_metrics_path = pirl_directory / "metrics.json"
    dg_metrics_path = dg_directory / "metrics.json"
    pirl_metrics_sha256 = _validate_hash(
        pirl_metrics_path,
        expected_pirl_metrics_sha256,
        "PIRL metrics",
    )
    dg_metrics_sha256 = _validate_hash(
        dg_metrics_path,
        expected_dg_metrics_sha256,
        "DG metrics",
    )
    pirl_metrics = _read_json(pirl_metrics_path)
    dg_metrics = _read_json(dg_metrics_path)
    gate = pirl_metrics.get("gate_decision", {})
    if not gate.get("mechanism_gate_passed") or not gate.get("efficacy_gate_passed"):
        raise ValueError("PIRL reference did not pass both frozen development gates")
    pirl_configuration = TrainingConfig(
        **pirl_metrics["common_selection"]["configuration"]
    )
    pirl_configuration.validate()
    if pirl_configuration.method != "pirl_ratio":
        raise ValueError("PIRL reference does not select pirl_ratio")
    erm_configuration = BaselineConfig(
        **dg_metrics["common_selections"]["erm"]["configuration"]
    )
    erm_configuration.validate()
    if erm_configuration.method != "erm":
        raise ValueError("DG reference does not select ERM")

    pirl_predictions_path = _artifact_path(
        pirl_directory, pirl_metrics, "predictions"
    )
    dg_predictions_path = _artifact_path(dg_directory, dg_metrics, "predictions")
    pirl_trace_path = _artifact_path(
        pirl_directory, pirl_metrics, "final_training_traces"
    )
    dg_trace_path = _artifact_path(
        dg_directory, dg_metrics, "final_training_traces"
    )
    pirl_predictions = pd.read_parquet(pirl_predictions_path)
    dg_predictions = pd.read_parquet(dg_predictions_path)
    pirl_predictions = pirl_predictions.loc[
        pirl_predictions["method"] == "pirl_ratio"
    ].copy()
    dg_predictions = dg_predictions.loc[dg_predictions["method"] == "erm"].copy()
    if pirl_predictions.empty or dg_predictions.empty:
        raise ValueError("reference predictions do not contain PIRL and tuned ERM")
    predictions = pd.concat(
        [pirl_predictions, dg_predictions], ignore_index=True, sort=False
    )
    trace_hashes = {
        **_trace_index(_read_json(pirl_trace_path), expected_method="pirl_ratio"),
        **_trace_index(_read_json(dg_trace_path), expected_method="erm"),
    }
    expected_models = 2 * len(AUDIT_SEEDS) * 13
    if len(trace_hashes) != expected_models:
        raise ValueError(
            f"reference trace count mismatch: expected {expected_models}, "
            f"observed {len(trace_hashes)}"
        )
    return LockedReferences(
        pirl_directory=pirl_directory.resolve(),
        dg_directory=dg_directory.resolve(),
        pirl_metrics_sha256=pirl_metrics_sha256,
        dg_metrics_sha256=dg_metrics_sha256,
        configurations={
            "pirl_ratio": pirl_configuration,
            "erm": erm_configuration,
        },
        predictions=predictions,
        model_state_sha256=trace_hashes,
        artifact_hashes={
            "pirl_predictions": _sha256(pirl_predictions_path),
            "dg_predictions": _sha256(dg_predictions_path),
            "pirl_final_training_traces": _sha256(pirl_trace_path),
            "dg_final_training_traces": _sha256(dg_trace_path),
        },
    )


def _fit_model(
    method: str,
    fold: SourceOnlyFold,
    configuration: BaselineConfig | TrainingConfig,
    seed: int,
    *,
    device: str,
) -> Any:
    if method == "erm":
        if not isinstance(configuration, BaselineConfig):
            raise TypeError("ERM requires a BaselineConfig")
        return fit_dg_fold(fold, replace(configuration, seed=seed), device=device)
    if method == "pirl_ratio":
        if not isinstance(configuration, TrainingConfig):
            raise TypeError("PIRL requires a TrainingConfig")
        return fit_fold(fold, replace(configuration, seed=seed), device=device)
    raise ValueError(f"unsupported locked selective method: {method}")


def _predict_model(method: str, fitted: Any, features: np.ndarray) -> PredictionBundle:
    return predict_dg(fitted, features) if method == "erm" else predict(fitted, features)


def _prediction_records(
    outer_fold: SourceOnlyFold,
    bundle: PredictionBundle,
    support_distance: np.ndarray,
    *,
    method: str,
    seed: int,
    row_indices: np.ndarray,
    environments: np.ndarray,
    inner_split_id: str | None,
) -> pd.DataFrame:
    row_indices = np.asarray(row_indices, dtype=np.int64)
    environments = np.asarray(environments)
    if len(bundle.predictions) != len(row_indices) or len(environments) != len(row_indices):
        raise ValueError("prediction records are not aligned")
    truth_indices = outer_fold.labels[row_indices]
    records = pd.DataFrame(
        {
            "dataset": outer_fold.dataset,
            "method": method,
            "seed": seed,
            "fold_id": outer_fold.fold_id,
            "held_factor": outer_fold.held_factor,
            "held_level": outer_fold.held_level,
            "inner_split_id": inner_split_id,
            "row_index": row_indices,
            "environment_id": environments,
            "block_id": outer_fold.block_ids[row_indices],
            "truth": [outer_fold.label_names[value] for value in truth_indices],
            "prediction": [
                outer_fold.label_names[value] for value in bundle.predictions
            ],
            "correct": bundle.predictions == truth_indices,
            "confidence": bundle.probabilities.max(axis=1),
            "robust_class_support_distance": support_distance,
        }
    )
    for index, label in enumerate(outer_fold.label_names):
        records[f"probability_{label}"] = bundle.probabilities[:, index]
        records[f"logit_{label}"] = bundle.logits[:, index]
    for index in range(bundle.representations.shape[1]):
        records[f"representation_{index:02d}"] = bundle.representations[:, index]
    return records


def _fit_and_predict(
    outer_fold: SourceOnlyFold,
    training_fold: SourceOnlyFold,
    configuration: BaselineConfig | TrainingConfig,
    *,
    method: str,
    seed: int,
    device: str,
    row_indices: np.ndarray,
    environments: np.ndarray,
    inner_split_id: str | None,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    if device.startswith("cuda"):
        torch.cuda.reset_peak_memory_stats(0)
    started = perf_counter()
    fitted = _fit_model(method, training_fold, configuration, seed, device=device)
    fit_seconds = perf_counter() - started
    source_bundle = _predict_model(method, fitted, training_fold.source_features)
    evaluation_bundle = _predict_model(method, fitted, training_fold.target_features)
    support = fit_class_support(
        source_bundle.representations,
        training_fold.source_labels,
        class_count=len(training_fold.label_names),
    )
    support_distance = robust_class_distance(
        evaluation_bundle.representations, support
    ).min(axis=1)
    records = _prediction_records(
        outer_fold,
        evaluation_bundle,
        support_distance,
        method=method,
        seed=seed,
        row_indices=row_indices,
        environments=environments,
        inner_split_id=inner_split_id,
    )
    trace = {
        "dataset": outer_fold.dataset,
        "method": method,
        "seed": seed,
        "fold_id": outer_fold.fold_id,
        "inner_split_id": inner_split_id,
        "configuration": asdict(replace(configuration, seed=seed)),
        "fit_seconds": fit_seconds,
        "peak_memory_bytes": (
            int(torch.cuda.max_memory_allocated(0))
            if device.startswith("cuda")
            else None
        ),
        "model_state_sha256": fitted.state_sha256,
        "auxiliary_state_sha256": getattr(
            fitted, "auxiliary_state_sha256", None
        ),
        "history": fitted.history,
    }
    return records, trace


def _inner_prediction(
    outer_fold: SourceOnlyFold,
    split: InnerSplit,
    configuration: BaselineConfig | TrainingConfig,
    *,
    method: str,
    seed: int,
    device: str,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    inner_fold = materialize_inner_fold(outer_fold, split)
    outer_source = outer_fold.source_indices
    return _fit_and_predict(
        outer_fold,
        inner_fold,
        configuration,
        method=method,
        seed=seed,
        device=device,
        row_indices=outer_source[split.validation_indices],
        environments=outer_fold.source_environments[split.validation_indices],
        inner_split_id=split.split_id,
    )


def _final_prediction(
    fold: SourceOnlyFold,
    configuration: BaselineConfig | TrainingConfig,
    *,
    method: str,
    seed: int,
    device: str,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    return _fit_and_predict(
        fold,
        fold,
        configuration,
        method=method,
        seed=seed,
        device=device,
        row_indices=fold.target_indices,
        environments=fold.target_environments,
        inner_split_id=None,
    )


def reference_crosscheck(
    observed: pd.DataFrame,
    reference: pd.DataFrame,
    *,
    tolerance: float = REFERENCE_ABSOLUTE_TOLERANCE,
) -> dict[str, Any]:
    """Require exact row identity and near-exact locked target probabilities."""

    key_columns = ["dataset", "method", "seed", "fold_id", "row_index"]
    probability_columns = sorted(
        column
        for column in observed.columns
        if column.startswith("probability_") and observed[column].notna().all()
    )
    reference_probability_columns = [
        column for column in probability_columns if column in reference.columns
    ]
    if reference_probability_columns != probability_columns:
        raise ValueError("reference is missing an observed probability column")
    observed_ordered = observed.sort_values(key_columns, kind="stable").reset_index(
        drop=True
    )
    reference_ordered = reference.sort_values(key_columns, kind="stable").reset_index(
        drop=True
    )
    if len(observed_ordered) != len(reference_ordered):
        raise ValueError("reference and observed prediction row counts differ")
    if not observed_ordered[key_columns].equals(reference_ordered[key_columns]):
        raise ValueError("reference and observed prediction keys differ")
    for column in ("truth", "prediction", "correct"):
        if not np.array_equal(
            observed_ordered[column].to_numpy(),
            reference_ordered[column].to_numpy(),
        ):
            raise ValueError(f"reference and observed {column} values differ")
    observed_probabilities = observed_ordered.loc[
        :, probability_columns
    ].to_numpy(dtype=float)
    reference_probabilities = reference_ordered.loc[
        :, probability_columns
    ].to_numpy(dtype=float)
    maximum_difference = float(
        np.max(np.abs(observed_probabilities - reference_probabilities))
    )
    if maximum_difference > tolerance:
        raise ValueError(
            "reference probability crosscheck failed: "
            f"maximum absolute difference {maximum_difference} exceeds {tolerance}"
        )
    return {
        "rows": len(observed_ordered),
        "probability_columns": probability_columns,
        "maximum_absolute_probability_difference": maximum_difference,
        "tolerance": tolerance,
    }


def _reference_group(
    references: LockedReferences,
    *,
    dataset: str,
    method: str,
    seed: int,
    fold_id: str,
) -> pd.DataFrame:
    rows = references.predictions.loc[
        (references.predictions["dataset"] == dataset)
        & (references.predictions["method"] == method)
        & (references.predictions["seed"] == seed)
        & (references.predictions["fold_id"] == fold_id)
    ]
    if rows.empty:
        raise ValueError("locked reference prediction group is missing")
    return rows


def _artifact(path: Path, **counts: int) -> dict[str, Any]:
    return {
        "path": path.name,
        **counts,
        "bytes": path.stat().st_size,
        "sha256": _sha256(path),
    }


def validate_prediction_topology(
    source_oof: pd.DataFrame,
    target: pd.DataFrame,
    datasets: dict[str, list[SourceOnlyFold]],
    *,
    methods: tuple[str, ...] = METHODS,
    seeds: tuple[int, ...] = AUDIT_SEEDS,
    expected_inner_partitions: int = 4,
) -> dict[str, int]:
    """Prove one OOF/source and one target prediction per frozen group row."""

    group_columns = ["dataset", "method", "seed", "fold_id"]
    if source_oof.duplicated([*group_columns, "row_index"]).any():
        raise ValueError("source OOF predictions contain duplicate group rows")
    if target.duplicated([*group_columns, "row_index"]).any():
        raise ValueError("target predictions contain duplicate group rows")
    if source_oof["inner_split_id"].isna().any():
        raise ValueError("source OOF predictions are missing inner split IDs")
    if target["inner_split_id"].notna().any():
        raise ValueError("final target predictions unexpectedly have inner split IDs")
    checked_groups = 0
    for dataset, folds in datasets.items():
        for method in methods:
            for seed in seeds:
                for fold in folds:
                    selector = (
                        (source_oof["dataset"] == dataset)
                        & (source_oof["method"] == method)
                        & (source_oof["seed"] == seed)
                        & (source_oof["fold_id"] == fold.fold_id)
                    )
                    source_group = source_oof.loc[selector]
                    target_group = target.loc[
                        (target["dataset"] == dataset)
                        & (target["method"] == method)
                        & (target["seed"] == seed)
                        & (target["fold_id"] == fold.fold_id)
                    ]
                    if set(source_group["row_index"].astype(int)) != set(
                        fold.source_indices.astype(int)
                    ):
                        raise ValueError("source OOF row topology differs from the outer source")
                    if set(target_group["row_index"].astype(int)) != set(
                        fold.target_indices.astype(int)
                    ):
                        raise ValueError("target row topology differs from the outer target")
                    if source_group["inner_split_id"].nunique() != expected_inner_partitions:
                        raise ValueError("source OOF group has the wrong inner partition count")
                    checked_groups += 1
    expected_groups = sum(len(folds) for folds in datasets.values()) * len(
        methods
    ) * len(seeds)
    observed_source_groups = source_oof.groupby(
        group_columns, observed=True
    ).ngroups
    observed_target_groups = target.groupby(group_columns, observed=True).ngroups
    if (
        checked_groups != expected_groups
        or observed_source_groups != expected_groups
        or observed_target_groups != expected_groups
    ):
        raise ValueError("prediction groups do not exactly match the frozen topology")
    return {
        "groups": checked_groups,
        "source_oof_rows": len(source_oof),
        "target_rows": len(target),
    }


def _json_write(path: Path, value: Any) -> None:
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n",
        encoding="utf-8",
    )


def _headline_summary(policy_metrics: list[dict[str, Any]]) -> dict[str, Any]:
    rows = pd.DataFrame(
        [
            {
                "dataset": row["dataset"],
                "method": row["method"],
                "score_name": row["score_name"],
                "nominal_source_coverage": row["nominal_source_coverage"],
                "coverage": row["coverage"],
                "selective_risk": row["selective_risk"],
                "effective_accuracy": row["effective_accuracy"],
                "macro_f1_abstention_as_error": row[
                    "macro_f1_abstention_as_error"
                ],
                "minimum_environment_coverage": row[
                    "minimum_environment_coverage"
                ],
            }
            for row in policy_metrics
            if row["score_name"] == "risk_envelope"
        ]
    )
    output: dict[str, Any] = {}
    for (dataset, method, coverage), group in rows.groupby(
        ["dataset", "method", "nominal_source_coverage"],
        sort=True,
        observed=True,
    ):
        valid_risks = group["selective_risk"].dropna().to_numpy(dtype=float)
        output.setdefault(str(dataset), {}).setdefault(str(method), {})[
            str(float(coverage))
        ] = {
            "fold_seed_groups": len(group),
            "zero_coverage_groups": int(group["selective_risk"].isna().sum()),
            "mean_target_coverage": float(group["coverage"].mean()),
            "minimum_target_coverage": float(group["coverage"].min()),
            "mean_selective_risk": (
                float(valid_risks.mean()) if len(valid_risks) else None
            ),
            "maximum_selective_risk": (
                float(valid_risks.max()) if len(valid_risks) else None
            ),
            "mean_effective_accuracy": float(group["effective_accuracy"].mean()),
            "mean_macro_f1_abstention_as_error": float(
                group["macro_f1_abstention_as_error"].mean()
            ),
            "minimum_environment_coverage": float(
                group["minimum_environment_coverage"].min()
            ),
        }
    return output


def run_selective_evaluation(
    uci_feature_matrix: Path,
    pirl_reference_directory: Path,
    dg_reference_directory: Path,
    output_directory: Path,
    *,
    uci_feature_matrix_sha256: str,
    pirl_metrics_sha256: str,
    dg_metrics_sha256: str,
    protocol_document: Path,
    protocol_sha256: str,
    input_preflight: Path,
    input_preflight_sha256: str,
    expected_manifest: Path,
    expected_manifest_sha256: str,
    device: str = "cuda:0",
) -> dict[str, Any]:
    authorization_hashes = validate_execution_authorization(
        uci_feature_matrix=uci_feature_matrix,
        uci_feature_matrix_sha256=uci_feature_matrix_sha256,
        pirl_reference_directory=pirl_reference_directory,
        dg_reference_directory=dg_reference_directory,
        pirl_metrics_sha256=pirl_metrics_sha256,
        dg_metrics_sha256=dg_metrics_sha256,
        protocol_document=protocol_document,
        protocol_sha256=protocol_sha256,
        input_preflight=input_preflight,
        input_preflight_sha256=input_preflight_sha256,
        expected_manifest=expected_manifest,
        expected_manifest_sha256=expected_manifest_sha256,
    )
    if device.startswith("cuda"):
        if not torch.cuda.is_available():
            raise RuntimeError("formal selective evaluation requires validated CUDA")
        torch.cuda.init()
    references = load_locked_references(
        pirl_reference_directory,
        dg_reference_directory,
        expected_pirl_metrics_sha256=pirl_metrics_sha256,
        expected_dg_metrics_sha256=dg_metrics_sha256,
    )
    datasets = {
        "cranfield": build_cranfield_folds(),
        "uci_hydraulic": build_uci_folds(uci_feature_matrix),
    }
    source_records = []
    target_records = []
    training_traces = []
    crosschecks = []
    expected_final_models = 0
    for method in METHODS:
        configuration = references.configurations[method]
        for dataset, folds in datasets.items():
            for seed in AUDIT_SEEDS:
                for fold in folds:
                    for split in build_inner_splits(fold):
                        records, trace = _inner_prediction(
                            fold,
                            split,
                            configuration,
                            method=method,
                            seed=int(seed),
                            device=device,
                        )
                        source_records.append(records)
                        training_traces.append(trace)
                        print(
                            json.dumps(
                                {
                                    "event": "selective_source_oof_fit_complete",
                                    "dataset": dataset,
                                    "method": method,
                                    "seed": int(seed),
                                    "fold_id": fold.fold_id,
                                    "inner_split_id": split.split_id,
                                    "fit_seconds": trace["fit_seconds"],
                                    "model_state_sha256": trace[
                                        "model_state_sha256"
                                    ],
                                }
                            ),
                            flush=True,
                        )
                    records, trace = _final_prediction(
                        fold,
                        configuration,
                        method=method,
                        seed=int(seed),
                        device=device,
                    )
                    reference_key = (dataset, method, int(seed), fold.fold_id)
                    if (
                        references.model_state_sha256[reference_key]
                        != trace["model_state_sha256"]
                    ):
                        raise ValueError(
                            f"locked final model state crosscheck failed: {reference_key}"
                        )
                    crosscheck = reference_crosscheck(
                        records,
                        _reference_group(
                            references,
                            dataset=dataset,
                            method=method,
                            seed=int(seed),
                            fold_id=fold.fold_id,
                        ),
                    )
                    crosschecks.append(
                        {
                            "dataset": dataset,
                            "method": method,
                            "seed": int(seed),
                            "fold_id": fold.fold_id,
                            **crosscheck,
                        }
                    )
                    target_records.append(records)
                    training_traces.append(trace)
                    expected_final_models += 1
                    print(
                        json.dumps(
                            {
                                "event": "selective_final_fit_crosschecked",
                                "dataset": dataset,
                                "method": method,
                                "seed": int(seed),
                                "fold_id": fold.fold_id,
                                "fit_seconds": trace["fit_seconds"],
                                "model_state_sha256": trace[
                                    "model_state_sha256"
                                ],
                                "maximum_absolute_probability_difference": (
                                    crosscheck[
                                        "maximum_absolute_probability_difference"
                                    ]
                                ),
                            }
                        ),
                        flush=True,
                    )
    if expected_final_models != 2 * len(AUDIT_SEEDS) * 13:
        raise AssertionError("selective final model count does not match the frozen design")

    source = pd.concat(source_records, ignore_index=True, sort=False)
    target = pd.concat(target_records, ignore_index=True, sort=False)
    topology = validate_prediction_topology(source, target, datasets)
    analysis = analyze_individual_predictions(source, target)
    ensemble_analysis = analyze_ensemble_predictions(
        source,
        target,
        expected_seeds=tuple(int(seed) for seed in AUDIT_SEEDS),
    )
    policies = [*analysis["policies"], *ensemble_analysis["policies"]]
    beta_selections = [
        *analysis["beta_selections"],
        *ensemble_analysis["beta_selections"],
    ]
    policy_metrics = [
        *analysis["policy_metrics"],
        *ensemble_analysis["policy_metrics"],
    ]
    ranking_metrics = [
        *analysis["ranking_metrics"],
        *ensemble_analysis["ranking_metrics"],
    ]
    decisions = pd.concat(
        [analysis["decisions"], ensemble_analysis["decisions"]],
        ignore_index=True,
        sort=False,
    )
    output_directory.mkdir(parents=True, exist_ok=True)
    source_path = output_directory / "source_oof_predictions.parquet"
    target_path = output_directory / "target_predictions.parquet"
    source_ensemble_path = output_directory / "source_oof_ensemble_predictions.parquet"
    target_ensemble_path = output_directory / "target_ensemble_predictions.parquet"
    decisions_path = output_directory / "selection_decisions.parquet"
    policies_path = output_directory / "policies.json"
    beta_path = output_directory / "beta_selections.json"
    policy_metrics_path = output_directory / "policy_metrics.json"
    ranking_metrics_path = output_directory / "ranking_metrics.json"
    traces_path = output_directory / "training_traces.json"
    crosschecks_path = output_directory / "reference_crosschecks.json"
    analysis["source_scored"].to_parquet(source_path, index=False)
    analysis["target_scored"].to_parquet(target_path, index=False)
    ensemble_analysis["source_ensemble"].to_parquet(
        source_ensemble_path, index=False
    )
    ensemble_analysis["target_ensemble"].to_parquet(
        target_ensemble_path, index=False
    )
    decisions.to_parquet(decisions_path, index=False)
    _json_write(policies_path, policies)
    _json_write(beta_path, beta_selections)
    _json_write(policy_metrics_path, policy_metrics)
    _json_write(ranking_metrics_path, ranking_metrics)
    _json_write(traces_path, training_traces)
    _json_write(crosschecks_path, crosschecks)
    metrics = {
        "run_version": RUN_VERSION,
        "selective_evaluation_version": SELECTIVE_EVALUATION_VERSION,
        "generated_at": datetime.now(UTC).isoformat(),
        "protocol_document": (
            "research/protocols/source_selective_evaluation_v0.1.md"
        ),
        "input": {
            "uci_feature_matrix": str(uci_feature_matrix.resolve()),
            "uci_feature_matrix_sha256": authorization_hashes["uci_feature_matrix"],
            "pirl_reference_directory": str(references.pirl_directory),
            "dg_reference_directory": str(references.dg_directory),
            "pirl_metrics_sha256": references.pirl_metrics_sha256,
            "dg_metrics_sha256": references.dg_metrics_sha256,
            "protocol_document": str(protocol_document.resolve()),
            "protocol_document_sha256": authorization_hashes["protocol_document"],
            "input_preflight": str(input_preflight.resolve()),
            "input_preflight_sha256": authorization_hashes["input_preflight"],
            "expected_manifest": str(expected_manifest.resolve()),
            "expected_manifest_sha256": authorization_hashes["expected_manifest"],
            "reference_artifact_hashes": references.artifact_hashes,
            "paderborn_archive_contents_opened": False,
        },
        "configuration": {
            "methods": list(METHODS),
            "method_configurations": {
                method: asdict(configuration)
                for method, configuration in references.configurations.items()
            },
            "seeds": list(AUDIT_SEEDS),
            "outer_folds": {name: len(folds) for name, folds in datasets.items()},
            "inner_partitions_per_fold": 4,
            "device": device,
            "reference_absolute_tolerance": REFERENCE_ABSOLUTE_TOLERANCE,
        },
        "integrity": {
            "reference_crosschecks": len(crosschecks),
            "maximum_absolute_probability_difference": max(
                row["maximum_absolute_probability_difference"]
                for row in crosschecks
            ),
            "all_final_model_state_hashes_exact": True,
            "prediction_topology": topology,
        },
        "headline_risk_envelope_summary": _headline_summary(
            policy_metrics
        ),
        "artifacts": {
            "source_oof_predictions": _artifact(
                source_path, rows=len(analysis["source_scored"])
            ),
            "target_predictions": _artifact(
                target_path, rows=len(analysis["target_scored"])
            ),
            "source_oof_ensemble_predictions": _artifact(
                source_ensemble_path,
                rows=len(ensemble_analysis["source_ensemble"]),
            ),
            "target_ensemble_predictions": _artifact(
                target_ensemble_path,
                rows=len(ensemble_analysis["target_ensemble"]),
            ),
            "selection_decisions": _artifact(
                decisions_path, rows=len(decisions)
            ),
            "policies": _artifact(policies_path, policies=len(policies)),
            "beta_selections": _artifact(
                beta_path, selections=len(beta_selections)
            ),
            "policy_metrics": _artifact(
                policy_metrics_path, evaluations=len(policy_metrics)
            ),
            "ranking_metrics": _artifact(
                ranking_metrics_path, evaluations=len(ranking_metrics)
            ),
            "training_traces": _artifact(
                traces_path, models=len(training_traces)
            ),
            "reference_crosschecks": _artifact(
                crosschecks_path, groups=len(crosschecks)
            ),
        },
    }
    _json_write(output_directory / "metrics.json", metrics)
    return metrics


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--uci-feature-matrix", type=Path, required=True)
    parser.add_argument("--uci-feature-matrix-sha256", required=True)
    parser.add_argument("--pirl-reference-directory", type=Path, required=True)
    parser.add_argument("--dg-reference-directory", type=Path, required=True)
    parser.add_argument("--pirl-metrics-sha256", required=True)
    parser.add_argument("--dg-metrics-sha256", required=True)
    parser.add_argument("--protocol-document", type=Path, required=True)
    parser.add_argument("--protocol-sha256", required=True)
    parser.add_argument("--input-preflight", type=Path, required=True)
    parser.add_argument("--input-preflight-sha256", required=True)
    parser.add_argument("--expected-manifest", type=Path, required=True)
    parser.add_argument("--expected-manifest-sha256", required=True)
    parser.add_argument("--output-directory", type=Path, required=True)
    parser.add_argument("--device", default="cuda:0")
    args = parser.parse_args()
    result = run_selective_evaluation(
        args.uci_feature_matrix,
        args.pirl_reference_directory,
        args.dg_reference_directory,
        args.output_directory,
        uci_feature_matrix_sha256=args.uci_feature_matrix_sha256,
        pirl_metrics_sha256=args.pirl_metrics_sha256,
        dg_metrics_sha256=args.dg_metrics_sha256,
        protocol_document=args.protocol_document,
        protocol_sha256=args.protocol_sha256,
        input_preflight=args.input_preflight,
        input_preflight_sha256=args.input_preflight_sha256,
        expected_manifest=args.expected_manifest,
        expected_manifest_sha256=args.expected_manifest_sha256,
        device=args.device,
    )
    print(json.dumps(result["integrity"], ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
