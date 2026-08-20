from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from smartvalve.experiments.uci_hydraulic_access import (
    context_design,
    fold_definitions,
    matched_context_references,
    protocol_feature_frame,
    source_context_references,
)


def _frame() -> pd.DataFrame:
    rows = []
    value = 0.0
    for cooler in (3, 20, 100):
        for pump in (0, 1, 2):
            for accumulator in (90, 100, 115, 130):
                for truth in (
                    "close_to_failure",
                    "severe_lag",
                    "small_lag",
                    "optimal",
                ):
                    for repetition in range(1, 11):
                        rows.append(
                            {
                                "cooler": cooler,
                                "pump": pump,
                                "accumulator": accumulator,
                                "truth": truth,
                                "repetition": repetition,
                                "f": value,
                                "g": value + 1.0,
                            }
                        )
                        value += 1.0
    return pd.DataFrame(rows)


def test_context_design_is_bounded_and_quadratic() -> None:
    frame = pd.DataFrame(
        [
            {"cooler": 100, "pump": 0, "accumulator": 130},
            {"cooler": 3, "pump": 2, "accumulator": 90},
        ]
    )

    design = context_design(frame)

    assert design.shape == (2, 9)
    assert design[0] == pytest.approx(np.zeros(9))
    assert design[1] == pytest.approx(np.ones(9))


def test_fold_definitions_cover_all_ten_held_levels() -> None:
    folds = fold_definitions()

    assert len(folds) == 10
    assert len(set(folds)) == 10
    assert {factor for factor, _ in folds} == {"cooler", "pump", "accumulator"}


def test_source_context_reference_does_not_read_target_features() -> None:
    frame = _frame()
    source_mask = frame["cooler"] != 3
    reference = source_context_references(frame, source_mask, ["f", "g"])
    target_indices = frame.index[~source_mask]
    frame.loc[target_indices, ["f", "g"]] = -1_000_000.0

    repeated = source_context_references(frame, source_mask, ["f", "g"])

    assert repeated[target_indices] == pytest.approx(reference[target_indices])


def test_p2_reference_rotates_within_exact_context() -> None:
    frame = _frame()
    references, baselines = matched_context_references(frame, ["f", "g"])
    first = frame.iloc[0]
    expected = frame.loc[
        (frame["cooler"] == first["cooler"])
        & (frame["pump"] == first["pump"])
        & (frame["accumulator"] == first["accumulator"])
        & (frame["truth"] == "optimal")
        & (frame["repetition"] == 2),
        ["f", "g"],
    ].iloc[0]

    assert baselines[0] == 2
    assert references[0] == pytest.approx(expected.to_numpy(dtype=float))


def test_protocol_fold_is_disjoint_and_has_frozen_feature_counts() -> None:
    frame = _frame()

    p0, source_mask, test_mask, p0_baselines = protocol_feature_frame(
        frame,
        "P0",
        "cooler",
        3,
        ["f", "g"],
    )
    p1, _, _, p1_baselines = protocol_feature_frame(
        frame,
        "P1",
        "cooler",
        3,
        ["f", "g"],
    )
    p2, _, _, p2_baselines = protocol_feature_frame(
        frame,
        "P2",
        "cooler",
        3,
        ["f", "g"],
    )

    assert p0.shape == (1440, 2)
    assert p1.shape == p2.shape == (1440, 4)
    assert source_mask.sum() == 960
    assert test_mask.sum() == 480
    assert not set(frame.loc[source_mask, "cooler"]) & set(frame.loc[test_mask, "cooler"])
    assert set(p0_baselines) == {-1}
    assert set(p1_baselines) == {-1}
    assert set(p2_baselines) == set(range(1, 11))
