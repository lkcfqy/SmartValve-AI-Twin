from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from smartvalve.experiments.cranfield_baselines import (
    ESTIMATORS,
    _fit_classifier,
    _model_independence,
    _probe_seed_metrics,
    classifier_for,
    probe_feature_frame,
)
from smartvalve.experiments.cranfield_causal_audit import (
    LABELS,
    LOADS,
    _aligned_probabilities,
)


def test_frozen_estimators_fit_and_emit_aligned_probabilities() -> None:
    features = pd.DataFrame(
        {
            "a": np.linspace(-1.0, 1.0, 12),
            "b": np.tile([0.0, 1.0, 2.0], 4),
        }
    )
    truth = pd.Series(list(LABELS) * 4)

    for estimator_name in ESTIMATORS:
        classifier = classifier_for(estimator_name, seed=11)
        _fit_classifier(classifier, estimator_name, features, truth)
        probabilities = _aligned_probabilities(classifier, features)

        assert probabilities.shape == (len(features), len(LABELS))
        assert probabilities.sum(axis=1) == pytest.approx(np.ones(len(features)))

    with pytest.raises(ValueError, match="unknown estimator"):
        classifier_for("future_model", seed=11)


def _probe_raw() -> pd.DataFrame:
    rows = []
    for load_kg in LOADS:
        for repetition in (1, 2, 3):
            for truth_index, truth in enumerate(("normal", "backlash")):
                rows.append(
                    {
                        "motion": "trap",
                        "load_kg": load_kg,
                        "repetition": repetition,
                        "truth": truth,
                        "f": load_kg + 10 * repetition + truth_index,
                    }
                )
    return pd.DataFrame(rows)


def test_probe_p2_never_reads_held_or_same_repetition_as_reference() -> None:
    raw = _probe_raw()

    features, baseline_repetitions = probe_feature_frame(
        raw,
        "P2",
        "trap",
        held_out_repetition=2,
        feature_columns=["f"],
    )

    assert list(features.columns) == ["delta_f", "relative_f"]
    assert 2 not in baseline_repetitions
    for row_index, baseline_repetition in zip(
        features.index, baseline_repetitions, strict=True
    ):
        assert baseline_repetition != raw.loc[row_index, "repetition"]


def test_perfect_probe_predictions_have_perfect_metrics() -> None:
    rows = [
        {
            "motion": motion,
            "truth_load_kg": load_kg,
            "predicted_load_kg": load_kg,
        }
        for motion in ("trap", "sin")
        for load_kg in LOADS
    ]

    result = _probe_seed_metrics(pd.DataFrame(rows))

    assert result["accuracy"] == pytest.approx(1.0)
    assert result["macro_f1"] == pytest.approx(1.0)
    assert result["per_motion"]["trap"]["macro_f1"] == pytest.approx(1.0)


def test_model_independence_requires_three_estimator_families() -> None:
    results = {"P0": {}}
    for estimator_index, estimator_name in enumerate(ESTIMATORS):
        failed_seeds = [11, 23, 37, 53, 71] if estimator_index < 3 else [11]
        results["P0"][estimator_name] = {
            "summary": {
                "folds": [
                    {
                        "motion": "trap",
                        "held_out_load_kg": -40,
                        "chance_level_or_worse_seeds": failed_seeds,
                    }
                ]
            }
        }

    result = _model_independence(results)

    assert result["criterion_met"] is True
    assert result["corroborated_folds"][0]["estimator_count"] == 3
