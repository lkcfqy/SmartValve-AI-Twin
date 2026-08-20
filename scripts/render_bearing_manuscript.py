#!/usr/bin/env python3
"""Render the empirically final bearing manuscript from a locked paper manifest."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from smartvalve.experiments.bearing_manuscript import render_empirical_final_manuscript


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--template", type=Path, required=True)
    parser.add_argument("--artifact-manifest", type=Path, required=True)
    parser.add_argument("--artifact-manifest-sha256", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    arguments = parser.parse_args()
    if arguments.output.resolve() == arguments.template.resolve():
        raise ValueError("empirical manuscript output must not overwrite its working template")
    rendered, report = render_empirical_final_manuscript(
        template_path=arguments.template,
        artifact_manifest_path=arguments.artifact_manifest,
        expected_manifest_sha256=arguments.artifact_manifest_sha256,
    )
    arguments.output.parent.mkdir(parents=True, exist_ok=True)
    arguments.report.parent.mkdir(parents=True, exist_ok=True)
    arguments.output.write_text(rendered, encoding="utf-8")
    arguments.report.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
