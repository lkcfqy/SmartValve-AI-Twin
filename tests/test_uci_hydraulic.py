from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from smartvalve.data.uci_hydraulic import (
    CONTEXT_LEVELS,
    SENSOR_FEATURES,
    VALVE_LEVELS,
    load_profile,
    select_stable_factorial,
    sensor_feature_matrix,
)


def _complete_profile() -> pd.DataFrame:
    rows = []
    archive_row = 1
    for cooler in CONTEXT_LEVELS["cooler"]:
        for pump in CONTEXT_LEVELS["pump"]:
            for accumulator in CONTEXT_LEVELS["accumulator"]:
                for valve in VALVE_LEVELS:
                    for _ in range(10):
                        rows.append(
                            {
                                "archive_row": archive_row,
                                "cooler": cooler,
                                "valve": valve,
                                "pump": pump,
                                "accumulator": accumulator,
                                "stable": 0,
                            }
                        )
                        archive_row += 1
    return pd.DataFrame(rows)


def test_stable_factorial_has_complete_four_state_blocks() -> None:
    profile = _complete_profile()
    extra = profile.iloc[[0]].copy()
    extra["archive_row"] = len(profile) + 1
    profile = pd.concat([profile, extra], ignore_index=True)

    selected = select_stable_factorial(profile)

    assert len(selected) == 1440
    assert selected["context_id"].nunique() == 36
    assert selected.groupby(["context_id", "repetition"])["truth"].nunique().eq(4).all()
    assert selected["repetition"].max() == 10
    assert selected["archive_row"].max() == 1440


def test_stable_factorial_rejects_incomplete_cell() -> None:
    profile = _complete_profile().iloc[:-1].copy()

    with pytest.raises(ValueError, match="incomplete cells"):
        select_stable_factorial(profile)


def test_sensor_features_are_finite_and_frozen() -> None:
    time = np.linspace(0.0, 2.0 * np.pi, 64, endpoint=False)
    values = np.vstack((np.ones(64), np.sin(time)))

    features = sensor_feature_matrix(values)

    assert features.shape == (2, 24)
    assert len(SENSOR_FEATURES) == 24
    assert np.isfinite(features).all()
    assert features[0, SENSOR_FEATURES.index("std")] == pytest.approx(0.0)
    assert features[0, SENSOR_FEATURES.index("spectral_entropy")] == pytest.approx(0.0)
    assert features[1, SENSOR_FEATURES.index("rms")] == pytest.approx(2**-0.5)


def test_verified_official_profile_matches_frozen_cohort() -> None:
    profile = load_profile()
    selected = select_stable_factorial(profile)

    assert len(profile) == 2205
    assert len(selected) == 1440
    assert selected["context_id"].nunique() == 36
    assert selected.groupby("truth").size().to_dict() == {
        "close_to_failure": 360,
        "optimal": 360,
        "severe_lag": 360,
        "small_lag": 360,
    }
