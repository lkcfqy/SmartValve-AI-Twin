#!/usr/bin/env python3
"""Independently validate the final bearing-paper artifact package."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from smartvalve.experiments.bearing_paper_validation import (
    validate_bearing_paper_artifacts,
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--manifest-sha256", required=True)
    parser.add_argument("--project-root", type=Path, default=Path.cwd())
    parser.add_argument("--output", type=Path)
    parser.add_argument(
        "--release-input-mode",
        action="store_true",
        help=(
            "Validate all manifest inputs and decisions without requiring unconsumed raw "
            "outputs intentionally omitted from the evidence release."
        ),
    )
    arguments = parser.parse_args()
    result = validate_bearing_paper_artifacts(
        manifest_path=arguments.manifest,
        expected_manifest_sha256=arguments.manifest_sha256,
        project_root=arguments.project_root,
        release_input_mode=arguments.release_input_mode,
    )
    rendered = json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    if arguments.output is not None:
        arguments.output.parent.mkdir(parents=True, exist_ok=True)
        arguments.output.write_text(rendered, encoding="utf-8")
    print(rendered, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
