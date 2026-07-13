"""Map valve availability into a small WNTR water-network impact model."""

from __future__ import annotations

from dataclasses import asdict, dataclass

import numpy as np

NODE_COORDINATES: dict[str, tuple[float, float]] = {
    "R1": (0.0, 0.0),
    "J1": (1.0, 0.0),
    "J2": (2.0, 0.0),
    "J3": (3.0, 1.0),
    "J4": (3.0, -1.0),
}

LINKS: tuple[tuple[str, str, str], ...] = (
    ("P1", "R1", "J1"),
    ("V1", "J1", "J2"),
    ("P2", "J2", "J3"),
    ("P3", "J2", "J4"),
)


@dataclass(frozen=True)
class NetworkImpact:
    available_travel_pct: float
    equivalent_loss_coefficient: float
    baseline_pressure_m: dict[str, float]
    fault_pressure_m: dict[str, float]
    pressure_delta_m: dict[str, float]
    baseline_flow_lps: dict[str, float]
    fault_flow_lps: dict[str, float]
    affected_nodes: list[str]
    service_pressure_threshold_m: float
    impact_score: float
    engine: str

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def travel_to_loss_coefficient(available_travel_pct: float) -> float:
    """Illustrative monotonic mapping, not a manufacturer-calibrated Cv curve."""

    opening = float(np.clip(available_travel_pct, 10.0, 100.0)) / 100.0
    return float(0.1 + 8000.0 * (1.0 - opening) ** 2)


def _build_network(tcv_setting: float):
    import wntr

    network = wntr.network.WaterNetworkModel()
    network.options.time.duration = 0
    network.options.hydraulic.demand_model = "PDD"
    network.options.hydraulic.minimum_pressure = 10.0
    network.options.hydraulic.required_pressure = 35.0
    network.options.hydraulic.pressure_exponent = 0.5

    network.add_reservoir("R1", base_head=60.0, coordinates=NODE_COORDINATES["R1"])
    network.add_junction("J1", base_demand=0.002, elevation=5.0, coordinates=NODE_COORDINATES["J1"])
    network.add_junction("J2", base_demand=0.004, elevation=8.0, coordinates=NODE_COORDINATES["J2"])
    network.add_junction(
        "J3", base_demand=0.003, elevation=12.0, coordinates=NODE_COORDINATES["J3"]
    )
    network.add_junction(
        "J4", base_demand=0.002, elevation=15.0, coordinates=NODE_COORDINATES["J4"]
    )

    network.add_pipe("P1", "R1", "J1", length=500.0, diameter=0.20, roughness=110.0)
    network.add_valve(
        "V1",
        "J1",
        "J2",
        diameter=0.15,
        valve_type="TCV",
        initial_setting=tcv_setting,
    )
    network.add_pipe("P2", "J2", "J3", length=700.0, diameter=0.12, roughness=105.0)
    network.add_pipe("P3", "J2", "J4", length=500.0, diameter=0.10, roughness=105.0)
    return network


def _run_wntr(loss_coefficient: float) -> tuple[dict[str, float], dict[str, float]]:
    import wntr

    network = _build_network(loss_coefficient)
    results = wntr.sim.WNTRSimulator(network).run_sim()
    pressure = results.node["pressure"].iloc[0]
    flow = results.link["flowrate"].iloc[0]
    node_pressure = {name: float(pressure[name]) for name in ("J1", "J2", "J3", "J4")}
    link_flow = {name: float(flow[name] * 1000.0) for name in ("P1", "V1", "P2", "P3")}
    return node_pressure, link_flow


def _fallback(available_travel_pct: float) -> tuple[dict[str, float], dict[str, float]]:
    restriction = (1.0 - np.clip(available_travel_pct, 10.0, 100.0) / 100.0) ** 2
    pressure = {
        "J1": 54.5,
        "J2": 51.5 - 42.0 * restriction,
        "J3": 46.6 - 42.0 * restriction,
        "J4": 43.8 - 42.0 * restriction,
    }
    flow_factor = max(0.35, 1.0 - 1.2 * restriction)
    flow = {
        "P1": 11.0 * flow_factor,
        "V1": 9.0 * flow_factor,
        "P2": 3.0 * flow_factor,
        "P3": 2.0 * flow_factor,
    }
    return pressure, flow


def simulate_network_impact(
    available_travel_pct: float,
    service_pressure_threshold_m: float = 35.0,
) -> NetworkImpact:
    available_travel_pct = float(np.clip(available_travel_pct, 10.0, 100.0))
    loss = travel_to_loss_coefficient(available_travel_pct)
    try:
        baseline_pressure, baseline_flow = _run_wntr(0.1)
        fault_pressure, fault_flow = _run_wntr(loss)
        engine = "WNTR 1.5 / pressure-dependent demand"
    except (ImportError, RuntimeError, ValueError):
        baseline_pressure, baseline_flow = _fallback(100.0)
        fault_pressure, fault_flow = _fallback(available_travel_pct)
        engine = "Lightweight hydraulic fallback"

    pressure_delta = {
        node: fault_pressure[node] - baseline_pressure[node] for node in baseline_pressure
    }
    affected = sorted(
        node for node, pressure in fault_pressure.items() if pressure < service_pressure_threshold_m
    )
    max_drop = max(abs(min(0.0, value)) for value in pressure_delta.values())
    impact_score = float(np.clip(max_drop * 2.2 + len(affected) * 12.0, 0.0, 100.0))

    def rounded(values: dict[str, float]) -> dict[str, float]:
        return {name: round(value, 3) for name, value in values.items()}

    return NetworkImpact(
        available_travel_pct=round(available_travel_pct, 2),
        equivalent_loss_coefficient=round(loss, 3),
        baseline_pressure_m=rounded(baseline_pressure),
        fault_pressure_m=rounded(fault_pressure),
        pressure_delta_m=rounded(pressure_delta),
        baseline_flow_lps=rounded(baseline_flow),
        fault_flow_lps=rounded(fault_flow),
        affected_nodes=affected,
        service_pressure_threshold_m=service_pressure_threshold_m,
        impact_score=round(impact_score, 1),
        engine=engine,
    )
