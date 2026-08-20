"""Run sealed source-OOF selective evaluation on prospective Paderborn outputs."""

from __future__ import annotations

import argparse
import hashlib
import json
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import torch

from smartvalve.config import project_root
from smartvalve.experiments.cranfield_causal_audit import AUDIT_SEEDS
from smartvalve.experiments.inner_splits import build_inner_splits
from smartvalve.experiments.paderborn_domain import build_paderborn_model_folds
from smartvalve.experiments.paderborn_evaluation import (
    _load_feature_frame,
    _resolve_sealed_artifact,
    load_sealed_configurations,
)
from smartvalve.experiments.paderborn_structure_probe import _load_and_validate_seal
from smartvalve.experiments.selective_evaluation import (
    ENSEMBLE_SCORE_COLUMNS,
    INDIVIDUAL_SCORE_COLUMNS,
    _active_columns,
    _policy_from_record,
    analyze_ensemble_predictions,
    analyze_individual_predictions,
)
from smartvalve.experiments.selective_expected_manifest import ENSEMBLE_SEED
from smartvalve.experiments.selective_prediction_run import (
    METHODS,
    _artifact,
    _headline_summary,
    _inner_prediction,
)
from smartvalve.experiments.selective_scores import (
    energy_uncertainty,
    ensemble_jensen_shannon,
    maximum_softmax_uncertainty,
    negative_max_logit,
    normalized_predictive_entropy,
    pnorm_normalized_max_logit,
)
from smartvalve.experiments.source_selective import apply_score_policy

RUN_VERSION = "paderborn-sealed-source-oof-selective-0.2.0"
EXPECTED_MANIFEST_VERSION = "paderborn-selective-expected-key-manifest-0.2.0"
BASE_VALIDATION_STATUS = "passed_against_sealed_metadata_only_paderborn_manifest"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _json_write(path: Path, value: Any) -> None:
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n",
        encoding="utf-8",
    )


def validate_execution_authorization(
    root: Path,
    seal: dict[str, Any],
    *,
    expected_manifest: Path,
    expected_manifest_sha256: str,
    execution_seal: Path,
    execution_seal_sha256: str,
    base_output_directory: Path,
    base_validation: Path,
    base_validation_sha256: str,
    prospective_seal_sha256: str,
) -> dict[str, str]:
    """Require sealed topology and an independently validated base evaluation."""

    execution_seal = execution_seal.resolve(strict=True)
    if _sha256(execution_seal) != execution_seal_sha256:
        raise ValueError("Paderborn D2 execution-seal hash changed")
    amended_seal = _read_json(execution_seal)
    if (
        amended_seal.get("schema_version") != "smartvalve-paderborn-d2-execution-seal-0.1.0"
        or amended_seal.get("status") != "sealed_after_features_before_paderborn_model_outcomes"
        or amended_seal.get("decision") != seal.get("decision")
        or amended_seal.get("statistics") != seal.get("statistics")
        or amended_seal.get("artifacts", {}).get("original_prospective_seal", {}).get("sha256")
        != prospective_seal_sha256
    ):
        raise ValueError("Paderborn D2 execution seal changed the original decision")
    expected_manifest = expected_manifest.resolve(strict=True)
    if _sha256(expected_manifest) != expected_manifest_sha256:
        raise ValueError("Paderborn selective expected-manifest hash changed")
    if (
        _resolve_sealed_artifact(root, amended_seal, "amended_selective_expected_manifest")
        != expected_manifest
    ):
        raise ValueError("Paderborn seal references another selective manifest")
    manifest = _read_json(expected_manifest)
    if manifest.get("manifest_version") != EXPECTED_MANIFEST_VERSION:
        raise ValueError("Paderborn selective expected-manifest version changed")
    manifest_input = manifest.get("input", {})
    protocol = _resolve_sealed_artifact(root, amended_seal, "execution_amendment_protocol")
    base_manifest = _resolve_sealed_artifact(root, amended_seal, "amended_expected_manifest")
    if (
        Path(str(manifest_input.get("protocol_document", ""))).resolve() != protocol
        or manifest_input.get("protocol_document_sha256") != _sha256(protocol)
        or Path(str(manifest_input.get("base_expected_manifest", ""))).resolve() != base_manifest
        or manifest_input.get("base_expected_manifest_sha256") != _sha256(base_manifest)
        or manifest_input.get("signal_features_used_to_define_topology") is not False
        or manifest_input.get("model_outcomes_inspected_before_manifest") is not False
    ):
        raise ValueError("Paderborn selective manifest input drift")

    base_validation = base_validation.resolve(strict=True)
    if _sha256(base_validation) != base_validation_sha256:
        raise ValueError("Paderborn base validation hash changed")
    validation = _read_json(base_validation)
    if validation.get("status") != BASE_VALIDATION_STATUS:
        raise ValueError("Paderborn base artifact validation did not pass")
    if validation.get("expected_manifest", {}).get("sha256") != _sha256(base_manifest):
        raise ValueError("Paderborn base validation used another manifest")
    base_output_directory = base_output_directory.resolve(strict=True)
    metrics_path = (base_output_directory / "metrics.json").resolve(strict=True)
    if validation.get("paderborn_metrics", {}).get("sha256") != _sha256(metrics_path):
        raise ValueError("Paderborn base metrics changed after validation")
    metrics = _read_json(metrics_path)
    if metrics["input"].get("prospective_seal_sha256") != prospective_seal_sha256:
        raise ValueError("Paderborn base metrics reference another seal")
    if metrics["input"].get("execution_seal_sha256") != execution_seal_sha256:
        raise ValueError("Paderborn base metrics reference another execution seal")
    for name in ("predictions", "compound_predictions"):
        record = metrics["artifacts"][name]
        path = (base_output_directory / str(record["path"])).resolve(strict=True)
        if (
            path.stat().st_size != int(record["bytes"])
            or _sha256(path) != record["sha256"]
            or validation.get("artifact_hashes", {}).get(name) != record["sha256"]
        ):
            raise ValueError(f"Paderborn validated base artifact changed: {name}")
    return {
        "expected_manifest": expected_manifest_sha256,
        "protocol_document": _sha256(protocol),
        "base_expected_manifest": _sha256(base_manifest),
        "base_validation": base_validation_sha256,
        "base_metrics": _sha256(metrics_path),
        "execution_seal": execution_seal_sha256,
        "base_predictions": str(
            (base_output_directory / metrics["artifacts"]["predictions"]["path"]).resolve(
                strict=True
            )
        ),
        "base_compound_predictions": str(
            (base_output_directory / metrics["artifacts"]["compound_predictions"]["path"]).resolve(
                strict=True
            )
        ),
    }


