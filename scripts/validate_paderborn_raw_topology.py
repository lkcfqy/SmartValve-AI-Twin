#!/usr/bin/env python3
"""Validate every raw-sensitivity prediction key against a pre-outcome manifest."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from smartvalve.experiments.paderborn_raw_topology import validate_result_topology


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--result-dir", type=Path, required=True)
    parser.add_argument("--result-summary-sha256", required=True)
    parser.add_argument("--expected-manifest", type=Path, required=True)
    parser.add_argument("--expected-manifest-sha256", required=True)
    parser.add_argument("--features", type=Path, required=True)
    parser.add_argument("--features-sha256", required=True)
    parser.add_argument("--raw-window-dir", type=Path, required=True)
    parser.add_argument("--raw-window-summary-sha256", required=True)
    parser.add_argument("--seal", type=Path, required=True)
    parser.add_argument("--seal-sha256", required=True)
    parser.add_argument("--output", type=Path, required=True)
    return parser


def main() -> int:
    arguments = build_parser().parse_args()
    result = validate_result_topology(
        result_directory=arguments.result_dir,
        result_summary_sha256=arguments.result_summary_sha256,
        expected_manifest_path=arguments.expected_manifest,
        expected_manifest_sha256=arguments.expected_manifest_sha256,
        features_path=arguments.features,
        features_sha256=arguments.features_sha256,
        raw_window_directory=arguments.raw_window_dir,
        raw_window_summary_sha256=arguments.raw_window_summary_sha256,
        seal_path=arguments.seal,
        seal_sha256=arguments.seal_sha256,
        output_path=arguments.output,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
