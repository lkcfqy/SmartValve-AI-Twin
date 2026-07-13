import pandas as pd

from smartvalve.simulation.model import FaultConfig, ValveSimulator


def test_simulation_is_reproducible() -> None:
    simulator = ValveSimulator()
    config = FaultConfig(fault_type="stiction", severity=0.6, seed=42)
    first = simulator.simulate(config)
    second = simulator.simulate(config)
    pd.testing.assert_frame_equal(first, second)


def test_normal_valve_completes_travel() -> None:
    data = ValveSimulator().simulate(FaultConfig())
    assert data["actual_position_pct"].max() >= 99.0
    assert data["actual_position_pct"].iloc[-1] <= 1.0


def test_obstruction_reduces_available_travel() -> None:
    data = ValveSimulator().simulate(FaultConfig(fault_type="obstruction", severity=0.8))
    assert data["actual_position_pct"].max() < 70.0
    assert data["motor_current_a"].max() > 0.8
