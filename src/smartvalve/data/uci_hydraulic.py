"""Integrity-aware loader and frozen cycle features for UCI hydraulic dataset 447."""

from __future__ import annotations

import io
from collections.abc import Sequence
from dataclasses import dataclass
from hashlib import sha256
from itertools import product
from pathlib import Path
from zipfile import ZipFile

import numpy as np
import pandas as pd

from smartvalve.data.external import cache_directory

ARCHIVE_FILENAME = "uci_hydraulic.zip"
ARCHIVE_SHA256 = "24128aad2ee45eea7e6b63ebbd9992cdf25d0483a2cebefbfc13bc69079af1f2"
PROFILE_COLUMNS = ("cooler", "valve", "pump", "accumulator", "stable")
CONTEXT_COLUMNS = ("cooler", "pump", "accumulator")
CONTEXT_LEVELS = {
    "cooler": (3, 20, 100),
    "pump": (0, 1, 2),
    "accumulator": (90, 100, 115, 130),
}
VALVE_LEVELS = (73, 80, 90, 100)
VALVE_LABELS = {
    73: "close_to_failure",
    80: "severe_lag",
    90: "small_lag",
    100: "optimal",
}
PRIMARY_REPETITIONS = tuple(range(1, 11))


@dataclass(frozen=True)
class SensorSpec:
    name: str
    sampling_hz: int

    @property
    def samples_per_cycle(self) -> int:
        return self.sampling_hz * 60


PHYSICAL_SENSORS = (
    *(SensorSpec(f"PS{index}", 100) for index in range(1, 7)),
    SensorSpec("EPS1", 100),
    SensorSpec("FS1", 10),
    SensorSpec("FS2", 10),
    *(SensorSpec(f"TS{index}", 1) for index in range(1, 5)),
    SensorSpec("VS1", 1),
)
DERIVED_SENSORS = (
    SensorSpec("CE", 1),
    SensorSpec("CP", 1),
    SensorSpec("SE", 1),
)
SENSOR_FEATURES = (
    "mean",
    "std",
    "rms",
    "minimum",
    "maximum",
    "peak_to_peak",
    "q05",
    "q25",
    "q50",
    "q75",
    "q95",
    "iqr",
    "mean_absolute",
    "skewness",
    "excess_kurtosis",
    "diff_mean_absolute",
    "diff_rms",
    "linear_slope",
    "spectral_centroid",
    "spectral_bandwidth",
    "spectral_entropy",
    "spectral_power_low",
    "spectral_power_mid",
    "spectral_power_high",
)


def archive_path(path: Path | None = None) -> Path:
    return path or cache_directory() / ARCHIVE_FILENAME


def file_sha256(path: Path) -> str:
    digest = sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def verify_archive(path: Path | None = None) -> Path:
    resolved = archive_path(path)
    if not resolved.is_file():
        raise FileNotFoundError(f"missing UCI hydraulic archive: {resolved}")
    actual = file_sha256(resolved)
    if actual != ARCHIVE_SHA256:
        raise ValueError(
            f"UCI hydraulic archive hash mismatch: expected {ARCHIVE_SHA256}, got {actual}"
        )
    return resolved


def load_profile(path: Path | None = None, *, verify: bool = True) -> pd.DataFrame:
    """Load the five cycle-level condition fields in official archive order."""

    resolved = verify_archive(path) if verify else archive_path(path)
    with ZipFile(resolved) as archive:
        payload = archive.read("profile.txt")
    profile = pd.read_csv(
        io.BytesIO(payload),
        sep=r"\s+",
        header=None,
        names=list(PROFILE_COLUMNS),
        dtype=int,
    )
    profile.insert(0, "archive_row", np.arange(1, len(profile) + 1, dtype=int))
    return profile


