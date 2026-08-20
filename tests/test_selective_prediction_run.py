from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from smartvalve.experiments.domain_data import SourceOnlyFold
from smartvalve.experiments.pirl_sore import PredictionBundle
from smartvalve.experiments.selective_prediction_run import (
    _prediction_records,
    reference_crosscheck,
    validate_execution_authorization,
)


def _fold() -> SourceOnlyFold:
    return SourceOnlyFold(
        dataset="fixture",
        fold_id="context=1",
        held_factor="context",
        held_level=1,
        features=np.asarray([[0.0], [1.0], [2.0], [3.0]], dtype=np.float32),
        labels=np.asarray([0, 1, 0, 1]),
        label_names=("healthy", "fault"),
        feature_names=("x",),
        environment_ids=np.asarray(["a", "a", "b", "b"]),
        block_ids=np.asarray(["a0", "a1", "b0", "b1"]),
        source_indices=np.asarray([0, 1]),
        target_indices=np.asarray([2, 3]),
        nuisance_pairs=np.asarray([[0, 1]]),
        fault_pairs=np.asarray([[0, 1]]),
    )


def test_prediction_records_preserve_global_row_and_score_inputs() -> None:
    fold = _fold()
    probabilities = np.asarray([[0.8, 0.2], [0.3, 0.7]], dtype=np.float32)
    bundle = PredictionBundle(
        logits=np.log(probabilities),
        probabilities=probabilities,
        predictions=np.asarray([0, 1]),
        representations=np.asarray([[1.0, 2.0], [3.0, 4.0]], dtype=np.float32),
    )

    records = _prediction_records(
        fold,
        bundle,
        np.asarray([0.25, 0.5]),
        method="erm",
        seed=11,
        row_indices=fold.target_indices,
        environments=fold.target_environments,
        inner_split_id=None,
    )

    assert records["row_index"].tolist() == [2, 3]
    assert records["truth"].tolist() == ["healthy", "fault"]
    assert records["correct"].all()
    assert records["logit_fault"].tolist() == pytest.approx(
        np.log(probabilities)[:, 1]
    )


def test_reference_crosscheck_rejects_probability_drift() -> None:
    observed = pd.DataFrame(
        {
            "dataset": ["fixture"],
            "method": ["erm"],
            "seed": [11],
            "fold_id": ["context=1"],
            "row_index": [2],
            "truth": ["healthy"],
            "prediction": ["healthy"],
            "correct": [True],
            "probability_fault": [0.2],
            "probability_healthy": [0.8],
        }
    )
    reference = observed.copy()

    result = reference_crosscheck(observed, reference)
    assert result["maximum_absolute_probability_difference"] == pytest.approx(0.0)

    reference.loc[0, "probability_fault"] = 0.3
    with pytest.raises(ValueError, match="probability crosscheck failed"):
        reference_crosscheck(observed, reference, tolerance=1e-4)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _authorization_fixture(tmp_path: Path) -> dict[str, object]:
    uci = tmp_path / "features.parquet"
    uci.write_bytes(b"frozen-feature-matrix")
    pirl = tmp_path / "pirl"
    dg = tmp_path / "dg"
    pirl.mkdir()
    dg.mkdir()
    uci_hash = _sha256(uci)
    pirl_hash = "a" * 64
    dg_hash = "b" * 64
    protocol = tmp_path / "protocol.md"
    protocol.write_text(
        f"# frozen v0.1\n{uci_hash}\n{pirl_hash}\n{dg_hash}\n", encoding="utf-8"
    )
    preflight = tmp_path / "preflight.json"
    preflight.write_text(
        json.dumps(
            {
                "status": "locked_selective_inputs_validated_before_refit",
                "inputs": {
                    "uci_feature_matrix": str(uci.resolve()),
                    "uci_feature_matrix_sha256": uci_hash,
                    "pirl_reference_directory": str(pirl.resolve()),
                    "dg_reference_directory": str(dg.resolve()),
                    "pirl_metrics_sha256": pirl_hash,
                    "dg_metrics_sha256": dg_hash,
                },
                "access_attestation": {
                    "target_outcomes_used_for_configuration_selection": False,
                    "paderborn_archive_path_supplied": False,
                    "paderborn_archive_contents_opened": False,
                },
            }
        ),
        encoding="utf-8",
    )
    manifest = tmp_path / "manifest.json"
    manifest.write_text(
        json.dumps(
            {
                "manifest_version": "selective-expected-key-manifest-0.1.0",
                "input": {
                    "uci_feature_matrix_sha256": uci_hash,
                    "pirl_metrics_sha256": pirl_hash,
                    "dg_metrics_sha256": dg_hash,
                    "paderborn_archive_contents_opened": False,
                },
            }
        ),
        encoding="utf-8",
    )
    return {
        "uci_feature_matrix": uci,
        "uci_feature_matrix_sha256": uci_hash,
        "pirl_reference_directory": pirl,
        "dg_reference_directory": dg,
        "pirl_metrics_sha256": pirl_hash,
        "dg_metrics_sha256": dg_hash,
        "protocol_document": protocol,
        "protocol_sha256": _sha256(protocol),
        "input_preflight": preflight,
        "input_preflight_sha256": _sha256(preflight),
        "expected_manifest": manifest,
        "expected_manifest_sha256": _sha256(manifest),
    }


def test_selective_run_requires_all_frozen_authorization_artifacts(
    tmp_path: Path,
) -> None:
    arguments = _authorization_fixture(tmp_path)

    hashes = validate_execution_authorization(**arguments)  # type: ignore[arg-type]

    assert hashes["uci_feature_matrix"] == arguments["uci_feature_matrix_sha256"]
    assert hashes["protocol_document"] == arguments["protocol_sha256"]


def test_selective_run_rejects_changed_authorization_artifact(tmp_path: Path) -> None:
    arguments = _authorization_fixture(tmp_path)
    manifest = arguments["expected_manifest"]
    assert isinstance(manifest, Path)
    manifest.write_text("{}", encoding="utf-8")

    with pytest.raises(ValueError, match="expected_manifest SHA-256 mismatch"):
        validate_execution_authorization(**arguments)  # type: ignore[arg-type]
