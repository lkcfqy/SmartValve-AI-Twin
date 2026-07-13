from smartvalve.network_twin.model import simulate_network_impact, travel_to_loss_coefficient


def test_loss_mapping_is_monotonic_with_reduced_travel() -> None:
    assert travel_to_loss_coefficient(100.0) < travel_to_loss_coefficient(80.0)
    assert travel_to_loss_coefficient(80.0) < travel_to_loss_coefficient(60.0)


def test_restricted_valve_reduces_downstream_pressure_and_flow() -> None:
    healthy = simulate_network_impact(100.0)
    restricted = simulate_network_impact(60.0)
    assert restricted.fault_pressure_m["J3"] < healthy.fault_pressure_m["J3"]
    assert restricted.fault_flow_lps["P2"] < healthy.fault_flow_lps["P2"]
    assert restricted.impact_score > healthy.impact_score
