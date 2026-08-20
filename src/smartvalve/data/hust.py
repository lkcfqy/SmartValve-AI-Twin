"""Sealed HUST Bearing v3 primary-cohort and signal feature contract."""

from __future__ import annotations

import hashlib
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from scipy.io import loadmat

from smartvalve.data.uci_hydraulic import SENSOR_FEATURES, sensor_feature_matrix

HUST_SAMPLING_HZ = 51_200
HUST_RECORDING_SECONDS = 10
HUST_WINDOW_SECONDS = 1
HUST_SAMPLES_PER_RECORDING = HUST_SAMPLING_HZ * HUST_RECORDING_SECONDS
HUST_SAMPLES_PER_WINDOW = HUST_SAMPLING_HZ * HUST_WINDOW_SECONDS
HUST_WINDOWS_PER_RECORDING = HUST_RECORDING_SECONDS // HUST_WINDOW_SECONDS
HUST_PRIMARY_CONDITIONS = ("N", "I", "O")
HUST_SPECIFICATION_GROUPS = (4, 5, 6, 7, 8)
HUST_LOADS_W = (0, 200, 400)
HUST_LABELS = ("healthy", "outer", "inner")
HUST_CONDITION_TO_LABEL = {"N": "healthy", "O": "outer", "I": "inner"}
HUST_INVENTORY_SHA256 = "98283df45832cf5504403d1d7573cd0f03e11b91161b944f91ff124075209713"


@dataclass(frozen=True)
class HustMatSignal:
    variable_name: str
    original_shape: tuple[int, ...]
    original_dtype: str
    values: np.ndarray


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def hust_feature_names() -> tuple[str, ...]:
    return tuple(f"vibration__{name}" for name in SENSOR_FEATURES)


def select_hust_primary_inventory(inventory: pd.DataFrame) -> pd.DataFrame:
    """Select and validate the sealed 45-record N/I/O factorial from official metadata."""

    required = {
        "filename",
        "file_id",
        "folder_id",
        "condition",
        "bearing_type",
        "load_w",
        "bytes",
        "sha256",
    }
    missing = required - set(inventory)
    if missing:
        raise ValueError(f"HUST inventory is missing columns: {sorted(missing)}")
    primary = inventory.loc[inventory["condition"].astype(str).isin(HUST_PRIMARY_CONDITIONS)].copy()
    primary.rename(columns={"bearing_type": "specification_group"}, inplace=True)
    primary["specification_group"] = primary["specification_group"].astype(int)
    primary["load_w"] = primary["load_w"].astype(int)
    primary["bearing_code"] = primary["condition"].astype(str) + primary[
        "specification_group"
    ].astype(str)
    primary["truth"] = primary["condition"].map(HUST_CONDITION_TO_LABEL)
    expected = {
        (condition, group, load)
        for condition in HUST_PRIMARY_CONDITIONS
        for group in HUST_SPECIFICATION_GROUPS
        for load in HUST_LOADS_W
    }
    observed = set(
        primary.loc[:, ["condition", "specification_group", "load_w"]].itertuples(
            index=False, name=None
        )
    )
    if (
        len(primary) != 45
        or primary["filename"].nunique() != 45
        or observed != expected
        or primary["truth"].isna().any()
    ):
        raise ValueError("HUST primary inventory differs from the sealed 45-record factorial")
    counts = primary.groupby("bearing_code", observed=True).agg(
        loads=("load_w", "nunique"), labels=("truth", "nunique")
    )
    if len(counts) != 15 or not counts["loads"].eq(3).all() or not counts["labels"].eq(1).all():
        raise ValueError("HUST physical-bearing hierarchy changed")
    return primary.sort_values(
        ["condition", "specification_group", "load_w"], kind="stable"
    ).reset_index(drop=True)


def inspect_hust_signal_vector(mat_contents: Mapping[str, Any]) -> HustMatSignal:
    """Inspect and return the sole eligible signal without outcome-dependent selection."""

    candidates = []
    for name, value in mat_contents.items():
        if str(name).startswith("__"):
            continue
        array = np.asarray(value)
        if (
            not np.issubdtype(array.dtype, np.number)
            or np.iscomplexobj(array)
            or array.dtype == object
        ):
            continue
        squeezed = np.squeeze(array)
        if squeezed.ndim != 1 or len(squeezed) != HUST_SAMPLES_PER_RECORDING:
            continue
        numeric = squeezed.astype(np.float64, copy=False)
        if not np.isfinite(numeric).all():
            raise ValueError(f"HUST MAT candidate {name} contains non-finite samples")
        candidates.append(
            HustMatSignal(
                variable_name=str(name),
                original_shape=tuple(int(size) for size in array.shape),
                original_dtype=str(array.dtype),
                values=numeric,
            )
        )
    if len(candidates) != 1:
        names = [candidate.variable_name for candidate in candidates]
        raise ValueError(f"HUST MAT must contain exactly one eligible signal vector: {names}")
    return candidates[0]


def select_hust_signal_vector(mat_contents: Mapping[str, Any]) -> np.ndarray:
    """Select the sole eligible finite 512,000-sample real vector from a MAT mapping."""

    return inspect_hust_signal_vector(mat_contents).values


def extract_hust_window_features(signal: np.ndarray) -> pd.DataFrame:
    """Apply the sealed ten non-overlapping one-second window feature contract."""

    values = np.asarray(signal, dtype=np.float64)
    if values.ndim != 1 or len(values) != HUST_SAMPLES_PER_RECORDING:
        raise ValueError(f"HUST signal must contain exactly {HUST_SAMPLES_PER_RECORDING} samples")
    if not np.isfinite(values).all():
        raise ValueError("HUST signal contains non-finite samples")
    windows = values.reshape(HUST_WINDOWS_PER_RECORDING, HUST_SAMPLES_PER_WINDOW)
    features = sensor_feature_matrix(windows)
    result = pd.DataFrame(features, columns=hust_feature_names())
    result.insert(0, "window_index", np.arange(HUST_WINDOWS_PER_RECORDING, dtype=int))
    if (
        len(result) != 10
        or not np.isfinite(result.loc[:, hust_feature_names()].to_numpy(dtype=float)).all()
    ):
        raise ValueError("HUST window feature output changed")
    return result


def load_hust_mat_features(path: Path, *, expected_sha256: str) -> pd.DataFrame:
    """Verify one official MAT payload before opening and extracting features."""

    if not path.is_file():
        raise FileNotFoundError(path)
    observed = file_sha256(path)
    if observed != expected_sha256:
        raise ValueError(
            f"HUST MAT SHA-256 changed for {path.name}: expected {expected_sha256}, "
            f"observed {observed}"
        )
    contents = loadmat(path, verify_compressed_data_integrity=True)
    return extract_hust_window_features(inspect_hust_signal_vector(contents).values)
