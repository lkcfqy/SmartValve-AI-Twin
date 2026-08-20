#!/usr/bin/env python3
"""Write the sealed metadata-only HUST D3 expected manifest."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from smartvalve.experiments.hust_expected_manifest import (
    build_hust_expected_manifest,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--inventory", type=Path, required=True)
    parser.add_argument("--factorial-seal", type=Path, required=True)
    parser.add_argument("--prospective-seal", type=Path, required=True)
    parser.add_argument("--clarification", type=Path, required=True)
    parser.add_argument("--clarification-sha256", required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    return parser


def main() -> int:
    arguments = build_parser().parse_args()
    manifest = build_hust_expected_manifest(
        inventory=arguments.inventory,
        factorial_seal=arguments.factorial_seal,
        prospective_seal=arguments.prospective_seal,
        clarification=arguments.clarification,
        expected_clarification_sha256=arguments.clarification_sha256,
        output_directory=arguments.output_dir,
    )
    print(
        json.dumps(
            {
                "status": manifest["status"],
                "expected_counts": manifest["expected_counts"],
                "expected_key_sets": manifest["expected_key_sets"],
            },
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
