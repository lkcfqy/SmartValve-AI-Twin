from __future__ import annotations

import numpy as np
import pytest

from smartvalve.experiments.selective_scores import (
    energy_uncertainty,
    ensemble_jensen_shannon,
    maximum_softmax_uncertainty,
    negative_max_logit,
    normalized_predictive_entropy,
    pnorm_normalized_max_logit,
)


def test_probability_scores_rank_uniform_prediction_as_more_uncertain() -> None:
    probabilities = np.asarray([[0.99, 0.01], [0.5, 0.5]])

    assert maximum_softmax_uncertainty(probabilities)[1] > (
        maximum_softmax_uncertainty(probabilities)[0]
    )
    assert normalized_predictive_entropy(probabilities)[1] > (
        normalized_predictive_entropy(probabilities)[0]
    )
    assert normalized_predictive_entropy(probabilities)[1] == pytest.approx(1.0)


def test_logit_scores_use_common_higher_means_reject_direction() -> None:
    logits = np.asarray([[5.0, 0.0], [0.0, 0.0]])

    assert energy_uncertainty(logits)[1] > energy_uncertainty(logits)[0]
    assert negative_max_logit(logits)[1] > negative_max_logit(logits)[0]


def test_pnorm_score_is_invariant_to_rowwise_logit_offset() -> None:
    logits = np.asarray([[3.0, 1.0, -2.0], [2.0, -1.0, 0.0]])
    offsets = np.asarray([[100.0], [-75.0]])

    assert pnorm_normalized_max_logit(logits + offsets) == pytest.approx(
        pnorm_normalized_max_logit(logits)
    )


def test_ensemble_disagreement_is_zero_for_copies_and_positive_for_conflict() -> None:
    member = np.asarray([[0.9, 0.1], [0.6, 0.4]])
    identical = np.stack((member, member))
    conflicting = np.stack(
        (
            np.asarray([[0.99, 0.01], [0.6, 0.4]]),
            np.asarray([[0.01, 0.99], [0.6, 0.4]]),
        )
    )

    assert ensemble_jensen_shannon(identical) == pytest.approx([0.0, 0.0])
    assert ensemble_jensen_shannon(conflicting)[0] > 0
    assert ensemble_jensen_shannon(conflicting)[1] == pytest.approx(0.0)


def test_scores_reject_malformed_inputs() -> None:
    with pytest.raises(ValueError, match="normalized"):
        maximum_softmax_uncertainty(np.asarray([[0.8, 0.8]]))
    with pytest.raises(ValueError, match="temperature"):
        energy_uncertainty(np.asarray([[1.0, 0.0]]), temperature=0)
    with pytest.raises(ValueError, match="M x N x C"):
        ensemble_jensen_shannon(np.asarray([[0.5, 0.5]]))
