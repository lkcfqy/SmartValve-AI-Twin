"""Canonical data contract shared by simulation, benchmarks and physical rigs."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from enum import StrEnum
from hashlib import sha256

import numpy as np
import pandas as pd


class SourceKind(StrEnum):
    SIMULATION = "simulation"
    CRANFIELD = "cranfield_real_actuator"
    SKAB = "skab_real_water_loop"
    DESKTOP_RIG = "desktop_rig"
    ENTERPRISE = "enterprise_valve"


class EvidenceGrade(StrEnum):
    S0_SIMULATION = "S0 · Simulation"
    S1_PUBLIC_RIG = "S1 · Public physical rig"
    S2_OWN_RIG = "S2 · Own physical rig"
    S3_ENTERPRISE = "S3 · Enterprise valve validation"


@dataclass(frozen=True)
class DataSourceMetadata:
    source_id: str
    name: str
    kind: SourceKind
    evidence_grade: EvidenceGrade
    physical_scope: str
    provenance_url: str
    license_name: str
    product_specific: bool = False

    def to_dict(self) -> dict[str, object]:
        data = asdict(self)
        data["kind"] = self.kind.value
        data["evidence_grade"] = self.evidence_grade.value
        return data


@dataclass(frozen=True)
class DataQualityReport:
    status: str
    score: float
    sample_count: int
    duration_s: float
    sampling_hz: float
    missing_required_pct: float
    duplicate_timestamps: int
    violations: tuple[str, ...]
    data_sha256: str

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


VALVE_REQUIRED_COLUMNS = (
    "timestamp_s",
    "valve_id",
    "source",
    "command_pct",
    "position_pct",
    "motor_current_a",
    "direction",
)


def _frame_digest(frame: pd.DataFrame) -> str:
    stable = frame.copy()
    stable = stable.reindex(sorted(stable.columns), axis=1)
    hashed = pd.util.hash_pandas_object(stable, index=True).to_numpy().tobytes()
    return sha256(hashed).hexdigest()


def validate_valve_frame(frame: pd.DataFrame, *, strict: bool = True) -> DataQualityReport:
    """Validate a full-stroke frame and return an auditable quality report."""

    missing_columns = [name for name in VALVE_REQUIRED_COLUMNS if name not in frame]
    if missing_columns:
        message = f"missing required columns: {', '.join(missing_columns)}"
        if strict:
            raise ValueError(message)
        return DataQualityReport(
            status="REJECTED",
            score=0.0,
            sample_count=len(frame),
            duration_s=0.0,
            sampling_hz=0.0,
            missing_required_pct=100.0,
            duplicate_timestamps=0,
            violations=(message,),
            data_sha256=_frame_digest(frame),
        )

    violations: list[str] = []
    numeric = frame.loc[:, ["timestamp_s", "command_pct", "position_pct", "motor_current_a"]]
    missing_pct = float(numeric.isna().mean().mean() * 100.0)
    timestamps = pd.to_numeric(frame["timestamp_s"], errors="coerce")
    duplicate_count = int(timestamps.duplicated().sum())
    finite_times = timestamps[np.isfinite(timestamps)]
    duration = float(finite_times.max() - finite_times.min()) if len(finite_times) > 1 else 0.0
    deltas = np.diff(finite_times.to_numpy(dtype=float))
    positive_deltas = deltas[deltas > 0]
    sampling_hz = float(1.0 / np.median(positive_deltas)) if positive_deltas.size else 0.0

    if missing_pct > 0.0:
        violations.append(f"required numeric missing rate is {missing_pct:.2f}%")
    if duplicate_count:
        violations.append(f"{duplicate_count} duplicate timestamps")
    if (deltas < 0).any():
        violations.append("timestamps are not monotonic")
    if not frame["command_pct"].dropna().between(0.0, 100.0).all():
        violations.append("command_pct outside 0..100")
    if not frame["position_pct"].dropna().between(0.0, 100.0).all():
        violations.append("position_pct outside 0..100")
    if (frame["motor_current_a"].dropna() < 0.0).any():
        violations.append("negative motor current")
    invalid_directions = set(frame["direction"].dropna()) - {"opening", "closing", "idle"}
    if invalid_directions:
        violations.append(f"invalid directions: {sorted(invalid_directions)}")
    if len(frame) < 50:
        violations.append("too few samples for a full-stroke signature")

    penalty = missing_pct * 2.5 + duplicate_count * 0.2 + len(violations) * 4.0
    score = float(np.clip(100.0 - penalty, 0.0, 100.0))
    status = "ACCEPTED" if score >= 90.0 and not violations else "REVIEW"
    if strict and score < 70.0:
        raise ValueError("data quality rejected: " + "; ".join(violations))
    return DataQualityReport(
        status=status,
        score=round(score, 1),
        sample_count=len(frame),
        duration_s=round(duration, 3),
        sampling_hz=round(sampling_hz, 3),
        missing_required_pct=round(missing_pct, 3),
        duplicate_timestamps=duplicate_count,
        violations=tuple(violations),
        data_sha256=_frame_digest(frame),
    )
