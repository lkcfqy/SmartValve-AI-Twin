#!/usr/bin/env python3
"""Render and machine-check a deterministic RESS manuscript PDF."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from smartvalve.experiments.ress_pdf import render_ress_pdf


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manuscript", type=Path, required=True)
    parser.add_argument("--bibliography", type=Path, required=True)
    parser.add_argument("--figure-pdf", type=Path, action="append", default=[])
    parser.add_argument("--working-preflight", action="store_true")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    arguments = parser.parse_args()
    result = render_ress_pdf(
        manuscript_path=arguments.manuscript,
        bibliography_path=arguments.bibliography,
        figure_pdfs=arguments.figure_pdf,
        working_preflight=arguments.working_preflight,
        output_path=arguments.output,
        report_path=arguments.report,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
