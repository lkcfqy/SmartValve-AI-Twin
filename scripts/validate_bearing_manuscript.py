#!/usr/bin/env python3
"""Independently validate an empirically final SmartValve bearing manuscript."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from smartvalve.experiments.bearing_manuscript_validation import (
    validate_empirical_final_manuscript,
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manuscript", type=Path, required=True)
    parser.add_argument("--manuscript-sha256", required=True)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--report-sha256", required=True)
    parser.add_argument("--template", type=Path, required=True)
    parser.add_argument("--template-sha256", required=True)
    parser.add_argument("--artifact-manifest", type=Path, required=True)
    parser.add_argument("--artifact-manifest-sha256", required=True)
    parser.add_argument("--output", type=Path, required=True)
    arguments = parser.parse_args()
    result = validate_empirical_final_manuscript(
        manuscript_path=arguments.manuscript,
        expected_manuscript_sha256=arguments.manuscript_sha256,
        report_path=arguments.report,
        expected_report_sha256=arguments.report_sha256,
        template_path=arguments.template,
        expected_template_sha256=arguments.template_sha256,
        artifact_manifest_path=arguments.artifact_manifest,
        expected_artifact_manifest_sha256=arguments.artifact_manifest_sha256,
    )
    rendered = json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    arguments.output.parent.mkdir(parents=True, exist_ok=True)
    arguments.output.write_text(rendered, encoding="utf-8")
    print(rendered, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
