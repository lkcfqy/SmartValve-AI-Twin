"""Run the one-shot sealed Paderborn comparison with D0/D1-selected configurations."""

from __future__ import annotations

import argparse
import hashlib
import json
from dataclasses import asdict, replace
from datetime import UTC, datetime
from pathlib import Path
from time import perf_counter
from typing import Any

import numpy as np
import pandas as pd
import torch

from smartvalve.config import project_root
from smartvalve.experiments.cranfield_causal_audit import AUDIT_SEEDS
from smartvalve.experiments.dg_selection import candidate_id as dg_candidate_id
from smartvalve.experiments.dg_training import (
    BASELINE_METHODS,
    BaselineConfig,
    fit_dg_fold,
    predict_dg,
)
from smartvalve.experiments.paderborn_domain import (
    PaderbornModelFold,
    build_paderborn_model_folds,
)
from smartvalve.experiments.paderborn_structure_probe import _load_and_validate_seal
from smartvalve.experiments.pirl_development import (
    _fold_metrics,
    _macro_f1,
    _multiclass_brier,
    _numeric_summary,
    _response,
)
from smartvalve.experiments.pirl_ratio_selection import (
    candidate_id as pirl_candidate_id,
)
from smartvalve.experiments.pirl_sore import (
    TrainingConfig,
    fit_class_support,
    fit_fold,
    predict,
    risk_envelope_score,
    robust_class_distance,
)

RUN_VERSION = "paderborn-sealed-prospective-evaluation-0.2.0"
METHODS = ("pirl_ratio", *BASELINE_METHODS)
PROBABILITY_TOLERANCE = 2e-6
REPRESENTATION_TOLERANCE = 2e-6
EXPECTED_MANIFEST_VERSION = "paderborn-prospective-expected-key-manifest-0.2.0"
EXPECTED_EXECUTION_SEAL_VERSION = "smartvalve-paderborn-d2-execution-seal-0.1.0"
EXPECTED_MODEL_COUNT = 1_080
EXPECTED_TARGET_PREDICTIONS = 104_355
EXPECTED_COMPOUND_PREDICTIONS = 259_200


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _resolve_sealed_artifact(root: Path, seal: dict[str, Any], role: str) -> Path:
    record = seal.get("artifacts", {}).get(role)
    if not isinstance(record, dict):
        raise ValueError(f"prospective seal is missing artifact role {role}")
    relative = Path(str(record.get("path", "")))
    if relative.is_absolute() or ".." in relative.parts:
        raise ValueError(f"sealed artifact path is unsafe for role {role}")
    path = (root / relative).resolve(strict=True)
    if root != path and root not in path.parents:
        raise ValueError(f"sealed artifact escapes the project root for role {role}")
    if path.stat().st_size != record.get("bytes") or _sha256(path) != record.get("sha256"):
        raise ValueError(f"sealed artifact changed for role {role}")
    return path


def load_sealed_configurations(
    root: Path, seal: dict[str, Any]
) -> tuple[
    dict[str, TrainingConfig | BaselineConfig],
    dict[str, str],
    dict[str, str],
]:
    """Load all nine exact D0/D1 selections referenced by the final seal."""

    pirl_path = _resolve_sealed_artifact(root, seal, "pirl_development_metrics")
    dg_path = _resolve_sealed_artifact(root, seal, "dg_selection_metrics")
    pirl_metrics = _read_json(pirl_path)
    dg_metrics = _read_json(dg_path)
    gate = pirl_metrics.get("gate_decision", {})
    if not gate.get("mechanism_gate_passed") or not gate.get("efficacy_gate_passed"):
        raise ValueError("sealed PIRL development reference did not pass both gates")
    pirl = TrainingConfig(**pirl_metrics["common_selection"]["configuration"])
    pirl.validate()
    if pirl.method != "pirl_ratio":
        raise ValueError("sealed headline configuration is not pirl_ratio")
    identifiers = {"pirl_ratio": str(pirl_metrics["common_selection"]["selected_candidate_id"])}
    if identifiers["pirl_ratio"] != pirl_candidate_id(pirl):
        raise ValueError("sealed PIRL candidate identifier mismatch")
    configurations: dict[str, TrainingConfig | BaselineConfig] = {"pirl_ratio": pirl}
    common = dg_metrics.get("common_selections", {})
    if set(common) != set(BASELINE_METHODS):
        raise ValueError("sealed DG reference does not contain all eight methods")
    for method in BASELINE_METHODS:
        configuration = BaselineConfig(**common[method]["configuration"])
        configuration.validate()
        if configuration.method != method:
            raise ValueError(f"sealed DG configuration method mismatch: {method}")
        identifier = str(common[method]["selected_candidate_id"])
        if identifier != dg_candidate_id(configuration):
            raise ValueError(f"sealed DG candidate identifier mismatch: {method}")
        configurations[method] = configuration
        identifiers[method] = identifier

    decision = seal.get("decision", {})
    selected = decision.get("selected_configurations", {})
    if selected.get("pirl") != identifiers["pirl_ratio"]:
        raise ValueError("seal decision changes the PIRL candidate")
    for method in BASELINE_METHODS:
        if selected.get(method) != identifiers[method]:
            raise ValueError(f"seal decision changes the {method} candidate")
    return (
        configurations,
        identifiers,
        {"pirl_metrics_sha256": _sha256(pirl_path), "dg_metrics_sha256": _sha256(dg_path)},
    )


