from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from smartvalve.experiments.selective_evaluation import (
    ENSEMBLE_SCORE_COLUMNS,
    INDIVIDUAL_SCORE_COLUMNS,
    add_individual_scores,
    analyze_ensemble_predictions,
    analyze_individual_predictions,
    evaluate_fold_policies,
    select_fold_policies,
)


def _records(*, target: bool, permute_truth: bool = False) -> pd.DataFrame:
    probabilities = np.asarray(
        [
            [0.90, 0.10],
            [0.80, 0.20],
            [0.55, 0.45],
            [0.40, 0.60],
            [0.85, 0.15],
            [0.70, 0.30],
            [0.45, 0.55],
            [0.35, 0.65],
        ]
    )
    logits = np.log(probabilities)
    truth = np.asarray(["ok", "ok", "bad", "bad"] * 2)
    if permute_truth:
        truth = truth[::-1]
    prediction = np.where(probabilities[:, 0] >= probabilities[:, 1], "ok", "bad")
    return pd.DataFrame(
        {
            "dataset": "fixture",
            "method": "erm",
            "seed": 11,
            "fold_id": "held=1",
            "row_index": np.arange(8) + (100 if target else 0),
            "environment_id": np.asarray(["a"] * 4 + ["b"] * 4),
            "block_id": [f"block-{index}" for index in range(8)],
            "truth": truth,
            "prediction": prediction,
            "correct": prediction == truth,
            "robust_class_support_distance": np.linspace(0.0, 1.4, 8),
            "probability_bad": probabilities[:, 1],
            "probability_ok": probabilities[:, 0],
            "logit_bad": logits[:, 1],
            "logit_ok": logits[:, 0],
        }
    )


def test_individual_scores_are_finite_and_directionally_consistent() -> None:
    scored = add_individual_scores(_records(target=False))

    assert set(INDIVIDUAL_SCORE_COLUMNS.values()).issubset(scored.columns)
    assert np.isfinite(scored[list(INDIVIDUAL_SCORE_COLUMNS.values())]).all().all()
    assert scored.loc[0, "score_msp"] < scored.loc[2, "score_msp"]


def test_target_label_permutation_cannot_change_source_selected_policies() -> None:
    source = add_individual_scores(_records(target=False))
    target = add_individual_scores(_records(target=True))
    permuted_target = add_individual_scores(
        _records(target=True, permute_truth=True)
    )

    policies, beta = select_fold_policies(source)
    _, _, decisions = evaluate_fold_policies(target, policies, beta)
    _, _, permuted_decisions = evaluate_fold_policies(
        permuted_target, policies, beta
    )

    repeated_policies, repeated_beta = select_fold_policies(source)
    assert [record["threshold"] for record in policies] == pytest.approx(
        [record["threshold"] for record in repeated_policies]
    )
    assert beta == repeated_beta
    assert beta["beta"] in (0.0, 0.1, 0.25, 0.5, 1.0)
    assert np.array_equal(
        decisions["accepted"].to_numpy(),
        permuted_decisions["accepted"].to_numpy(),
    )


def test_end_to_end_analysis_emits_all_frozen_policy_rows() -> None:
    result = analyze_individual_predictions(
        _records(target=False),
        _records(target=True),
    )

    score_count = len(INDIVIDUAL_SCORE_COLUMNS) + 1
    assert len(result["policies"]) == score_count * 3
    assert len(result["policy_metrics"]) == score_count * 3
    assert len(result["ranking_metrics"]) == score_count
    assert len(result["decisions"]) == score_count * 3 * 8
    assert set(result["decisions"]["row_index"]) == set(range(100, 108))


def test_fixed_ensemble_adds_disagreement_without_additional_selection_access() -> None:
    source_members = []
    target_members = []
    for seed, shift in ((11, 0.0), (29, 0.02)):
        source = _records(target=False)
        target = _records(target=True)
        source["seed"] = seed
        target["seed"] = seed
        source["probability_bad"] += shift
        source["probability_ok"] -= shift
        target["probability_bad"] += shift
        target["probability_ok"] -= shift
        source_members.append(source)
        target_members.append(target)

    result = analyze_ensemble_predictions(
        pd.concat(source_members, ignore_index=True),
        pd.concat(target_members, ignore_index=True),
        expected_seeds=(11, 29),
    )

    score_count = len(ENSEMBLE_SCORE_COLUMNS) + 1
    assert len(result["policies"]) == score_count * 3
    assert len(result["ranking_metrics"]) == score_count
    assert result["source_ensemble"]["seed"].eq(-1).all()
    assert result["source_ensemble"]["score_ensemble_jensen_shannon"].gt(0).all()
