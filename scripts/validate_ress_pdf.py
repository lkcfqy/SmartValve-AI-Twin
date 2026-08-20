#!/usr/bin/env python3
"""Independently validate the post-release empirical RESS working PDF."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from smartvalve.experiments.ress_pdf_validation import (
    validate_ress_empirical_pdf_preflight,
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    for name in (
        "pdf",
        "report",
        "manuscript",
        "bibliography",
        "artifact-manifest",
        "artifact-validation",
        "manuscript-validation",
        "release-manifest",
        "release-validation",
    ):
        parser.add_argument(f"--{name}", type=Path, required=True)
        parser.add_argument(f"--{name}-sha256", required=True)
    parser.add_argument("--output", type=Path, required=True)
    arguments = parser.parse_args()
    result = validate_ress_empirical_pdf_preflight(
        pdf_path=arguments.pdf,
        expected_pdf_sha256=arguments.pdf_sha256,
        report_path=arguments.report,
        expected_report_sha256=arguments.report_sha256,
        manuscript_path=arguments.manuscript,
        expected_manuscript_sha256=arguments.manuscript_sha256,
        bibliography_path=arguments.bibliography,
        expected_bibliography_sha256=arguments.bibliography_sha256,
        artifact_manifest_path=arguments.artifact_manifest,
        expected_artifact_manifest_sha256=arguments.artifact_manifest_sha256,
        artifact_validation_path=arguments.artifact_validation,
        expected_artifact_validation_sha256=arguments.artifact_validation_sha256,
        manuscript_validation_path=arguments.manuscript_validation,
        expected_manuscript_validation_sha256=arguments.manuscript_validation_sha256,
        release_manifest_path=arguments.release_manifest,
        expected_release_manifest_sha256=arguments.release_manifest_sha256,
        release_validation_path=arguments.release_validation,
        expected_release_validation_sha256=arguments.release_validation_sha256,
    )
    rendered = json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    arguments.output.parent.mkdir(parents=True, exist_ok=True)
    if arguments.output.exists():
        raise ValueError(f"RESS PDF validation output already exists: {arguments.output}")
    arguments.output.write_text(rendered, encoding="utf-8")
    print(rendered, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
