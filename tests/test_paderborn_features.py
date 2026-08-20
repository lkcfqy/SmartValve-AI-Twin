from __future__ import annotations

import numpy as np
import pytest

from smartvalve.data.paderborn_features import (
    MAIN_SIGNAL_CHANNELS,
    PADERBORN_SAMPLING_HZ,
    SAMPLES_PER_MAIN_SIGNAL,
    STRUCTURALLY_EXCLUDED_FILENAMES,
    PaderbornMeasurementKey,
    expected_measurement_filenames,
    extract_main_signal_features,
    main_signal_feature_names,
    measurement_filename,
    parse_measurement_filename,
    retained_measurement_filenames,
)


def test_expected_filename_inventory_is_complete_and_round_trips() -> None:
    all_files = expected_measurement_filenames()
    pure_files = expected_measurement_filenames(pure_class_only=True)

    assert len(all_files) == len(set(all_files)) == 2560
    assert len(pure_files) == len(set(pure_files)) == 2320
    assert len(retained_measurement_filenames()) == 2559
    assert len(retained_measurement_filenames(pure_class_only=True)) == 2319
    assert set(STRUCTURALLY_EXCLUDED_FILENAMES) < set(pure_files)
    assert set(pure_files) < set(all_files)
    for filename in (all_files[0], all_files[79], all_files[-1]):
        assert measurement_filename(parse_measurement_filename(filename)) == filename


def test_filename_parser_rejects_unknown_or_noncanonical_keys() -> None:
    with pytest.raises(ValueError, match="unknown Paderborn setting"):
        parse_measurement_filename("N99_M99_F99_K001_1.mat")
    with pytest.raises(ValueError, match="noncanonical"):
        parse_measurement_filename("N15_M07_F10_K001_01.mat")
    with pytest.raises(ValueError, match="1..20"):
        measurement_filename(PaderbornMeasurementKey("N15_M07_F10", "K001", 21))


def test_whole_measurement_feature_contract_has_exact_finite_schema() -> None:
    time = np.arange(SAMPLES_PER_MAIN_SIGNAL, dtype=np.float64) / PADERBORN_SAMPLING_HZ
    channels = {
        "vibration": np.sin(2.0 * np.pi * 75.0 * time),
        "current_u": np.sin(2.0 * np.pi * 50.0 * time),
        "current_v": np.cos(2.0 * np.pi * 50.0 * time),
    }

    features = extract_main_signal_features(channels)

    assert tuple(channels) == MAIN_SIGNAL_CHANNELS
    assert len(main_signal_feature_names()) == 72
    assert features.shape == (72,)
    assert np.isfinite(features).all()


def test_feature_contract_rejects_extra_channels_or_wrong_length() -> None:
    valid = np.zeros(SAMPLES_PER_MAIN_SIGNAL)
    channels = {channel: valid for channel in MAIN_SIGNAL_CHANNELS}
    with pytest.raises(ValueError, match="exactly"):
        extract_main_signal_features({**channels, "speed": valid})
    with pytest.raises(ValueError, match=str(SAMPLES_PER_MAIN_SIGNAL)):
        extract_main_signal_features({**channels, "vibration": valid[:-1]})
