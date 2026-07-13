"""Versioned API request and response schemas."""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

AssetId = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True,
        min_length=1,
        max_length=80,
        pattern=r"^[A-Za-z0-9][A-Za-z0-9._:-]*$",
    ),
]

FaultName = Literal[
    "normal",
    "friction",
    "stiction",
    "obstruction",
    "actuator_degradation",
    "sensor_drift",
]


class SimulationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    asset_id: AssetId = "VALVE-DEMO-07"
    fault_type: FaultName = "stiction"
    severity: float = Field(default=0.75, ge=0.0, le=1.0)
    location_pct: float = Field(default=65.0, ge=5.0, le=95.0)
    width_pct: float = Field(default=8.0, gt=0.0, le=30.0)
    supply_voltage_v: float = Field(default=5.0, gt=0.0, le=1000.0)
    load_factor: float = Field(default=1.0, gt=0.0, le=10.0)
    seed: int = Field(default=7, ge=0, le=2_147_483_647)


class CranfieldRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    asset_id: AssetId = "CRANFIELD-EMA-01"
    fault: Literal["lack_of_lubrication", "backlash"] = "lack_of_lubrication"
    motion: Literal["trap", "sin"] = "trap"
    load_kg: Literal[-40, 20, 40] = 20
    repetition: int = Field(default=1, ge=1, le=10)


class DiagnosticResponse(BaseModel):
    run_id: str
    correlation_id: str
    created_at: str
    operator_id: str
    asset_id: str
    source: str
    evidence_grade: str
    model_version: str
    diagnosis: dict[str, object]
    network: dict[str, object]
    quality: dict[str, object]
    baseline_trace: list[dict[str, object]]
    trace: list[dict[str, object]]
    signature: dict[str, object]
    limitations: list[str]
    audit: dict[str, str]
