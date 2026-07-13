"""Extract and compare ValveDNA current-versus-position signatures."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd


@dataclass(frozen=True)
class SignatureAnalysis:
    baseline_signature: pd.DataFrame
    current_signature: pd.DataFrame
    baseline_features: dict[str, float]
    current_features: dict[str, float]
    similarity_pct: float
    abnormal_start_pct: float | None
    abnormal_end_pct: float | None
    max_current_residual_a: float
    residual_rmse_a: float


def _direction_signature(data: pd.DataFrame, direction: str, grid: np.ndarray) -> np.ndarray:
    segment = data.loc[data["direction"] == direction, ["position_pct", "motor_current_a"]]
    if segment.empty:
        return np.full(grid.shape, np.nan)
    grouped = segment.groupby("position_pct", as_index=False)["motor_current_a"].mean()
    grouped = grouped.sort_values("position_pct")
    x = grouped["position_pct"].to_numpy(dtype=float)
    y = grouped["motor_current_a"].to_numpy(dtype=float)
    if len(x) < 2:
        return np.full(grid.shape, np.nan)
    values = np.interp(grid, x, y)
    values[(grid < x.min()) | (grid > x.max())] = np.nan
    return values


def build_signature(data: pd.DataFrame, points: int = 101) -> pd.DataFrame:
    grid = np.linspace(0.0, 100.0, points)
    return pd.DataFrame(
        {
            "position_pct": grid,
            "current_open_a": _direction_signature(data, "opening", grid),
            "current_close_a": _direction_signature(data, "closing", grid),
        }
    )


def _stroke_time(data: pd.DataFrame, direction: str) -> float:
    segment = data.loc[data["direction"] == direction]
    if segment.empty:
        return float("nan")
    if direction == "opening":
        start = segment.loc[segment["position_pct"] >= 5.0]
        end = segment.loc[segment["position_pct"] >= 95.0]
    else:
        start = segment.loc[segment["position_pct"] <= 95.0]
        end = segment.loc[segment["position_pct"] <= 5.0]
    if start.empty:
        return float("nan")
    start_time = float(start["timestamp_s"].iloc[0])
    end_time = (
        float(end["timestamp_s"].iloc[0]) if not end.empty else float(segment["timestamp_s"].max())
    )
    return max(0.0, end_time - start_time)


def _longest_stagnation(data: pd.DataFrame) -> float:
    dt = float(np.median(np.diff(data["timestamp_s"])))
    commanded = data["direction"].isin(["opening", "closing"])
    delta = data["position_pct"].diff().abs().fillna(0.0)
    threshold = float(data.loc[commanded, "motor_current_a"].median()) if commanded.any() else 0.0
    stagnant = commanded & (delta < 0.015) & (data["motor_current_a"] > threshold)
    longest = run = 0
    for value in stagnant.to_numpy(dtype=bool):
        run = run + 1 if value else 0
        longest = max(longest, run)
    return longest * dt


def extract_features(data: pd.DataFrame, signature: pd.DataFrame | None = None) -> dict[str, float]:
    signature = signature if signature is not None else build_signature(data)
    moving = data["direction"].isin(["opening", "closing"])
    process_residual = 0.0
    if "flow_lpm" in data:
        observed_flow = pd.to_numeric(data["flow_lpm"], errors="coerce")
        finite_flow = np.isfinite(observed_flow)
        if finite_flow.any():
            nominal_flow = max(float(observed_flow[finite_flow].max()), 1e-6)
            expected_flow = (
                nominal_flow
                * np.clip(data.loc[finite_flow, "position_pct"] / 100.0, 0.0, 1.0) ** 1.8
            )
            process_residual = float(
                np.mean(np.abs(observed_flow[finite_flow] - expected_flow)) / nominal_flow
            )
    hysteresis = np.nanmean(
        np.abs(signature["current_open_a"].to_numpy() - signature["current_close_a"].to_numpy())
    )
    return {
        "stroke_time_open_s": _stroke_time(data, "opening"),
        "stroke_time_close_s": _stroke_time(data, "closing"),
        "peak_current_a": float(data["motor_current_a"].max()),
        "mean_moving_current_a": float(data.loc[moving, "motor_current_a"].mean()),
        "max_position_pct": float(data["position_pct"].max()),
        "min_position_pct": float(data["position_pct"].min()),
        "stagnation_s": _longest_stagnation(data),
        "hysteresis_current_a": float(hysteresis),
        "process_consistency_error": process_residual,
    }


def analyze_signature(baseline: pd.DataFrame, current: pd.DataFrame) -> SignatureAnalysis:
    baseline_signature = build_signature(baseline)
    current_signature = build_signature(current)
    baseline_features = extract_features(baseline, baseline_signature)
    current_features = extract_features(current, current_signature)

    residuals: list[np.ndarray] = []
    for column in ("current_open_a", "current_close_a"):
        residuals.append(
            current_signature[column].to_numpy() - baseline_signature[column].to_numpy()
        )
    residual_matrix = np.vstack(residuals)
    finite = np.isfinite(residual_matrix)
    finite_residuals = residual_matrix[finite]
    rmse = float(np.sqrt(np.mean(finite_residuals**2))) if finite_residuals.size else float("inf")
    baseline_peak = max(baseline_features["peak_current_a"], 0.1)
    similarity = float(np.clip(100.0 * (1.0 - rmse / (1.6 * baseline_peak)), 0.0, 100.0))

    masked_residual = np.where(np.isfinite(residual_matrix), residual_matrix, -np.inf)
    positive_residual = np.max(masked_residual, axis=0)
    positive_residual[~np.isfinite(positive_residual)] = np.nan
    threshold = max(0.08, baseline_peak * 0.16)
    abnormal = np.isfinite(positive_residual) & (positive_residual > threshold)
    grid = baseline_signature["position_pct"].to_numpy()
    abnormal_start = float(grid[abnormal].min()) if abnormal.any() else None
    abnormal_end = float(grid[abnormal].max()) if abnormal.any() else None
    max_residual = (
        float(np.nanmax(positive_residual)) if np.isfinite(positive_residual).any() else 0.0
    )

    return SignatureAnalysis(
        baseline_signature=baseline_signature,
        current_signature=current_signature,
        baseline_features=baseline_features,
        current_features=current_features,
        similarity_pct=similarity,
        abnormal_start_pct=abnormal_start,
        abnormal_end_pct=abnormal_end,
        max_current_residual_a=max_residual,
        residual_rmse_a=rmse,
    )
