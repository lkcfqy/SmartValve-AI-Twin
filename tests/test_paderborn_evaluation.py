from __future__ import annotations

import hashlib
import json
from dataclasses import asdict
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

import smartvalve.experiments.paderborn_evaluation as evaluation
from smartvalve.experiments.dg_selection import candidate_id as dg_candidate_id
from smartvalve.experiments.dg_training import BASELINE_METHODS, BaselineConfig
from smartvalve.experiments.domain_data import SourceOnlyFold
from smartvalve.experiments.paderborn_domain import PaderbornModelFold
from smartvalve.experiments.paderborn_evaluation import (
    fit_progress_event,
    release_target_outcomes,
    validate_compound_prediction_topology,
    validate_prediction_topology,
)
from smartvalve.experiments.pirl_ratio_selection import (
    candidate_id as pirl_candidate_id,
)
from smartvalve.experiments.pirl_sore import TrainingConfig


def _predictions() -> pd.DataFrame:
    rows = []
    for method in ("pirl_ratio", "erm"):
        for seed in (11, 23):
            for fold_id, row_index in (("f0", 0), ("f1", 1)):
                rows.append(
                    {
                        "dataset": "paderborn",
                        "method": method,
                        "seed": seed,
                        "fold_id": fold_id,
                        "row_index": row_index,
                        "probability_healthy": 0.6,
                        "probability_inner": 0.2,
                        "probability_outer": 0.2,
                        "representation_00": 1.0,
                        "representation_01": 0.0,
                    }
                )
    return pd.DataFrame(rows)


def test_paderborn_prediction_topology_requires_every_row_and_unit_representation() -> None:
    result = validate_prediction_topology(
        _predictions(),
        row_count=2,
        methods=("pirl_ratio", "erm"),
        seeds=(11, 23),
        expected_folds=2,
    )

    assert result["method_seed_groups"] == 4
    assert result["model_fold_groups"] == 8
    assert result["prediction_rows"] == 8
    assert result["representation_dimensions"] == {"pirl_ratio": 2, "erm": 2}
    assert result["maximum_probability_sum_error"] == pytest.approx(0.0)
    assert result["maximum_representation_norm_error"] == pytest.approx(0.0)


@pytest.mark.parametrize(
    ("column", "value", "message"),
    [
        ("row_index", 1, "duplicate model/row keys"),
        ("probability_healthy", 0.7, "not normalized"),
        ("representation_00", 0.5, "not unit normalized"),
    ],
)
def test_paderborn_prediction_topology_rejects_drift(
    column: str, value: float, message: str
) -> None:
    frame = _predictions()
    frame.loc[0, column] = value

    with pytest.raises(ValueError, match=message):
        validate_prediction_topology(
            frame,
            row_count=2,
            methods=("pirl_ratio", "erm"),
            seeds=(11, 23),
            expected_folds=2,
        )


def test_paderborn_prediction_topology_rejects_nonfinite_values() -> None:
    frame = _predictions()
    frame.loc[0, "probability_healthy"] = np.nan
    with pytest.raises(ValueError, match="probabilities"):
        validate_prediction_topology(
            frame,
            row_count=2,
            methods=("pirl_ratio", "erm"),
            seeds=(11, 23),
            expected_folds=2,
        )


def test_paderborn_prediction_topology_allows_frozen_per_method_dimensions() -> None:
    frame = _predictions()
    frame["representation_02"] = np.nan
    frame.loc[frame["method"] == "erm", "representation_02"] = 0.0

    result = validate_prediction_topology(
        frame,
        row_count=2,
        methods=("pirl_ratio", "erm"),
        seeds=(11, 23),
        expected_folds=2,
        expected_representation_dimensions={"pirl_ratio": 2, "erm": 3},
    )

    assert result["representation_dimensions"] == {"pirl_ratio": 2, "erm": 3}


