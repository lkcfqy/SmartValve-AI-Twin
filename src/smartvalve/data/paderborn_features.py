"""Prospective Paderborn filename and main-signal feature contract."""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass

import numpy as np

from smartvalve.data.paderborn import (
    BEARING_METADATA,
    OPERATING_SETTINGS,
    PRIMARY_BEARING_CODES,
)
from smartvalve.data.uci_hydraulic import SENSOR_FEATURES, sensor_feature_matrix

PADERBORN_SAMPLING_HZ = 64_000
MEASUREMENT_DURATION_SECONDS = 4
SAMPLES_PER_MAIN_SIGNAL = PADERBORN_SAMPLING_HZ * MEASUREMENT_DURATION_SECONDS
STORED_SAMPLES_PER_MAIN_SIGNAL = SAMPLES_PER_MAIN_SIGNAL + 1
MINIMUM_STORED_SAMPLES_PER_MAIN_SIGNAL = 249_940
MAXIMUM_STORED_SAMPLES_PER_MAIN_SIGNAL = 299_038
MAIN_SIGNAL_ENDPOINT_POLICY = "linear_resample_full_measurement_to_256000"
MAIN_SIGNAL_CHANNELS = ("vibration", "current_u", "current_v")
MAIN_SIGNAL_FEATURE_FAMILIES = ("vibration", "motor_current", "fusion")
STRUCTURALLY_EXCLUDED_FILENAMES = ("N15_M01_F10_KA08_2.mat",)
MEASUREMENT_PATTERN = re.compile(
    r"^(?P<setting>N\d{2}_M\d{2}_F\d{2})_"
    r"(?P<bearing>K(?:\d{3}|[A-Z]\d{2}))_"
    r"(?P<measurement>\d{1,2})\.mat$"
)


@dataclass(frozen=True)
class PaderbornMeasurementKey:
    setting_code: str
    bearing_code: str
    measurement_index: int


def measurement_filename(key: PaderbornMeasurementKey) -> str:
    setting_codes = {setting.code for setting in OPERATING_SETTINGS}
    bearing_codes = {bearing.code for bearing in BEARING_METADATA}
    if key.setting_code not in setting_codes:
        raise ValueError(f"unknown Paderborn setting: {key.setting_code}")
    if key.bearing_code not in bearing_codes:
        raise ValueError(f"unknown Paderborn bearing: {key.bearing_code}")
    if not 1 <= key.measurement_index <= 20:
        raise ValueError("Paderborn measurement index must lie in 1..20")
    return f"{key.setting_code}_{key.bearing_code}_{key.measurement_index}.mat"


def parse_measurement_filename(filename: str) -> PaderbornMeasurementKey:
    match = MEASUREMENT_PATTERN.fullmatch(filename)
    if match is None:
        raise ValueError(f"invalid Paderborn measurement filename: {filename}")
    key = PaderbornMeasurementKey(
        setting_code=match.group("setting"),
        bearing_code=match.group("bearing"),
        measurement_index=int(match.group("measurement")),
    )
    if measurement_filename(key) != filename:
        raise ValueError(f"noncanonical Paderborn measurement filename: {filename}")
    return key


def expected_measurement_filenames(
    *,
    pure_class_only: bool = False,
) -> tuple[str, ...]:
    bearings = (
        PRIMARY_BEARING_CODES
        if pure_class_only
        else tuple(bearing.code for bearing in BEARING_METADATA)
    )
    return tuple(
        measurement_filename(PaderbornMeasurementKey(setting.code, bearing, measurement))
        for bearing in bearings
        for setting in OPERATING_SETTINGS
        for measurement in range(1, 21)
    )


def retained_measurement_filenames(*, pure_class_only: bool = False) -> tuple[str, ...]:
    excluded = set(STRUCTURALLY_EXCLUDED_FILENAMES)
    return tuple(
        filename
        for filename in expected_measurement_filenames(pure_class_only=pure_class_only)
        if filename not in excluded
    )


def main_signal_feature_names() -> tuple[str, ...]:
    return tuple(
        f"{channel}__{feature}" for channel in MAIN_SIGNAL_CHANNELS for feature in SENSOR_FEATURES
    )


def main_signal_feature_family_names(family: str) -> tuple[str, ...]:
    """Return one frozen sensor-family view of the 72-feature contract."""

    if family not in MAIN_SIGNAL_FEATURE_FAMILIES:
        raise ValueError(f"unknown Paderborn feature family: {family}")
    names = main_signal_feature_names()
    if family == "vibration":
        selected = tuple(name for name in names if name.startswith("vibration__"))
    elif family == "motor_current":
        selected = tuple(
            name
            for name in names
            if name.startswith(("current_u__", "current_v__"))
        )
    else:
        selected = names
    expected_count = {"vibration": 24, "motor_current": 48, "fusion": 72}[family]
    if len(selected) != expected_count:
        raise ValueError("Paderborn feature-family schema changed")
    return selected


def extract_main_signal_features(
    channels: Mapping[str, np.ndarray],
) -> np.ndarray:
    """Extract 72 frozen whole-measurement features from three synchronous channels."""

    if set(channels) != set(MAIN_SIGNAL_CHANNELS):
        raise ValueError("Paderborn primary channels must be exactly vibration/current_u/current_v")
    blocks = []
    for channel in MAIN_SIGNAL_CHANNELS:
        values = np.asarray(channels[channel], dtype=np.float64)
        if values.ndim != 1 or len(values) != SAMPLES_PER_MAIN_SIGNAL:
            raise ValueError(f"{channel} must contain exactly {SAMPLES_PER_MAIN_SIGNAL} samples")
        if not np.isfinite(values).all():
            raise ValueError(f"{channel} contains non-finite samples")
        blocks.append(sensor_feature_matrix(values[None, :])[0])
    features = np.concatenate(blocks).astype(np.float64, copy=False)
    if len(features) != len(main_signal_feature_names()) or not np.isfinite(features).all():
        raise ValueError("Paderborn main-signal feature extraction failed its schema")
    return features
