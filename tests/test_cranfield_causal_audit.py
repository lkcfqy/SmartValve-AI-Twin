from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from smartvalve.experiments.cranfield_causal_audit import (
    LABELS,
    _seed_metrics,
    calibration_metrics,
    control_metrics,
    protocol_feature_frame,
    source_linear_reference,
)


def test_source_linear_reference_uses_only_source_and_leaves_normal_self_out() -> None:
    raw = pd.DataFrame(
        [
            {"motion": "trap", "load_kg": 0, "repetition": 1, "truth": "normal", "f": 0.0},
            {"motion": "trap", "load_kg": 0, "repetition": 2, "truth": "normal", "f": 2.0},
            {"motion": "trap", "load_kg": 10, "repetition": 1, "truth": "normal", "f": 10.0},
            {"motion": "trap", "load_kg": 10, "repetition": 2, "truth": "normal", "f": 12.0},
            {"motion": "trap", "load_kg": 20, "repetition": 1, "truth": "normal", "f": 999.0},
        ]
    )
    source_indices = pd.Index([0, 1, 2, 3])

    target_reference = source_linear_reference(raw, source_indices, 4, ["f"])
    raw.loc[4, "f"] = -999.0
    repeated_reference = source_linear_reference(raw, source_indices, 4, ["f"])
    leave_one_out_reference = source_linear_reference(raw, source_indices, 0, ["f"])

    assert target_reference == pytest.approx([21.0])
    assert repeated_reference == pytest.approx(target_reference)
    assert leave_one_out_reference == pytest.approx([2.0])


def test_matched_target_reference_rotates_repetition_and_interleaves_features() -> None:
    raw = pd.DataFrame(
        [
            {"motion": "trap", "load_kg": 20, "repetition": 1, "truth": "normal", "f": 1.0},
            {"motion": "trap", "load_kg": 20, "repetition": 2, "truth": "normal", "f": 2.0},
            {
                "motion": "trap",
                "load_kg": 20,
                "repetition": 1,
                "truth": "backlash",
                "f": 5.0,
            },
        ]
    )

    features, baseline_repetitions = protocol_feature_frame(
        raw,
        "P2",
        pd.Index([2]),
        pd.Index([0, 1]),
        ["f"],
    )

    assert list(features.columns) == ["delta_f", "relative_f"]
    assert features.loc[2, "delta_f"] == pytest.approx(3.0)
    assert features.loc[2, "relative_f"] == pytest.approx(1.5)
    assert baseline_repetitions == [2]


def test_controls_reward_load_invariance_and_fault_separation() -> None:
    rows = []
    class_probabilities = {
        "normal": (1.0, 0.0, 0.0),
        "lack_of_lubrication": (0.0, 1.0, 0.0),
        "backlash": (0.0, 0.0, 1.0),
    }
    for load_kg in (-40, 20, 40):
        for truth in LABELS:
            probabilities = class_probabilities[truth]
            rows.append(
                {
                    "motion": "trap",
                    "load_kg": load_kg,
                    "repetition": 1,
                    "truth": truth,
                    **{
                        f"probability_{label}": probabilities[index]
                        for index, label in enumerate(LABELS)
                    },
                }
            )

    metrics = control_metrics(pd.DataFrame(rows))

    assert metrics["nuisance_sensitivity_tv"] == pytest.approx(0.0)
    assert metrics["fault_sensitivity_tv"] == pytest.approx(1.0)
    assert metrics["control_ratio"] == pytest.approx(0.0)
    assert metrics["negative_control_pass"] is True
    assert metrics["nuisance_pairs"] == 9
    assert metrics["fault_pairs"] == 9


def test_perfect_probabilities_have_zero_calibration_error() -> None:
    probabilities = np.eye(len(LABELS), dtype=float)

    metrics = calibration_metrics(LABELS, probabilities)

    assert metrics["ece_10_bin"] == pytest.approx(0.0)
    assert metrics["maximum_calibration_error"] == pytest.approx(0.0)
    assert metrics["mean_confidence"] == pytest.approx(1.0)


def test_chance_level_fold_triggers_second_falsification_rule() -> None:
    rows = []
    for load_kg in (-40, 20, 40):
        for truth_index, truth in enumerate(LABELS):
            rows.append(
                {
                    "motion": "trap",
                    "load_kg": load_kg,
                    "repetition": 1,
                    "truth": truth,
                    "prediction": truth,
                    **{
                        f"probability_{label}": float(index == truth_index)
                        for index, label in enumerate(LABELS)
                    },
                }
            )
    fold = {
        "motion": "trap",
        "held_out_load_kg": -40,
        "accuracy": 1.0 / 3.0,
        "macro_f1": 1.0 / 6.0,
    }

    metrics = _seed_metrics(pd.DataFrame(rows), [fold])

    assert metrics["negative_control_pass"] is True
    assert metrics["worst_fold_chance_failure"] is True
    assert metrics["falsification_triggered"] is True