def test_paderborn_compound_topology_is_unlabeled_and_complete() -> None:
    compound = pd.DataFrame(
        {
            "full_row_index": [8, 9],
            "filename": ["a.mat", "b.mat"],
            "bearing_code": ["KB23", "KB24"],
            "setting_code": ["s0", "s1"],
            "measurement_index": [1, 1],
        }
    )
    rows = []
    for method, dimension in (("pirl_ratio", 2), ("erm", 3)):
        for fold_id in ("f0", "f1"):
            for record in compound.to_dict(orient="records"):
                row = {
                    "dataset": "paderborn_compound",
                    "method": method,
                    "seed": 11,
                    "fold_id": fold_id,
                    "row_index": record["full_row_index"],
                    "filename": record["filename"],
                    "bearing_code": record["bearing_code"],
                    "setting_code": record["setting_code"],
                    "measurement_index": record["measurement_index"],
                    "prediction": "healthy",
                    "probability_healthy": 0.6,
                    "probability_outer": 0.2,
                    "probability_inner": 0.2,
                }
                for index in range(dimension):
                    row[f"representation_{index:02d}"] = 1.0 if index == 0 else 0.0
                rows.append(row)
    predictions = pd.DataFrame(rows)

    result = validate_compound_prediction_topology(
        predictions,
        compound,
        fold_ids=("f0", "f1"),
        methods=("pirl_ratio", "erm"),
        seeds=(11,),
        expected_representation_dimensions={"pirl_ratio": 2, "erm": 3},
    )

    assert result["model_groups"] == 4
    assert result["prediction_rows"] == 8
    assert result["forced_ground_truth_defined"] is False
    with pytest.raises(ValueError, match="forced outcome"):
        validate_compound_prediction_topology(
            predictions.assign(truth="compound"),
            compound,
            fold_ids=("f0", "f1"),
            methods=("pirl_ratio", "erm"),
            seeds=(11,),
            expected_representation_dimensions={"pirl_ratio": 2, "erm": 3},
        )


def test_paderborn_fit_progress_event_cannot_release_target_outcomes() -> None:
    event = fit_progress_event(
        {
            "method": "pirl_ratio",
            "seed": 11,
            "fold_id": "identity=0|setting=N15_M07_F10",
            "candidate_id": "r64_l1p0_m0p5",
            "fit_seconds": 1.25,
            "model_state_sha256": "a" * 64,
            "macro_f1": 0.99,
            "accuracy": 0.99,
        }
    )

    assert event["event"] == "paderborn_prospective_fit_complete"
    assert "macro_f1" not in event
    assert "accuracy" not in event
    assert "truth" not in event


def test_paderborn_fit_emits_compound_predictions_without_outcomes() -> None:
    fold = SourceOnlyFold(
        dataset="paderborn",
        fold_id="f0",
        held_factor="identity_fold_and_setting",
        held_level=0,
        features=np.arange(8, dtype=np.float32).reshape(-1, 1),
        labels=np.asarray([0, 0, 1, 1, 2, 2, 0, 2], dtype=np.int64),
        label_names=("healthy", "outer", "inner"),
        feature_names=("feature",),
        environment_ids=np.asarray(["s0", "s1", "s0", "s1", "s0", "s1", "s3", "s3"]),
        block_ids=np.asarray([f"b{index}" for index in range(8)]),
        source_indices=np.arange(6, dtype=np.int64),
        target_indices=np.asarray([6, 7], dtype=np.int64),
        nuisance_pairs=np.asarray([[0, 1]], dtype=np.int64),
        fault_pairs=np.asarray([[0, 2]], dtype=np.int64),
    )
    model_fold = PaderbornModelFold(
        fold=fold,
        held_bearing_codes=("K001",),
        held_setting_code="s3",
        source_global_indices=np.arange(6, dtype=np.int64),
        target_global_indices=np.asarray([0, 1], dtype=np.int64),
        quarantine_global_indices=np.asarray([], dtype=np.int64),
    )
    full_frame = pd.DataFrame(
        {
            "filename": ["a.mat", "b.mat"],
            "bearing_code": ["K001", "KI01"],
            "setting_code": ["s3", "s3"],
            "measurement_index": [1, 1],
            "damage_origin": ["healthy", "real"],
            "component": ["healthy", "inner"],
            "damage_extent": ["none", "single"],
        }
    )
    compound = pd.DataFrame(
        {
            "feature": [0.5],
            "full_row_index": [8],
            "filename": ["compound.mat"],
            "bearing_code": ["KB23"],
            "setting_code": ["s3"],
            "measurement_index": [1],
            "truth": ["compound"],
        }
    )

    fit_record, target, compound_predictions, trace = evaluation._fit_one(
        model_fold,
        BaselineConfig(method="erm", hidden_dim=8, representation_dim=2, epochs=1),
        method="erm",
        seed=11,
        device="cpu",
        full_frame=full_frame,
        compound_frame=compound,
        candidate_identifier="erm_fixture",
    )

    assert len(target) == 2
    assert len(compound_predictions) == 1
    assert "truth" not in compound_predictions
    assert compound_predictions["row_index"].tolist() == [8]
    assert fit_record["compound_inference_seconds"] >= 0
    assert trace["compound_full_row_indices_sha256"]


