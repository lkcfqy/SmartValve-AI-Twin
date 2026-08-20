#!/usr/bin/env python3
"""Run the fixed final local source-quality gate and emit its hash-linked summary."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from smartvalve.experiments.final_quality_gate import run_final_quality_gate


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", type=Path, required=True)
    parser.add_argument("--output-directory", type=Path, required=True)
    parser.add_argument("--expected-test-count", type=int, required=True)
    arguments = parser.parse_args()
    result = run_final_quality_gate(
        project_root=arguments.project_root,
        output_directory=arguments.output_directory,
        expected_test_count=arguments.expected_test_count,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False))
    return 0 if result["status"] == "passed_final_local_quality_gate" else 1


if __name__ == "__main__":
    raise SystemExit(main())
