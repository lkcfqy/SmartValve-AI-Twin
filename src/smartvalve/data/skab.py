"""Adapter and transparent benchmark for the SKAB physical water loop."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path

import numpy as np
import pandas as pd

from smartvalve.data.contract import DataSourceMetadata, EvidenceGrade, SourceKind
from smartvalve.data.external import cache_directory

METADATA = DataSourceMetadata(
    source_id="skab-v0.9-valve1",
    name="SKAB Real Water Circulation Testbed",
    kind=SourceKind.SKAB,
    evidence_grade=EvidenceGrade.S1_PUBLIC_RIG,
    physical_scope="Physical water loop and valve closure; not a valve mechanical signature",
    provenance_url="https://github.com/waico/SKAB",
    license_name="GPL-3.0 repository license",
)


@dataclass(frozen=True)
class SkabValidationResult:
    data: pd.DataFrame
    score: pd.Series
    threshold: float
    precision: float
    recall: float
    f1: float
    normal_pressure_bar: float
    anomaly_pressure_bar: float
    normal_flow_lpm: float
    anomaly_flow_lpm: float
    anomaly_samples: int
    total_samples: int
    training_samples: int
    evaluation_samples: int

    def summary(self) -> dict[str, object]:
        result = asdict(self)
        result.pop("data")
        result.pop("score")
        return result


def load_skab_frame(path: Path | None = None) -> pd.DataFrame:
    path = path or cache_directory() / "skab_valve1_1.csv"
    if not path.is_file():
        raise FileNotFoundError(f"{path} is missing; run `make data`")
    frame = pd.read_csv(path, sep=";")
    frame = frame.rename(columns={"Volume Flow RateRMS": "FlowLPM"})
    frame["datetime"] = pd.to_datetime(frame["datetime"], errors="raise")
    frame["timestamp_s"] = (frame["datetime"] - frame["datetime"].iloc[0]).dt.total_seconds()
    numeric_columns = [
        "Accelerometer1RMS",
        "Accelerometer2RMS",
        "Current",
        "Pressure",
        "Temperature",
        "Thermocouple",
        "Voltage",
        "FlowLPM",
        "anomaly",
        "changepoint",
    ]
    frame[numeric_columns] = frame[numeric_columns].apply(pd.to_numeric, errors="raise")
    return frame


def _classification_metrics(
    labels: np.ndarray, prediction: np.ndarray
) -> tuple[float, float, float]:
    true_positive = int(np.sum(labels & prediction))
    false_positive = int(np.sum(~labels & prediction))
    false_negative = int(np.sum(labels & ~prediction))
    precision = true_positive / max(1, true_positive + false_positive)
    recall = true_positive / max(1, true_positive + false_negative)
    f1 = 2.0 * precision * recall / max(1e-12, precision + recall)
    return precision, recall, f1


def run_skab_validation(path: Path | None = None) -> SkabValidationResult:
    """Evaluate a fixed robust-distance baseline without leaking anomaly labels."""

    frame = load_skab_frame(path)
    feature_names = [
        "Pressure",
        "FlowLPM",
        "Current",
        "Voltage",
        "Accelerometer1RMS",
        "Accelerometer2RMS",
        "Temperature",
        "Thermocouple",
    ]
    values = frame[feature_names].to_numpy(dtype=float)
    training = values[:400]
    median = np.median(training, axis=0)
    mad = np.median(np.abs(training - median), axis=0)
    scale = np.maximum(1.4826 * mad, np.std(training, axis=0) * 0.15 + 1e-9)
    z_score = np.abs((values - median) / scale)
    score = np.mean(np.sort(z_score, axis=1)[:, -2:], axis=1)
    threshold = float(np.quantile(score[:400], 0.975))
    prediction = score > threshold
    labels = frame["anomaly"].to_numpy(dtype=bool)
    evaluation = slice(400, None)
    precision, recall, f1 = _classification_metrics(
        labels[evaluation], prediction[evaluation]
    )
    normal = frame.loc[~labels]
    anomaly = frame.loc[labels]
    return SkabValidationResult(
        data=frame,
        score=pd.Series(score, index=frame.index, name="anomaly_score"),
        threshold=round(threshold, 3),
        precision=round(precision, 3),
        recall=round(recall, 3),
        f1=round(f1, 3),
        normal_pressure_bar=round(float(normal["Pressure"].median()), 4),
        anomaly_pressure_bar=round(float(anomaly["Pressure"].median()), 4),
        normal_flow_lpm=round(float(normal["FlowLPM"].median()), 3),
        anomaly_flow_lpm=round(float(anomaly["FlowLPM"].median()), 3),
        anomaly_samples=int(labels.sum()),
        total_samples=len(frame),
        training_samples=400,
        evaluation_samples=len(frame) - 400,
    )
