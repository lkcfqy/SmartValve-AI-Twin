from __future__ import annotations

import numpy as np
import pytest

torch = pytest.importorskip("torch")

from smartvalve.experiments.domain_data import SourceOnlyFold  # noqa: E402
from smartvalve.experiments.pirl_sore import (  # noqa: E402
    TrainingConfig,
    fit_class_support,
    fit_fold,
    intervention_loss,
    predict,
    response_ratio_loss,
    risk_envelope_score,
    robust_class_distance,
)


def test_intervention_loss_has_expected_direction() -> None:
    representation = torch.tensor(
        [[1.0, 0.0], [1.0, 0.0], [0.0, 1.0], [1.0, 0.0]]
    )

    good, good_nuisance, good_fault = intervention_loss(
        representation,
        torch.tensor([[0, 1]]),
        torch.tensor([[0, 2]]),
        rho=0.5,
    )
    bad, bad_nuisance, bad_fault = intervention_loss(
        representation,
        torch.tensor([[0, 2]]),
        torch.tensor([[0, 3]]),
        rho=0.5,
    )

    assert good.item() == pytest.approx(0.0)
    assert good_nuisance.item() == pytest.approx(0.0)
    assert good_fault.item() == pytest.approx(2.0)
    assert bad.item() == pytest.approx(2.0)
    assert bad_nuisance.item() == pytest.approx(2.0)
    assert bad_fault.item() == pytest.approx(0.0)


def test_ablation_method_names_switch_only_the_declared_loss_terms() -> None:
    assert TrainingConfig(method="erm").effective_loss_weights() == (0.0, 0.0)
    assert TrainingConfig(method="worst_erm").effective_loss_weights() == (0.0, 0.5)
    assert TrainingConfig(method="pirl_only").effective_loss_weights() == (0.5, 0.0)
    assert TrainingConfig(method="pirl_sore").effective_loss_weights() == (0.5, 0.5)
    assert TrainingConfig(method="pirl_ratio").effective_loss_weights() == (0.5, 0.0)


def test_response_ratio_loss_is_nonzero_after_hinge_would_saturate() -> None:
    representation = torch.tensor(
        [[1.0, 0.0], [0.9, 0.1], [0.0, 1.0], [0.1, 0.9]]
    )

    ratio_loss, nuisance, fault = response_ratio_loss(
        representation,
        torch.tensor([[0, 1]]),
        torch.tensor([[0, 2], [1, 3]]),
        fault_margin=1.0,
        ratio_term_weight=1.0,
        fault_margin_weight=1.0,
        epsilon=1e-4,
    )

    assert nuisance.item() > 0
    assert fault.item() > 1.0
    assert ratio_loss.item() > 0
    assert ratio_loss.item() == pytest.approx(
        nuisance.item() / (fault.item() + 1e-4)
    )


def test_response_ratio_components_can_be_ablated_independently() -> None:
    representation = torch.tensor(
        [[1.0, 0.0], [0.8, 0.2], [0.7, 0.3], [0.6, 0.4]]
    )
    nuisance_pairs = torch.tensor([[0, 1]])
    fault_pairs = torch.tensor([[2, 3]])

    ratio_only, nuisance, fault = response_ratio_loss(
        representation,
        nuisance_pairs,
        fault_pairs,
        fault_margin=1.0,
        ratio_term_weight=1.0,
        fault_margin_weight=0.0,
        epsilon=1e-4,
    )
    margin_only, _, _ = response_ratio_loss(
        representation,
        nuisance_pairs,
        fault_pairs,
        fault_margin=1.0,
        ratio_term_weight=0.0,
        fault_margin_weight=1.0,
        epsilon=1e-4,
    )

    assert ratio_only.item() == pytest.approx(
        nuisance.item() / (fault.item() + 1e-4)
    )
    assert margin_only.item() == pytest.approx(max(0.0, 1.0 - fault.item()))


def _synthetic_fold() -> SourceOnlyFold:
    rng = np.random.default_rng(91)
    labels = np.concatenate(
        (
            np.tile(np.arange(3), 15),
            np.tile(np.arange(3), 15),
            np.tile(np.arange(3), 10),
        )
    )
    contexts = np.repeat(np.arange(3), (45, 45, 30))
    features = np.column_stack(
        (
            labels + rng.normal(0, 0.05, len(labels)),
            contexts * 2.0 + rng.normal(0, 0.05, len(labels)),
            rng.normal(0, 0.1, len(labels)),
        )
    ).astype(np.float32)
    source_indices = np.arange(90)
    target_indices = np.arange(90, 120)
    source_labels = labels[source_indices]
    nuisance_pairs = np.asarray(
        [
            [left, right]
            for left in range(45)
            for right in range(45, 90)
            if source_labels[left] == source_labels[right]
        ],
        dtype=np.int64,
    )
    fault_pairs = np.asarray(
        [
            [left, right]
            for left in range(89)
            for right in range(left + 1, 90)
            if source_labels[left] != source_labels[right]
            and contexts[left] == contexts[right]
        ],
        dtype=np.int64,
    )
    fold = SourceOnlyFold(
        dataset="synthetic",
        fold_id="context=target",
        held_factor="context",
        held_level=2,
        features=features,
        labels=labels.astype(np.int64),
        label_names=("a", "b", "c"),
        feature_names=("label_signal", "context_signal", "noise"),
        environment_ids=np.asarray([f"e{value}" for value in contexts]),
        block_ids=np.asarray([f"b{index}" for index in range(len(labels))]),
        source_indices=source_indices,
        target_indices=target_indices,
        nuisance_pairs=nuisance_pairs,
        fault_pairs=fault_pairs,
    )
    fold.validate()
    return fold


def test_training_is_deterministic_and_predictions_are_normalized() -> None:
    fold = _synthetic_fold()
    config = TrainingConfig(
        representation_dim=8,
        hidden_dim=16,
        epochs=30,
        learning_rate=5e-3,
        seed=17,
    )

    first = fit_fold(fold, config, device="cpu")
    second = fit_fold(fold, config, device="cpu")
    first_prediction = predict(first, fold.target_features)
    second_prediction = predict(second, fold.target_features)

    assert first.state_sha256 == second.state_sha256
    assert np.array_equal(first_prediction.logits, second_prediction.logits)
    assert np.array_equal(first_prediction.probabilities, second_prediction.probabilities)
    assert first_prediction.logits.shape == first_prediction.probabilities.shape
    assert first_prediction.probabilities.sum(axis=1) == pytest.approx(1.0)
    assert np.isfinite(first_prediction.representations).all()
    assert np.linalg.norm(first_prediction.representations, axis=1) == pytest.approx(1.0)


def test_robust_support_distance_and_risk_score_are_finite() -> None:
    representations = np.asarray(
        [[0.0, 0.0], [0.1, 0.0], [2.0, 2.0], [2.1, 2.0]], dtype=float
    )
    labels = np.asarray([0, 0, 1, 1])
    support = fit_class_support(representations, labels, class_count=2)
    distances = robust_class_distance(np.asarray([[0.05, 0.0], [2.05, 2.0]]), support)
    probabilities = np.asarray([[0.9, 0.1], [0.2, 0.8]])
    scores = risk_envelope_score(
        probabilities,
        np.asarray([[0.05, 0.0], [2.05, 2.0]]),
        support,
        beta=0.25,
    )

    assert distances.shape == (2, 2)
    assert distances[0, 0] < distances[0, 1]
    assert distances[1, 1] < distances[1, 0]
    assert scores.shape == (2,)
    assert np.isfinite(scores).all()
