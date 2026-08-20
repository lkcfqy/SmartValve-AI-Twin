from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from smartvalve.experiments.cranfield_bootstrap import (
    _control_sample,
    _interval,
    _performance_metrics,
    _performance_sample,
)
from smartvalve.experiments.cranfield_causal_audit import LABELS, LOADS, MOTIONS


def _synthetic_records() -> pd.DataFrame:
    rows = []
    for protocol in ("P0", "P1"):
        for seed in (11,):
            for motion in MOTIONS:
                for load_kg in LOADS:
                    for repetition in (1, 2):
                        for truth_index, truth in enumerate(LABELS):
                            rows.append(
                                {
                                    "protocol": protocol,
                                    "seed": seed,
                                    "motion": motion,
                                    "load_kg": load_kg,
                                    "repetition": repetition,
                                    "truth": truth,
                                    "prediction": truth,
                                    **{
                                        f"probability_{label}": float(index == truth_index)
                                        for index, label in enumerate(LABELS)
                                    },
                                }
                            )
    return pd.DataFrame(rows)


def test_performance_bootstrap_preserves_paired_protocol_draws() -> None:
    sampled = _performance_sample(_synthetic_records(), np.random.default_rng(7))

    for _, group in sampled.groupby(["motion", "load_kg", "bootstrap_draw"]):
        assert group.groupby("protocol").size().to_dict() == {"P0": 3, "P1": 3}
        assert group["repetition"].nunique() == 1


def test_control_bootstrap_synchronizes_repetition_across_loads() -> None:
    sampled = _control_sample(_synthetic_records(), np.random.default_rng(11))

    for _, group in sampled.groupby(["motion", "repetition", "protocol"]):
        assert set(group["load_kg"]) == set(LOADS)
        assert set(group["truth"]) == set(LABELS)
        assert group["original_repetition"].nunique() == 1


def test_perfect_predictions_have_perfect_performance_metrics() -> None:
    records = _synthetic_records().query("protocol == 'P0'")

    metrics = _performance_metrics(records)

    assert metrics["accuracy"] == pytest.approx(1.0)
    assert metrics["macro_f1"] == pytest.approx(1.0)
    assert metrics["worst_fold_accuracy"] == pytest.approx(1.0)
    assert metrics["worst_fold_macro_f1"] == pytest.approx(1.0)
    assert metrics["multiclass_brier"] == pytest.approx(0.0)


def test_interval_uses_percentiles_and_rejects_nonfinite_values() -> None:
    result = _interval(2.0, [0.0, 1.0, 2.0, 3.0, 4.0])

    assert result["point_estimate"] == pytest.approx(2.0)
    assert result["ci95_low"] == pytest.approx(0.1)
    assert result["ci95_high"] == pytest.approx(3.9)
    with pytest.raises(ValueError, match="finite"):
        _interval(0.0, [np.nan])
