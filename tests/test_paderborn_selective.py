from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import pytest

from smartvalve.experiments.dg_expected_manifest import canonical_key_record
from smartvalve.experiments.paderborn_expected_manifest import (
    run_manifest as run_base_manifest,
)
from smartvalve.experiments.paderborn_selective import (
    add_unlabeled_scores,
    build_unlabeled_ensemble_predictions,
    evaluate_compound_policies,
    validate_execution_authorization,
)
from smartvalve.experiments.paderborn_selective_artifact_validation import (
    ARTIFACT_KEY_SETS,
    EVALUATION_STATUS,
    PARQUET_ARTIFACTS,
    VALIDATION_STATUS,
    validate_paderborn_selective_artifacts,
)
from smartvalve.experiments.paderborn_selective_expected_manifest import (
    KEY_SCHEMAS,
    MANIFEST_VERSION,
)
from smartvalve.experiments.paderborn_selective_expected_manifest import (
    run_manifest as run_selective_manifest,
)
from smartvalve.experiments.selective_evaluation import (
    ENSEMBLE_SCORE_COLUMNS,
    INDIVIDUAL_SCORE_COLUMNS,
)
from smartvalve.experiments.selective_scores import (
    energy_uncertainty,
    negative_max_logit,
    normalized_predictive_entropy,
    pnorm_normalized_max_logit,
)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _compound_members() -> pd.DataFrame:
    rows = []
    for seed, shift in ((11, 0.0), (23, 0.1)):
        for row_index, base in ((2320, 0.8), (2321, 0.55)):
            probabilities = np.asarray([base - shift, 1.0 - base + shift, 0.0], dtype=float)
            logits = np.log(np.maximum(probabilities, 1e-6))
            rows.append(
                {
                    "dataset": "paderborn_compound",
                    "method": "erm",
                    "seed": seed,
                    "fold_id": "f0",
                    "row_index": row_index,
                    "filename": f"compound-{row_index}.mat",
                    "bearing_code": "KB23",
                    "setting_code": "N15_M07_F10",
                    "measurement_index": row_index - 2319,
                    "prediction": "healthy" if probabilities[0] >= probabilities[1] else "outer",
                    "confidence": float(probabilities.max()),
                    "robust_class_support_distance": float(row_index - 2319),
                    "probability_healthy": probabilities[0],
                    "probability_outer": probabilities[1],
                    "probability_inner": probabilities[2],
                    "logit_healthy": logits[0],
                    "logit_outer": logits[1],
                    "logit_inner": logits[2],
                }
            )
    return pd.DataFrame(rows)