def validate_execution_authorization(
    root: Path,
    seal: dict[str, Any],
    *,
    prospective_seal: Path,
    expected_prospective_seal_sha256: str,
    execution_seal: Path,
    expected_execution_seal_sha256: str,
    feature_metrics: Path,
    expected_feature_metrics_sha256: str,
    expected_manifest: Path,
    expected_manifest_sha256: str,
) -> dict[str, str]:
    """Bind the evaluator to the amended post-feature, pre-model execution seal."""

    prospective_seal = prospective_seal.resolve(strict=True)
    if _sha256(prospective_seal) != expected_prospective_seal_sha256:
        raise ValueError("original Paderborn prospective-seal SHA-256 mismatch")
    execution_seal = execution_seal.resolve(strict=True)
    if _sha256(execution_seal) != expected_execution_seal_sha256:
        raise ValueError("Paderborn D2 execution-seal SHA-256 mismatch")
    amended_seal = _read_json(execution_seal)
    if (
        amended_seal.get("schema_version") != EXPECTED_EXECUTION_SEAL_VERSION
        or amended_seal.get("status") != "sealed_after_features_before_paderborn_model_outcomes"
    ):
        raise ValueError("Paderborn D2 execution seal is not valid for model fitting")
    if amended_seal.get("decision") != seal.get("decision") or amended_seal.get(
        "statistics"
    ) != seal.get("statistics"):
        raise ValueError("Paderborn D2 execution seal changes the original decision")
    if (
        _resolve_sealed_artifact(root, amended_seal, "original_prospective_seal")
        != prospective_seal
    ):
        raise ValueError("Paderborn D2 execution seal references another original seal")
    feature_metrics = feature_metrics.resolve(strict=True)
    if (
        _sha256(feature_metrics) != expected_feature_metrics_sha256
        or _resolve_sealed_artifact(root, amended_seal, "feature_metrics") != feature_metrics
    ):
        raise ValueError("Paderborn D2 execution seal references other features")
    expected_manifest = expected_manifest.resolve(strict=True)
    if _sha256(expected_manifest) != expected_manifest_sha256:
        raise ValueError("Paderborn expected-manifest SHA-256 mismatch")
    sealed_manifest = _resolve_sealed_artifact(root, amended_seal, "amended_expected_manifest")
    if sealed_manifest != expected_manifest:
        raise ValueError("Paderborn seal references a different expected manifest")
    manifest = _read_json(expected_manifest)
    if manifest.get("manifest_version") != EXPECTED_MANIFEST_VERSION:
        raise ValueError("Paderborn expected-manifest version changed")
    manifest_input = manifest.get("input", {})
    role_by_field = {
        "protocol_document": "execution_amendment_protocol",
        "split_manifest": "amended_split_manifest",
        "model_fold_manifest": "amended_model_fold_manifest",
        "feature_contract_amendment": "feature_contract_amendment",
        "feature_validation": "feature_validation",
    }
    hashes = {"expected_manifest": expected_manifest_sha256}
    for field, role in role_by_field.items():
        path = _resolve_sealed_artifact(root, amended_seal, role)
        digest = _sha256(path)
        if (
            Path(str(manifest_input.get(field, ""))).resolve() != path
            or manifest_input.get(f"{field}_sha256") != digest
        ):
            raise ValueError(f"Paderborn expected-manifest input drift: {field}")
        hashes[field] = digest
    key_sets = manifest.get("expected_key_sets", {})
    expected_counts = {
        "training_models": EXPECTED_MODEL_COUNT,
        "fold_metrics": EXPECTED_MODEL_COUNT,
        "target_predictions": EXPECTED_TARGET_PREDICTIONS,
        "compound_predictions": EXPECTED_COMPOUND_PREDICTIONS,
    }
    for name, count in expected_counts.items():
        if key_sets.get(name, {}).get("count") != count:
            raise ValueError(f"Paderborn expected topology changed: {name}")
    amended_attestation = amended_seal.get("attestation", {})
    if (
        manifest_input.get("signal_features_used_to_define_topology") is not False
        or manifest_input.get("model_outcomes_inspected_before_manifest") is not False
        or seal.get("attestation", {}).get("paderborn_model_outcomes_inspected") is not False
        or amended_attestation.get("paderborn_models_fitted") is not False
        or amended_attestation.get("paderborn_model_outcomes_inspected") is not False
        or amended_attestation.get("target_guided_reselection_performed") is not False
    ):
        raise ValueError("Paderborn execution authorization is not prospective")
    hashes["execution_seal"] = expected_execution_seal_sha256
    hashes["feature_metrics"] = expected_feature_metrics_sha256
    return hashes


def _load_feature_frame(
    metrics_path: Path,
    *,
    expected_metrics_sha256: str,
    expected_seal_sha256: str,
) -> tuple[pd.DataFrame, pd.DataFrame, dict[str, Any], Path, Path]:
    if _sha256(metrics_path) != expected_metrics_sha256:
        raise ValueError("Paderborn feature metrics SHA-256 mismatch")
    metrics = _read_json(metrics_path)
    if metrics.get("status") != "sealed_paderborn_features_complete_without_model_outcome_access":
        raise ValueError("Paderborn feature run did not complete the frozen contract")
    if metrics["input"].get("prospective_seal_sha256") != expected_seal_sha256:
        raise ValueError("Paderborn features reference a different prospective seal")
    if metrics["access_attestation"].get("model_outcomes_inspected") is not False:
        raise ValueError("Paderborn feature input already crossed the model-outcome boundary")
    loaded = {}
    paths = {}
    for artifact_name in ("feature_matrix", "primary_feature_matrix"):
        record = metrics["artifacts"][artifact_name]
        path = (metrics_path.parent / str(record["path"])).resolve(strict=True)
        if path.stat().st_size != record["bytes"] or _sha256(path) != record["sha256"]:
            raise ValueError(f"Paderborn {artifact_name} changed")
        frame = pd.read_parquet(path)
        if len(frame) != int(record["rows"]):
            raise ValueError(f"Paderborn {artifact_name} row count changed")
        loaded[artifact_name] = frame
        paths[artifact_name] = path
    full_frame = loaded["feature_matrix"].reset_index(drop=True)
    primary = loaded["primary_feature_matrix"].reset_index(drop=True)
    derived_primary = full_frame.loc[full_frame["truth"] != "compound"].reset_index(drop=True)
    if not primary.equals(derived_primary):
        raise ValueError("Paderborn primary matrix is not the exact pure-class subset")
    compound = full_frame.loc[full_frame["truth"] == "compound"].copy()
    compound["full_row_index"] = compound.index.to_numpy(dtype=np.int64)
    compound = compound.reset_index(drop=True)
    if compound.empty:
        raise ValueError("Paderborn compound stress set is empty")
    corpus = metrics.get("corpus", {})
    if (
        int(corpus.get("measurement_count", -1)) != len(full_frame)
        or int(corpus.get("primary_measurement_count", -1)) != len(primary)
        or int(corpus.get("compound_measurement_count", -1)) != len(compound)
    ):
        raise ValueError("Paderborn feature corpus counts changed")
    return (
        primary,
        compound,
        metrics,
        paths["primary_feature_matrix"],
        paths["feature_matrix"],
    )