def add_unlabeled_scores(records: pd.DataFrame) -> pd.DataFrame:
    """Compute frozen uncertainty scores without requiring a compound outcome."""

    required = {
        "dataset",
        "method",
        "seed",
        "fold_id",
        "row_index",
        "prediction",
        "robust_class_support_distance",
    }
    missing = required - set(records)
    if missing:
        raise ValueError(f"compound predictions are missing columns: {sorted(missing)}")
    if {"truth", "correct"} & set(records):
        raise ValueError("compound predictions define a forced outcome")
    output = []
    for _, group in records.groupby(
        ["dataset", "method", "seed", "fold_id"], sort=True, observed=True
    ):
        group = group.copy()
        probability_columns = _active_columns(group, "probability_")
        logit_columns = _active_columns(group, "logit_")
        if [column.removeprefix("probability_") for column in probability_columns] != [
            column.removeprefix("logit_") for column in logit_columns
        ]:
            raise ValueError("compound probability/logit labels differ")
        probabilities = group[probability_columns].to_numpy(dtype=float)
        logits = group[logit_columns].to_numpy(dtype=float)
        distance = group["robust_class_support_distance"].to_numpy(dtype=float)
        if np.any(distance < 0) or not np.isfinite(distance).all():
            raise ValueError("compound support distance is invalid")
        group["score_msp"] = maximum_softmax_uncertainty(probabilities)
        group["score_predictive_entropy"] = normalized_predictive_entropy(probabilities)
        group["score_energy_t1"] = energy_uncertainty(logits)
        group["score_negative_max_logit"] = negative_max_logit(logits)
        group["score_pnorm_max_logit_p2"] = pnorm_normalized_max_logit(logits, order=2.0)
        group["score_robust_class_support"] = distance
        output.append(group)
    return pd.concat(output, ignore_index=True, sort=False)