def _outcome_release_fixture() -> tuple[
    pd.DataFrame,
    list[dict[str, object]],
    tuple[PaderbornModelFold, ...],
    pd.DataFrame,
]:
    fold = SourceOnlyFold(
        dataset="paderborn",
        fold_id="f0",
        held_factor="identity_fold_and_setting",
        held_level=0,
        features=np.zeros((6, 1), dtype=np.float32),
        labels=np.asarray([0, 0, 1, 2, 0, 2], dtype=np.int64),
        label_names=("healthy", "outer", "inner"),
        feature_names=("feature",),
        environment_ids=np.asarray(["s0", "s1", "s2", "s2", "s3", "s3"]),
        block_ids=np.asarray(["b0", "b1", "b2", "b3", "b4", "b5"]),
        source_indices=np.asarray([0, 1, 2, 3], dtype=np.int64),
        target_indices=np.asarray([4, 5], dtype=np.int64),
        nuisance_pairs=np.asarray([[0, 1]], dtype=np.int64),
        fault_pairs=np.asarray([[0, 2]], dtype=np.int64),
    )
    model_fold = PaderbornModelFold(
        fold=fold,
        held_bearing_codes=("K001",),
        held_setting_code="s3",
        source_global_indices=np.asarray([], dtype=np.int64),
        target_global_indices=np.asarray([0, 1], dtype=np.int64),
        quarantine_global_indices=np.asarray([], dtype=np.int64),
    )
    predictions = pd.DataFrame(
        {
            "dataset": ["paderborn", "paderborn"],
            "method": ["erm", "erm"],
            "seed": [11, 11],
            "fold_id": ["f0", "f0"],
            "row_index": [0, 1],
            "prediction": ["healthy", "outer"],
            "probability_healthy": [0.8, 0.1],
            "probability_outer": [0.1, 0.8],
            "probability_inner": [0.1, 0.1],
            "risk_envelope_score_beta_0_25": [0.1, 0.9],
        }
    )
    fit_records: list[dict[str, object]] = [
        {
            "method": "erm",
            "seed": 11,
            "fold_id": "f0",
            "source_nuisance_representation_response": 0.25,
            "source_fault_representation_response": 1.0,
            "source_nuisance_probability_response": 0.2,
            "source_fault_probability_response": 0.8,
        }
    ]
    full_frame = pd.DataFrame({"truth": ["healthy", "inner"]})
    return predictions, fit_records, (model_fold,), full_frame


def test_paderborn_target_outcomes_are_released_after_completed_fit_set() -> None:
    predictions, fit_records, folds, frame = _outcome_release_fixture()

    released, fold_metrics = release_target_outcomes(
        predictions,
        fit_records,
        folds,
        frame,
        methods=("erm",),
        seeds=(11,),
    )

    assert released["truth"].tolist() == ["healthy", "inner"]
    assert released["correct"].tolist() == [True, False]
    assert fold_metrics[0]["accuracy"] == pytest.approx(0.5)
    assert "accuracy" not in fit_records[0]


def test_paderborn_outcome_release_rejects_early_target_metrics() -> None:
    predictions, fit_records, folds, frame = _outcome_release_fixture()
    fit_records[0]["macro_f1"] = 0.9

    with pytest.raises(ValueError, match="before the release boundary"):
        release_target_outcomes(
            predictions,
            fit_records,
            folds,
            frame,
            methods=("erm",),
            seeds=(11,),
        )


def _file_record(path: Path, root: Path) -> dict[str, object]:
    return {
        "path": str(path.relative_to(root)),
        "bytes": path.stat().st_size,
        "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
    }