def test_metadata_only_manifest_runners_freeze_exact_paderborn_topology(
    tmp_path: Path,
) -> None:
    protocol = tmp_path / "protocol.md"
    protocol.write_text(
        "Status: frozen v0.1\n1,080\n104,355\n259,200\n720\n347,850\n1,382,400\n",
        encoding="utf-8",
    )
    split = tmp_path / "split.json"
    model_folds = tmp_path / "model_folds.json"
    split.write_text(
        json.dumps(
            {
                "seal": {
                    "signal_features_used_to_define_partitions": False,
                    "model_outcomes_inspected": False,
                }
            }
        )
        + "\n",
        encoding="utf-8",
    )
    model_folds.write_text(
        json.dumps(
            {
                "signal_features_used_to_define_folds": False,
                "model_outcomes_inspected": False,
            }
        )
        + "\n",
        encoding="utf-8",
    )
    feature_amendment = tmp_path / "feature_amendment.json"
    feature_amendment.write_text(
        json.dumps({"status": "authorized_outcome_blind_bulk_feature_extraction"}),
        encoding="utf-8",
    )
    feature_validation = tmp_path / "feature_validation.json"
    feature_validation.write_text(
        json.dumps({"status": "passed_before_paderborn_model_outcome_access"}),
        encoding="utf-8",
    )
    base_manifest_path = tmp_path / "base_manifest.json"
    base_manifest = run_base_manifest(
        protocol_document=protocol,
        expected_protocol_sha256=_sha256(protocol),
        split_manifest=split,
        expected_split_manifest_sha256=_sha256(split),
        model_fold_manifest=model_folds,
        expected_model_fold_manifest_sha256=_sha256(model_folds),
        feature_contract_amendment=feature_amendment,
        expected_feature_contract_amendment_sha256=_sha256(feature_amendment),
        feature_validation=feature_validation,
        expected_feature_validation_sha256=_sha256(feature_validation),
        output=base_manifest_path,
    )
    manifest = run_selective_manifest(
        protocol_document=protocol,
        expected_protocol_sha256=_sha256(protocol),
        base_expected_manifest=base_manifest_path,
        expected_base_manifest_sha256=_sha256(base_manifest_path),
        output=tmp_path / "selective_manifest.json",
    )

    expected_counts = {
        "source_oof_predictions": 347_850,
        "target_predictions": 23_190,
        "compound_predictions": 57_600,
        "source_oof_ensemble_predictions": 69_570,
        "target_ensemble_predictions": 4_638,
        "compound_ensemble_predictions": 11_520,
        "policies": 5_760,
        "beta_selections": 288,
        "policy_metrics": 5_760,
        "ranking_metrics": 1_920,
        "selection_decisions": 556_560,
        "compound_decisions": 1_382_400,
        "compound_policy_metrics": 5_760,
        "training_models": 720,
    }
    assert {
        name: record["count"] for name, record in manifest["expected_key_sets"].items()
    } == expected_counts
    assert manifest["configuration"]["inner_partitions_per_fold"] == 3
    assert manifest["input"]["model_outcomes_inspected_before_manifest"] is False
    assert base_manifest["expected_key_sets"]["training_models"]["count"] == 1_080


def test_compound_scores_are_finite_and_cannot_accept_truth() -> None:
    records = _compound_members()

    scored = add_unlabeled_scores(records)

    assert set(INDIVIDUAL_SCORE_COLUMNS.values()).issubset(scored.columns)
    assert np.isfinite(scored[list(INDIVIDUAL_SCORE_COLUMNS.values())]).all().all()
    with pytest.raises(ValueError, match="forced outcome"):
        add_unlabeled_scores(records.assign(truth="compound"))


def test_compound_ensemble_requires_aligned_unlabeled_members() -> None:
    scored = add_unlabeled_scores(_compound_members())

    ensemble = build_unlabeled_ensemble_predictions(scored, expected_seeds=(11, 23))

    assert len(ensemble) == 2
    assert ensemble["seed"].eq(-1).all()
    assert not {"truth", "correct"}.intersection(ensemble.columns)
    assert np.isfinite(ensemble[list(ENSEMBLE_SCORE_COLUMNS.values())]).all().all()
    changed = scored.copy()
    changed.loc[(changed["seed"] == 23) & (changed["row_index"] == 2320), "filename"] = (
        "different.mat"
    )
    with pytest.raises(ValueError, match="identities do not align"):
        build_unlabeled_ensemble_predictions(changed, expected_seeds=(11, 23))


def test_compound_policy_application_never_reports_outcomes() -> None:
    compound = add_unlabeled_scores(_compound_members().loc[lambda frame: frame.seed == 11])
    policy = {
        "dataset": "paderborn",
        "method": "erm",
        "seed": 11,
        "fold_id": "f0",
        "score_name": "msp",
        "nominal_source_coverage": 0.5,
        "minimum_source_environment_coverage": 0.25,
        "threshold": 0.5,
        "source_coverage": 0.5,
        "source_selective_risk": 0.0,
        "source_worst_environment_risk": 0.0,
        "source_minimum_environment_coverage": 0.5,
        "source_accepted": 1,
        "risk_envelope_beta": None,
    }

    metrics, decisions = evaluate_compound_policies(
        compound,
        [policy],
        [{"method": "erm", "seed": 11, "fold_id": "f0", "beta": 0.25}],
        ensemble=False,
    )

    assert metrics[0]["accuracy_reported"] is False
    assert not {"accuracy", "selective_risk", "truth", "correct"}.intersection(metrics[0])
    assert not {"truth", "correct"}.intersection(decisions.columns)