def build_unlabeled_ensemble_predictions(
    records: pd.DataFrame,
    *,
    expected_seeds: tuple[int, ...] = AUDIT_SEEDS,
) -> pd.DataFrame:
    """Average compound members while retaining only unlabeled diagnostics."""

    identity_columns = [
        "row_index",
        "filename",
        "bearing_code",
        "setting_code",
        "measurement_index",
    ]
    output = []
    for _, group in records.groupby(["dataset", "method", "fold_id"], sort=True, observed=True):
        if tuple(sorted(int(value) for value in group["seed"].unique())) != tuple(
            sorted(expected_seeds)
        ):
            raise ValueError("compound ensemble seed set changed")
        probability_columns = _active_columns(group, "probability_")
        members = []
        distances = []
        reference = None
        for seed in sorted(expected_seeds):
            member = group.loc[group["seed"] == seed].sort_values("row_index", kind="stable")
            if reference is None:
                reference = member
            elif (
                not member[identity_columns]
                .reset_index(drop=True)
                .equals(reference[identity_columns].reset_index(drop=True))
            ):
                raise ValueError("compound ensemble row identities do not align")
            members.append(member[probability_columns].to_numpy(dtype=float))
            distances.append(member["robust_class_support_distance"].to_numpy(dtype=float))
        if reference is None:
            raise AssertionError("compound ensemble unexpectedly has no members")
        member_probabilities = np.stack(members)
        probabilities = member_probabilities.mean(axis=0)
        mean_distance = np.stack(distances).mean(axis=0)
        labels = [column.removeprefix("probability_") for column in probability_columns]
        ensemble = reference.loc[
            :,
            [
                column
                for column in reference
                if not column.startswith(("probability_", "logit_", "representation_"))
                and column
                not in {
                    "seed",
                    "prediction",
                    "confidence",
                    "robust_class_support_distance",
                    *INDIVIDUAL_SCORE_COLUMNS.values(),
                }
            ],
        ].copy()
        ensemble.insert(2, "seed", ENSEMBLE_SEED)
        ensemble["ensemble_size"] = len(expected_seeds)
        ensemble["prediction"] = [labels[index] for index in probabilities.argmax(axis=1)]
        ensemble["confidence"] = probabilities.max(axis=1)
        ensemble["robust_class_support_distance"] = mean_distance
        for index, column in enumerate(probability_columns):
            ensemble[column] = probabilities[:, index]
        ensemble["score_msp"] = maximum_softmax_uncertainty(probabilities)
        ensemble["score_predictive_entropy"] = normalized_predictive_entropy(probabilities)
        ensemble["score_ensemble_jensen_shannon"] = ensemble_jensen_shannon(member_probabilities)
        ensemble["score_robust_class_support"] = mean_distance
        output.append(ensemble)
    return pd.concat(output, ignore_index=True, sort=False)


def evaluate_compound_policies(
    compound: pd.DataFrame,
    policies: list[dict[str, Any]],
    beta_selections: list[dict[str, Any]],
    *,
    ensemble: bool,
) -> tuple[list[dict[str, Any]], pd.DataFrame]:
    """Apply source-frozen policies and report no compound accuracy."""

    score_columns = ENSEMBLE_SCORE_COLUMNS if ensemble else INDIVIDUAL_SCORE_COLUMNS
    envelope_name = "ensemble_risk_envelope" if ensemble else "risk_envelope"
    beta_index = {
        (str(row["method"]), int(row["seed"]), str(row["fold_id"])): row for row in beta_selections
    }
    policy_index: dict[tuple[str, int, str], list[dict[str, Any]]] = {}
    for policy in policies:
        key = (
            str(policy["method"]),
            int(policy["seed"]),
            str(policy["fold_id"]),
        )
        policy_index.setdefault(key, []).append(policy)
    metric_rows = []
    decision_frames = []
    for (method, seed, fold_id), group in compound.groupby(
        ["method", "seed", "fold_id"], sort=True, observed=True
    ):
        key = (str(method), int(seed), str(fold_id))
        if key not in beta_index or key not in policy_index:
            raise ValueError("compound group has no source-frozen policy")
        beta = float(beta_index[key]["beta"])
        score_values = {
            name: group[column].to_numpy(dtype=float) for name, column in score_columns.items()
        }
        score_values[envelope_name] = group["score_msp"].to_numpy(dtype=float) + beta * group[
            "score_robust_class_support"
        ].to_numpy(dtype=float)
        for record in policy_index[key]:
            policy = _policy_from_record(record)
            scores = score_values[policy.score_name]
            accepted = apply_score_policy(policy, scores)
            counts = group["prediction"].value_counts()
            accepted_counts = group.loc[accepted, "prediction"].value_counts()
            metric_rows.append(
                {
                    "dataset": "paderborn_compound",
                    "method": str(method),
                    "seed": int(seed),
                    "fold_id": str(fold_id),
                    "score_name": policy.score_name,
                    "nominal_source_coverage": policy.nominal_source_coverage,
                    "source_threshold": policy.threshold,
                    "source_coverage": policy.source_coverage,
                    "rows": len(group),
                    "accepted": int(accepted.sum()),
                    "coverage": float(accepted.mean()),
                    "predicted_class_counts": {
                        label: int(counts.get(label, 0)) for label in ("healthy", "outer", "inner")
                    },
                    "accepted_predicted_class_counts": {
                        label: int(accepted_counts.get(label, 0))
                        for label in ("healthy", "outer", "inner")
                    },
                    "score_quantiles": {
                        str(quantile): float(np.quantile(scores, quantile))
                        for quantile in (0.05, 0.25, 0.5, 0.75, 0.95)
                    },
                    "risk_envelope_beta": beta,
                    "accuracy_reported": False,
                }
            )
            decisions = group.loc[
                :,
                [
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
                ],
            ].copy()
            decisions["score_name"] = policy.score_name
            decisions["nominal_source_coverage"] = policy.nominal_source_coverage
            decisions["score"] = scores
            decisions["threshold"] = policy.threshold
            decisions["accepted"] = accepted
            decisions["risk_envelope_beta"] = beta
            decision_frames.append(decisions)
    if len(policy_index) != compound.groupby(["method", "seed", "fold_id"], observed=True).ngroups:
        raise ValueError("source policy groups and compound groups differ")
    return metric_rows, pd.concat(decision_frames, ignore_index=True, sort=False)