def test_paderborn_sealed_configuration_loader_verifies_every_selection(
    tmp_path: Path,
) -> None:
    pirl_configuration = TrainingConfig(method="pirl_ratio")
    pirl_identifier = pirl_candidate_id(pirl_configuration)
    pirl_path = tmp_path / "pirl.json"
    pirl_path.write_text(
        json.dumps(
            {
                "gate_decision": {
                    "mechanism_gate_passed": True,
                    "efficacy_gate_passed": True,
                },
                "common_selection": {
                    "selected_candidate_id": pirl_identifier,
                    "configuration": asdict(pirl_configuration),
                },
            }
        ),
        encoding="utf-8",
    )
    common = {}
    selected = {"pirl": pirl_identifier}
    for method in BASELINE_METHODS:
        configuration = BaselineConfig(method=method)
        identifier = dg_candidate_id(configuration)
        common[method] = {
            "selected_candidate_id": identifier,
            "configuration": asdict(configuration),
        }
        selected[method] = identifier
    dg_path = tmp_path / "dg.json"
    dg_path.write_text(json.dumps({"common_selections": common}), encoding="utf-8")
    seal = {
        "artifacts": {
            "pirl_development_metrics": _file_record(pirl_path, tmp_path),
            "dg_selection_metrics": _file_record(dg_path, tmp_path),
        },
        "decision": {"selected_configurations": selected},
    }

    configurations, identifiers, hashes = evaluation.load_sealed_configurations(
        tmp_path.resolve(), seal
    )

    assert set(configurations) == {"pirl_ratio", *BASELINE_METHODS}
    assert identifiers["pirl_ratio"] == pirl_identifier
    assert identifiers["erm"] == "erm_r32"
    assert hashes["pirl_metrics_sha256"] == _file_record(pirl_path, tmp_path)["sha256"]


def test_paderborn_feature_input_loader_checks_seal_and_matrix_hashes(
    tmp_path: Path,
) -> None:
    full_frame = pd.DataFrame({"truth": ["healthy", "compound"], "feature": [1.0, 2.0]})
    frame = full_frame.iloc[[0]].reset_index(drop=True)
    full_matrix = tmp_path / "full.parquet"
    matrix = tmp_path / "primary.parquet"
    full_frame.to_parquet(full_matrix, index=False)
    frame.to_parquet(matrix, index=False)
    seal_hash = "d" * 64
    metrics = {
        "status": "sealed_paderborn_features_complete_without_model_outcome_access",
        "input": {"prospective_seal_sha256": seal_hash},
        "corpus": {
            "measurement_count": 2,
            "primary_measurement_count": 1,
            "compound_measurement_count": 1,
        },
        "access_attestation": {"model_outcomes_inspected": False},
        "artifacts": {
            "feature_matrix": {
                "path": full_matrix.name,
                "rows": 2,
                "bytes": full_matrix.stat().st_size,
                "sha256": hashlib.sha256(full_matrix.read_bytes()).hexdigest(),
            },
            "primary_feature_matrix": {
                "path": matrix.name,
                "rows": 1,
                "bytes": matrix.stat().st_size,
                "sha256": hashlib.sha256(matrix.read_bytes()).hexdigest(),
            },
        },
    }
    metrics_path = tmp_path / "metrics.json"
    metrics_path.write_text(json.dumps(metrics), encoding="utf-8")
    metrics_hash = hashlib.sha256(metrics_path.read_bytes()).hexdigest()

    loaded, compound, record, path, loaded_full_path = evaluation._load_feature_frame(
        metrics_path,
        expected_metrics_sha256=metrics_hash,
        expected_seal_sha256=seal_hash,
    )

    assert loaded.equals(frame)
    assert compound["truth"].tolist() == ["compound"]
    assert compound["full_row_index"].tolist() == [1]
    assert record["status"].startswith("sealed_paderborn_features_complete")
    assert path == matrix
    assert loaded_full_path == full_matrix