def _fit_one(
    model_fold: PaderbornModelFold,
    configuration: TrainingConfig | BaselineConfig,
    *,
    method: str,
    seed: int,
    device: str,
    full_frame: pd.DataFrame,
    compound_frame: pd.DataFrame,
    candidate_identifier: str,
) -> tuple[dict[str, Any], pd.DataFrame, pd.DataFrame, dict[str, Any]]:
    fold = model_fold.fold
    final_configuration = replace(configuration, seed=seed)
    if device.startswith("cuda"):
        torch.cuda.reset_peak_memory_stats(0)
    started = perf_counter()
    if method == "pirl_ratio":
        if not isinstance(final_configuration, TrainingConfig):
            raise TypeError("PIRL requires TrainingConfig")
        fitted = fit_fold(fold, final_configuration, device=device)
        predictor = predict
    else:
        if not isinstance(final_configuration, BaselineConfig):
            raise TypeError("DG baseline requires BaselineConfig")
        fitted = fit_dg_fold(fold, final_configuration, device=device)
        predictor = predict_dg
    fit_seconds = perf_counter() - started
    source = predictor(fitted, fold.source_features)
    inference_started = perf_counter()
    target = predictor(fitted, fold.target_features)
    inference_seconds = perf_counter() - inference_started
    compound_started = perf_counter()
    compound = predictor(
        fitted,
        compound_frame.loc[:, list(fold.feature_names)].to_numpy(dtype=np.float32),
    )
    compound_inference_seconds = perf_counter() - compound_started
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
    support_distance = robust_class_distance(target.representations, support).min(axis=1)
    compound_scores = risk_envelope_score(
        compound.probabilities,
        compound.representations,
        support,
        beta=0.25,
    )
    compound_support_distance = robust_class_distance(compound.representations, support).min(axis=1)
    nuisance_representation = _response(
        source.representations, fold.nuisance_pairs, total_variation=False
    )
    fault_representation = _response(
        source.representations, fold.fault_pairs, total_variation=False
    )
    nuisance_probability = _response(
        source.probabilities, fold.nuisance_pairs, total_variation=True
    )
    fault_probability = _response(source.probabilities, fold.fault_pairs, total_variation=True)
    if min(fault_representation, fault_probability) <= 0:
        raise ValueError("Paderborn fitted model has a zero source fault response")
    fit_record = {
        "dataset": "paderborn",
        "method": method,
        "seed": seed,
        "fold_id": fold.fold_id,
        "candidate_id": candidate_identifier,
        "held_bearing_codes": list(model_fold.held_bearing_codes),
        "held_setting_code": model_fold.held_setting_code,
        "source_rows": len(fold.source_indices),
        "target_rows": len(fold.target_indices),
        "quarantine_rows": len(model_fold.quarantine_global_indices),
        "source_nuisance_representation_response": nuisance_representation,
        "source_fault_representation_response": fault_representation,
        "source_representation_response_ratio": (nuisance_representation / fault_representation),
        "source_nuisance_probability_response": nuisance_probability,
        "source_fault_probability_response": fault_probability,
        "source_probability_response_ratio": nuisance_probability / fault_probability,
        "fit_seconds": fit_seconds,
        "inference_seconds": inference_seconds,
        "compound_inference_seconds": compound_inference_seconds,
        "peak_memory_bytes": (
            int(torch.cuda.max_memory_allocated(0)) if device.startswith("cuda") else None
        ),
        "parameter_count_network_only": int(
            sum(parameter.numel() for parameter in fitted.network.parameters())
        ),
        "model_state_sha256": fitted.state_sha256,
        "auxiliary_state_sha256": getattr(fitted, "auxiliary_state_sha256", None),
    }
    global_indices = model_fold.target_global_indices.astype(np.int64)
    records = pd.DataFrame(
        {
            "dataset": "paderborn",
            "method": method,
            "seed": seed,
            "fold_id": fold.fold_id,
            "held_factor": fold.held_factor,
            "held_level": fold.held_level,
            "row_index": global_indices,
            "environment_id": fold.target_environments,
            "block_id": fold.block_ids[fold.target_indices],
            "prediction": [fold.label_names[value] for value in target.predictions],
            "confidence": target.probabilities.max(axis=1),
            "msp_uncertainty": 1.0 - target.probabilities.max(axis=1),
            "robust_class_support_distance": support_distance,
            "risk_envelope_score_beta_0_25": scores,
        }
    )
    for index, label in enumerate(fold.label_names):
        records[f"probability_{label}"] = target.probabilities[:, index]
        records[f"logit_{label}"] = target.logits[:, index]
    for index in range(target.representations.shape[1]):
        records[f"representation_{index:02d}"] = target.representations[:, index]
    target_metadata = full_frame.iloc[global_indices].reset_index(drop=True)
    for column in (
        "filename",
        "bearing_code",
        "setting_code",
        "measurement_index",
        "damage_origin",
        "component",
        "damage_extent",
    ):
        records[column] = target_metadata[column].to_numpy()
    compound_records = pd.DataFrame(
        {
            "dataset": "paderborn_compound",
            "method": method,
            "seed": seed,
            "fold_id": fold.fold_id,
            "held_setting_code": model_fold.held_setting_code,
            "row_index": compound_frame["full_row_index"].to_numpy(dtype=np.int64),
            "filename": compound_frame["filename"].astype(str).to_numpy(),
            "bearing_code": compound_frame["bearing_code"].astype(str).to_numpy(),
            "setting_code": compound_frame["setting_code"].astype(str).to_numpy(),
            "measurement_index": compound_frame["measurement_index"].to_numpy(dtype=np.int64),
            "prediction": [fold.label_names[value] for value in compound.predictions],
            "confidence": compound.probabilities.max(axis=1),
            "msp_uncertainty": 1.0 - compound.probabilities.max(axis=1),
            "robust_class_support_distance": compound_support_distance,
            "risk_envelope_score_beta_0_25": compound_scores,
        }
    )
    for index, label in enumerate(fold.label_names):
        compound_records[f"probability_{label}"] = compound.probabilities[:, index]
        compound_records[f"logit_{label}"] = compound.logits[:, index]
    for index in range(compound.representations.shape[1]):
        compound_records[f"representation_{index:02d}"] = compound.representations[:, index]
    trace = {
        "dataset": "paderborn",
        "method": method,
        "seed": seed,
        "fold_id": fold.fold_id,
        "candidate_id": candidate_identifier,
        "configuration": asdict(final_configuration),
        "source_global_indices_sha256": hashlib.sha256(
            model_fold.source_global_indices.tobytes()
        ).hexdigest(),
        "target_global_indices_sha256": hashlib.sha256(
            model_fold.target_global_indices.tobytes()
        ).hexdigest(),
        "quarantine_global_indices_sha256": hashlib.sha256(
            model_fold.quarantine_global_indices.tobytes()
        ).hexdigest(),
        "compound_full_row_indices_sha256": hashlib.sha256(
            compound_frame["full_row_index"].to_numpy(dtype=np.int64).tobytes()
        ).hexdigest(),
        "model_state_sha256": fitted.state_sha256,
        "auxiliary_state_sha256": getattr(fitted, "auxiliary_state_sha256", None),
        "history": fitted.history,
    }
    return fit_record, records, compound_records, trace