def _enrich_primary_decisions(decisions: pd.DataFrame, predictions: pd.DataFrame) -> pd.DataFrame:
    keys = ["dataset", "method", "seed", "fold_id", "row_index"]
    metadata = predictions.loc[
        :, [*keys, "bearing_code", "setting_code", "measurement_index"]
    ].drop_duplicates(keys)
    enriched = decisions.merge(metadata, on=keys, how="left", validate="many_to_one")
    if enriched[["bearing_code", "setting_code", "measurement_index"]].isna().any().any():
        raise ValueError("selective decisions lost Paderborn physical metadata")
    return enriched


def run_selective_evaluation(
    *,
    prospective_seal: Path,
    expected_seal_sha256: str,
    execution_seal: Path,
    expected_execution_seal_sha256: str,
    feature_metrics: Path,
    expected_feature_metrics_sha256: str,
    base_output_directory: Path,
    base_validation: Path,
    base_validation_sha256: str,
    expected_manifest: Path,
    expected_manifest_sha256: str,
    output_directory: Path,
    device: str = "cuda:0",
    root: Path | None = None,
) -> dict[str, Any]:
    root = (root or project_root()).resolve()
    seal = _load_and_validate_seal(prospective_seal.resolve(strict=True), expected_seal_sha256)
    authorization = validate_execution_authorization(
        root,
        seal,
        expected_manifest=expected_manifest,
        expected_manifest_sha256=expected_manifest_sha256,
        execution_seal=execution_seal,
        execution_seal_sha256=expected_execution_seal_sha256,
        base_output_directory=base_output_directory,
        base_validation=base_validation,
        base_validation_sha256=base_validation_sha256,
        prospective_seal_sha256=expected_seal_sha256,
    )
    configurations, _, development_hashes = load_sealed_configurations(root, seal)
    feature_frame, _, _, _, _ = _load_feature_frame(
        feature_metrics.resolve(strict=True),
        expected_metrics_sha256=expected_feature_metrics_sha256,
        expected_seal_sha256=expected_seal_sha256,
    )
    model_folds = build_paderborn_model_folds(feature_frame)
    target = pd.read_parquet(authorization["base_predictions"])
    compound = pd.read_parquet(authorization["base_compound_predictions"])
    target = target.loc[target["method"].isin(METHODS)].copy()
    compound = compound.loc[compound["method"].isin(METHODS)].copy()
    if device.startswith("cuda"):
        if not torch.cuda.is_available():
            raise RuntimeError("formal Paderborn selective evaluation requires CUDA")
        torch.cuda.init()

    source_frames = []
    traces = []
    for method in METHODS:
        for seed in AUDIT_SEEDS:
            for model_fold in model_folds:
                fold = model_fold.fold
                for split in build_inner_splits(fold):
                    records, trace = _inner_prediction(
                        fold,
                        split,
                        configurations[method],
                        method=method,
                        seed=int(seed),
                        device=device,
                    )
                    source_frames.append(records)
                    traces.append(trace)
                    print(
                        json.dumps(
                            {
                                "event": "paderborn_selective_source_oof_fit_complete",
                                "method": method,
                                "seed": int(seed),
                                "fold_id": fold.fold_id,
                                "inner_split_id": split.split_id,
                                "fit_seconds": trace["fit_seconds"],
                                "model_state_sha256": trace["model_state_sha256"],
                            }
                        ),
                        flush=True,
                    )
    source = pd.concat(source_frames, ignore_index=True, sort=False)
    individual = analyze_individual_predictions(source, target)
    ensemble_analysis = analyze_ensemble_predictions(
        source, target, expected_seeds=tuple(int(seed) for seed in AUDIT_SEEDS)
    )
    compound_scored = add_unlabeled_scores(compound)
    compound_ensemble = build_unlabeled_ensemble_predictions(compound_scored)
    individual_compound_metrics, individual_compound_decisions = evaluate_compound_policies(
        compound_scored,
        individual["policies"],
        individual["beta_selections"],
        ensemble=False,
    )
    ensemble_compound_metrics, ensemble_compound_decisions = evaluate_compound_policies(
        compound_ensemble,
        ensemble_analysis["policies"],
        ensemble_analysis["beta_selections"],
        ensemble=True,
    )
    policies = [*individual["policies"], *ensemble_analysis["policies"]]
    beta_selections = [
        *individual["beta_selections"],
        *ensemble_analysis["beta_selections"],
    ]
    policy_metrics = [
        *individual["policy_metrics"],
        *ensemble_analysis["policy_metrics"],
    ]
    ranking_metrics = [
        *individual["ranking_metrics"],
        *ensemble_analysis["ranking_metrics"],
    ]
    target_all = pd.concat(
        [individual["target_scored"], ensemble_analysis["target_ensemble"]],
        ignore_index=True,
        sort=False,
    )
    decisions = _enrich_primary_decisions(
        pd.concat(
            [individual["decisions"], ensemble_analysis["decisions"]],
            ignore_index=True,
            sort=False,
        ),
        target_all,
    )
    compound_policy_metrics = [
        *individual_compound_metrics,
        *ensemble_compound_metrics,
    ]
    compound_decisions = pd.concat(
        [individual_compound_decisions, ensemble_compound_decisions],
        ignore_index=True,
        sort=False,
    )

    output_directory = output_directory.resolve()
    output_directory.mkdir(parents=True, exist_ok=True)
    artifacts: dict[str, tuple[Path, Any]] = {
        "source_oof_predictions": (
            output_directory / "source_oof_predictions.parquet",
            individual["source_scored"],
        ),
        "target_predictions": (
            output_directory / "target_predictions.parquet",
            individual["target_scored"],
        ),
        "compound_predictions": (
            output_directory / "compound_predictions.parquet",
            compound_scored,
        ),
        "source_oof_ensemble_predictions": (
            output_directory / "source_oof_ensemble_predictions.parquet",
            ensemble_analysis["source_ensemble"],
        ),
        "target_ensemble_predictions": (
            output_directory / "target_ensemble_predictions.parquet",
            ensemble_analysis["target_ensemble"],
        ),
        "compound_ensemble_predictions": (
            output_directory / "compound_ensemble_predictions.parquet",
            compound_ensemble,
        ),
        "selection_decisions": (
            output_directory / "selection_decisions.parquet",
            decisions,
        ),
        "compound_decisions": (
            output_directory / "compound_decisions.parquet",
            compound_decisions,
        ),
    }
    for path, frame in artifacts.values():
        frame.to_parquet(path, index=False)
    json_artifacts: dict[str, tuple[Path, list[dict[str, Any]]]] = {
        "policies": (output_directory / "policies.json", policies),
        "beta_selections": (
            output_directory / "beta_selections.json",
            beta_selections,
        ),
        "policy_metrics": (output_directory / "policy_metrics.json", policy_metrics),
        "ranking_metrics": (
            output_directory / "ranking_metrics.json",
            ranking_metrics,
        ),
        "compound_policy_metrics": (
            output_directory / "compound_policy_metrics.json",
            compound_policy_metrics,
        ),
        "training_traces": (output_directory / "training_traces.json", traces),
    }
    for path, values in json_artifacts.values():
        _json_write(path, values)
    artifact_records = {
        name: _artifact(path, rows=len(frame)) for name, (path, frame) in artifacts.items()
    }
    count_field = {
        "policies": "policies",
        "beta_selections": "selections",
        "policy_metrics": "evaluations",
        "ranking_metrics": "evaluations",
        "compound_policy_metrics": "evaluations",
        "training_traces": "models",
    }
    artifact_records.update(
        {
            name: _artifact(path, **{count_field[name]: len(values)})
            for name, (path, values) in json_artifacts.items()
        }
    )
    metrics = {
        "run_version": RUN_VERSION,
        "generated_at": datetime.now(UTC).isoformat(),
        "status": "sealed_paderborn_source_oof_selective_evaluation_complete",
        "input": {
            "prospective_seal": str(prospective_seal.resolve()),
            "prospective_seal_sha256": expected_seal_sha256,
            "execution_seal": str(execution_seal.resolve()),
            "execution_seal_sha256": authorization["execution_seal"],
            "feature_metrics": str(feature_metrics.resolve()),
            "feature_metrics_sha256": expected_feature_metrics_sha256,
            "base_output_directory": str(base_output_directory.resolve()),
            "base_validation": str(base_validation.resolve()),
            "base_validation_sha256": authorization["base_validation"],
            "base_metrics_sha256": authorization["base_metrics"],
            "expected_manifest": str(expected_manifest.resolve()),
            "expected_manifest_sha256": authorization["expected_manifest"],
            "protocol_document_sha256": authorization["protocol_document"],
            "base_expected_manifest_sha256": authorization["base_expected_manifest"],
            **development_hashes,
        },
        "configuration": {
            "methods": list(METHODS),
            "method_configurations": {method: asdict(configurations[method]) for method in METHODS},
            "seeds": list(AUDIT_SEEDS),
            "outer_folds": len(model_folds),
            "inner_partitions_per_fold": 3,
            "device": device,
            "target_access": "P0",
        },
        "headline_risk_envelope_summary": _headline_summary(policy_metrics),
        "compound_policy_metrics": compound_policy_metrics,
        "artifacts": artifact_records,
        "access_attestation": {
            "all_thresholds_and_betas_selected_from_source_oof_only": True,
            "target_coverage_used_for_threshold_selection": False,
            "target_labels_used_for_threshold_selection": False,
            "configuration_reselection_performed": False,
            "compound_forced_ground_truth_defined": False,
            "compound_accuracy_computed": False,
        },
    }
    _json_write(output_directory / "metrics.json", metrics)
    return metrics


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--prospective-seal", type=Path, required=True)
    parser.add_argument("--prospective-seal-sha256", required=True)
    parser.add_argument("--execution-seal", type=Path, required=True)
    parser.add_argument("--execution-seal-sha256", required=True)
    parser.add_argument("--feature-metrics", type=Path, required=True)
    parser.add_argument("--feature-metrics-sha256", required=True)
    parser.add_argument("--base-output-directory", type=Path, required=True)
    parser.add_argument("--base-validation", type=Path, required=True)
    parser.add_argument("--base-validation-sha256", required=True)
    parser.add_argument("--expected-manifest", type=Path, required=True)
    parser.add_argument("--expected-manifest-sha256", required=True)
    parser.add_argument("--output-directory", type=Path, required=True)
    parser.add_argument("--device", default="cuda:0")
    args = parser.parse_args()
    result = run_selective_evaluation(
        prospective_seal=args.prospective_seal,
        expected_seal_sha256=args.prospective_seal_sha256,
        execution_seal=args.execution_seal,
        expected_execution_seal_sha256=args.execution_seal_sha256,
        feature_metrics=args.feature_metrics,
        expected_feature_metrics_sha256=args.feature_metrics_sha256,
        base_output_directory=args.base_output_directory,
        base_validation=args.base_validation,
        base_validation_sha256=args.base_validation_sha256,
        expected_manifest=args.expected_manifest,
        expected_manifest_sha256=args.expected_manifest_sha256,
        output_directory=args.output_directory,
        device=args.device,
    )
    print(json.dumps(result["headline_risk_envelope_summary"], indent=2))


if __name__ == "__main__":
    main()
