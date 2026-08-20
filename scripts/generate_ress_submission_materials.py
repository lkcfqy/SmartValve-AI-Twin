#!/usr/bin/env python3
"""Render RESS submission materials from the final bearing artifact manifest."""

from __future__ import annotations

import argparse
from pathlib import Path

from smartvalve.experiments.ress_submission import (
    render_ress_highlights,
    render_ress_materials,
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--artifact-manifest", type=Path, required=True)
    parser.add_argument("--artifact-manifest-sha256", required=True)
    parser.add_argument(
        "--code-commit-sha",
        required=True,
        help="Author-approved 40- or 64-character lowercase Git commit SHA.",
    )
    parser.add_argument(
        "--artifact-doi",
        required=True,
        help="Persistent evidence-archive identifier as an https://doi.org URL.",
    )
    parser.add_argument(
        "--human-review-confirmed",
        action="store_true",
        help="Confirm that the human authors completed the review stated in the AI declaration.",
    )
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--highlights-output",
        type=Path,
        required=True,
        help="Separate editable .txt upload whose filename contains 'highlights'.",
    )
    arguments = parser.parse_args()
    if arguments.output.exists():
        raise ValueError(f"RESS material output already exists: {arguments.output}")
    if arguments.highlights_output.exists():
        raise ValueError(
            f"RESS highlights output already exists: {arguments.highlights_output}"
        )
    if arguments.highlights_output.suffix.casefold() != ".txt":
        raise ValueError("RESS highlights output must use the .txt extension")
    if "highlight" not in arguments.highlights_output.stem.casefold():
        raise ValueError("RESS highlights filename must contain 'highlights'")
    if arguments.output.resolve() == arguments.highlights_output.resolve():
        raise ValueError("RESS materials and highlights outputs must differ")
    rendered = render_ress_materials(
        artifact_manifest_path=arguments.artifact_manifest,
        expected_manifest_sha256=arguments.artifact_manifest_sha256,
        human_review_confirmed=arguments.human_review_confirmed,
        code_commit_sha=arguments.code_commit_sha,
        artifact_doi=arguments.artifact_doi,
    )
    highlights = render_ress_highlights(rendered)
    arguments.output.parent.mkdir(parents=True, exist_ok=True)
    arguments.highlights_output.parent.mkdir(parents=True, exist_ok=True)
    arguments.output.write_text(rendered, encoding="utf-8")
    arguments.highlights_output.write_text(highlights, encoding="utf-8")
    print(arguments.output)
    print(arguments.highlights_output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
