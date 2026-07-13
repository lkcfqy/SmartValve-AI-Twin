from smartvalve.pipeline import run_twin
from smartvalve.simulation.model import FaultConfig


def test_normal_signature_stays_healthy() -> None:
    run = run_twin(FaultConfig(fault_type="normal", severity=0.0, seed=11))
    assert run.signature.similarity_pct > 98.0
    assert run.diagnosis.health_score > 90.0
    assert run.diagnosis.ne107_status == "Normal"
    assert run.network.affected_nodes == []


def test_obstruction_links_valve_fault_to_network_impact() -> None:
    run = run_twin(FaultConfig(fault_type="obstruction", severity=0.8, seed=11))
    assert run.diagnosis.available_travel_pct < 70.0
    assert run.diagnosis.ne107_status == "F — Failure"
    assert run.network.pressure_delta_m["J4"] < -5.0
    assert run.network.affected_nodes
    assert run.network.engine.startswith("WNTR")


def test_sensor_drift_is_detected_without_hydraulic_restriction() -> None:
    run = run_twin(FaultConfig(fault_type="sensor_drift", severity=0.9, seed=11))
    assert "sensor" in run.diagnosis.primary_finding.lower()
    assert run.network.affected_nodes == []


def test_friction_is_a_maintenance_fault_without_hydraulic_restriction() -> None:
    run = run_twin(FaultConfig(fault_type="friction", severity=0.8, seed=11))
    assert run.diagnosis.primary_finding == "Friction growth"
    assert run.diagnosis.ne107_status == "M — Maintenance Required"
    assert run.network.affected_nodes == []


def test_out_of_scope_supply_is_explicitly_rejected_for_review() -> None:
    run = run_twin(
        FaultConfig(
            fault_type="actuator_degradation",
            severity=0.8,
            supply_voltage_v=3.8,
            seed=11,
        )
    )
    assert run.diagnosis.decision_state == "needs_review"
    assert run.diagnosis.ne107_status == "S — Out of Specification"
