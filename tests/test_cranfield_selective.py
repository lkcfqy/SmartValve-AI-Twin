from __future__ import annotations

import pandas as pd
import pytest

from smartvalve.experiments.cranfield_causal_audit import LABELS, LOADS, MOTIONS
from smartvalve.experiments.cranfield_selective import (
    _apply_policy,
    _summary,
    conformal_quantile,
    metadata_support_ratio,
    selection_metrics,
)


def _base_records() -> pd.DataFrame:
    rows = []
    for motion in MOTIONS:
        for load_kg in LOADS:
            for truth in LABELS:
                base_prediction = "normal"
                rows.append(
                    {
                        "motion": motion,
                        "load_kg": load_kg,
                        "repetition": 1,
                        "truth": truth,
                        "base_prediction": base_prediction,
                        "base_correct": base_prediction == truth,
                        "conformal_set_size": 1,
                        "conformal_singleton_label": base_prediction,
                        "metadata_supported": load_kg != -40,
                    }
                )
    return pd.DataFrame(rows)


def test_conformal_quantile_uses_finite_sample_upper_rank() -> None:
    scores = [0.9, 0.1, 0.8, 0.2, 0.7, 0.3, 0.6, 0.4, 0.5]

    assert conformal_quantile(scores, alpha=0.1) == pytest.approx(0.9)
    assert conformal_quantile(scores, alpha=0.2) == pytest.approx(0.8)
    with pytest.raises(ValueError, match="non-empty"):
        conformal_quantile([])


def test_metadata_support_ratio_distinguishes_interpolation_and_extrapolation() -> None:
    assert metadata_support_ratio(-40, (20, 40)) == pytest.approx(3.0)
    assert metadata_support_ratio(20, (-40, 40)) == pytest.approx(0.0)
    assert metadata_support_ratio(40, (-40, 20)) == pytest.approx(1.0 / 3.0)
    with pytest.raises(ValueError, match="distinct"):
        metadata_support_ratio(20, (20, 20))


def test_hybrid_policy_requires_both_source_evidence_and_metadata_support() -> None:
    base = _base_records()
    base.loc[base["load_kg"] == 40, "conformal_set_size"] = 2

    records = _apply_policy(base, "hybrid")

    assert records.loc[records["load_kg"] == 20, "accepted"].all()
    assert not records.loc[records["load_kg"].isin((-40, 40)), "accepted"].any()
    assert set(records.loc[~records["accepted"], "selective_prediction"]) == {"abstain"}


def test_zero_coverage_is_explicit_and_never_perfect() -> None:
    records = _apply_policy(_base_records(), "metadata_support")
    records["accepted"] = False
    records["selective_prediction"] = "abstain"
    records["selective_correct"] = False

    metrics = selection_metrics(records)

    assert metrics["coverage"] == pytest.approx(0.0)
    assert metrics["selective_accuracy"] is None
    assert metrics["worst_nonempty_fold_selective_accuracy"] is None
    assert metrics["accepted_errors"] == 0
    assert metrics["error_detection_recall"] == pytest.approx(1.0)
    assert len(metrics["zero_coverage_folds"]) == len(MOTIONS) * len(LOADS)

    summary = _summary([metrics, metrics])
    assert summary["selective_accuracy"] is None
    assert summary["worst_nonempty_fold_selective_accuracy"] is None