def test_amended_execution_authorization_binds_every_pre_model_input(
    tmp_path: Path,
) -> None:
    root = tmp_path.resolve()
    prospective_seal = root / "prospective_seal.json"
    prospective_seal.write_text("{}\n", encoding="utf-8")
    feature_metrics = root / "feature_metrics.json"
    feature_metrics.write_text("{}\n", encoding="utf-8")
    protocol = root / "execution_protocol.md"
    protocol.write_text("Status: frozen\n", encoding="utf-8")
    split = root / "split.json"
    split.write_text("{}\n", encoding="utf-8")
    folds = root / "folds.json"
    folds.write_text("{}\n", encoding="utf-8")
    feature_amendment = root / "feature_amendment.json"
    feature_amendment.write_text("{}\n", encoding="utf-8")
    feature_validation = root / "feature_validation.json"
    feature_validation.write_text("{}\n", encoding="utf-8")
    expected_manifest = root / "expected_manifest.json"
    manifest_input = {
        "protocol_document": str(protocol),
        "protocol_document_sha256": _file_record(protocol, root)["sha256"],
        "split_manifest": str(split),
        "split_manifest_sha256": _file_record(split, root)["sha256"],
        "model_fold_manifest": str(folds),
        "model_fold_manifest_sha256": _file_record(folds, root)["sha256"],
        "feature_contract_amendment": str(feature_amendment),
        "feature_contract_amendment_sha256": _file_record(feature_amendment, root)["sha256"],
        "feature_validation": str(feature_validation),
        "feature_validation_sha256": _file_record(feature_validation, root)["sha256"],
        "signal_features_used_to_define_topology": False,
        "model_outcomes_inspected_before_manifest": False,
    }
    expected_manifest.write_text(
        json.dumps(
            {
                "manifest_version": ("paderborn-prospective-expected-key-manifest-0.2.0"),
                "input": manifest_input,
                "expected_key_sets": {
                    "training_models": {"count": 1080},
                    "fold_metrics": {"count": 1080},
                    "target_predictions": {"count": 104355},
                    "compound_predictions": {"count": 259200},
                },
            }
        )
        + "\n",
        encoding="utf-8",
    )
    decision = {"selected_configurations": {"fixture": "locked"}}
    statistics = {"bootstrap_replicates": 2000}
    original = {
        "decision": decision,
        "statistics": statistics,
        "attestation": {"paderborn_model_outcomes_inspected": False},
    }
    execution_seal = root / "execution_seal.json"
    execution_seal.write_text(
        json.dumps(
            {
                "schema_version": ("smartvalve-paderborn-d2-execution-seal-0.1.0"),
                "status": "sealed_after_features_before_paderborn_model_outcomes",
                "decision": decision,
                "statistics": statistics,
                "attestation": {
                    "paderborn_models_fitted": False,
                    "paderborn_model_outcomes_inspected": False,
                    "target_guided_reselection_performed": False,
                },
                "artifacts": {
                    "original_prospective_seal": _file_record(prospective_seal, root),
                    "feature_metrics": _file_record(feature_metrics, root),
                    "amended_expected_manifest": _file_record(expected_manifest, root),
                    "execution_amendment_protocol": _file_record(protocol, root),
                    "amended_split_manifest": _file_record(split, root),
                    "amended_model_fold_manifest": _file_record(folds, root),
                    "feature_contract_amendment": _file_record(feature_amendment, root),
                    "feature_validation": _file_record(feature_validation, root),
                },
            }
        )
        + "\n",
        encoding="utf-8",
    )

    result = evaluation.validate_execution_authorization(
        root,
        original,
        prospective_seal=prospective_seal,
        expected_prospective_seal_sha256=_file_record(prospective_seal, root)["sha256"],
        execution_seal=execution_seal,
        expected_execution_seal_sha256=_file_record(execution_seal, root)["sha256"],
        feature_metrics=feature_metrics,
        expected_feature_metrics_sha256=_file_record(feature_metrics, root)["sha256"],
        expected_manifest=expected_manifest,
        expected_manifest_sha256=_file_record(expected_manifest, root)["sha256"],
    )

    assert result["expected_manifest"] == _file_record(expected_manifest, root)["sha256"]
    assert result["feature_metrics"] == _file_record(feature_metrics, root)["sha256"]
    assert result["execution_seal"] == _file_record(execution_seal, root)["sha256"]


