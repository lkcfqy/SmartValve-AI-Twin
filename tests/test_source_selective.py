from __future__ import annotations

import numpy as np
import pytest

from smartvalve.experiments.source_selective import (
    apply_policy,
    apply_score_policy,
    evaluate_policy,
    evaluate_score_policy,
    risk_coverage_summary,
    select_risk_envelope_beta,
    select_source_coverage_policy,
    select_source_policy,
)


def test_source_selection_respects_global_and_per_environment_coverage() -> None:
    uncertainty = np.asarray([0.1, 0.2, 0.8, 0.9, 0.1, 0.3, 0.7, 1.0])
    distance = np.asarray([0.0, 0.1, 0.4, 0.8, 0.0, 0.2, 0.5, 0.9])
    errors = np.asarray([False, False, True, True, False, False, True, True])
    environments = np.asarray(["a"] * 4 + ["b"] * 4)

    policy = select_source_policy(
        uncertainty,
        distance,
        errors,
        environments,
        minimum_coverage=0.5,
        minimum_environment_coverage=0.25,
    )

    assert policy.source_coverage >= 0.5
    assert policy.source_minimum_environment_coverage >= 0.25
    assert policy.source_selective_risk == pytest.approx(0.0)
    assert apply_policy(policy, uncertainty, distance).sum() == policy.source_accepted


def test_evaluation_reports_environment_coverage_collapse_without_hiding_it() -> None:
    uncertainty = np.asarray([0.1, 0.2, 0.8, 0.9, 0.1, 0.3, 0.7, 1.0])
    distance = np.zeros(8)
    errors = np.asarray([False, False, True, True, False, False, True, True])
    environments = np.asarray(["a"] * 4 + ["b"] * 4)
    policy = select_source_policy(uncertainty, distance, errors, environments)
    target_uncertainty = np.asarray([0.1, 0.2, 2.0, 3.0])
    target_distance = np.zeros(4)
    target_errors = np.asarray([False, True, True, True])
    target_environments = np.asarray(["x", "x", "y", "y"])

    result = evaluate_policy(
        policy,
        target_uncertainty,
        target_distance,
        target_errors,
        target_environments,
    )

    assert result["per_environment"]["y"]["accepted"] == 0
    assert result["per_environment"]["y"]["selective_risk"] is None
    assert result["minimum_environment_coverage"] == pytest.approx(0.0)
    assert result["worst_environment_risk"] == pytest.approx(1.0)


def test_source_selection_rejects_single_environment_input() -> None:
    with pytest.raises(ValueError, match="multiple environments"):
        select_source_policy(
            np.asarray([0.1, 0.2]),
            np.asarray([0.0, 0.1]),
            np.asarray([False, True]),
            np.asarray(["only", "only"]),
        )


def test_fixed_coverage_policy_honors_pooled_and_environment_floors() -> None:
    scores = np.asarray([0.01, 0.02, 0.03, 1.0, 0.10, 0.20, 0.30, 0.40])
    errors = np.asarray([False, False, False, True, False, False, True, True])
    environments = np.asarray(["a"] * 4 + ["b"] * 4)

    policy = select_source_coverage_policy(
        scores,
        errors,
        environments,
        score_name="msp",
        nominal_source_coverage=0.5,
        minimum_source_environment_coverage=0.5,
    )

    assert policy.threshold == pytest.approx(0.2)
    assert policy.source_coverage >= 0.5
    assert policy.source_minimum_environment_coverage >= 0.5
    assert np.array_equal(
        apply_score_policy(policy, scores), scores <= policy.threshold
    )


def test_fixed_policy_reports_zero_target_coverage_instead_of_failing() -> None:
    policy = select_source_coverage_policy(
        np.asarray([0.1, 0.2, 0.3, 0.4]),
        np.asarray([False, False, True, True]),
        np.asarray(["a", "a", "b", "b"]),
        score_name="energy",
        nominal_source_coverage=0.5,
    )

    result = evaluate_score_policy(
        policy,
        np.asarray([10.0, 11.0]),
        np.asarray([True, False]),
        np.asarray(["target", "target"]),
    )

    assert result["coverage"] == pytest.approx(0.0)
    assert result["selective_risk"] is None
    assert result["worst_environment_risk"] == pytest.approx(1.0)


def test_risk_coverage_summary_rewards_perfect_error_ranking() -> None:
    scores = np.asarray([0.1, 0.2, 0.9, 1.0])
    errors = np.asarray([False, False, True, True])

    result = risk_coverage_summary(scores, errors)

    assert result["excess_aurc"] == pytest.approx(0.0)
    assert result["error_detection_auroc"] == pytest.approx(1.0)
    assert result["error_detection_average_precision"] == pytest.approx(1.0)
    assert result["coverage_points"]["0.5"]["selective_risk"] == pytest.approx(0.0)


def test_risk_envelope_beta_is_selected_only_from_source_oof_ranking() -> None:
    uncertainty = np.asarray([0.1, 0.2, 0.3, 0.4, 0.1, 0.2, 0.3, 0.4])
    distance = np.asarray([0.0, 0.0, 2.0, 3.0, 0.0, 0.0, 2.0, 3.0])
    errors = np.asarray([False, False, True, True] * 2)
    environments = np.asarray(["a"] * 4 + ["b"] * 4)

    selection = select_risk_envelope_beta(
        uncertainty,
        distance,
        errors,
        environments,
        beta_candidates=(0.0, 0.5, 1.0),
    )

    assert selection.beta == pytest.approx(0.0)
    assert selection.source_worst_environment_aurc >= 0.0
    assert len(selection.candidates) == 3
