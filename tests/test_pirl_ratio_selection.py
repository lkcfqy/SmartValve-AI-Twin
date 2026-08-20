from __future__ import annotations

import pytest

pytest.importorskip("torch")

from smartvalve.experiments.pirl_ratio_selection import (  # noqa: E402
    candidate_grid,
    candidate_id,
    select_common_candidate,
    select_outer_candidate,
)


def _metric(
    candidate: str,
    *,
    dataset: str = "d",
    fold: str = "f",
    f1: float,
    ratio: float,
    brier: float = 0.2,
) -> dict:
    return {
        "dataset": dataset,
        "outer_fold_id": fold,
        "candidate_id": candidate,
        "source_oof_macro_f1": f1,
        "source_oof_multiclass_brier": brier,
        "source_oof_probability_response_ratio": ratio,
    }


def test_candidate_grid_is_the_frozen_twelve_unique_configurations() -> None:
    candidates = candidate_grid()

    assert len(candidates) == 12
    assert len({candidate_id(config) for config in candidates}) == 12
    assert {config.representation_dim for config in candidates} == {32, 64}
    assert {config.intervention_weight for config in candidates} == {
        0.1,
        0.5,
        1.0,
    }
    assert {config.fault_margin for config in candidates} == {0.5, 1.0}


def test_outer_selection_uses_f1_tolerance_before_response_ratio() -> None:
    metrics = [
        _metric("best", f1=0.90, ratio=0.50),
        _metric("mechanism", f1=0.895, ratio=0.20),
        _metric("ineligible", f1=0.88, ratio=0.01),
    ]

    selected = select_outer_candidate(metrics)

    assert selected["selected_candidate_id"] == "mechanism"
    assert selected["eligible_candidates"] == ["best", "mechanism"]


def test_common_selection_uses_mode_before_rank_tie_breaks() -> None:
    selections = [
        {"selected_candidate_id": "a"},
        {"selected_candidate_id": "a"},
        {"selected_candidate_id": "b"},
    ]
    metrics = []
    for fold in ("f1", "f2", "f3"):
        metrics.extend(
            (
                _metric("a", fold=fold, f1=0.8, ratio=0.2),
                _metric("b", fold=fold, f1=0.9, ratio=0.1),
            )
        )

    selected = select_common_candidate(selections, metrics)

    assert selected["selected_candidate_id"] == "a"
    assert selected["selection_counts"] == {"a": 2, "b": 1}