def test_paderborn_evaluation_orchestrates_one_shot_release_and_artifacts(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _, fit_records, _, _ = _outcome_release_fixture()
    fold = SourceOnlyFold(
        dataset="paderborn",
        fold_id="f0",
        held_factor="identity_fold_and_setting",
        held_level=0,
        features=np.zeros((7, 1), dtype=np.float32),
        labels=np.asarray([0, 0, 1, 2, 0, 1, 2], dtype=np.int64),
        label_names=("healthy", "outer", "inner"),
        feature_names=("feature",),
        environment_ids=np.asarray(["s0", "s1", "s2", "s2", "s3", "s3", "s3"]),
        block_ids=np.asarray([f"b{index}" for index in range(7)]),
        source_indices=np.asarray([0, 1, 2, 3], dtype=np.int64),
        target_indices=np.asarray([4, 5, 6], dtype=np.int64),
        nuisance_pairs=np.asarray([[0, 1]], dtype=np.int64),
        fault_pairs=np.asarray([[0, 2]], dtype=np.int64),
    )
    folds = (
        PaderbornModelFold(
            fold=fold,
            held_bearing_codes=("K001", "KA01", "KI01"),
            held_setting_code="s3",
            source_global_indices=np.asarray([], dtype=np.int64),
            target_global_indices=np.asarray([0, 1, 2], dtype=np.int64),
            quarantine_global_indices=np.asarray([], dtype=np.int64),
        ),
    )
    frame = pd.DataFrame(
        {
            "truth": ["healthy", "outer", "inner"],
            "filename": ["a.mat", "b.mat", "c.mat"],
            "bearing_code": ["K001", "KA01", "KI01"],
            "setting_code": ["s3", "s3", "s3"],
            "measurement_index": [1, 1, 1],
            "damage_origin": ["healthy", "artificial", "artificial"],
            "component": ["healthy", "outer", "inner"],
            "damage_extent": ["none", "single", "single"],
        }
    )
    compound_frame = pd.DataFrame(
        {
            "truth": ["compound"],
            "full_row_index": [3],
            "filename": ["compound.mat"],
            "bearing_code": ["KB23"],
            "setting_code": ["s3"],
            "measurement_index": [1],
        }
    )
    predictions = pd.DataFrame(
        {
            "dataset": ["paderborn"] * 3,
            "method": ["erm"] * 3,
            "seed": [11] * 3,
            "fold_id": ["f0"] * 3,
            "row_index": [0, 1, 2],
            "prediction": ["healthy", "outer", "outer"],
            "probability_healthy": [0.8, 0.1, 0.1],
            "probability_outer": [0.1, 0.8, 0.7],
            "probability_inner": [0.1, 0.1, 0.2],
            "risk_envelope_score_beta_0_25": [0.1, 0.2, 0.8],
        }
    )
    fit_record = {
        **fit_records[0],
        "dataset": "paderborn",
        "candidate_id": "erm_fixture",
        "held_bearing_codes": ["K001"],
        "held_setting_code": "s3",
        "source_rows": 4,
        "target_rows": 3,
        "quarantine_rows": 0,
        "source_representation_response_ratio": 0.25,
        "source_probability_response_ratio": 0.25,
        "fit_seconds": 0.1,
        "inference_seconds": 0.01,
        "peak_memory_bytes": None,
        "parameter_count_network_only": 10,
        "model_state_sha256": "c" * 64,
        "auxiliary_state_sha256": None,
    }
    predictions = predictions.assign(
        representation_00=[1.0, 1.0, 1.0],
        filename=frame["filename"],
        bearing_code=frame["bearing_code"],
        setting_code=frame["setting_code"],
        measurement_index=frame["measurement_index"],
        damage_origin=frame["damage_origin"],
        component=frame["component"],
        damage_extent=frame["damage_extent"],
    )
    compound_predictions = pd.DataFrame(
        {
            "dataset": ["paderborn_compound"],
            "method": ["erm"],
            "seed": [11],
            "fold_id": ["f0"],
            "row_index": [3],
            "filename": ["compound.mat"],
            "bearing_code": ["KB23"],
            "setting_code": ["s3"],
            "measurement_index": [1],
            "prediction": ["healthy"],
            "confidence": [0.8],
            "risk_envelope_score_beta_0_25": [0.2],
            "probability_healthy": [0.8],
            "probability_outer": [0.1],
            "probability_inner": [0.1],
            "representation_00": [1.0],
        }
    )
    trace = {
        "dataset": "paderborn",
        "method": "erm",
        "seed": 11,
        "fold_id": "f0",
        "model_state_sha256": "c" * 64,
    }
    prospective_seal = tmp_path / "seal.json"
    prospective_seal.write_text("{}", encoding="utf-8")
    execution_seal = tmp_path / "execution_seal.json"
    execution_seal.write_text("{}", encoding="utf-8")
    feature_metrics = tmp_path / "feature_metrics.json"
    feature_metrics.write_text("{}", encoding="utf-8")
    expected_manifest = tmp_path / "expected_manifest.json"
    expected_manifest.write_text("{}", encoding="utf-8")
    feature_path = tmp_path / "features.parquet"
    feature_path.write_bytes(b"fixture")
    full_feature_path = tmp_path / "full_features.parquet"
    full_feature_path.write_bytes(b"full fixture")
    configuration = BaselineConfig(method="erm", epochs=1)

    monkeypatch.setattr(evaluation, "METHODS", ("erm",))
    monkeypatch.setattr(evaluation, "AUDIT_SEEDS", (11,))
    monkeypatch.setattr(evaluation, "_load_and_validate_seal", lambda *_: {})
    monkeypatch.setattr(
        evaluation,
        "validate_execution_authorization",
        lambda *_args, **_kwargs: {
            "expected_manifest": "manifest-hash",
            "protocol_document": "protocol-hash",
            "split_manifest": "split-hash",
            "model_fold_manifest": "fold-hash",
            "execution_seal": "execution-seal-hash",
        },
    )
    monkeypatch.setattr(
        evaluation,
        "load_sealed_configurations",
        lambda *_: (
            {"erm": configuration},
            {"erm": "erm_fixture"},
            {"pirl_metrics_sha256": "p", "dg_metrics_sha256": "d"},
        ),
    )
    monkeypatch.setattr(
        evaluation,
        "_load_feature_frame",
        lambda *_args, **_kwargs: (
            frame,
            compound_frame,
            {"access_attestation": {"model_outcomes_inspected": False}},
            feature_path,
            full_feature_path,
        ),
    )
    monkeypatch.setattr(evaluation, "build_paderborn_model_folds", lambda *_: folds)
    monkeypatch.setattr(
        evaluation,
        "_fit_one",
        lambda *_args, **_kwargs: (
            fit_record,
            predictions,
            compound_predictions,
            trace,
        ),
    )
    monkeypatch.setattr(
        evaluation,
        "validate_prediction_topology",
        lambda values, **_: {
            "method_seed_groups": 1,
            "model_fold_groups": 1,
            "prediction_rows": len(values),
        },
    )
    monkeypatch.setattr(
        evaluation,
        "validate_compound_prediction_topology",
        lambda values, *_args, **_kwargs: {
            "model_groups": 1,
            "prediction_rows": len(values),
            "unique_compound_measurements": 1,
            "forced_ground_truth_defined": False,
        },
    )

    result = evaluation.run_evaluation(
        prospective_seal=prospective_seal,
        expected_seal_sha256="seal-hash",
        execution_seal=execution_seal,
        expected_execution_seal_sha256="execution-seal-hash",
        feature_metrics=feature_metrics,
        expected_feature_metrics_sha256="feature-hash",
        expected_manifest=expected_manifest,
        expected_manifest_sha256="manifest-hash",
        output_directory=tmp_path / "outputs",
        device="cpu",
        root=tmp_path,
    )

    assert result["status"] == "one_shot_paderborn_prospective_evaluation_complete"
    assert result["integrity"]["models"] == 1
    summary = result["seed_summaries"]["erm"]["11"]
    assert summary["pooled_macro_f1"] < 1.0
    assert summary["per_class_recall"]["healthy"] == pytest.approx(1.0)
    assert summary["confusion_matrix"]["rows_truth_columns_prediction"] == [
        [1, 0, 0],
        [0, 1, 0],
        [0, 1, 0],
    ]
    assert summary["damage_origin_strata"]["artificial"]["rows"] == 2
    assert summary["parameter_count_network_only"] == 10
    assert summary["maximum_peak_memory_bytes"] == 0
    assert result["access_attestation"]["paderborn_model_outcomes_emitted_only_after_all_fits"]
    assert (tmp_path / "outputs" / "metrics.json").is_file()
    written = pd.read_parquet(tmp_path / "outputs" / "predictions.parquet")
    assert written["truth"].tolist() == ["healthy", "outer", "inner"]
    compound_written = pd.read_parquet(tmp_path / "outputs" / "compound_predictions.parquet")
    assert "truth" not in compound_written
    assert result["access_attestation"]["compound_accuracy_computed"] is False
