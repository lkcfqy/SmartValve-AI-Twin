from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from smartvalve.experiments.domain_data import SourceOnlyFold
from smartvalve.experiments.pirl_ratio_ablation import (
    ABLATION_ARMS,
    AUDIT_SEEDS,
    REFERENCE_HASHES,
    validate_execution_authorization,
)
from smartvalve.experiments.pirl_ratio_ablation_artifact_validation import (
    _maximum_probability_error,
    validate_ablation_artifacts,
)
from smartvalve.experiments.pirl_ratio_ablation_expected_manifest import (
    MANIFEST_VERSION,
    build_expected_ablation_manifest,
)


def _fold(dataset: str) -> SourceOnlyFold:
    return SourceOnlyFold(
        dataset=dataset,
        fold_id="held=0",
        held_factor="context",
        held_level=0,
        features=np.asarray(
            [[0.0], [1.0], [2.0], [3.0], [4.0], [5.0]], dtype=np.float32
        ),
        labels=np.asarray([0, 0, 1, 1, 0, 1], dtype=np.int64),
        label_names=("healthy", "fault"),
        feature_names=("x",),
        environment_ids=np.asarray(["a", "b", "a", "b", "c", "c"]),
        block_ids=np.asarray(["a0", "b0", "a1", "b1", "c0", "c1"]),
        source_indices=np.asarray([0, 1, 2, 3], dtype=np.int64),
        target_indices=np.asarray([4, 5], dtype=np.int64),
        nuisance_pairs=np.asarray([[0, 1]], dtype=np.int64),
        fault_pairs=np.asarray([[0, 2]], dtype=np.int64),
    )


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_ablation_manifest_is_outcome_blind_and_has_exact_keys() -> None:
    manifest = build_expected_ablation_manifest(
        {
            "cranfield": [_fold("cranfield")],
            "uci_hydraulic": [_fold("uci_hydraulic")],
        },
        uci_feature_matrix="features.parquet",
        uci_feature_matrix_sha256="a" * 64,
        protocol_document="protocol.md",
        protocol_document_sha256="b" * 64,
        reference_directory="reference",
        arms=("erm", "ratio"),
        seeds=(11, 23),
    )

    assert manifest["expected_key_sets"]["training_models"]["count"] == 8
    assert manifest["expected_key_sets"]["target_predictions"]["count"] == 16
    assert set(manifest["expected_key_sets"]) == {
        "training_models",
        "target_predictions",
    }
    assert "results" not in manifest
    assert "contains no" in manifest["role"]


def test_ablation_probability_validator_rejects_nonfinite_or_unnormalized() -> None:
    frame = pd.DataFrame(
        {
            "dataset": ["d", "d"],
            "method": ["ratio_only", "ratio_only"],
            "seed": [11, 11],
            "fold_id": ["f", "f"],
            "probability_a": [0.8, 0.3],
            "probability_b": [0.2, 0.7],
        }
    )
    assert _maximum_probability_error(frame) == pytest.approx(0.0)
    frame.loc[0, "probability_a"] = 0.9
    with pytest.raises(ValueError, match="not normalized"):
        _maximum_probability_error(frame)