def select_stable_factorial(
    profile: pd.DataFrame, *, repetitions: int = len(PRIMARY_REPETITIONS)
) -> pd.DataFrame:
    """Select the balanced complete stable factorial before any sensor values are read."""

    required = {"archive_row", *PROFILE_COLUMNS}
    missing = required - set(profile.columns)
    if missing:
        raise ValueError(f"profile is missing columns: {sorted(missing)}")
    stable = profile.loc[profile["stable"] == 0].copy()
    expected_cells = pd.MultiIndex.from_tuples(
        list(
            product(
                CONTEXT_LEVELS["cooler"],
                CONTEXT_LEVELS["pump"],
                CONTEXT_LEVELS["accumulator"],
                VALVE_LEVELS,
            )
        ),
        names=[*CONTEXT_COLUMNS, "valve"],
    )
    counts = stable.groupby([*CONTEXT_COLUMNS, "valve"], sort=True).size()
    if not counts.index.equals(expected_cells):
        missing_cells = expected_cells.difference(counts.index).tolist()
        extra_cells = counts.index.difference(expected_cells).tolist()
        raise ValueError(
            f"stable profile does not match frozen factorial: "
            f"missing={missing_cells}, extra={extra_cells}"
        )
    insufficient = counts.loc[counts < repetitions]
    if not insufficient.empty:
        raise ValueError(
            "stable profile has incomplete cells: "
            + ", ".join(f"{cell}={count}" for cell, count in insufficient.items())
        )
    stable["repetition"] = (
        stable.groupby([*CONTEXT_COLUMNS, "valve"], sort=False).cumcount() + 1
    )
    selected = stable.loc[stable["repetition"] <= repetitions].copy()
    selected["truth"] = selected["valve"].map(VALVE_LABELS)
    selected["sensor_row"] = selected["archive_row"] - 1
    selected["context_id"] = selected.apply(
        lambda row: (
            f"C{int(row['cooler'])}_P{int(row['pump'])}_A{int(row['accumulator'])}"
        ),
        axis=1,
    )
    expected_rows = len(expected_cells) * repetitions
    if len(selected) != expected_rows or selected["truth"].isna().any():
        raise ValueError("stable-factorial selection violated its frozen size or label mapping")
    return selected.sort_values("archive_row").reset_index(drop=True)


def load_stable_factorial(path: Path | None = None) -> pd.DataFrame:
    return select_stable_factorial(load_profile(path))


def _safe_divide(numerator: np.ndarray, denominator: np.ndarray) -> np.ndarray:
    return np.divide(
        numerator,
        denominator,
        out=np.zeros_like(numerator, dtype=float),
        where=denominator > 1e-12,
    )


