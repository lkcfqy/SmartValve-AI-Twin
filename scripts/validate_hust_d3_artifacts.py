#!/usr/bin/env python3
"""Validate and recompute sealed HUST D3 artifacts without fitting models."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from smartvalve.experiments.hust_artifact_validation import (
    validate_hust_d3_artifacts,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--result-dir", type=Path, required=True)
    parser.add_argument("--expected-manifest", type=Path, required=True)
    parser.add_argument("--expected-manifest-sha256", required=True)
    parser.add_argument("--execution-seal", type=Path, required=True)
    parser.add_argument("--execution-seal-sha256", required=True)
    parser.add_argument("--output", type=Path, required=True)
    return parser


def main() -> int:
    arguments = build_parser().parse_args()
    result = validate_hust_d3_artifacts(
        result_directory=arguments.result_dir,
        expected_manifest_path=arguments.expected_manifest,
        expected_manifest_sha256=arguments.expected_manifest_sha256,
        execution_seal_path=arguments.execution_seal,
        execution_seal_sha256=arguments.execution_seal_sha256,
        output_path=arguments.output,
    )
    print(
        json.dumps(
            {
                "status": result["status"],
                "maximum_probability_sum_error": result["maximum_probability_sum_error"],
                "maximum_absolute_numeric_difference": result[
                    "maximum_absolute_numeric_difference"
                ],
            },
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