def fit_progress_event(fit_record: dict[str, Any]) -> dict[str, Any]:
    """Return an outcome-blind progress event from a completed frozen fit."""

    return {
        "event": "paderborn_prospective_fit_complete",
        "method": fit_record["method"],
        "seed": fit_record["seed"],
        "fold_id": fit_record["fold_id"],
        "candidate_id": fit_record["candidate_id"],
        "fit_seconds": fit_record["fit_seconds"],
        "model_state_sha256": fit_record["model_state_sha256"],
    }


def validate_prediction_topology(
    predictions: pd.DataFrame,
    *,
    row_count: int,
    methods: tuple[str, ...] = METHODS,
    seeds: tuple[int, ...] = AUDIT_SEEDS,
    expected_folds: int = 24,
    expected_representation_dimensions: dict[str, int] | None = None,
) -> dict[str, Any]:
    required = {"dataset", "method", "seed", "fold_id", "row_index"}
    missing = required - set(predictions)
    if missing:
        raise ValueError(f"Paderborn predictions are missing columns: {sorted(missing)}")
    if set(predictions["dataset"].astype(str)) != {"paderborn"}:
        raise ValueError("Paderborn prediction dataset identity changed")
    if set(predictions["method"].astype(str)) != set(methods):
        raise ValueError("Paderborn prediction method set changed")
    if set(predictions["seed"].astype(int)) != set(seeds):
        raise ValueError("Paderborn prediction seed set changed")
    if expected_representation_dimensions is not None and set(
        expected_representation_dimensions
    ) != set(methods):
        raise ValueError("Paderborn expected representation dimensions are incomplete")
    keys = ["dataset", "method", "seed", "row_index"]
    if predictions.duplicated(keys).any():
        raise ValueError("Paderborn predictions contain duplicate model/row keys")
    expected_rows = set(range(row_count))
    groups = 0
    maximum_probability_error = 0.0
    maximum_representation_norm_error = 0.0
    representation_schemas: dict[str, tuple[str, ...]] = {}
    for method in methods:
        for seed in seeds:
            group = predictions.loc[
                (predictions["method"] == method) & (predictions["seed"] == seed)
            ]
            if set(group["row_index"].astype(int)) != expected_rows or len(group) != row_count:
                raise ValueError("Paderborn method/seed does not predict every primary row once")
            if group["fold_id"].nunique() != expected_folds:
                raise ValueError("Paderborn method/seed has the wrong outer-fold count")
            probability_columns = sorted(
                column
                for column in group
                if column.startswith("probability_") and group[column].notna().all()
            )
            probabilities = group[probability_columns].to_numpy(dtype=float)
            if len(probability_columns) != 3 or not np.isfinite(probabilities).all():
                raise ValueError("Paderborn probabilities have an invalid schema")
            error = float(np.max(np.abs(probabilities.sum(axis=1) - 1.0)))
            maximum_probability_error = max(maximum_probability_error, error)
            representation_columns = sorted(
                column
                for column in group
                if column.startswith("representation_") and group[column].notna().all()
            )
            schema = tuple(representation_columns)
            if method not in representation_schemas:
                representation_schemas[method] = schema
            elif schema != representation_schemas[method]:
                raise ValueError("Paderborn representation schema changes within a method")
            if (
                expected_representation_dimensions is not None
                and len(schema) != expected_representation_dimensions[method]
            ):
                raise ValueError(f"Paderborn representation dimension differs for {method}")
            representations = group[representation_columns].to_numpy(dtype=float)
            if not representation_columns or not np.isfinite(representations).all():
                raise ValueError("Paderborn representations have an invalid schema")
            norm_error = float(np.max(np.abs(np.linalg.norm(representations, axis=1) - 1.0)))
            maximum_representation_norm_error = max(maximum_representation_norm_error, norm_error)
            groups += 1
    observed_groups = predictions.groupby(["method", "seed", "fold_id"], observed=True).ngroups
    expected_groups = len(methods) * len(seeds) * expected_folds
    if groups != len(methods) * len(seeds) or observed_groups != expected_groups:
        raise ValueError("Paderborn prediction groups differ from the frozen design")
    if maximum_probability_error > PROBABILITY_TOLERANCE:
        raise ValueError("Paderborn probabilities are not normalized")
    if maximum_representation_norm_error > REPRESENTATION_TOLERANCE:
        raise ValueError("Paderborn representations are not unit normalized")
    return {
        "method_seed_groups": groups,
        "model_fold_groups": observed_groups,
        "prediction_rows": len(predictions),
        "representation_dimensions": {
            method: len(representation_schemas[method]) for method in methods
        },
        "maximum_probability_sum_error": maximum_probability_error,
        "maximum_representation_norm_error": maximum_representation_norm_error,
    }


