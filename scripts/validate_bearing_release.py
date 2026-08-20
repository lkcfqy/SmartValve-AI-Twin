#!/usr/bin/env python3
"""Independently validate a deterministic SmartValve bearing evidence archive."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from smartvalve.experiments.bearing_release import validate_release_archive


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--archive", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--checksum", type=Path, required=True)
    parser.add_argument("--archive-sha256", required=True)
    parser.add_argument("--manifest-sha256", required=True)
    parser.add_argument("--output", type=Path)
    arguments = parser.parse_args()
    result = validate_release_archive(
        archive_path=arguments.archive,
        manifest_path=arguments.manifest,
        checksum_path=arguments.checksum,
        expected_archive_sha256=arguments.archive_sha256,
        expected_manifest_sha256=arguments.manifest_sha256,
    )
    rendered = json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    if arguments.output is not None:
        arguments.output.parent.mkdir(parents=True, exist_ok=True)
        arguments.output.write_text(rendered, encoding="utf-8")
    print(rendered, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
