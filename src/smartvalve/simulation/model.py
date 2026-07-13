"""Deterministic lumped-parameter simulation of an electric quarter-turn valve.

The model is deliberately small and interpretable. It is not a CFD model and its
parameters are not calibrated to a specific manufacturer's product.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

FAULT_TYPES = (
    "normal",
    "friction",
    "stiction",
    "obstruction",
    "actuator_degradation",
    "sensor_drift",
)


@dataclass(frozen=True)
class FaultConfig:
    """Fault and operating-condition inputs for one full-stroke test."""

    fault_type: str = "normal"
    severity: float = 0.0
    location_pct: float = 65.0
    width_pct: float = 8.0
    supply_voltage_v: float = 5.0
    load_factor: float = 1.0
    seed: int = 7

    def __post_init__(self) -> None:
        if self.fault_type not in FAULT_TYPES:
            raise ValueError(f"Unsupported fault_type={self.fault_type!r}")
        if not 0.0 <= self.severity <= 1.0:
            raise ValueError("severity must be between 0 and 1")
        if not 5.0 <= self.location_pct <= 95.0:
            raise ValueError("location_pct must be between 5 and 95")
        if self.width_pct <= 0:
            raise ValueError("width_pct must be positive")
        if self.supply_voltage_v <= 0 or self.load_factor <= 0:
            raise ValueError("supply voltage and load factor must be positive")


@dataclass(frozen=True)
class ValveModelParameters:
    """Nominal, non-product-specific parameters for the demonstration model."""

    dt_s: float = 0.05
    duration_s: float = 14.0
    open_command_s: float = 1.0
    close_command_s: float = 7.5
    max_speed_pct_s: float = 24.0
    no_load_current_a: float = 0.11
    speed_current_gain: float = 0.010
    friction_current_gain: float = 0.075
    max_flow_lpm: float = 12.0
    upstream_pressure_kpa: float = 350.0
    downstream_pressure_kpa: float = 250.0


class ValveSimulator:
    """Generate a reproducible full-open/full-close diagnostic test."""

    def __init__(self, parameters: ValveModelParameters | None = None) -> None:
        self.parameters = parameters or ValveModelParameters()

    def simulate(self, fault: FaultConfig | None = None) -> pd.DataFrame:
        fault = fault or FaultConfig()
        p = self.parameters
        rng = np.random.default_rng(fault.seed)
        times = np.arange(0.0, p.duration_s + p.dt_s / 2, p.dt_s)

        actual_position = 0.0
        rows: list[dict[str, float | str | int]] = []

        obstruction_limit = 100.0
        if fault.fault_type == "obstruction":
            obstruction_limit = 100.0 - 45.0 * fault.severity

        for time_s in times:
            if time_s < p.open_command_s:
                command = 0.0
            elif time_s < p.close_command_s:
                command = 100.0
            else:
                command = 0.0

            error = command - actual_position
            direction_sign = float(np.sign(error))
            local_profile = float(
                np.exp(-0.5 * ((actual_position - fault.location_pct) / fault.width_pct) ** 2)
            )

            friction_load = fault.load_factor
            if fault.fault_type == "friction":
                friction_load *= 1.0 + 0.50 * fault.severity
            elif fault.fault_type == "stiction":
                friction_load *= 1.0 + 18.0 * fault.severity * local_profile

            actuator_gain = fault.supply_voltage_v / 5.0
            if fault.fault_type == "actuator_degradation":
                actuator_gain *= 1.0 - 0.62 * fault.severity

            requested_speed = p.max_speed_pct_s * np.tanh(abs(error) / 7.0)
            speed = direction_sign * requested_speed * actuator_gain / friction_load
            blocked = False

            if direction_sign > 0 and actual_position >= obstruction_limit:
                speed = 0.0
                blocked = command > obstruction_limit + 0.5

            movement = float(np.clip(speed * p.dt_s, -abs(error), abs(error)))
            actual_position = float(np.clip(actual_position + movement, 0.0, obstruction_limit))

            moving = abs(speed) > 0.03
            current = p.no_load_current_a
            if moving:
                current += p.speed_current_gain * abs(speed)
                current += p.friction_current_gain * friction_load
                current += 0.35 * max(0.0, friction_load - fault.load_factor)
            if blocked:
                current += 0.65 + 0.35 * fault.severity
            current += float(rng.normal(0.0, 0.006))
            current = float(np.clip(current, 0.02, 2.5))

            sensor_offset = 0.0
            if fault.fault_type == "sensor_drift":
                sensor_offset = fault.severity * (2.0 + 7.0 * time_s / p.duration_s)
            measured_position = float(
                np.clip(actual_position + sensor_offset + rng.normal(0.0, 0.08), 0.0, 100.0)
            )

            pressure_drop = p.upstream_pressure_kpa - p.downstream_pressure_kpa
            opening_fraction = np.clip(actual_position / 100.0, 0.0, 1.0)
            flow = p.max_flow_lpm * opening_fraction**1.8 * np.sqrt(pressure_drop / 100.0)
            flow = max(0.0, float(flow + rng.normal(0.0, 0.025)))

            if command > actual_position + 0.15:
                direction = "opening"
            elif command < actual_position - 0.15:
                direction = "closing"
            else:
                direction = "idle"

            rows.append(
                {
                    "timestamp_s": round(float(time_s), 6),
                    "valve_id": "VALVE-DEMO-07",
                    "test_id": f"full-stroke-{fault.seed}",
                    "source": "simulation",
                    "command_pct": command,
                    "position_pct": measured_position,
                    "actual_position_pct": actual_position,
                    "velocity_pct_s": speed,
                    "motor_current_a": current,
                    "supply_voltage_v": fault.supply_voltage_v,
                    "pressure_upstream_kpa": p.upstream_pressure_kpa,
                    "pressure_downstream_kpa": p.downstream_pressure_kpa,
                    "flow_lpm": flow,
                    "temperature_c": 25.0,
                    "direction": direction,
                    "fault_type": fault.fault_type,
                    "fault_severity": fault.severity,
                    "operating_condition_id": f"load-{fault.load_factor:.2f}",
                    "seed": fault.seed,
                }
            )

        return pd.DataFrame.from_records(rows)
