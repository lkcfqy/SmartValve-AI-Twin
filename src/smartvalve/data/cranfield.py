"""Adapter for the Cranfield real linear-actuator condition-monitoring dataset."""

from __future__ import annotations

import re
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.io import loadmat

from smartvalve.data.contract import (
    DataSourceMetadata,
    EvidenceGrade,
    SourceKind,
    validate_valve_frame,
)
from smartvalve.data.external import cache_directory

METADATA = DataSourceMetadata(
    source_id="cranfield-linear-actuator-2018",
    name="Cranfield Real Linear Actuator Rig",
    kind=SourceKind.CRANFIELD,
    evidence_grade=EvidenceGrade.S1_PUBLIC_RIG,
    physical_scope="Electromechanical ball-screw actuator; not a water valve",
    provenance_url="https://doi.org/10.17862/cranfield.rd.5097649",
    license_name="CC BY 4.0",
)

FILE_TO_FAULT = {
    "Normal.mat": ("normal", 0.0),
    "LackLubrication2.mat": ("lack_of_lubrication", 1.0),
    "Backlash2.mat": ("backlash", 1.0),
}


def _variable_pattern(filename: str, motion: str, load_kg: int, repetition: int) -> re.Pattern[str]:
    if motion not in {"trap", "sin"}:
        raise ValueError("motion must be 'trap' or 'sin'")
    if load_kg not in {-40, 20, 40}:
        raise ValueError("load_kg must be -40, 20 or 40")
    if not 1 <= repetition <= 10:
        raise ValueError("repetition must be between 1 and 10")
    prefix = {
        "Normal.mat": f"train{motion}",
        "LackLubrication2.mat": f"lub{motion}2nd",
        "Backlash2.mat": f"back{motion}2nd",
    }.get(filename)
    if prefix is None:
        raise ValueError(f"unsupported Cranfield file: {filename}")
    load_token = "neg40kg" if load_kg < 0 else f"{load_kg}kg"
    return re.compile(rf"^{prefix}{load_token}{repetition}$", re.IGNORECASE)


def _select_matrix(
    path: Path,
    *,
    motion: str,
    load_kg: int,
    repetition: int,
) -> tuple[str, np.ndarray]:
    contents = loadmat(path)
    pattern = _variable_pattern(path.name, motion, load_kg, repetition)
    matches = [(name, value) for name, value in contents.items() if pattern.match(name)]
    if len(matches) != 1:
        names = [name for name in contents if not name.startswith("__")]
        raise ValueError(f"expected one matrix for {pattern.pattern!r}; available={names[:6]}...")
    name, values = matches[0]
    if values.ndim != 2 or values.shape[1] != 3:
        raise ValueError(f"unexpected matrix shape for {name}: {values.shape}")
    return name, values.astype(float)


def load_cranfield_frame(
    filename: str,
    *,
    motion: str = "trap",
    load_kg: int = 20,
    repetition: int = 1,
    path: Path | None = None,
) -> pd.DataFrame:
    """Normalize one real 25 Hz experiment into the ValveDNA contract."""

    path = path or cache_directory() / filename
    if not path.is_file():
        raise FileNotFoundError(f"{path} is missing; run `make data`")
    variable, matrix = _select_matrix(path, motion=motion, load_kg=load_kg, repetition=repetition)
    setpoint_mm, position_error_mm, current_a = matrix.T
    lower, upper = float(np.min(setpoint_mm)), float(np.max(setpoint_mm))
    span = upper - lower
    if span <= 0:
        raise ValueError("Cranfield experiment has no commanded travel")
    actual_mm = setpoint_mm - position_error_mm
    command_pct = np.clip((setpoint_mm - lower) / span * 100.0, 0.0, 100.0)
    position_pct = np.clip((actual_mm - lower) / span * 100.0, 0.0, 100.0)
    command_delta = np.diff(command_pct, prepend=command_pct[0])
    direction = np.where(
        command_delta > 1e-5, "opening", np.where(command_delta < -1e-5, "closing", "idle")
    )
    fault_type, fault_severity = FILE_TO_FAULT[filename]
    dt_s = 0.04
    frame = pd.DataFrame(
        {
            "timestamp_s": np.arange(len(matrix), dtype=float) * dt_s,
            "valve_id": "CRANFIELD-EMA-01",
            "test_id": variable,
            "source": SourceKind.CRANFIELD.value,
            "command_pct": command_pct,
            "position_pct": position_pct,
            "actual_position_pct": position_pct,
            "velocity_pct_s": np.gradient(position_pct, dt_s),
            "motor_current_a": np.clip(current_a, 0.0, None),
            "supply_voltage_v": np.nan,
            "pressure_upstream_kpa": np.nan,
            "pressure_downstream_kpa": np.nan,
            "flow_lpm": np.nan,
            "temperature_c": np.nan,
            "direction": direction,
            "fault_type": fault_type,
            "fault_severity": fault_severity,
            "operating_condition_id": f"{motion}-{load_kg}kg",
            "seed": repetition,
        }
    )
    validate_valve_frame(frame)
    return frame


def load_cranfield_pair(
    *,
    fault_filename: str = "LackLubrication2.mat",
    motion: str = "trap",
    load_kg: int = 20,
    repetition: int = 1,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    baseline = load_cranfield_frame(
        "Normal.mat", motion=motion, load_kg=load_kg, repetition=repetition
    )
    current = load_cranfield_frame(
        fault_filename, motion=motion, load_kg=load_kg, repetition=repetition
    )
    return baseline, current