def validate_compound_prediction_topology(
    predictions: pd.DataFrame,
    compound_frame: pd.DataFrame,
    *,
    fold_ids: tuple[str, ...],
    methods: tuple[str, ...] = METHODS,
    seeds: tuple[int, ...] = AUDIT_SEEDS,
    expected_representation_dimensions: dict[str, int],
) -> dict[str, Any]:
    """Validate unlabeled compound predictions without defining a forced outcome."""

    required = {
        "dataset",
        "method",
        "seed",
        "fold_id",
        "row_index",
        "filename",
        "bearing_code",
        "setting_code",
        "measurement_index",
        "prediction",
    }
    missing = required - set(predictions)
    if missing:
        raise ValueError(f"Paderborn compound predictions are missing columns: {sorted(missing)}")
    forbidden = {"truth", "correct", "component", "damage_extent", "damage_origin"}
    if forbidden & set(predictions):
        raise ValueError("Paderborn compound predictions expose a forced outcome field")
    if set(predictions["dataset"].astype(str)) != {"paderborn_compound"}:
        raise ValueError("Paderborn compound dataset identity changed")
    if set(predictions["method"].astype(str)) != set(methods):
        raise ValueError("Paderborn compound method set changed")
    if set(predictions["seed"].astype(int)) != set(seeds):
        raise ValueError("Paderborn compound seed set changed")
    if set(predictions["fold_id"].astype(str)) != set(fold_ids):
        raise ValueError("Paderborn compound fold set changed")
    if not set(predictions["prediction"].astype(str)).issubset({"healthy", "outer", "inner"}):
        raise ValueError("Paderborn compound prediction label changed")
    if set(expected_representation_dimensions) != set(methods):
        raise ValueError("Paderborn compound representation dimensions are incomplete")
    keys = ["dataset", "method", "seed", "fold_id", "row_index"]
    if predictions.duplicated(keys).any():
        raise ValueError("Paderborn compound predictions contain duplicate model/row keys")
    metadata = compound_frame.set_index("full_row_index", verify_integrity=True)
    expected_rows = set(metadata.index.astype(int))
    maximum_probability_error = 0.0
    maximum_representation_norm_error = 0.0
    representation_schemas: dict[str, tuple[str, ...]] = {}
    groups = 0
    for method in methods:
        for seed in seeds:
            for fold_id in fold_ids:
                group = predictions.loc[
                    (predictions["method"] == method)
                    & (predictions["seed"] == seed)
                    & (predictions["fold_id"] == fold_id)
                ].sort_values("row_index", kind="stable")
                if set(group["row_index"].astype(int)) != expected_rows or len(group) != len(
                    metadata
                ):
                    raise ValueError(
                        "Paderborn compound model does not predict every stress row once"
                    )
                aligned = metadata.loc[group["row_index"].to_numpy(dtype=np.int64)]
                for column in (
                    "filename",
                    "bearing_code",
                    "setting_code",
                    "measurement_index",
                ):
                    if not np.array_equal(group[column].to_numpy(), aligned[column].to_numpy()):
                        raise ValueError(
                            f"Paderborn compound {column} differs from feature provenance"
                        )
                probability_columns = sorted(
                    column
                    for column in group
                    if column.startswith("probability_") and group[column].notna().all()
                )
                probabilities = group[probability_columns].to_numpy(dtype=float)
                if len(probability_columns) != 3 or not np.isfinite(probabilities).all():
                    raise ValueError("Paderborn compound probabilities have an invalid schema")
                maximum_probability_error = max(
                    maximum_probability_error,
                    float(np.max(np.abs(probabilities.sum(axis=1) - 1.0))),
                )
                representation_columns = sorted(
                    column
                    for column in group
                    if column.startswith("representation_") and group[column].notna().all()
                )
                schema = tuple(representation_columns)
                if method not in representation_schemas:
                    representation_schemas[method] = schema
                elif representation_schemas[method] != schema:
                    raise ValueError(
                        "Paderborn compound representation schema changes within a method"
                    )
                if len(schema) != expected_representation_dimensions[method]:
                    raise ValueError(
                        f"Paderborn compound representation dimension differs for {method}"
                    )
                representations = group[representation_columns].to_numpy(dtype=float)
                if not representation_columns or not np.isfinite(representations).all():
                    raise ValueError("Paderborn compound representations have an invalid schema")
                maximum_representation_norm_error = max(
                    maximum_representation_norm_error,
                    float(np.max(np.abs(np.linalg.norm(representations, axis=1) - 1.0))),
                )
                groups += 1
    expected_groups = len(methods) * len(seeds) * len(fold_ids)
    if (
        groups != expected_groups
        or predictions.groupby(["method", "seed", "fold_id"], observed=True).ngroups
        != expected_groups
    ):
        raise ValueError("Paderborn compound groups differ from the frozen design")
    if maximum_probability_error > PROBABILITY_TOLERANCE:
        raise ValueError("Paderborn compound probabilities are not normalized")
    if maximum_representation_norm_error > REPRESENTATION_TOLERANCE:
        raise ValueError("Paderborn compound representations are not unit normalized")
    return {
        "model_groups": groups,
        "prediction_rows": len(predictions),
        "unique_compound_measurements": len(metadata),
        "representation_dimensions": {
            method: len(representation_schemas[method]) for method in methods
        },
        "maximum_probability_sum_error": maximum_probability_error,
        "maximum_representation_norm_error": maximum_representation_norm_error,
        "forced_ground_truth_defined": False,
    }


