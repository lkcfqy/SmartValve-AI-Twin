from __future__ import annotations

import numpy as np
import pytest
from scipy.io import savemat

from smartvalve.data.paderborn_features import (
    MAXIMUM_STORED_SAMPLES_PER_MAIN_SIGNAL,
    MINIMUM_STORED_SAMPLES_PER_MAIN_SIGNAL,
    SAMPLES_PER_MAIN_SIGNAL,
    STORED_SAMPLES_PER_MAIN_SIGNAL,
)
from smartvalve.data.paderborn_mat import (
    extract_measurement_features,
    extract_named_main_channels,
    extract_named_main_channels_with_length,
    inspect_main_channel_structure,
    inspect_named_main_channel_structure,
    load_main_channels,
    normalize_main_signal,
)


def _records(length: int = STORED_SAMPLES_PER_MAIN_SIGNAL) -> dict[str, object]:
    time = np.arange(length, dtype=float)
    return {
        "Description": "synthetic structural fixture",
        "Y": [
            {"Name": "force", "Data": np.ones(4)},
            {"Name": "phase_current_2", "Data": np.cos(time / 10)},
            {"Name": "vibration_1", "Data": np.sin(time / 7)},
            {"Name": "phase_current_1", "Data": np.sin(time / 10)},
        ],
    }


def test_semantic_parser_is_independent_of_signal_record_order() -> None:
    channels = extract_named_main_channels(_records())

    assert tuple(channels) == ("vibration", "current_u", "current_v")
    assert all(values.shape == (SAMPLES_PER_MAIN_SIGNAL,) for values in channels.values())


def test_synthetic_mat_round_trip_emits_structure_only_and_72_features(tmp_path) -> None:
    path = tmp_path / "N15_M07_F10_K001_1.mat"
    savemat(path, {path.stem: _records()})

    structure = inspect_main_channel_structure(path)
    channels = load_main_channels(path)
    features = extract_measurement_features(path)

    assert structure["values_or_statistics_emitted"] is False
    assert structure["value_dependent_validation_performed"] is False
    assert structure["signal_values_loaded_by_mat_reader"] is True
    assert set(structure["channels"]) == {"vibration", "current_u", "current_v"}
    assert all(
        metadata["shape"] == [STORED_SAMPLES_PER_MAIN_SIGNAL]
        for metadata in structure["channels"].values()
    )
    assert set(channels) == set(structure["channels"])
    assert features.shape == (72,)
    assert np.isfinite(features).all()


def test_structure_probe_is_value_blind_but_full_parser_rejects_nonfinite(
    tmp_path,
) -> None:
    records = _records()
    records["Y"][1]["Data"][0] = np.nan
    path = tmp_path / "N15_M07_F10_K001_1.mat"
    savemat(path, {path.stem: records})

    structure = inspect_main_channel_structure(path)

    assert structure["value_dependent_validation_performed"] is False
    assert structure["channels"]["current_v"]["samples"] == STORED_SAMPLES_PER_MAIN_SIGNAL
    with pytest.raises(ValueError, match="non-finite"):
        load_main_channels(path)


def test_structure_probe_reports_unexpected_lengths_without_accepting_them() -> None:
    records = _records(length=128)

    structure = inspect_named_main_channel_structure(records)

    assert {channel: metadata["samples"] for channel, metadata in structure.items()} == {
        "vibration": 128,
        "current_u": 128,
        "current_v": 128,
    }
    with pytest.raises(ValueError, match=str(MINIMUM_STORED_SAMPLES_PER_MAIN_SIGNAL)):
        extract_named_main_channels(records)


def test_value_parser_accepts_exact_window_or_longer_equal_length_channels() -> None:
    exact, exact_stored = extract_named_main_channels_with_length(
        _records(length=SAMPLES_PER_MAIN_SIGNAL)
    )
    longer, longer_stored = extract_named_main_channels_with_length(
        _records(length=SAMPLES_PER_MAIN_SIGNAL + 5196)
    )

    assert all(values.shape == (SAMPLES_PER_MAIN_SIGNAL,) for values in exact.values())
    assert all(values.shape == (SAMPLES_PER_MAIN_SIGNAL,) for values in longer.values())
    assert exact_stored == SAMPLES_PER_MAIN_SIGNAL
    assert longer_stored == SAMPLES_PER_MAIN_SIGNAL + 5196


def test_length_normalization_preserves_linear_endpoints_and_target_shape() -> None:
    values = np.linspace(-2.0, 3.0, MINIMUM_STORED_SAMPLES_PER_MAIN_SIGNAL)

    normalized = normalize_main_signal(values)

    assert normalized.shape == (SAMPLES_PER_MAIN_SIGNAL,)
    assert normalized[[0, -1]] == pytest.approx(values[[0, -1]])
    with pytest.raises(ValueError, match="outside"):
        normalize_main_signal(np.zeros(MINIMUM_STORED_SAMPLES_PER_MAIN_SIGNAL - 1))
    with pytest.raises(ValueError, match="outside"):
        normalize_main_signal(np.zeros(MAXIMUM_STORED_SAMPLES_PER_MAIN_SIGNAL + 1))


def test_value_parser_rejects_different_channel_lengths() -> None:
    records = _records(length=STORED_SAMPLES_PER_MAIN_SIGNAL)
    records["Y"][1]["Data"] = records["Y"][1]["Data"][:-1]

    with pytest.raises(ValueError, match="same stored length"):
        extract_named_main_channels(records)


def test_parser_rejects_missing_duplicate_or_wrong_length_signals() -> None:
    missing = _records()
    missing["Y"] = missing["Y"][:-1]
    with pytest.raises(ValueError, match="missing"):
        extract_named_main_channels(missing)

    duplicate = _records()
    duplicate["Y"] = [*duplicate["Y"], duplicate["Y"][0], duplicate["Y"][1]]
    with pytest.raises(ValueError, match="duplicate"):
        extract_named_main_channels(duplicate)

    with pytest.raises(ValueError, match="between"):
        extract_named_main_channels(_records(length=128))
    with pytest.raises(ValueError, match="duplicate"):
        inspect_named_main_channel_structure(duplicate)


def test_loader_rejects_noncanonical_filename_or_changed_root_key(tmp_path) -> None:
    wrong_name = tmp_path / "bad.mat"
    savemat(wrong_name, {"bad": _records()})
    with pytest.raises(ValueError, match="invalid Paderborn"):
        load_main_channels(wrong_name)

    wrong_root = tmp_path / "N15_M07_F10_K001_1.mat"
    savemat(wrong_root, {"different": _records()})
    with pytest.raises(ValueError, match="root keys"):
        load_main_channels(wrong_root)
