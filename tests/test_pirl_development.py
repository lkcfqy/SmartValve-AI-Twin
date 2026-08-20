from __future__ import annotations

import numpy as np
import pytest

pytest.importorskip("torch")

from smartvalve.experiments.pirl_development import (  # noqa: E402
    _aggregate_folds,
    _macro_f1,
    _multiclass_brier,
    _risk_coverage,
)


def test_development_metrics_recover_perfect_predictions() -> None:
    truth = np.asarray([0, 1, 2, 0, 1, 2])
    probabilities = np.eye(3)[truth]
    scores = np.linspace(0.0, 1.0, len(truth))

    assert _macro_f1(truth, truth, 3) == pytest.approx(1.0)
    assert _multiclass_brier(truth, probabilities, 3) == pytest.approx(0.0)
    assert _risk_coverage(truth, truth, scores) == pytest.approx((0.0, 0.0))


def test_risk_coverage_rewards_ranking_errors_last() -> None:
    truth = np.asarray([0, 0, 0, 0])
    prediction = np.asarray([0, 0, 1, 1])

    good_aurc, good_half = _risk_coverage(
        truth, prediction, np.asarray([0.1, 0.2, 0.8, 0.9])
    )
    bad_aurc, bad_half = _risk_coverage(
        truth, prediction, np.asarray([0.8, 0.9, 0.1, 0.2])
    )

    assert good_aurc < bad_aurc
    assert good_half == pytest.approx(0.0)
    assert bad_half == pytest.approx(1.0)


def test_fold_aggregation_is_unweighted_and_preserves_worst_fold() -> None:
    base = {
        "accuracy": 0.9,
        "macro_f1": 0.8,
        "multiclass_brier": 0.2,
        "aurc": 0.1,
        "risk_at_50pct": 0.0,
        "source_representation_response_ratio": 0.3,
        "source_probability_response_ratio": 0.4,
    }
    second = {**base, "accuracy": 0.5, "macro_f1": 0.2}

    result = _aggregate_folds([base, second])

    assert result["mean_fold_accuracy"] == pytest.approx(0.7)
    assert result["mean_fold_macro_f1"] == pytest.approx(0.5)
    assert result["worst_fold_macro_f1"] == pytest.approx(0.2)
