#!/usr/bin/env python3
"""Independently validate a hash-locked final local quality-gate package."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from smartvalve.experiments.final_quality_validation import validate_final_quality_gate


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--summary", type=Path, required=True)
    parser.add_argument("--summary-sha256", required=True)
    parser.add_argument("--output", type=Path, required=True)
    arguments = parser.parse_args()
    result = validate_final_quality_gate(
        summary_path=arguments.summary,
        expected_summary_sha256=arguments.summary_sha256,
    )
    arguments.output.parent.mkdir(parents=True, exist_ok=True)
    rendered = json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    arguments.output.write_text(rendered, encoding="utf-8")
    print(rendered, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