def _compound_diagnostics(
    predictions: pd.DataFrame,
    *,
    methods: tuple[str, ...] = METHODS,
    seeds: tuple[int, ...] = AUDIT_SEEDS,
) -> dict[str, Any]:
    output = {}
    labels = ("healthy", "outer", "inner")
    for method in methods:
        output[method] = {}
        for seed in seeds:
            rows = predictions.loc[
                (predictions["method"] == method) & (predictions["seed"] == seed)
            ]
            counts = rows["prediction"].value_counts().reindex(labels, fill_value=0)
            scores = rows["risk_envelope_score_beta_0_25"].to_numpy(dtype=float)
            confidence = rows["confidence"].to_numpy(dtype=float)
            output[method][str(int(seed))] = {
                "rows": len(rows),
                "model_folds": int(rows["fold_id"].nunique()),
                "unique_measurements": int(rows["row_index"].nunique()),
                "predicted_class_counts": {label: int(counts[label]) for label in labels},
                "predicted_class_distribution": {
                    label: float(counts[label] / len(rows)) for label in labels
                },
                "risk_envelope_score_quantiles": {
                    str(quantile): float(np.quantile(scores, quantile))
                    for quantile in (0.05, 0.25, 0.5, 0.75, 0.95)
                },
                "confidence_quantiles": {
                    str(quantile): float(np.quantile(confidence, quantile))
                    for quantile in (0.05, 0.25, 0.5, 0.75, 0.95)
                },
                "accuracy_reported": False,
            }
    return output


def release_target_outcomes(
    predictions: pd.DataFrame,
    fit_records: list[dict[str, Any]],
    model_folds: tuple[PaderbornModelFold, ...],
    full_frame: pd.DataFrame,
    *,
    methods: tuple[str, ...] = METHODS,
    seeds: tuple[int, ...] = AUDIT_SEEDS,
) -> tuple[pd.DataFrame, list[dict[str, Any]]]:
    """Attach truth and calculate metrics only after every frozen fit is complete."""

    if {"truth", "correct"} & set(predictions):
        raise ValueError("target outcomes were attached before the release boundary")
    forbidden_fit_fields = {
        "accuracy",
        "macro_f1",
        "multiclass_brier",
        "aurc",
        "risk_at_50pct",
    }
    if any(forbidden_fit_fields & set(record) for record in fit_records):
        raise ValueError("target metrics were calculated before the release boundary")
    fold_by_id = {model_fold.fold.fold_id: model_fold for model_fold in model_folds}
    expected = {
        (method, int(seed), fold_id)
        for method in methods
        for seed in seeds
        for fold_id in fold_by_id
    }
    identities = [
        (str(record["method"]), int(record["seed"]), str(record["fold_id"]))
        for record in fit_records
    ]
    if len(identities) != len(set(identities)) or set(identities) != expected:
        raise ValueError("completed Paderborn fits differ from the frozen design")

    released = predictions.copy()
    row_indices = released["row_index"].to_numpy(dtype=np.int64)
    if len(full_frame) == 0 or (row_indices < 0).any() or (row_indices >= len(full_frame)).any():
        raise ValueError("Paderborn prediction row indices are out of bounds")
    released["truth"] = full_frame["truth"].astype(str).to_numpy()[row_indices]
    released["correct"] = released["prediction"] == released["truth"]

    fold_metrics = []
    for record, identity in zip(fit_records, identities, strict=True):
        method, seed, fold_id = identity
        model_fold = fold_by_id[fold_id]
        fold = model_fold.fold
        rows = released.loc[
            (released["method"] == method)
            & (released["seed"] == seed)
            & (released["fold_id"] == fold_id)
        ]
        if not np.array_equal(
            rows["row_index"].to_numpy(dtype=np.int64),
            model_fold.target_global_indices,
        ):
            raise ValueError("Paderborn target row order changed before outcome release")
        probabilities = rows[[f"probability_{label}" for label in fold.label_names]].to_numpy(
            dtype=float
        )
        label_index = {label: index for index, label in enumerate(fold.label_names)}
        predicted = rows["prediction"].map(label_index)
        if predicted.isna().any():
            raise ValueError("Paderborn prediction label changed before outcome release")
        metrics = _fold_metrics(
            fold,
            probabilities,
            predicted.to_numpy(dtype=np.int64),
            rows["risk_envelope_score_beta_0_25"].to_numpy(dtype=float),
            nuisance_representation_response=float(
                record["source_nuisance_representation_response"]
            ),
            fault_representation_response=float(record["source_fault_representation_response"]),
            nuisance_probability_response=float(record["source_nuisance_probability_response"]),
            fault_probability_response=float(record["source_fault_probability_response"]),
        )
        metrics.update(record)
        fold_metrics.append(metrics)
    return released, fold_metrics


def _ece(truth: np.ndarray, prediction: np.ndarray, confidence: np.ndarray) -> float:
    bin_ids = np.minimum((confidence * 10).astype(int), 9)
    correct = prediction == truth
    value = 0.0
    for bin_id in range(10):
        mask = bin_ids == bin_id
        if mask.any():
            value += float(mask.mean()) * abs(
                float(correct[mask].mean()) - float(confidence[mask].mean())
            )
    return value


