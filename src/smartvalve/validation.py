"""Three-source validation summary for CLI, CI and the industrial dashboard."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass

from smartvalve.data.contract import EvidenceGrade
from smartvalve.data.cranfield import load_cranfield_pair
from smartvalve.data.external import artifact_status
from smartvalve.data.skab import run_skab_validation
from smartvalve.pipeline import run_from_frames, run_twin
from smartvalve.simulation.model import FaultConfig


@dataclass(frozen=True)
class ValidationLayer:
    layer: str
    evidence_grade: str
    status: str
    result: dict[str, object]
    limitation: str


def run_validation() -> list[ValidationLayer]:
    layers: list[ValidationLayer] = []
    simulation = run_twin(FaultConfig(fault_type="stiction", severity=0.75, seed=11))
    layers.append(
        ValidationLayer(
            layer="Deterministic simulation",
            evidence_grade=EvidenceGrade.S0_SIMULATION.value,
            status="PASS",
            result={
                "finding": simulation.diagnosis.primary_finding,
                "health_score": simulation.diagnosis.health_score,
                "network_impact": simulation.network.impact_score,
            },
            limitation="Non-product-specific lumped model",
        )
    )

    availability = {item["filename"]: item["available"] for item in artifact_status()}
    if availability.get("Normal.mat") and availability.get("LackLubrication2.mat"):
        baseline, current = load_cranfield_pair()
        cranfield = run_from_frames(baseline, current)
        layers.append(
            ValidationLayer(
                layer="Cranfield public physical actuator",
                evidence_grade=EvidenceGrade.S1_PUBLIC_RIG.value,
                status="PASS",
                result={
                    "finding": cranfield.diagnosis.primary_finding,
                    "health_score": cranfield.diagnosis.health_score,
                    "data_quality": cranfield.current_quality.score,
                    "samples": cranfield.current_quality.sample_count,
                },
                limitation="Real electromechanical actuator, but not a water valve",
            )
        )
    else:
        layers.append(
            ValidationLayer(
                layer="Cranfield public physical actuator",
                evidence_grade=EvidenceGrade.S1_PUBLIC_RIG.value,
                status="NOT_SYNCED",
                result={},
                limitation="Run `make data` to fetch CC BY 4.0 source files",
            )
        )

    if availability.get("skab_valve1_1.csv"):
        skab = run_skab_validation()
        layers.append(
            ValidationLayer(
                layer="SKAB public physical water loop",
                evidence_grade=EvidenceGrade.S1_PUBLIC_RIG.value,
                status="PASS",
                result=skab.summary(),
                limitation="Validates process anomalies, not valve mechanical root cause",
            )
        )
    else:
        layers.append(
            ValidationLayer(
                layer="SKAB public physical water loop",
                evidence_grade=EvidenceGrade.S1_PUBLIC_RIG.value,
                status="NOT_SYNCED",
                result={},
                limitation="Run `make data` to fetch the public experiment",
            )
        )

    layers.append(
        ValidationLayer(
            layer="Own CNY 200 desktop rig",
            evidence_grade=EvidenceGrade.S2_OWN_RIG.value,
            status="ADAPTER_READY / HARDWARE_PENDING",
            result={"contract": "canonical full-stroke CSV v1"},
            limitation="No physical hardware has been purchased or tested",
        )
    )
    return layers


def main() -> None:
    print(json.dumps([asdict(layer) for layer in run_validation()], ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
