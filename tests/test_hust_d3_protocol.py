from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from smartvalve.data.hust import (
    HUST_LABELS,
    HUST_SAMPLES_PER_RECORDING,
    HUST_WINDOWS_PER_RECORDING,
    extract_hust_window_features,
    hust_feature_names,
    inspect_hust_signal_vector,
    select_hust_primary_inventory,
    select_hust_signal_vector,
)
from smartvalve.experiments.hust_protocol import (
    HUST_PROTOCOLS,
    attach_hust_common_cells,
    build_hust_protocol_model_folds,
    build_hust_protocol_splits,
)


@pytest.fixture(scope="module")
def inventory() -> pd.DataFrame:
    records = []
    for condition in ("N", "I", "O", "B"):
        groups = range(4, 9) if condition != "B" else range(5, 9)
        for group in groups:
            for load in (0, 200, 400):
                code = {0: 0, 200: 2, 400: 4}[load]
                records.append(
                    {
                        "filename": f"{condition}{group}0{code}.mat",
                        "file_id": f"id-{condition}-{group}-{load}",
                        "folder_id": "folder",
                        "condition": condition,
                        "bearing_type": group,
                        "load_w": load,
                        "bytes": 100,
                        "sha256": "a" * 64,
                    }
                )
    return pd.DataFrame(records)


@pytest.fixture(scope="module")
def feature_frame(inventory: pd.DataFrame) -> pd.DataFrame:
    primary = select_hust_primary_inventory(inventory)
    records = []
    for recording_number, row in enumerate(primary.itertuples(index=False)):
        for window_index in range(HUST_WINDOWS_PER_RECORDING):
            record = {
                "filename": row.filename,
                "bearing_code": row.bearing_code,
                "specification_group": row.specification_group,
                "load_w": row.load_w,
                "truth": row.truth,
                "window_index": window_index,
            }
            for feature_number, feature_name in enumerate(hust_feature_names(), start=1):
                record[feature_name] = recording_number + window_index / 10 + feature_number / 100
            records.append(record)
    return pd.DataFrame(records)


def test_primary_inventory_has_15_physical_bearings(inventory: pd.DataFrame) -> None:
    primary = select_hust_primary_inventory(inventory)

    assert len(primary) == 45
    assert primary["bearing_code"].nunique() == 15
    assert primary.groupby("truth")["bearing_code"].nunique().to_dict() == {
        "healthy": 5,
        "inner": 5,
        "outer": 5,
    }


def test_signal_selection_and_windows_are_exact() -> None:
    signal = np.linspace(-1.0, 1.0, HUST_SAMPLES_PER_RECORDING)
    contents = {"__header__": "x", "data": signal[None, :]}
    candidate = inspect_hust_signal_vector(contents)
    selected = select_hust_signal_vector(contents)
    features = extract_hust_window_features(selected)

    assert candidate.variable_name == "data"
    assert candidate.original_shape == (1, HUST_SAMPLES_PER_RECORDING)
    assert candidate.original_dtype == "float64"
    np.testing.assert_array_equal(selected, signal)
    assert len(features) == 10
    assert tuple(features.columns) == ("window_index", *hust_feature_names())
    with pytest.raises(ValueError, match="exactly one"):
        select_hust_signal_vector({"x": signal, "y": signal})
    with pytest.raises(ValueError, match="exactly one"):
        select_hust_signal_vector({"short": signal[:-1]})


def test_four_protocols_keep_recordings_nested_and_target_every_window(
    feature_frame: pd.DataFrame,
) -> None:
    frame = attach_hust_common_cells(feature_frame)
    protocols = build_hust_protocol_splits(frame)

    assert tuple(protocols) == HUST_PROTOCOLS
    assert {name: len(splits) for name, splits in protocols.items()} == {
        "recording_random": 5,
        "load_holdout": 3,
        "matched_specification_holdout": 5,
        "crossed_holdout": 15,
    }
    for splits in protocols.values():
        target_counts = np.zeros(len(frame), dtype=int)
        for split in splits:
            target_counts[split.target_indices] += 1
            for indices in (
                split.source_indices,
                split.target_indices,
                split.quarantine_indices,
            ):
                counts = frame.iloc[indices].groupby("filename").size()
                assert counts.eq(10).all()
        np.testing.assert_array_equal(target_counts, np.ones(len(frame), dtype=int))

    crossed = protocols["crossed_holdout"][0]
    assert tuple(
        len(values)
        for values in (
            crossed.source_indices,
            crossed.target_indices,
            crossed.quarantine_indices,
        )
    ) == (240, 30, 180)
    target = frame.iloc[crossed.target_indices]
    assert set(target["truth"]) == set(HUST_LABELS)
    assert target["filename"].nunique() == 3


def test_crossed_model_pairs_match_sealed_aligned_window_counts(
    feature_frame: pd.DataFrame,
) -> None:
    folds = build_hust_protocol_model_folds(feature_frame)

    assert all(
        len(model_fold.fold.nuisance_pairs) == 120 and len(model_fold.fold.fault_pairs) == 240
        for model_fold in folds["crossed_holdout"]
    )
    for protocol_folds in folds.values():
        for model_fold in protocol_folds:
            model_fold.fold.validate()
            assert model_fold.fold.features.shape[1] == 24
            assert set(model_fold.fold.label_names) == set(HUST_LABELS)
