#!/usr/bin/env python3
"""Generate the final deterministic bearing-manuscript tables and figures."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from smartvalve.experiments.bearing_paper_artifacts import generate


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--paderborn-dir", type=Path, required=True)
    parser.add_argument("--paderborn-summary-sha256", required=True)
    parser.add_argument("--paderborn-validation", type=Path, required=True)
    parser.add_argument("--paderborn-validation-sha256", required=True)
    parser.add_argument("--sensor-dir", type=Path, required=True)
    parser.add_argument("--sensor-summary-sha256", required=True)
    parser.add_argument("--sensor-validation", type=Path, required=True)
    parser.add_argument("--sensor-validation-sha256", required=True)
    parser.add_argument("--hust-dir", type=Path, required=True)
    parser.add_argument("--hust-summary-sha256", required=True)
    parser.add_argument("--hust-validation", type=Path, required=True)
    parser.add_argument("--hust-validation-sha256", required=True)
    parser.add_argument("--hust-control-dir", type=Path, required=True)
    parser.add_argument("--hust-control-summary-sha256", required=True)
    parser.add_argument("--hust-control-validation", type=Path, required=True)
    parser.add_argument("--hust-control-validation-sha256", required=True)
    parser.add_argument("--hust-influence-dir", type=Path, required=True)
    parser.add_argument("--hust-influence-summary-sha256", required=True)
    parser.add_argument("--hust-influence-validation", type=Path, required=True)
    parser.add_argument("--hust-influence-validation-sha256", required=True)
    parser.add_argument("--raw-dir", type=Path, required=True)
    parser.add_argument("--raw-summary-sha256", required=True)
    parser.add_argument("--raw-window-dir", type=Path, required=True)
    parser.add_argument("--raw-window-summary-sha256", required=True)
    parser.add_argument("--raw-validation", type=Path, required=True)
    parser.add_argument("--raw-validation-sha256", required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--project-root", type=Path, default=Path.cwd())
    parser.add_argument(
        "--release-input-mode",
        action="store_true",
        help=(
            "Allow parent summaries to declare unconsumed raw outputs omitted from the "
            "raw-data-free release; all consumed inputs remain hash-locked."
        ),
    )
    return parser


def main() -> int:
    arguments = build_parser().parse_args()
    manifest = generate(
        paderborn_directory=arguments.paderborn_dir,
        paderborn_summary_sha256=arguments.paderborn_summary_sha256,
        paderborn_validation=arguments.paderborn_validation,
        paderborn_validation_sha256=arguments.paderborn_validation_sha256,
        sensor_directory=arguments.sensor_dir,
        sensor_summary_sha256=arguments.sensor_summary_sha256,
        sensor_validation=arguments.sensor_validation,
        sensor_validation_sha256=arguments.sensor_validation_sha256,
        hust_directory=arguments.hust_dir,
        hust_summary_sha256=arguments.hust_summary_sha256,
        hust_validation=arguments.hust_validation,
        hust_validation_sha256=arguments.hust_validation_sha256,
        hust_control_directory=arguments.hust_control_dir,
        hust_control_summary_sha256=arguments.hust_control_summary_sha256,
        hust_control_validation=arguments.hust_control_validation,
        hust_control_validation_sha256=arguments.hust_control_validation_sha256,
        hust_influence_directory=arguments.hust_influence_dir,
        hust_influence_summary_sha256=arguments.hust_influence_summary_sha256,
        hust_influence_validation=arguments.hust_influence_validation,
        hust_influence_validation_sha256=arguments.hust_influence_validation_sha256,
        raw_directory=arguments.raw_dir,
        raw_summary_sha256=arguments.raw_summary_sha256,
        raw_window_directory=arguments.raw_window_dir,
        raw_window_summary_sha256=arguments.raw_window_summary_sha256,
        raw_validation=arguments.raw_validation,
        raw_validation_sha256=arguments.raw_validation_sha256,
        output_directory=arguments.output_dir,
        project_root=arguments.project_root,
        release_input_mode=arguments.release_input_mode,
    )
    print(json.dumps(manifest["decision"], ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
