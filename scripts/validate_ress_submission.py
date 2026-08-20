#!/usr/bin/env python3
"""Validate final RESS-facing text against the current journal constraints."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from smartvalve.experiments.ress_submission import validate_ress_submission


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--materials", type=Path, required=True)
    parser.add_argument("--manuscript", type=Path, required=True)
    parser.add_argument("--bibliography", type=Path, required=True)
    parser.add_argument("--highlights", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    arguments = parser.parse_args()
    result = validate_ress_submission(
        materials_path=arguments.materials,
        manuscript_path=arguments.manuscript,
        bibliography_path=arguments.bibliography,
        highlights_path=arguments.highlights,
    )
    rendered = json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    if arguments.output is not None:
        arguments.output.parent.mkdir(parents=True, exist_ok=True)
        arguments.output.write_text(rendered, encoding="utf-8")
    print(rendered, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
