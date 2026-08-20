from __future__ import annotations

from dataclasses import replace

import numpy as np
import pytest

torch = pytest.importorskip("torch")

from smartvalve.experiments.dg_training import (  # noqa: E402
    BASELINE_METHODS,
    BaselineConfig,
    fit_dg_fold,
    predict_dg,
)
from smartvalve.experiments.domain_data import SourceOnlyFold  # noqa: E402


def _fold() -> SourceOnlyFold:
    rng = np.random.default_rng(19)
    labels = np.concatenate(
        (
            np.tile(np.arange(3), 6),
            np.tile(np.arange(3), 6),
            np.tile(np.arange(3), 3),
        )
    )
    environments = np.repeat(np.arange(3), (18, 18, 9))
    features = np.column_stack(
        (
            labels + rng.normal(0, 0.1, len(labels)),
            environments + rng.normal(0, 0.1, len(labels)),
            rng.normal(0, 0.1, len(labels)),
        )
    ).astype(np.float32)
    source_indices = np.arange(36)
    target_indices = np.arange(36, 45)
    nuisance = np.asarray(
        [
            [left, right]
            for left in range(18)
            for right in range(18, 36)
            if labels[left] == labels[right]
        ],
        dtype=np.int64,
    )
    fault = np.asarray(
        [
            [left, right]
            for left in range(35)
            for right in range(left + 1, 36)
            if environments[left] == environments[right]
            and labels[left] != labels[right]
        ],
        dtype=np.int64,
    )
    fold = SourceOnlyFold(
        dataset="synthetic",
        fold_id="environment=2",
        held_factor="environment",
        held_level=2,
        features=features,
        labels=labels.astype(np.int64),
        label_names=("a", "b", "c"),
        feature_names=("label", "environment", "noise"),
        environment_ids=np.asarray([f"e{value}" for value in environments]),
        block_ids=np.asarray([f"b{index}" for index in range(len(labels))]),
        source_indices=source_indices,
        target_indices=target_indices,
        nuisance_pairs=nuisance,
        fault_pairs=fault,
    )
    fold.validate()
    return fold


@pytest.mark.parametrize("method", BASELINE_METHODS)
def test_all_dg_baselines_fit_and_emit_normalized_probabilities(method: str) -> None:
    fold = _fold()
    config = BaselineConfig(
        method=method,
        representation_dim=8,
        hidden_dim=12,
        epochs=3,
        penalty_weight=0.1,
        seed=7,
    )

    fitted = fit_dg_fold(fold, config, device="cpu")
    prediction = predict_dg(fitted, fold.target_features)

    assert len(fitted.history) == 2
    assert len(fitted.state_sha256) == 64
    assert prediction.logits.shape == (9, 3)
    assert prediction.probabilities.shape == (9, 3)
    assert prediction.probabilities.sum(axis=1) == pytest.approx(1.0)
    assert np.isfinite(prediction.representations).all()
    if method == "dann":
        assert fitted.auxiliary_state_sha256 is not None
    else:
        assert fitted.auxiliary_state_sha256 is None


def test_erm_is_independent_of_unused_penalty_weight() -> None:
    fold = _fold()
    first = fit_dg_fold(
        fold,
        BaselineConfig(method="erm", epochs=3, penalty_weight=0.0, seed=13),
        device="cpu",
    )
    second = fit_dg_fold(
        fold,
        BaselineConfig(method="erm", epochs=3, penalty_weight=9.0, seed=13),
        device="cpu",
    )

    assert first.state_sha256 == second.state_sha256


@pytest.mark.parametrize("method", BASELINE_METHODS)
def test_dg_fit_is_invariant_to_target_features_and_labels(method: str) -> None:
    fold = _fold()
    changed_features = fold.features.copy()
    changed_labels = fold.labels.copy()
    changed_features[fold.target_indices] = (
        1000.0 + changed_features[fold.target_indices, ::-1]
    )
    changed_labels[fold.target_indices] = changed_labels[fold.target_indices][::-1]
    target_changed = replace(
        fold,
        features=changed_features,
        labels=changed_labels,
    )
    config = BaselineConfig(
        method=method,
        representation_dim=8,
        hidden_dim=12,
        epochs=1,
        penalty_weight=0.1,
        seed=29,
    )

    original = fit_dg_fold(fold, config, device="cpu")
    changed = fit_dg_fold(target_changed, config, device="cpu")

    assert original.state_sha256 == changed.state_sha256
    assert original.auxiliary_state_sha256 == changed.auxiliary_state_sha256
