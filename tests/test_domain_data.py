from __future__ import annotations

from itertools import product

import numpy as np
import pandas as pd

from smartvalve.data.uci_hydraulic import (
    CONTEXT_COLUMNS,
    CONTEXT_LEVELS,
    PHYSICAL_SENSORS,
    PRIMARY_REPETITIONS,
    SENSOR_FEATURES,
    VALVE_LABELS,
)
from smartvalve.experiments.cranfield_benchmark import LABELS, LOADS, MOTIONS, REPETITIONS
from smartvalve.experiments.domain_data import (
    _pair_indices,
    build_cranfield_folds,
    build_uci_folds,
)


def test_pair_indices_use_source_local_coordinates_and_declared_intervention() -> None:
    frame = pd.DataFrame(
        {
            "fault": ["a", "a", "a", "a", "b"],
            "block": [1, 1, 1, 2, 1],
            "context": [0, 1, 1, 0, 0],
        }
    )

    pairs = _pair_indices(
        frame,
        np.asarray([0, 1, 2, 4]),
        group_columns=("fault", "block"),
        distinct_column="context",
    )

    assert pairs.tolist() == [[0, 1], [0, 2]]


def _synthetic_cranfield() -> pd.DataFrame:
    rows = []
    for motion, label, load, repetition in product(
        MOTIONS, LABELS, LOADS, REPETITIONS
    ):
        rows.append(
            {
                "motion": motion,
                "load_kg": load,
                "repetition": repetition,
                "truth": label,
                "feature_a": float(load + repetition),
                "feature_b": float(LABELS.index(label)),
            }
        )
    return pd.DataFrame(rows)


def test_cranfield_folds_have_expected_source_only_pair_topology() -> None:
    folds = build_cranfield_folds(_synthetic_cranfield())

    assert len(folds) == 3
    for fold in folds:
        assert len(fold.source_indices) == 120
        assert len(fold.target_indices) == 60
        assert len(fold.nuisance_pairs) == 60
        assert len(fold.fault_pairs) == 120
        assert set(fold.source_labels) == {0, 1, 2}
        assert len(set(fold.source_environments)) == 4
        assert len(set(fold.target_environments)) == 2


def _synthetic_uci() -> pd.DataFrame:
    rows = []
    feature_names = [
        f"{sensor.name.lower()}__{feature}"
        for sensor in PHYSICAL_SENSORS
        for feature in SENSOR_FEATURES
    ]
    combinations = product(
        CONTEXT_LEVELS["cooler"],
        CONTEXT_LEVELS["pump"],
        CONTEXT_LEVELS["accumulator"],
        tuple(sorted(VALVE_LABELS)),
        PRIMARY_REPETITIONS,
    )
    for archive_row, (
        cooler,
        pump,
        accumulator,
        valve,
        repetition,
    ) in enumerate(combinations, start=1):
        row = {
            "archive_row": archive_row,
            "cooler": cooler,
            "valve": valve,
            "pump": pump,
            "accumulator": accumulator,
            "stable": 0,
            "repetition": repetition,
            "truth": VALVE_LABELS[valve],
            "sensor_row": archive_row - 1,
            "context_id": f"C{cooler}_P{pump}_A{accumulator}",
        }
        row.update(
            {
                name: float(
                    archive_row
                    + feature_index / max(1, len(feature_names))
                )
                for feature_index, name in enumerate(feature_names)
            }
        )
        rows.append(row)
    return pd.DataFrame(rows)


def test_uci_folds_have_expected_source_only_pair_topology() -> None:
    folds = build_uci_folds(_synthetic_uci())

    assert len(folds) == sum(len(CONTEXT_LEVELS[name]) for name in CONTEXT_COLUMNS)
    for fold in folds:
        levels = len(CONTEXT_LEVELS[fold.held_factor])
        source_contexts = 36 * (levels - 1) // levels
        expected_nuisance = (
            36
            // levels
            * len(VALVE_LABELS)
            * len(PRIMARY_REPETITIONS)
            * ((levels - 1) * (levels - 2) // 2)
        )
        assert len(fold.source_indices) == source_contexts * 40
        assert len(fold.target_indices) == 1440 - source_contexts * 40
        assert len(fold.nuisance_pairs) == expected_nuisance
        assert len(fold.fault_pairs) == source_contexts * 10 * 6
