from __future__ import annotations

from types import SimpleNamespace

import numpy as np
import pytest

from smartvalve.experiments.domain_data import SourceOnlyFold
from smartvalve.experiments.selective_expected_manifest import (
    build_expected_selective_manifest,
)


def _fold(dataset: str) -> SourceOnlyFold:
    fold = SourceOnlyFold(
        dataset=dataset,
        fold_id="context=1",
        held_factor="context",
        held_level=1,
        features=np.arange(12, dtype=np.float32).reshape(6, 2),
        labels=np.array([0, 0, 1, 1, 0, 1]),
        label_names=("healthy", "fault"),
        feature_names=("a", "b"),
        environment_ids=np.array(["s0", "s1", "s0", "s1", "t", "t"]),
        block_ids=np.array(["b0", "b1", "b2", "b3", "b4", "b5"]),
        source_indices=np.array([0, 1, 2, 3]),
        target_indices=np.array([4, 5]),
        nuisance_pairs=np.array([[0, 1], [2, 3]]),
        fault_pairs=np.array([[0, 2], [1, 3]]),
    )
    fold.validate()
    return fold


def test_selective_manifest_locks_every_artifact_key_set(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "smartvalve.experiments.selective_expected_manifest.build_inner_splits",
        lambda fold: [SimpleNamespace(split_id=f"inner={index}") for index in range(4)],
    )
    monkeypatch.setattr(
        "smartvalve.experiments.selective_expected_manifest.AUDIT_SEEDS", (11, 23)
    )
    manifest = build_expected_selective_manifest(
        {"cranfield": [_fold("cranfield")], "uci_hydraulic": [_fold("uci_hydraulic")]},
        uci_feature_matrix="features.parquet",
        uci_feature_matrix_sha256="a" * 64,
        pirl_metrics_sha256="b" * 64,
        dg_metrics_sha256="c" * 64,
    )

    expected = manifest["expected_key_sets"]
    assert expected["source_oof_predictions"]["count"] == 32
    assert expected["target_predictions"]["count"] == 16
    assert expected["source_oof_ensemble_predictions"]["count"] == 16
    assert expected["target_ensemble_predictions"]["count"] == 8
    assert expected["policies"]["count"] == 228
    assert expected["beta_selections"]["count"] == 12
    assert expected["policy_metrics"]["count"] == 228
    assert expected["ranking_metrics"]["count"] == 76
    assert expected["selection_decisions"]["count"] == 456
    assert expected["training_models"]["count"] == 40
    assert expected["reference_crosschecks"]["count"] == 8
    assert all(len(record["sha256"]) == 64 for record in expected.values())
    assert manifest["input"]["paderborn_archive_contents_opened"] is False


def test_selective_manifest_rejects_wrong_dataset_roles() -> None:
    with pytest.raises(ValueError, match="exactly Cranfield"):
        build_expected_selective_manifest(
            {"cranfield": [_fold("cranfield")]},
            uci_feature_matrix="features.parquet",
            uci_feature_matrix_sha256="a" * 64,
            pirl_metrics_sha256="b" * 64,
            dg_metrics_sha256="c" * 64,
        )
