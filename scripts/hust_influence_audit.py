#!/usr/bin/env python3
"""Run the frozen post-hoc HUST physical-unit influence audit without refitting."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from smartvalve.experiments.hust_influence_audit import run_hust_influence_audit


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--primary-summary", type=Path, required=True)
    parser.add_argument("--primary-summary-sha256", required=True)
    parser.add_argument("--primary-validation", type=Path, required=True)
    parser.add_argument("--primary-validation-sha256", required=True)
    parser.add_argument("--control-summary", type=Path, required=True)
    parser.add_argument("--control-summary-sha256", required=True)
    parser.add_argument("--control-validation", type=Path, required=True)
    parser.add_argument("--control-validation-sha256", required=True)
    parser.add_argument("--analysis-plan", type=Path, required=True)
    parser.add_argument("--analysis-plan-sha256", required=True)
    parser.add_argument("--output-directory", type=Path, required=True)
    arguments = parser.parse_args()
    result = run_hust_influence_audit(
        primary_summary=arguments.primary_summary,
        primary_summary_sha256=arguments.primary_summary_sha256,
        primary_validation=arguments.primary_validation,
        primary_validation_sha256=arguments.primary_validation_sha256,
        control_summary=arguments.control_summary,
        control_summary_sha256=arguments.control_summary_sha256,
        control_validation=arguments.control_validation,
        control_validation_sha256=arguments.control_validation_sha256,
        analysis_plan=arguments.analysis_plan,
        analysis_plan_sha256=arguments.analysis_plan_sha256,
        output_directory=arguments.output_directory,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