def test_selective_authorization_requires_the_independently_validated_base(
    tmp_path: Path,
) -> None:
    root = tmp_path.resolve()
    protocol = root / "protocol.md"
    protocol.write_text("Status: frozen v0.1\n", encoding="utf-8")
    base_manifest = root / "base_manifest.json"
    base_manifest.write_text("{}\n", encoding="utf-8")
    expected_manifest = root / "selective_manifest.json"
    expected_manifest.write_text(
        json.dumps(
            {
                "manifest_version": MANIFEST_VERSION,
                "input": {
                    "protocol_document": str(protocol),
                    "protocol_document_sha256": _sha256(protocol),
                    "base_expected_manifest": str(base_manifest),
                    "base_expected_manifest_sha256": _sha256(base_manifest),
                    "signal_features_used_to_define_topology": False,
                    "model_outcomes_inspected_before_manifest": False,
                },
            }
        )
        + "\n",
        encoding="utf-8",
    )
    base_directory = root / "base"
    base_directory.mkdir()
    artifact_hashes = {}
    artifacts = {}
    for name in ("predictions", "compound_predictions"):
        path = base_directory / f"{name}.parquet"
        path.write_bytes(name.encode("utf-8"))
        artifact_hashes[name] = _sha256(path)
        artifacts[name] = {
            "path": path.name,
            "bytes": path.stat().st_size,
            "sha256": artifact_hashes[name],
        }
    original_seal = root / "original_seal.json"
    original_seal.write_text("{}\n", encoding="utf-8")
    seal_hash = _sha256(original_seal)

    def sealed(path: Path) -> dict[str, Any]:
        return {
            "path": path.relative_to(root).as_posix(),
            "bytes": path.stat().st_size,
            "sha256": _sha256(path),
        }

    execution_seal = root / "execution_seal.json"
    execution_seal.write_text(
        json.dumps(
            {
                "schema_version": "smartvalve-paderborn-d2-execution-seal-0.1.0",
                "status": "sealed_after_features_before_paderborn_model_outcomes",
                "decision": {},
                "statistics": {},
                "artifacts": {
                    "original_prospective_seal": sealed(original_seal),
                    "amended_selective_expected_manifest": sealed(expected_manifest),
                    "execution_amendment_protocol": sealed(protocol),
                    "amended_expected_manifest": sealed(base_manifest),
                },
            }
        )
        + "\n",
        encoding="utf-8",
    )
    execution_seal_hash = _sha256(execution_seal)
    base_metrics = base_directory / "metrics.json"
    base_metrics.write_text(
        json.dumps(
            {
                "input": {
                    "prospective_seal_sha256": seal_hash,
                    "execution_seal_sha256": execution_seal_hash,
                },
                "artifacts": artifacts,
            }
        )
        + "\n",
        encoding="utf-8",
    )
    base_validation = root / "base_validation.json"
    base_validation.write_text(
        json.dumps(
            {
                "status": "passed_against_sealed_metadata_only_paderborn_manifest",
                "expected_manifest": {"sha256": _sha256(base_manifest)},
                "paderborn_metrics": {"sha256": _sha256(base_metrics)},
                "artifact_hashes": artifact_hashes,
            }
        )
        + "\n",
        encoding="utf-8",
    )

    authorization = validate_execution_authorization(
        root,
        {"decision": {}, "statistics": {}},
        expected_manifest=expected_manifest,
        expected_manifest_sha256=_sha256(expected_manifest),
        execution_seal=execution_seal,
        execution_seal_sha256=execution_seal_hash,
        base_output_directory=base_directory,
        base_validation=base_validation,
        base_validation_sha256=_sha256(base_validation),
        prospective_seal_sha256=seal_hash,
    )

    assert authorization["base_metrics"] == _sha256(base_metrics)
    assert authorization["base_predictions"].endswith("predictions.parquet")


