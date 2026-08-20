from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pandas as pd

from smartvalve.experiments.paderborn_artifact_validation import (
    validate_paderborn_artifacts,
)
from smartvalve.experiments.paderborn_expected_manifest import (
    build_expected_paderborn_manifest,
    metadata_only_indices,
)
from smartvalve.experiments.paderborn_partitions import build_paderborn_partitions


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _manifest(*, methods: tuple[str, ...], seeds: tuple[int, ...]) -> dict:
    return build_expected_paderborn_manifest(
        protocol_document="protocol.md",
        protocol_document_sha256="a" * 64,
        split_manifest="split.json",
        split_manifest_sha256="b" * 64,
        model_fold_manifest="folds.json",
        model_fold_manifest_sha256="c" * 64,
        feature_contract_amendment="feature-amendment.json",
        feature_contract_amendment_sha256="d" * 64,
        feature_validation="feature-validation.json",
        feature_validation_sha256="e" * 64,
        methods=methods,
        seeds=seeds,
    )


def test_metadata_only_paderborn_manifest_freezes_full_topology() -> None:
    primary, compound = metadata_only_indices()
    manifest = _manifest(
        methods=(
            "pirl_ratio",
            "erm",
            "coral",
            "vrex",
            "groupdro",
            "dann",
            "lisa",
            "matchdg",
            "ccdg",
        ),
        seeds=(11, 23, 37, 53, 71),
    )

    assert len(primary) == 2_319
    assert len(compound) == 240
    assert manifest["expected_key_sets"]["training_models"]["count"] == 1_080
    assert manifest["expected_key_sets"]["target_predictions"]["count"] == 104_355
    assert manifest["expected_key_sets"]["compound_predictions"]["count"] == 259_200
    assert manifest["input"]["model_outcomes_inspected_before_manifest"] is False
    assert manifest["input"]["signal_features_used_to_define_topology"] is False


def test_paderborn_validator_checks_closed_and_unlabeled_compound_artifacts(
    tmp_path: Path,
) -> None:
    primary, compound_index = metadata_only_indices()
    partitions = build_paderborn_partitions(primary)
    manifest = _manifest(methods=("erm",), seeds=(11,))
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    output_directory = tmp_path / "evaluation"
    output_directory.mkdir()
    prediction_rows = []
    compound_rows = []
    model_rows = []
    for partition in partitions:
        model = {
            "dataset": "paderborn",
            "method": "erm",
            "seed": 11,
            "fold_id": partition.fold_id,
        }
        model_rows.append(model)
        for row_index in partition.target_indices:
            metadata = primary.iloc[int(row_index)]
            truth = str(metadata["truth"])
            prediction_rows.append(
                {
                    **model,
                    "row_index": int(row_index),
                    "environment_id": str(metadata["setting_code"]),
                    "block_id": "|".join(
                        str(metadata[column])
                        for column in (
                            "bearing_code",
                            "setting_code",
                            "measurement_index",
                        )
                    ),
                    "bearing_code": str(metadata["bearing_code"]),
                    "setting_code": str(metadata["setting_code"]),
                    "measurement_index": int(metadata["measurement_index"]),
                    "truth": truth,
                    "prediction": truth,
                    "correct": True,
                    "confidence": 1.0,
                    "robust_class_support_distance": 0.0,
                    "probability_healthy": 1.0 if truth == "healthy" else 0.0,
                    "probability_outer": 1.0 if truth == "outer" else 0.0,
                    "probability_inner": 1.0 if truth == "inner" else 0.0,
                    "logit_healthy": 1.0 if truth == "healthy" else 0.0,
                    "logit_outer": 1.0 if truth == "outer" else 0.0,
                    "logit_inner": 1.0 if truth == "inner" else 0.0,
                    "representation_00": 1.0,
                }
            )
        compound_rows.extend(
            {
                "dataset": "paderborn_compound",
                "method": "erm",
                "seed": 11,
                "fold_id": partition.fold_id,
                "row_index": int(record.full_row_index),
                "filename": str(record.filename),
                "bearing_code": str(record.bearing_code),
                "setting_code": str(record.setting_code),
                "measurement_index": int(record.measurement_index),
                "prediction": "healthy",
                "confidence": 1.0,
                "robust_class_support_distance": 0.0,
                "probability_healthy": 1.0,
                "probability_outer": 0.0,
                "probability_inner": 0.0,
                "logit_healthy": 1.0,
                "logit_outer": 0.0,
                "logit_inner": 0.0,
                "representation_00": 1.0,
            }
            for record in compound_index.itertuples(index=False)
        )
    values = {
        "predictions": pd.DataFrame(prediction_rows),
        "compound_predictions": pd.DataFrame(compound_rows),
        "fold_metrics": model_rows,
        "training_traces": model_rows,
    }
    paths = {}
    for name, value in values.items():
        suffix = ".parquet" if isinstance(value, pd.DataFrame) else ".json"
        path = output_directory / f"{name}{suffix}"
        if isinstance(value, pd.DataFrame):
            value.to_parquet(path, index=False)
        else:
            path.write_text(json.dumps(value), encoding="utf-8")
        paths[name] = path
    artifacts = {
        "predictions": {
            "path": paths["predictions"].name,
            "rows": len(values["predictions"]),
            "bytes": paths["predictions"].stat().st_size,
            "sha256": _sha256(paths["predictions"]),
        },
        "compound_predictions": {
            "path": paths["compound_predictions"].name,
            "rows": len(values["compound_predictions"]),
            "bytes": paths["compound_predictions"].stat().st_size,
            "sha256": _sha256(paths["compound_predictions"]),
        },
        "fold_metrics": {
            "path": paths["fold_metrics"].name,
            "folds": len(values["fold_metrics"]),
            "bytes": paths["fold_metrics"].stat().st_size,
            "sha256": _sha256(paths["fold_metrics"]),
        },
        "training_traces": {
            "path": paths["training_traces"].name,
            "models": len(values["training_traces"]),
            "bytes": paths["training_traces"].stat().st_size,
            "sha256": _sha256(paths["training_traces"]),
        },
    }
    metrics = {
        "status": "one_shot_paderborn_prospective_evaluation_complete",
        "input": {
            "expected_manifest_sha256": _sha256(manifest_path),
            "frozen_protocol_sha256": "a" * 64,
            "split_manifest_sha256": "b" * 64,
            "model_fold_manifest_sha256": "c" * 64,
        },
        "configuration": {"method_configurations": {"erm": {"representation_dim": 1}}},
        "access_attestation": {
            "paderborn_model_outcomes_emitted_only_after_all_fits": True,
            "configuration_reselection_performed": False,
            "target_labels_used_for_fitting_selection_or_stopping": False,
            "quarantine_rows_exposed_to_trainer": False,
            "compound_forced_ground_truth_defined": False,
            "compound_accuracy_computed": False,
        },
        "artifacts": artifacts,
    }
    (output_directory / "metrics.json").write_text(json.dumps(metrics), encoding="utf-8")

    result = validate_paderborn_artifacts(
        paderborn_output_directory=output_directory,
        expected_manifest=manifest_path,
        expected_manifest_sha256=_sha256(manifest_path),
        output=tmp_path / "validation.json",
    )

    assert result["status"] == "passed_against_sealed_metadata_only_paderborn_manifest"
    assert result["compound_forced_ground_truth_defined"] is False
