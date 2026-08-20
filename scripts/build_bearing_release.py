#!/usr/bin/env python3
"""Build the deterministic raw-data-free bearing-paper evidence archive."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from smartvalve.experiments.bearing_release import build_release_archive


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--artifact-manifest",
        type=Path,
        default=Path("paper/generated/bearing_artifact_manifest.json"),
    )
    parser.add_argument("--artifact-validation", type=Path, required=True)
    parser.add_argument("--empirical-manuscript", type=Path, required=True)
    parser.add_argument("--manuscript-render-report", type=Path, required=True)
    parser.add_argument("--manuscript-validation", type=Path, required=True)
    parser.add_argument("--final-quality-summary", type=Path, required=True)
    parser.add_argument("--final-quality-validation", type=Path, required=True)
    parser.add_argument("--raw-topology-manifest", type=Path, required=True)
    parser.add_argument("--raw-topology-validation", type=Path, required=True)
    parser.add_argument("--output-directory", type=Path, required=True)
    parser.add_argument("--project-root", type=Path, default=Path.cwd())
    arguments = parser.parse_args()
    result = build_release_archive(
        project_root=arguments.project_root,
        artifact_manifest=arguments.artifact_manifest,
        artifact_validation=arguments.artifact_validation,
        empirical_manuscript=arguments.empirical_manuscript,
        manuscript_render_report=arguments.manuscript_render_report,
        manuscript_validation=arguments.manuscript_validation,
        final_quality_summary=arguments.final_quality_summary,
        final_quality_validation=arguments.final_quality_validation,
        raw_topology_manifest=arguments.raw_topology_manifest,
        raw_topology_validation=arguments.raw_topology_validation,
        output_directory=arguments.output_directory,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