def _prediction(*, ensemble: bool, compound: bool) -> pd.DataFrame:
    dataset = "paderborn_compound" if compound else "paderborn"
    probabilities = np.asarray([[0.8, 0.1, 0.1]])
    logits = np.asarray([[2.0, 0.0, 0.0]])
    record: dict[str, Any] = {
        "dataset": dataset,
        "method": "erm",
        "seed": -1 if ensemble else 11,
        "fold_id": "f0",
        "row_index": 2320 if compound else 0,
        "prediction": "healthy",
        "confidence": 0.8,
        "robust_class_support_distance": 0.2,
        "probability_healthy": 0.8,
        "probability_outer": 0.1,
        "probability_inner": 0.1,
        "score_msp": 0.2,
        "score_predictive_entropy": float(normalized_predictive_entropy(probabilities)[0]),
        "score_robust_class_support": 0.2,
    }
    if ensemble:
        record["ensemble_size"] = 2
        record["score_ensemble_jensen_shannon"] = 0.0
    else:
        record.update(
            {
                "logit_healthy": 2.0,
                "logit_outer": 0.0,
                "logit_inner": 0.0,
                "score_energy_t1": float(energy_uncertainty(logits)[0]),
                "score_negative_max_logit": float(negative_max_logit(logits)[0]),
                "score_pnorm_max_logit_p2": float(pnorm_normalized_max_logit(logits, order=2.0)[0]),
            }
        )
    if compound:
        record.update(
            {
                "filename": "compound.mat",
                "bearing_code": "KB23",
                "setting_code": "N15_M07_F10",
                "measurement_index": 1,
            }
        )
    else:
        record.update({"truth": "healthy", "correct": True})
    return pd.DataFrame([record])


def _json_record(name: str) -> dict[str, Any]:
    base: dict[str, Any] = {
        "dataset": "paderborn_compound" if name == "compound_policy_metrics" else "paderborn",
        "method": "erm",
        "seed": 11,
        "fold_id": "f0",
    }
    if name in {"policies", "policy_metrics", "compound_policy_metrics"}:
        base.update({"score_name": "msp", "nominal_source_coverage": 0.5})
    elif name == "ranking_metrics":
        base["score_name"] = "msp"
    elif name == "training_traces":
        base["inner_split_id"] = "inner=0"
    if name == "compound_policy_metrics":
        base["accuracy_reported"] = False
    return base


