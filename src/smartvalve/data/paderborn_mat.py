"""Semantic, outcome-blind parser for one Paderborn MATLAB measurement."""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Any

import numpy as np
from scipy.io import loadmat

from smartvalve.data.paderborn_features import (
    MAXIMUM_STORED_SAMPLES_PER_MAIN_SIGNAL,
    MINIMUM_STORED_SAMPLES_PER_MAIN_SIGNAL,
    SAMPLES_PER_MAIN_SIGNAL,
    extract_main_signal_features,
    parse_measurement_filename,
)

MAT_CHANNEL_MAP = {
    "vibration_1": "vibration",
    "phase_current_1": "current_u",
    "phase_current_2": "current_v",
}


def _field_mapping(value: Any) -> dict[str, Any] | None:
    if isinstance(value, Mapping):
        return {str(key): item for key, item in value.items()}
    field_names = getattr(value, "_fieldnames", None)
    if field_names:
        return {str(name): getattr(value, name) for name in field_names}
    if isinstance(value, np.void) and value.dtype.names:
        return {str(name): value[name] for name in value.dtype.names}
    return None


def _text(value: Any) -> str | None:
    if isinstance(value, str):
        return value
    array = np.asarray(value)
    if array.size != 1:
        return None
    scalar = array.reshape(-1)[0]
    if isinstance(scalar, str):
        return scalar
    return None


def _named_arrays(
    value: Any,
    *,
    path: str = "root",
) -> list[tuple[str, np.ndarray, str]]:
    """Find semantic Name/Data records without assuming MATLAB field positions."""

    mapping = _field_mapping(value)
    output: list[tuple[str, np.ndarray, str]] = []
    if mapping is not None:
        casefold = {key.casefold(): key for key in mapping}
        if "name" in casefold and "data" in casefold:
            name_key = casefold["name"]
            data_key = casefold["data"]
            name = _text(mapping[name_key])
            data = np.asarray(mapping[data_key])
            if name is not None and np.issubdtype(data.dtype, np.number):
                output.append((name, data, f"{path}.{data_key}"))
        for key, item in mapping.items():
            if key.startswith("__") or key.casefold() == "data":
                continue
            output.extend(_named_arrays(item, path=f"{path}.{key}"))
        return output
    if isinstance(value, np.ndarray):
        if value.dtype.names or value.dtype == object:
            for index, item in enumerate(value.reshape(-1)):
                output.extend(_named_arrays(item, path=f"{path}[{index}]"))
        return output
    if isinstance(value, (list, tuple)):
        for index, item in enumerate(value):
            output.extend(_named_arrays(item, path=f"{path}[{index}]"))
    return output


def extract_named_main_channels_with_length(
    root: Any,
) -> tuple[dict[str, np.ndarray], int]:
    """Extract the frozen window and return the common stored channel length."""

    matches: dict[str, tuple[np.ndarray, str]] = {}
    stored_lengths: set[int] = set()
    for original_name, data, path in _named_arrays(root):
        normalized_name = original_name.strip()
        if normalized_name not in MAT_CHANNEL_MAP:
            continue
        if normalized_name in matches:
            raise ValueError(f"duplicate Paderborn signal record: {normalized_name}")
        stored_values = np.asarray(data, dtype=np.float64).squeeze()
        if stored_values.ndim != 1 or not (
            MINIMUM_STORED_SAMPLES_PER_MAIN_SIGNAL
            <= len(stored_values)
            <= MAXIMUM_STORED_SAMPLES_PER_MAIN_SIGNAL
        ):
            raise ValueError(
                f"{normalized_name} at {path} must contain between "
                f"{MINIMUM_STORED_SAMPLES_PER_MAIN_SIGNAL} and "
                f"{MAXIMUM_STORED_SAMPLES_PER_MAIN_SIGNAL} stored samples"
            )
        if not np.isfinite(stored_values).all():
            raise ValueError(f"{normalized_name} at {path} contains non-finite samples")
        matches[normalized_name] = (stored_values, path)
        stored_lengths.add(len(stored_values))
    if set(matches) != set(MAT_CHANNEL_MAP):
        missing = sorted(set(MAT_CHANNEL_MAP) - set(matches))
        raise ValueError(f"Paderborn MAT root is missing main signals: {missing}")
    if len(stored_lengths) != 1:
        raise ValueError("Paderborn main channels must have the same stored length")
    stored_samples = stored_lengths.pop()
    channels = {
        MAT_CHANNEL_MAP[name]: normalize_main_signal(matches[name][0]) for name in MAT_CHANNEL_MAP
    }
    return channels, stored_samples


