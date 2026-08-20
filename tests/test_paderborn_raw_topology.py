from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from smartvalve.experiments.paderborn_expected_manifest import metadata_only_indices
from smartvalve.experiments.paderborn_protocol_contrast import PROBABILITY_COLUMNS
from smartvalve.experiments.paderborn_raw_topology import (
    BASE_METADATA,
    EXPECTED_WINDOW_OFFSETS,
    KEY_SCHEMAS,
    _attach_identity_cells,
    _frame_key_record,
    _probability_health,
    _trace_key_record,
    build_expected_key_sets,
    validate_window_index,
)


def _metadata_and_windows() -> tuple[pd.DataFrame, pd.DataFrame]:
    metadata, _ = metadata_only_indices()
    metadata = _attach_identity_cells(metadata.loc[:, BASE_METADATA])
    record_count = len(metadata)
    row_indices = np.repeat(np.arange(record_count, dtype=np.int64), 4)
    window_indices = np.tile(np.arange(4, dtype=np.int64), record_count)
    windows = pd.DataFrame(
        {
            "window_row_index": np.arange(record_count * 4, dtype=np.int64),
            "row_index": row_indices,
            "window_index": window_indices,
            "sample_offset": np.tile(
                np.asarray(EXPECTED_WINDOW_OFFSETS, dtype=np.int64), record_count
            ),
        }
    )
    for column in BASE_METADATA:
        windows[column] = metadata.iloc[row_indices][column].to_numpy()
    return metadata, windows


def test_raw_expected_topology_locks_every_fit_window_record_and_ensemble_key() -> None:
    metadata, windows = _metadata_and_windows()
    validated = validate_window_index(windows, metadata)

    key_sets, folds = build_expected_key_sets(metadata, validated)

    assert len(folds) == 30
    assert key_sets["window_predictions"]["count"] == 166_968
    assert key_sets["seed_recording_predictions"]["count"] == 41_742
    assert key_sets["ensemble_recording_predictions"]["count"] == 13_914
    assert key_sets["fits"]["count"] == 270
    assert key_sets["training_traces"]["count"] == 270
    assert all(len(value["sha256"]) == 64 for value in key_sets.values())


def test_raw_expected_topology_rejects_window_metadata_or_offset_drift() -> None:
    metadata, windows = _metadata_and_windows()
    windows.loc[0, "bearing_code"] = "tampered"

    with pytest.raises(ValueError, match="window metadata changed: bearing_code"):
        validate_window_index(windows, metadata)

    _, windows = _metadata_and_windows()
    windows.loc[0, "sample_offset"] = 1
    with pytest.raises(ValueError, match="window positions changed"):
        validate_window_index(windows, metadata)


def test_raw_observed_key_hash_rejects_duplicates() -> None:
    schema = KEY_SCHEMAS["training_traces"]
    frame = pd.DataFrame(
        [("measurement_random", "cnn1d", 41, "random=0")],
        columns=schema,
    )

    record = _frame_key_record(frame, "training_traces")

    assert record["count"] == 1
    with pytest.raises(ValueError, match="duplicate key"):
        _frame_key_record(pd.concat((frame, frame), ignore_index=True), "training_traces")


def test_raw_topology_diagnostics_validate_probabilities_and_training_schedule() -> None:
    probability_frame = pd.DataFrame(
        {
            PROBABILITY_COLUMNS[0]: [0.5],
            PROBABILITY_COLUMNS[1]: [0.3],
            PROBABILITY_COLUMNS[2]: [0.2],
        }
    )
    trace = {
        "protocol": "measurement_random",
        "model": "cnn1d",
        "seed": 41,
        "fold_id": "random=0",
        "epochs": [
            {
                "epoch": epoch,
                "source_training_loss": 1.0 / epoch,
                "learning_rate": 0.001 if epoch < 10 else 0.0005,
            }
            for epoch in range(1, 51)
        ],
    }

    assert _probability_health(probability_frame, "fixture") == pytest.approx(0.0)
    record, increase = _trace_key_record([trace])
    assert record["count"] == 1
    assert increase == pytest.approx(0.0)

    probability_frame.loc[0, PROBABILITY_COLUMNS[0]] = 0.7
    with pytest.raises(ValueError, match="do not sum to one"):
        _probability_health(probability_frame, "fixture")

    trace["epochs"][20]["learning_rate"] = 0.00075
    with pytest.raises(ValueError, match="learning rate increased"):
        _trace_key_record([trace])
