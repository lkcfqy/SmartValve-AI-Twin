from __future__ import annotations

import pytest

pytest.importorskip("torch")

from smartvalve.experiments.dg_selection import (  # noqa: E402
    candidate_grid,
    candidate_id,
    select_common_candidate,
    select_outer_candidate,
)
from smartvalve.experiments.dg_training import BASELINE_METHODS  # noqa: E402


def _metric(
    candidate: str,
    *,
    method: str = "coral",
    dataset: str = "d",
    fold: str = "f",
    worst_f1: float,
    macro_f1: float,
    brier: float = 0.2,
) -> dict:
    return {
        "method": method,
        "dataset": dataset,
        "outer_fold_id": fold,
        "candidate_id": candidate,
        "source_oof_worst_environment_macro_f1": worst_f1,
        "source_oof_macro_f1": macro_f1,
        "source_oof_multiclass_brier": brier,
    }


def test_candidate_grids_are_unique_and_frozen() -> None:
    grids = {method: candidate_grid(method) for method in BASELINE_METHODS}

    assert len(grids["erm"]) == 2
    assert len(grids["groupdro"]) == 6
    assert all(
        len(grid) == 6
        for method, grid in grids.items()
        if method not in {"erm", "groupdro"}
    )
    assert sum(len(grid) for grid in grids.values()) == 44
    assert all(
        len({candidate_id(config) for config in grid}) == len(grid)
        for grid in grids.values()
    )
    assert {
        config.groupdro_step_size for config in grids["groupdro"]
    } == {0.01, 0.1, 1.0}
    assert {config.ccdg_temperature for config in grids["ccdg"]} == {0.7}


def test_outer_selection_prioritizes_worst_environment_with_tolerance() -> None:
    metrics = [
        _metric("best-worst", worst_f1=0.80, macro_f1=0.81),
        _metric("best-mean", worst_f1=0.795, macro_f1=0.90),
        _metric("ineligible", worst_f1=0.78, macro_f1=0.99),
    ]

    selected = select_outer_candidate(metrics)

    assert selected["selected_candidate_id"] == "best-mean"
    assert selected["eligible_candidates"] == ["best-mean", "best-worst"]


def test_outer_selection_rejects_mixed_methods() -> None:
    metrics = [
        _metric("a", method="coral", worst_f1=0.8, macro_f1=0.8),
        _metric("b", method="vrex", worst_f1=0.8, macro_f1=0.8),
    ]

    with pytest.raises(ValueError, match="cannot mix"):
        select_outer_candidate(metrics)


def test_common_selection_uses_mode_before_rank_tie_breaks() -> None:
    selections = [
        {"method": "coral", "selected_candidate_id": "a"},
        {"method": "coral", "selected_candidate_id": "a"},
        {"method": "coral", "selected_candidate_id": "b"},
    ]
    metrics = []
    for fold in ("f1", "f2", "f3"):
        metrics.extend(
            (
                _metric("a", fold=fold, worst_f1=0.7, macro_f1=0.7),
                _metric("b", fold=fold, worst_f1=0.9, macro_f1=0.9),
            )
        )

    selected = select_common_candidate(selections, metrics)

    assert selected["selected_candidate_id"] == "a"
    assert selected["selection_counts"] == {"a": 2, "b": 1}