def test_selective_validator_checks_all_fourteen_artifacts(tmp_path: Path) -> None:
    directory = tmp_path / "selective"
    directory.mkdir()
    source = _prediction(ensemble=False, compound=False)
    target = _prediction(ensemble=False, compound=False)
    compound = _prediction(ensemble=False, compound=True)
    source = pd.concat([source, source.assign(seed=23)], ignore_index=True)
    target = pd.concat([target, target.assign(seed=23)], ignore_index=True)
    compound = pd.concat([compound, compound.assign(seed=23)], ignore_index=True)
    values: dict[str, pd.DataFrame | list[dict[str, Any]]] = {
        "source_oof_predictions": source,
        "target_predictions": target,
        "compound_predictions": compound,
        "source_oof_ensemble_predictions": _prediction(ensemble=True, compound=False),
        "target_ensemble_predictions": _prediction(ensemble=True, compound=False),
        "compound_ensemble_predictions": _prediction(ensemble=True, compound=True),
        "selection_decisions": pd.DataFrame(
            [
                {
                    "dataset": "paderborn",
                    "method": "erm",
                    "seed": 11,
                    "fold_id": "f0",
                    "score_name": "msp",
                    "nominal_source_coverage": 0.5,
                    "row_index": 0,
                    "prediction": "healthy",
                    "score": 0.2,
                    "threshold": 0.3,
                    "accepted": True,
                }
            ]
        ),
        "compound_decisions": pd.DataFrame(
            [
                {
                    "dataset": "paderborn_compound",
                    "method": "erm",
                    "seed": 11,
                    "fold_id": "f0",
                    "score_name": "msp",
                    "nominal_source_coverage": 0.5,
                    "row_index": 2320,
                    "prediction": "healthy",
                    "score": 0.2,
                    "threshold": 0.3,
                    "accepted": True,
                }
            ]
        ),
        **{
            name: [_json_record(name)]
            for name in (
                "policies",
                "beta_selections",
                "policy_metrics",
                "ranking_metrics",
                "compound_policy_metrics",
                "training_traces",
            )
        },
    }
    base_directory = tmp_path / "base"
    base_directory.mkdir()
    base_artifacts = {}
    for name, frame in (("predictions", target), ("compound_predictions", compound)):
        path = base_directory / f"{name}.parquet"
        frame.to_parquet(path, index=False)
        base_artifacts[name] = {
            "path": path.name,
            "rows": len(frame),
            "bytes": path.stat().st_size,
            "sha256": _sha256(path),
        }
    base_metrics_path = base_directory / "metrics.json"
    base_metrics_path.write_text(
        json.dumps(
            {
                "status": "one_shot_paderborn_prospective_evaluation_complete",
                "artifacts": base_artifacts,
            }
        )
        + "\n",
        encoding="utf-8",
    )
    base_validation_path = tmp_path / "base_validation.json"
    base_validation_path.write_text(
        json.dumps(
            {
                "status": "passed_against_sealed_metadata_only_paderborn_manifest",
                "paderborn_metrics": {"sha256": _sha256(base_metrics_path)},
                "artifact_hashes": {
                    name: record["sha256"] for name, record in base_artifacts.items()
                },
            }
        )
        + "\n",
        encoding="utf-8",
    )
    paths = {}
    artifacts = {}
    expected_key_sets = {}
    for artifact_name, key_name in ARTIFACT_KEY_SETS.items():
        value = values[artifact_name]
        suffix = ".parquet" if artifact_name in PARQUET_ARTIFACTS else ".json"
        path = directory / f"{artifact_name}{suffix}"
        if isinstance(value, pd.DataFrame):
            value.to_parquet(path, index=False)
        else:
            path.write_text(json.dumps(value) + "\n", encoding="utf-8")
        paths[artifact_name] = path
        artifacts[artifact_name] = {
            "path": path.name,
            "rows": len(value),
            "bytes": path.stat().st_size,
            "sha256": _sha256(path),
        }
        columns = KEY_SCHEMAS[key_name]
        rows = (
            value.loc[:, list(columns)].itertuples(index=False, name=None)
            if isinstance(value, pd.DataFrame)
            else (tuple(record[column] for column in columns) for record in value)
        )
        expected_key_sets[key_name] = canonical_key_record(rows, columns)
    manifest_path = tmp_path / "manifest.json"
    manifest = {
        "manifest_version": MANIFEST_VERSION,
        "input": {
            "protocol_document_sha256": "a" * 64,
            "base_expected_manifest_sha256": "b" * 64,
            "signal_features_used_to_define_topology": False,
            "model_outcomes_inspected_before_manifest": False,
        },
        "expected_key_sets": expected_key_sets,
    }
    manifest_path.write_text(json.dumps(manifest) + "\n", encoding="utf-8")
    metrics = {
        "status": EVALUATION_STATUS,
        "input": {
            "expected_manifest_sha256": _sha256(manifest_path),
            "protocol_document_sha256": "a" * 64,
            "base_expected_manifest_sha256": "b" * 64,
            "base_output_directory": str(base_directory),
            "base_validation": str(base_validation_path),
            "base_validation_sha256": _sha256(base_validation_path),
            "base_metrics_sha256": _sha256(base_metrics_path),
        },
        "access_attestation": {
            "all_thresholds_and_betas_selected_from_source_oof_only": True,
            "target_coverage_used_for_threshold_selection": False,
            "target_labels_used_for_threshold_selection": False,
            "configuration_reselection_performed": False,
            "compound_forced_ground_truth_defined": False,
            "compound_accuracy_computed": False,
        },
        "artifacts": artifacts,
    }
    (directory / "metrics.json").write_text(json.dumps(metrics) + "\n", encoding="utf-8")

    result = validate_paderborn_selective_artifacts(
        selective_output_directory=directory,
        expected_manifest=manifest_path,
        expected_manifest_sha256=_sha256(manifest_path),
        output=tmp_path / "validation.json",
    )

    assert result["status"] == VALIDATION_STATUS
    assert len(result["artifact_hashes"]) == 14
    assert result["maximum_probability_sum_error"] == pytest.approx(0.0)
    assert result["source_only_policy_selection"] is True
