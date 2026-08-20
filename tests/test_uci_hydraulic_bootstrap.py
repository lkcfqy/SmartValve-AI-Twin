from __future__ import annotations

import numpy as np
import pytest

from smartvalve.experiments.uci_hydraulic_bootstrap import (
    AUDIT_SEEDS,
    CONTEXT_COLUMNS,
    CONTEXTS,
    ESTIMATORS,
    LABELS,
    PRIMARY_REPETITIONS,
    PROTOCOLS,
    _all_metric_tensor,
    _control_choices,
    _interval,
    _macro_f1,
)


def test_macro_f1_is_one_for_perfect_four_class_predictions() -> None:
    truth = np.asarray([0, 1, 2, 3, 0, 1, 2, 3], dtype=np.int8)

    assert _macro_f1(truth, truth.copy()) == pytest.approx(1.0)


def test_control_choices_are_synchronized_across_held_factor_levels() -> None:
    choices = _control_choices(np.random.default_rng(17))

    for axis_index in range(3):
        other_axes = [index for index in range(3) if index != axis_index]
        groups: dict[tuple[int, int], list[int]] = {}
        for context_index, context in enumerate(CONTEXTS):
            key = tuple(context[index] for index in other_axes)
            groups.setdefault(key, []).append(context_index)
        for context_indices in groups.values():
            expected = choices[axis_index, context_indices[0]]
            for context_index in context_indices[1:]:
                assert choices[axis_index, context_index] == pytest.approx(expected)


def test_interval_uses_percentiles_and_rejects_nonfinite_values() -> None:
    result = _interval(2.0, [0.0, 1.0, 2.0, 3.0, 4.0])

    assert result["point_estimate"] == pytest.approx(2.0)
    assert result["ci95_low"] == pytest.approx(0.1)
    assert result["ci95_high"] == pytest.approx(3.9)
    with pytest.raises(ValueError, match="finite"):
        _interval(0.0, [np.nan])


def test_full_metric_tensor_recovers_known_invariant_perfect_case() -> None:
    prediction_shape = (
        len(ESTIMATORS),
        len(PROTOCOLS),
        len(AUDIT_SEEDS),
        len(CONTEXT_COLUMNS),
        len(CONTEXTS),
        len(PRIMARY_REPETITIONS),
        len(LABELS),
    )
    truth = np.arange(len(LABELS), dtype=np.int8)
    predictions = np.broadcast_to(truth, prediction_shape).copy()
    probabilities = np.eye(len(LABELS), dtype=float)[predictions]
    performance_choices = np.broadcast_to(
        np.arange(len(PRIMARY_REPETITIONS)),
        (len(CONTEXTS), len(PRIMARY_REPETITIONS)),
    )
    control_choices = np.broadcast_to(
        np.arange(len(PRIMARY_REPETITIONS)),
        (len(CONTEXT_COLUMNS), len(CONTEXTS), len(PRIMARY_REPETITIONS)),
    )

    metrics = _all_metric_tensor(
        probabilities,
        predictions,
        performance_choices,
        control_choices,
    )

    assert metrics.shape == (len(ESTIMATORS), len(PROTOCOLS), len(AUDIT_SEEDS), 8)
    assert metrics[..., 0] == pytest.approx(1.0)
    assert metrics[..., 1] == pytest.approx(1.0)
    assert metrics[..., 2] == pytest.approx(1.0)
    assert metrics[..., 3] == pytest.approx(0.0)
    assert metrics[..., 4] == pytest.approx(0.0)
    assert metrics[..., 5] == pytest.approx(0.0)
    assert metrics[..., 6] == pytest.approx(1.0)
    assert metrics[..., 7] == pytest.approx(0.0)