def _seed_summary(
    predictions: pd.DataFrame,
    fold_metrics: list[dict[str, Any]],
    *,
    method: str,
    seed: int,
) -> dict[str, Any]:
    rows = predictions.loc[(predictions["method"] == method) & (predictions["seed"] == seed)]
    labels = ("healthy", "outer", "inner")
    label_index = {label: index for index, label in enumerate(labels)}
    truth = rows["truth"].map(label_index).to_numpy(dtype=np.int64)
    prediction = rows["prediction"].map(label_index).to_numpy(dtype=np.int64)
    probabilities = rows[[f"probability_{label}" for label in labels]].to_numpy(dtype=float)
    recalls = [float((prediction[truth == index] == index).mean()) for index in range(3)]
    confusion = np.zeros((len(labels), len(labels)), dtype=np.int64)
    np.add.at(confusion, (truth, prediction), 1)
    setting_f1 = {}
    for setting, group in rows.groupby("setting_code", sort=True, observed=True):
        setting_truth = group["truth"].map(label_index).to_numpy(dtype=np.int64)
        setting_prediction = group["prediction"].map(label_index).to_numpy(dtype=np.int64)
        setting_f1[str(setting)] = _macro_f1(setting_truth, setting_prediction, 3)
    metric_rows = [row for row in fold_metrics if row["method"] == method and row["seed"] == seed]
    parameter_counts = {int(row["parameter_count_network_only"]) for row in metric_rows}
    if len(parameter_counts) != 1:
        raise ValueError("Paderborn network parameter count changes across folds")
    peak_memory = [
        int(row["peak_memory_bytes"]) for row in metric_rows if row["peak_memory_bytes"] is not None
    ]
    damage_origin_strata = {}
    for origin, group in rows.groupby("damage_origin", sort=True, observed=True):
        origin_truth = group["truth"].map(label_index).to_numpy(dtype=np.int64)
        origin_prediction = group["prediction"].map(label_index).to_numpy(dtype=np.int64)
        origin_recalls = {}
        for label, index in label_index.items():
            mask = origin_truth == index
            origin_recalls[label] = (
                float((origin_prediction[mask] == index).mean()) if mask.any() else None
            )
        damage_origin_strata[str(origin)] = {
            "rows": len(group),
            "accuracy": float((origin_prediction == origin_truth).mean()),
            "three_class_macro_f1": _macro_f1(origin_truth, origin_prediction, len(labels)),
            "per_class_recall": origin_recalls,
        }
    return {
        "pooled_macro_f1": _macro_f1(truth, prediction, 3),
        "pooled_balanced_accuracy": float(np.mean(recalls)),
        "pooled_multiclass_brier": _multiclass_brier(truth, probabilities, 3),
        "pooled_ece_10_bin": _ece(truth, prediction, probabilities.max(axis=1)),
        "per_class_recall": dict(zip(labels, recalls, strict=True)),
        "confusion_matrix": {
            "labels": list(labels),
            "rows_truth_columns_prediction": confusion.tolist(),
        },
        "damage_origin_strata": damage_origin_strata,
        "setting_macro_f1": setting_f1,
        "minimum_setting_macro_f1": float(min(setting_f1.values())),
        "minimum_identity_setting_fold_macro_f1": float(
            min(row["macro_f1"] for row in metric_rows)
        ),
        "mean_source_representation_response_ratio": float(
            np.mean([row["source_representation_response_ratio"] for row in metric_rows])
        ),
        "mean_source_probability_response_ratio": float(
            np.mean([row["source_probability_response_ratio"] for row in metric_rows])
        ),
        "total_fit_seconds": float(sum(row["fit_seconds"] for row in metric_rows)),
        "total_inference_seconds": float(sum(row["inference_seconds"] for row in metric_rows)),
        "parameter_count_network_only": next(iter(parameter_counts)),
        "maximum_peak_memory_bytes": max(peak_memory) if peak_memory else 0,
    }


def _artifact(path: Path, **counts: int) -> dict[str, Any]:
    return {
        "path": path.name,
        **counts,
        "bytes": path.stat().st_size,
        "sha256": _sha256(path),
    }


