from __future__ import annotations

from itertools import product

import numpy as np
import pandas as pd

from smartvalve.experiments.cranfield_benchmark import LABELS, LOADS, MOTIONS, REPETITIONS
from smartvalve.experiments.domain_data import build_cranfield_folds
from smartvalve.experiments.inner_splits import (
    build_inner_splits,
    materialize_inner_fold,
)


def _cranfield_frame() -> pd.DataFrame:
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
                "feature": float(load + LABELS.index(label)),
            }
        )
    return pd.DataFrame(rows)


def test_inner_splits_cover_only_outer_source_once() -> None:
    outer = build_cranfield_folds(_cranfield_frame())[0]

    splits = build_inner_splits(outer)

    assert len(splits) == 4
    validation = np.concatenate([split.validation_indices for split in splits])
    assert np.array_equal(np.sort(validation), np.arange(len(outer.source_indices)))
    for split in splits:
        assert not np.intersect1d(
            split.training_indices, split.validation_indices
        ).size
        assert len(split.training_nuisance_pairs) > 0
        assert len(split.training_fault_pairs) > 0


def test_materialized_inner_fold_preserves_pair_validation() -> None:
    outer = build_cranfield_folds(_cranfield_frame())[1]
    split = build_inner_splits(outer)[0]

    inner = materialize_inner_fold(outer, split)

    inner.validate()
    assert len(inner.features) == len(outer.source_indices)
    assert len(inner.source_indices) + len(inner.target_indices) == len(
        outer.source_indices
    )
    assert inner.fold_id.startswith(outer.fold_id)
