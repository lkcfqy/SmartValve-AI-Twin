"""Transparent rule-based diagnosis built on ValveDNA evidence."""

from __future__ import annotations

from dataclasses import asdict, dataclass

import numpy as np
import pandas as pd

from smartvalve.signature.analysis import SignatureAnalysis


@dataclass(frozen=True)
class DiagnosisResult:
    primary_finding: str
    decision_state: str
    ne107_status: str
    health_score: float
    confidence: float
    available_travel_pct: float
    resistance_multiplier: float
    abnormal_start_pct: float | None
    abnormal_end_pct: float | None
    evidence: dict[str, float]
    recommendation: str
    validation_source: str

    def to_dict(self) -> dict[str, object]:
        return {
            **asdict(self),
            "confidence_kind": "heuristic_evidence_strength_not_calibrated_probability",
        }


def _ratio(numerator: float, denominator: float) -> float:
    if not np.isfinite(numerator) or not np.isfinite(denominator) or abs(denominator) < 1e-9:
        return 1.0
    return float(numerator / denominator)


def diagnose(
    analysis: SignatureAnalysis,
    current_data: pd.DataFrame,
) -> DiagnosisResult:
    """Return an explainable diagnosis without reading the hidden fault label."""

    base = analysis.baseline_features
    current = analysis.current_features
    current_ratio = _ratio(current["mean_moving_current_a"], base["mean_moving_current_a"])
    stroke_ratio = _ratio(current["stroke_time_open_s"], base["stroke_time_open_s"])
    process_excess = max(
        0.0, current["process_consistency_error"] - base["process_consistency_error"]
    )
    baseline_max_position = float(np.clip(base["max_position_pct"], 0.0, 100.0))
    max_position = float(np.clip(current["max_position_pct"], 0.0, 100.0))
    travel_loss = max(0.0, baseline_max_position - max_position)
    peak_current_ratio = _ratio(current["peak_current_a"], base["peak_current_a"])
    stagnation_excess = max(0.0, current["stagnation_s"] - base["stagnation_s"])
    supply_voltage = 5.0
    if "supply_voltage_v" in current_data:
        voltage_samples = pd.to_numeric(current_data["supply_voltage_v"], errors="coerce").dropna()
        if not voltage_samples.empty:
            supply_voltage = float(voltage_samples.median())

    incomplete_travel = max_position < 94.0 and travel_loss > 2.0
    local_current_anomaly = analysis.max_current_residual_a > 0.10
    process_mismatch = process_excess > 0.015

    if process_mismatch and current_ratio < 1.18 and not incomplete_travel:
        finding = "Position sensor drift / process inconsistency"
        recommendation = (
            "Verify position feedback calibration and linkage; compare reported position "
            "with an independent travel reference."
        )
    elif incomplete_travel and analysis.max_current_residual_a > 0.90:
        finding = "Persistent localized stiction"
        location = analysis.abnormal_start_pct or max_position
        recommendation = (
            f"Inspect the stem/gear path near {location:.0f}% travel; remove the sticking source "
            "and repeat a full-stroke signature test before return to service."
        )
    elif current_ratio < 0.98 and (stroke_ratio > 1.10 or travel_loss > 3.0):
        finding = "Actuator performance degradation"
        recommendation = (
            "Check supply voltage, actuator output and drivetrain efficiency; verify stroke time "
            "under the same load condition."
        )
    elif incomplete_travel and peak_current_ratio > 1.75:
        finding = "Travel obstruction or persistent stiction"
        recommendation = (
            f"Inspect the mechanical path near {max_position:.0f}% travel; remove the obstruction "
            "and repeat a full-stroke test before return to service."
        )
    elif local_current_anomaly and stagnation_excess > 0.15:
        finding = "Localized stiction"
        location = analysis.abnormal_start_pct or 0.0
        recommendation = (
            f"Inspect stem/gear transmission near {location:.0f}% travel and repeat the "
            "signature test after adjustment or lubrication."
        )
    elif current_ratio > 1.15 and (stroke_ratio > 1.10 or analysis.similarity_pct < 95.0):
        finding = "Friction growth"
        recommendation = (
            "Check transmission alignment, lubrication, packing load and mechanical interference; "
            "compare the next test with the current signature."
        )
    elif stroke_ratio > 1.30 and current_ratio < 0.98:
        finding = "Actuator performance degradation"
        recommendation = (
            "Check supply voltage, actuator output and drivetrain efficiency; verify stroke time "
            "under the same load condition."
        )
    elif incomplete_travel or analysis.similarity_pct < 88.0:
        finding = "Unclassified signature deviation"
        recommendation = "Repeat the test under controlled load and request engineering review."
    else:
        finding = "No actionable deviation"
        recommendation = "Keep the current baseline and continue condition-based monitoring."

    actuation_penalty = np.clip((stroke_ratio - 1.0) * 55.0 + stagnation_excess * 8.0, 0, 100)
    friction_penalty = np.clip(
        (current_ratio - 1.0) * 75.0 + analysis.max_current_residual_a * 45.0, 0, 100
    )
    travel_health = np.clip(100.0 - 2.2 * travel_loss, 0, 100)
    sensor_health = np.clip(100.0 - process_excess * 700.0, 0, 100)
    process_health = 100.0
    actuation_health = 100.0 - actuation_penalty
    friction_health = 100.0 - friction_penalty
    health_score = float(
        np.clip(
            0.30 * actuation_health
            + 0.25 * friction_health
            + 0.20 * travel_health
            + 0.15 * sensor_health
            + 0.10 * process_health,
            0.0,
            100.0,
        )
    )

    if supply_voltage < 4.2 or supply_voltage > 5.8:
        ne107_status = "S — Out of Specification"
    elif max_position < 75.0:
        ne107_status = "F — Failure"
    elif health_score < 88.0 or finding != "No actionable deviation":
        ne107_status = "M — Maintenance Required"
    else:
        ne107_status = "Normal"

    evidence_strength = max(
        max(0.0, 1.0 - analysis.similarity_pct / 100.0),
        max(0.0, current_ratio - 1.0),
        max(0.0, stroke_ratio - 1.0),
        max(0.0, (100.0 - max_position) / 30.0),
        process_excess * 5.0,
    )
    confidence = (
        0.92 if finding == "No actionable deviation" else 0.62 + 0.30 * min(1.0, evidence_strength)
    )

    if finding == "No actionable deviation":
        decision_state = "normal"
    elif finding.startswith("Unclassified") or not 4.2 <= supply_voltage <= 5.8:
        decision_state = "needs_review"
    else:
        decision_state = "diagnosed"

    resistance_multiplier = 1.0
    if incomplete_travel:
        resistance_multiplier += 80.0 * ((100.0 - max_position) / 100.0) ** 2

    return DiagnosisResult(
        primary_finding=finding,
        decision_state=decision_state,
        ne107_status=ne107_status,
        health_score=round(health_score, 1),
        confidence=round(float(np.clip(confidence, 0.0, 0.96)), 2),
        available_travel_pct=round(max_position, 1),
        resistance_multiplier=round(float(resistance_multiplier), 2),
        abnormal_start_pct=analysis.abnormal_start_pct,
        abnormal_end_pct=analysis.abnormal_end_pct,
        evidence={
            "valvedna_similarity_pct": round(analysis.similarity_pct, 1),
            "moving_current_ratio": round(current_ratio, 3),
            "opening_stroke_time_ratio": round(stroke_ratio, 3),
            "max_current_residual_a": round(analysis.max_current_residual_a, 3),
            "stagnation_excess_s": round(stagnation_excess, 3),
            "process_consistency_excess": round(process_excess, 4),
            "max_reported_travel_pct": round(max_position, 2),
            "baseline_max_travel_pct": round(baseline_max_position, 2),
            "relative_travel_loss_pct": round(travel_loss, 2),
            "peak_current_ratio": round(peak_current_ratio, 3),
        },
        recommendation=recommendation,
        validation_source=str(current_data["source"].iloc[0]).title(),
    )