def _authorization_fixture(tmp_path: Path) -> dict[str, object]:
    uci = tmp_path / "features.parquet"
    protocol = tmp_path / "protocol.md"
    manifest_path = tmp_path / "manifest.json"
    reference = tmp_path / "reference"
    reference.mkdir()
    uci.write_bytes(b"frozen UCI features")
    uci_hash = _sha256(uci)
    protocol.write_text(
        "\n".join(
            (
                uci_hash,
                *REFERENCE_HASHES.values(),
                "195 model keys",
                "67,500",
            )
        ),
        encoding="utf-8",
    )
    protocol_hash = _sha256(protocol)
    manifest_path.write_text(
        json.dumps(
            {
                "manifest_version": MANIFEST_VERSION,
                "input": {
                    "uci_feature_matrix": str(uci.resolve()),
                    "uci_feature_matrix_sha256": uci_hash,
                    "protocol_document": str(protocol.resolve()),
                    "protocol_document_sha256": protocol_hash,
                    "reference_directory": str(reference.resolve()),
                    "reference_hashes": REFERENCE_HASHES,
                    "paderborn_archive_contents_opened": False,
                },
                "configuration": {
                    "arms": list(ABLATION_ARMS),
                    "seeds": list(AUDIT_SEEDS),
                    "epochs": 300,
                },
                "expected_key_sets": {
                    "training_models": {"count": 195},
                    "target_predictions": {"count": 67_500},
                },
            }
        ),
        encoding="utf-8",
    )
    return {
        "uci_feature_matrix": uci,
        "uci_feature_matrix_sha256": uci_hash,
        "protocol_document": protocol,
        "protocol_sha256": protocol_hash,
        "expected_manifest": manifest_path,
        "expected_manifest_sha256": _sha256(manifest_path),
        "reference_directory": reference,
    }


def test_ablation_execution_requires_exact_protocol_and_manifest(tmp_path: Path) -> None:
    arguments = _authorization_fixture(tmp_path)

    observed = validate_execution_authorization(**arguments)  # type: ignore[arg-type]

    assert observed["uci_feature_matrix"] == arguments["uci_feature_matrix_sha256"]
    protocol = arguments["protocol_document"]
    assert isinstance(protocol, Path)
    protocol.write_text("changed", encoding="utf-8")
    with pytest.raises(ValueError, match="protocol_document SHA-256 mismatch"):
        validate_execution_authorization(**arguments)  # type: ignore[arg-type]


def test_ablation_validator_checks_complete_package(tmp_path: Path) -> None:
    datasets = {
        "cranfield": [_fold("cranfield")],
        "uci_hydraulic": [_fold("uci_hydraulic")],
    }
    manifest = build_expected_ablation_manifest(
        datasets,
        uci_feature_matrix="features.parquet",
        uci_feature_matrix_sha256="a" * 64,
        protocol_document="protocol.md",
        protocol_document_sha256="b" * 64,
        reference_directory="reference",
        arms=("ratio_only",),
        seeds=(11,),
    )
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    output_directory = tmp_path / "ablation"
    output_directory.mkdir()
    prediction_rows = []
    traces = []
    for dataset, folds in datasets.items():
        fold = folds[0]
        traces.append(
            {
                "dataset": dataset,
                "method": "ratio_only",
                "seed": 11,
                "fold_id": fold.fold_id,
            }
        )
        for row_index in fold.target_indices:
            prediction_rows.append(
                {
                    "dataset": dataset,
                    "method": "ratio_only",
                    "seed": 11,
                    "fold_id": fold.fold_id,
                    "row_index": int(row_index),
                    "probability_healthy": 0.6,
                    "probability_fault": 0.4,
                }
            )
    predictions = pd.DataFrame(prediction_rows)
    predictions_path = output_directory / "predictions.parquet"
    traces_path = output_directory / "training_traces.json"
    predictions.to_parquet(predictions_path, index=False)
    traces_path.write_text(json.dumps(traces), encoding="utf-8")
    metrics = {
        "input": {
            "uci_feature_matrix_sha256": manifest["input"][
                "uci_feature_matrix_sha256"
            ],
            "protocol_document_sha256": manifest["input"][
                "protocol_document_sha256"
            ],
            "expected_manifest_sha256": _sha256(manifest_path),
            "reference_hashes": manifest["input"]["reference_hashes"],
            "paderborn_archive_contents_opened": False,
        },
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
        json.dumps(metrics), encoding="utf-8"
    )

    result = validate_ablation_artifacts(
        ablation_output_directory=output_directory,
        expected_manifest=manifest_path,
        expected_manifest_sha256=_sha256(manifest_path),
        output=tmp_path / "validation.json",
    )

    assert result["status"] == "passed_against_outcome_blind_ablation_manifest"
    assert result["observed_key_sets"] == manifest["expected_key_sets"]