def run_evaluation(
    *,
    prospective_seal: Path,
    expected_seal_sha256: str,
    execution_seal: Path,
    expected_execution_seal_sha256: str,
    feature_metrics: Path,
    expected_feature_metrics_sha256: str,
    expected_manifest: Path,
    expected_manifest_sha256: str,
    output_directory: Path,
    device: str = "cuda:0",
    root: Path | None = None,
) -> dict[str, Any]:
    root = (root or project_root()).resolve()
    prospective_seal = prospective_seal.resolve(strict=True)
    seal = _load_and_validate_seal(prospective_seal, expected_seal_sha256)
    authorization = validate_execution_authorization(
        root,
        seal,
        prospective_seal=prospective_seal,
        expected_prospective_seal_sha256=expected_seal_sha256,
        execution_seal=execution_seal,
        expected_execution_seal_sha256=expected_execution_seal_sha256,
        feature_metrics=feature_metrics,
        expected_feature_metrics_sha256=expected_feature_metrics_sha256,
        expected_manifest=expected_manifest,
        expected_manifest_sha256=expected_manifest_sha256,
    )
    configurations, candidate_ids, development_hashes = load_sealed_configurations(root, seal)
    feature_metrics = feature_metrics.resolve(strict=True)
    (
        feature_frame,
        compound_frame,
        feature_record,
        feature_path,
        full_feature_path,
    ) = _load_feature_frame(
        feature_metrics,
        expected_metrics_sha256=expected_feature_metrics_sha256,
        expected_seal_sha256=expected_seal_sha256,
    )
    model_folds = build_paderborn_model_folds(feature_frame)
    if device.startswith("cuda"):
        if not torch.cuda.is_available():
            raise RuntimeError("formal Paderborn evaluation requires validated CUDA")
        torch.cuda.init()

    fit_records = []
    prediction_frames = []
    compound_prediction_frames = []
    traces = []
    for method in METHODS:
        for seed in AUDIT_SEEDS:
            for model_fold in model_folds:
                fit_record, predictions, compound_predictions, trace = _fit_one(
                    model_fold,
                    configurations[method],
                    method=method,
                    seed=int(seed),
                    device=device,
                    full_frame=feature_frame,
                    compound_frame=compound_frame,
                    candidate_identifier=candidate_ids[method],
                )
                fit_records.append(fit_record)
                prediction_frames.append(predictions)
                compound_prediction_frames.append(compound_predictions)
                traces.append(trace)
                print(
                    json.dumps(fit_progress_event(fit_record)),
                    flush=True,
                )
    predictions = pd.concat(prediction_frames, ignore_index=True, sort=False)
    compound_predictions = pd.concat(compound_prediction_frames, ignore_index=True, sort=False)
    representation_dimensions = {
        method: configuration.representation_dim for method, configuration in configurations.items()
    }
    topology = validate_prediction_topology(
        predictions,
        row_count=len(feature_frame),
        methods=METHODS,
        seeds=AUDIT_SEEDS,
        expected_folds=len(model_folds),
        expected_representation_dimensions=representation_dimensions,
    )
    compound_topology = validate_compound_prediction_topology(
        compound_predictions,
        compound_frame,
        fold_ids=tuple(model_fold.fold.fold_id for model_fold in model_folds),
        methods=METHODS,
        seeds=AUDIT_SEEDS,
        expected_representation_dimensions=representation_dimensions,
    )
    expected_models = len(METHODS) * len(AUDIT_SEEDS) * len(model_folds)
    if len(fit_records) != expected_models or len(traces) != expected_models:
        raise AssertionError("Paderborn model count differs from the frozen design")
    predictions, fold_metrics = release_target_outcomes(
        predictions,
        fit_records,
        model_folds,
        feature_frame,
        methods=METHODS,
        seeds=AUDIT_SEEDS,
    )
    seed_summaries = {
        method: {
            str(int(seed)): _seed_summary(predictions, fold_metrics, method=method, seed=int(seed))
            for seed in AUDIT_SEEDS
        }
        for method in METHODS
    }
    summary_fields = (
        "pooled_macro_f1",
        "pooled_balanced_accuracy",
        "pooled_multiclass_brier",
        "pooled_ece_10_bin",
        "minimum_setting_macro_f1",
        "minimum_identity_setting_fold_macro_f1",
        "mean_source_representation_response_ratio",
        "mean_source_probability_response_ratio",
        "total_fit_seconds",
        "total_inference_seconds",
        "parameter_count_network_only",
        "maximum_peak_memory_bytes",
    )
    method_summaries = {
        method: {
            field: _numeric_summary(
                [seed_summaries[method][str(int(seed))][field] for seed in AUDIT_SEEDS]
            )
            for field in summary_fields
        }
        for method in METHODS
    }
    paired = {
        f"{method}_minus_erm": {
            field: _numeric_summary(
                [
                    seed_summaries[method][str(int(seed))][field]
                    - seed_summaries["erm"][str(int(seed))][field]
                    for seed in AUDIT_SEEDS
                ]
            )
            for field in summary_fields
            if field not in {"total_fit_seconds", "total_inference_seconds"}
        }
        for method in METHODS
        if method != "erm"
    }

    output_directory = output_directory.resolve()
    output_directory.mkdir(parents=True, exist_ok=True)
    predictions_path = output_directory / "predictions.parquet"
    compound_predictions_path = output_directory / "compound_predictions.parquet"
    folds_path = output_directory / "fold_metrics.json"
    traces_path = output_directory / "training_traces.json"
    predictions.to_parquet(predictions_path, index=False)
    compound_predictions.to_parquet(compound_predictions_path, index=False)
    folds_path.write_text(
        json.dumps(fold_metrics, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    traces_path.write_text(
        json.dumps(traces, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    metrics = {
        "run_version": RUN_VERSION,
        "generated_at": datetime.now(UTC).isoformat(),
        "status": "one_shot_paderborn_prospective_evaluation_complete",
        "input": {
            "prospective_seal": str(prospective_seal),
            "prospective_seal_sha256": expected_seal_sha256,
            "execution_seal": str(execution_seal.resolve()),
            "execution_seal_sha256": authorization["execution_seal"],
            "feature_metrics": str(feature_metrics),
            "feature_metrics_sha256": expected_feature_metrics_sha256,
            "expected_manifest": str(expected_manifest.resolve()),
            "expected_manifest_sha256": authorization["expected_manifest"],
            "frozen_protocol_sha256": authorization["protocol_document"],
            "split_manifest_sha256": authorization["split_manifest"],
            "model_fold_manifest_sha256": authorization["model_fold_manifest"],
            "primary_feature_matrix": str(feature_path),
            "primary_feature_matrix_sha256": _sha256(feature_path),
            "full_feature_matrix": str(full_feature_path),
            "full_feature_matrix_sha256": _sha256(full_feature_path),
            **development_hashes,
        },
        "configuration": {
            "methods": list(METHODS),
            "candidate_ids": candidate_ids,
            "method_configurations": {
                method: asdict(configuration) for method, configuration in configurations.items()
            },
            "seeds": list(AUDIT_SEEDS),
            "outer_folds": len(model_folds),
            "device": device,
            "target_access": "P0",
        },
        "integrity": {
            "topology": topology,
            "compound_topology": compound_topology,
            "models": expected_models,
            "quarantine_excluded_before_training": True,
            "target_used_for_training_or_selection": False,
            "feature_access_attestation": feature_record["access_attestation"],
        },
        "seed_summaries": seed_summaries,
        "method_summaries": method_summaries,
        "paired_method_minus_erm": paired,
        "compound_diagnostics": _compound_diagnostics(
            compound_predictions, methods=METHODS, seeds=AUDIT_SEEDS
        ),
        "artifacts": {
            "predictions": _artifact(predictions_path, rows=len(predictions)),
            "compound_predictions": _artifact(
                compound_predictions_path, rows=len(compound_predictions)
            ),
            "fold_metrics": _artifact(folds_path, folds=len(fold_metrics)),
            "training_traces": _artifact(traces_path, models=len(traces)),
        },
        "access_attestation": {
            "paderborn_model_outcomes_emitted_only_after_all_fits": True,
            "configuration_reselection_performed": False,
            "target_labels_used_for_fitting_selection_or_stopping": False,
            "quarantine_rows_exposed_to_trainer": False,
            "compound_forced_ground_truth_defined": False,
            "compound_accuracy_computed": False,
        },
    }
    metrics_path = output_directory / "metrics.json"
    metrics_path.write_text(
        json.dumps(metrics, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return metrics


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--prospective-seal", type=Path, required=True)
    parser.add_argument("--prospective-seal-sha256", required=True)
    parser.add_argument("--execution-seal", type=Path, required=True)
    parser.add_argument("--execution-seal-sha256", required=True)
    parser.add_argument("--feature-metrics", type=Path, required=True)
    parser.add_argument("--feature-metrics-sha256", required=True)
    parser.add_argument("--expected-manifest", type=Path, required=True)
    parser.add_argument("--expected-manifest-sha256", required=True)
    parser.add_argument("--output-directory", type=Path, required=True)
    parser.add_argument("--device", default="cuda:0")
    args = parser.parse_args()
    result = run_evaluation(
        prospective_seal=args.prospective_seal,
        expected_seal_sha256=args.prospective_seal_sha256,
        execution_seal=args.execution_seal,
        expected_execution_seal_sha256=args.execution_seal_sha256,
        feature_metrics=args.feature_metrics,
        expected_feature_metrics_sha256=args.feature_metrics_sha256,
        expected_manifest=args.expected_manifest,
        expected_manifest_sha256=args.expected_manifest_sha256,
        output_directory=args.output_directory,
        device=args.device,
    )
    print(json.dumps(result["integrity"], ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
