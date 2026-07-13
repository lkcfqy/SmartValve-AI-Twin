"""End-to-end orchestration for the two-layer digital twin."""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from smartvalve.data.contract import DataQualityReport, validate_valve_frame
from smartvalve.diagnosis.rules import DiagnosisResult, diagnose
from smartvalve.network_twin.model import NetworkImpact, simulate_network_impact
from smartvalve.signature.analysis import SignatureAnalysis, analyze_signature
from smartvalve.simulation.model import FaultConfig, ValveSimulator


@dataclass(frozen=True)
class TwinRun:
    baseline_data: pd.DataFrame
    current_data: pd.DataFrame
    signature: SignatureAnalysis
    diagnosis: DiagnosisResult
    network: NetworkImpact
    baseline_quality: DataQualityReport
    current_quality: DataQualityReport


def run_from_frames(baseline: pd.DataFrame, current: pd.DataFrame) -> TwinRun:
    """Run the same diagnostic chain for simulation, public rigs or physical uploads."""

    baseline_quality = validate_valve_frame(baseline)
    current_quality = validate_valve_frame(current)
    signature = analyze_signature(baseline, current)
    diagnosis = diagnose(signature, current)
    network = simulate_network_impact(diagnosis.available_travel_pct)
    return TwinRun(
        baseline_data=baseline,
        current_data=current,
        signature=signature,
        diagnosis=diagnosis,
        network=network,
        baseline_quality=baseline_quality,
        current_quality=current_quality,
    )


def run_twin(fault: FaultConfig | None = None) -> TwinRun:
    fault = fault or FaultConfig(fault_type="stiction", severity=0.75)
    simulator = ValveSimulator()
    baseline_fault = FaultConfig(
        fault_type="normal",
        severity=0.0,
        supply_voltage_v=fault.supply_voltage_v,
        load_factor=fault.load_factor,
        seed=fault.seed,
    )
    baseline = simulator.simulate(baseline_fault)
    current = simulator.simulate(fault)
    return run_from_frames(baseline, current)