def normalize_main_signal(values: np.ndarray) -> np.ndarray:
    """Linearly map one complete nominal four-second record to 256,000 samples."""

    array = np.asarray(values, dtype=np.float64)
    if array.ndim != 1 or not (
        MINIMUM_STORED_SAMPLES_PER_MAIN_SIGNAL
        <= len(array)
        <= MAXIMUM_STORED_SAMPLES_PER_MAIN_SIGNAL
    ):
        raise ValueError("Paderborn signal length is outside the frozen corpus range")
    if len(array) == SAMPLES_PER_MAIN_SIGNAL:
        return array.copy()
    source = np.linspace(0.0, 1.0, len(array), dtype=np.float64)
    target = np.linspace(0.0, 1.0, SAMPLES_PER_MAIN_SIGNAL, dtype=np.float64)
    return np.interp(target, source, array).astype(np.float64, copy=False)


def extract_named_main_channels(root: Any) -> dict[str, np.ndarray]:
    """Extract the three frozen channels from a simplified MATLAB root object."""

    return extract_named_main_channels_with_length(root)[0]


def inspect_named_main_channel_structure(root: Any) -> dict[str, dict[str, Any]]:
    """Return semantic names and array metadata without enforcing sample counts.

    The sealed structure probe exists to discover shapes before the value parser is
    allowed to run.  Enforcing the prospective length assumption here would turn
    that discovery step into a circular validation gate.  Dimensionality, length,
    finiteness, and feature compatibility remain strict in
    :func:`extract_named_main_channels`.
    """

    matches: dict[str, tuple[np.ndarray, str]] = {}
    for original_name, data, path in _named_arrays(root):
        normalized_name = original_name.strip()
        if normalized_name not in MAT_CHANNEL_MAP:
            continue
        if normalized_name in matches:
            raise ValueError(f"duplicate Paderborn signal record: {normalized_name}")
        array = np.asarray(data)
        matches[normalized_name] = (array, path)
    if set(matches) != set(MAT_CHANNEL_MAP):
        missing = sorted(set(MAT_CHANNEL_MAP) - set(matches))
        raise ValueError(f"Paderborn MAT root is missing main signals: {missing}")
    return {
        MAT_CHANNEL_MAP[name]: {
            "semantic_name": name,
            "semantic_path": matches[name][1],
            "stored_shape": list(matches[name][0].shape),
            "shape": list(matches[name][0].squeeze().shape),
            "dtype": str(matches[name][0].dtype),
            "samples": int(matches[name][0].size),
        }
        for name in MAT_CHANNEL_MAP
    }


def load_main_channels_with_length(
    path: Path,
) -> tuple[dict[str, np.ndarray], int]:
    """Load one canonical measurement plus its common stored channel length."""

    parse_measurement_filename(path.name)
    payload = loadmat(path, simplify_cells=True)
    roots = {key: value for key, value in payload.items() if not key.startswith("__")}
    if set(roots) != {path.stem}:
        raise ValueError(f"Paderborn MAT root keys must equal the filename stem: {sorted(roots)}")
    return extract_named_main_channels_with_length(roots[path.stem])


def load_main_channels(path: Path) -> dict[str, np.ndarray]:
    """Load one canonical measurement and require its root key to equal the stem."""

    return load_main_channels_with_length(path)[0]


def inspect_main_channel_structure(path: Path) -> dict[str, Any]:
    """Return names/shapes/dtypes only; never compute value-dependent diagnostics."""

    parse_measurement_filename(path.name)
    payload = loadmat(path, simplify_cells=True)
    roots = {key: value for key, value in payload.items() if not key.startswith("__")}
    if set(roots) != {path.stem}:
        raise ValueError(f"Paderborn MAT root keys must equal the filename stem: {sorted(roots)}")
    return {
        "filename": path.name,
        "root_key": path.stem,
        "channels": inspect_named_main_channel_structure(roots[path.stem]),
        "signal_values_loaded_by_mat_reader": True,
        "value_dependent_validation_performed": False,
        "values_or_statistics_emitted": False,
    }


def extract_measurement_features(path: Path) -> np.ndarray:
    return extract_main_signal_features(load_main_channels(path))


def extract_measurement_features_with_length(path: Path) -> tuple[np.ndarray, int]:
    channels, stored_samples = load_main_channels_with_length(path)
    return extract_main_signal_features(channels), stored_samples
