"""Command-line demonstration of ValveDNA plus WNTR impact."""

from __future__ import annotations

import argparse
import json

from smartvalve.pipeline import run_twin
from smartvalve.simulation.model import FAULT_TYPES, FaultConfig


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fault", choices=FAULT_TYPES, default="stiction")
    parser.add_argument("--severity", type=float, default=0.75)
    parser.add_argument("--location", type=float, default=65.0)
    parser.add_argument("--seed", type=int, default=7)
    return parser


def main() -> None:
    args = build_parser().parse_args()
    run = run_twin(
        FaultConfig(
            fault_type=args.fault,
            severity=args.severity,
            location_pct=args.location,
            seed=args.seed,
        )
    )
    output = {
        "data_source": "Simulation",
        "diagnosis": run.diagnosis.to_dict(),
        "network_impact": run.network.to_dict(),
        "limitations": [
            "No manufacturer-specific calibration",
            "No real pressure, flow, leakage, or RUL validation",
            "Equivalent valve-loss mapping is illustrative",
        ],
    }
    print(json.dumps(output, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