def sensor_feature_matrix(values: np.ndarray) -> np.ndarray:
    """Extract the 24 frozen time, dynamic, and normalized-frequency features."""

    matrix = np.asarray(values, dtype=float)
    if matrix.ndim != 2 or matrix.shape[1] < 4:
        raise ValueError("sensor matrix must be two-dimensional with at least four samples")
    if not np.isfinite(matrix).all():
        raise ValueError("sensor matrix contains non-finite values")
    mean = matrix.mean(axis=1)
    centered = matrix - mean[:, None]
    variance = np.mean(centered**2, axis=1)
    std = np.sqrt(variance)
    rms = np.sqrt(np.mean(matrix**2, axis=1))
    minimum = matrix.min(axis=1)
    maximum = matrix.max(axis=1)
    quantiles = np.quantile(matrix, (0.05, 0.25, 0.50, 0.75, 0.95), axis=1)
    mean_absolute = np.mean(np.abs(matrix), axis=1)
    skewness = _safe_divide(np.mean(centered**3, axis=1), std**3)
    excess_kurtosis = _safe_divide(np.mean(centered**4, axis=1), variance**2) - 3.0
    excess_kurtosis[std <= 1e-12] = 0.0
    differences = np.diff(matrix, axis=1)
    diff_mean_absolute = np.mean(np.abs(differences), axis=1)
    diff_rms = np.sqrt(np.mean(differences**2, axis=1))
    time = np.linspace(-1.0, 1.0, matrix.shape[1])
    linear_slope = matrix @ time / np.sum(time**2)

    frequencies = np.fft.rfftfreq(matrix.shape[1], d=1.0)
    spectrum = np.fft.rfft(centered, axis=1)
    power = np.abs(spectrum) ** 2
    power[:, 0] = 0.0
    total_power = power.sum(axis=1)
    spectral_centroid = _safe_divide(power @ frequencies, total_power)
    spectral_variance = _safe_divide(
        np.sum(power * (frequencies[None, :] - spectral_centroid[:, None]) ** 2, axis=1),
        total_power,
    )
    spectral_bandwidth = np.sqrt(spectral_variance)
    probabilities = _safe_divide(power, total_power[:, None])
    entropy_terms = probabilities * np.log(np.maximum(probabilities, 1e-300))
    entropy_denominator = np.log(max(2, len(frequencies) - 1))
    spectral_entropy = -entropy_terms.sum(axis=1) / entropy_denominator

    def band_fraction(low: float, high: float, *, include_high: bool = False) -> np.ndarray:
        mask = (frequencies >= low) & (
            frequencies <= high if include_high else frequencies < high
        )
        return _safe_divide(power[:, mask].sum(axis=1), total_power)

    result = np.column_stack(
        (
            mean,
            std,
            rms,
            minimum,
            maximum,
            maximum - minimum,
            quantiles[0],
            quantiles[1],
            quantiles[2],
            quantiles[3],
            quantiles[4],
            quantiles[3] - quantiles[1],
            mean_absolute,
            skewness,
            excess_kurtosis,
            diff_mean_absolute,
            diff_rms,
            linear_slope,
            spectral_centroid,
            spectral_bandwidth,
            spectral_entropy,
            band_fraction(0.0, 0.1),
            band_fraction(0.1, 0.25),
            band_fraction(0.25, 0.5, include_high=True),
        )
    )
    if result.shape[1] != len(SENSOR_FEATURES) or not np.isfinite(result).all():
        raise ValueError("frozen sensor feature extraction produced an invalid matrix")
    return result


def _read_sensor(archive: ZipFile, sensor: SensorSpec) -> np.ndarray:
    with archive.open(f"{sensor.name}.txt") as source:
        frame = pd.read_csv(source, sep=r"\s+", header=None, dtype=np.float64)
    matrix = frame.to_numpy(dtype=float, copy=False)
    expected_shape = (2205, sensor.samples_per_cycle)
    if matrix.shape != expected_shape:
        raise ValueError(
            f"unexpected {sensor.name} shape: expected {expected_shape}, got {matrix.shape}"
        )
    return matrix


def extract_cycle_features(
    path: Path | None = None,
    *,
    sensors: Sequence[SensorSpec] = PHYSICAL_SENSORS,
) -> pd.DataFrame:
    """Extract the frozen primary cohort and features from the verified official archive."""

    resolved = verify_archive(path)
    cohort = select_stable_factorial(load_profile(resolved, verify=False))
    row_indices = cohort["sensor_row"].to_numpy(dtype=int)
    feature_blocks: list[pd.DataFrame] = []
    with ZipFile(resolved) as archive:
        for sensor in sensors:
            values = _read_sensor(archive, sensor)[row_indices]
            features = sensor_feature_matrix(values)
            columns = [f"{sensor.name.lower()}__{name}" for name in SENSOR_FEATURES]
            feature_blocks.append(pd.DataFrame(features, columns=columns))
    result = pd.concat([cohort.reset_index(drop=True), *feature_blocks], axis=1)
    feature_columns = [
        column
        for column in result.columns
        if "__" in column and column.split("__", maxsplit=1)[1] in SENSOR_FEATURES
    ]
    if len(feature_columns) != len(sensors) * len(SENSOR_FEATURES):
        raise ValueError("unexpected UCI hydraulic feature count")
    if not np.isfinite(result.loc[:, feature_columns].to_numpy(dtype=float)).all():
        raise ValueError("UCI hydraulic cycle features contain non-finite values")
    return result
