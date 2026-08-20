from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

from smartvalve.experiments.ress_pdf import render_ress_pdf
from smartvalve.experiments.ress_pdf_validation import (
    EXPECTED_FIGURES,
    RELEASE_BOUND_SOURCE_PATHS,
    sha256_file,
    validate_ress_empirical_pdf_preflight,
)


def _write_json(path: Path, value: dict[str, Any]) -> None:
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _fixture(root: Path) -> dict[str, Path]:
    manuscript = root / "manuscript.md"
    manuscript.write_text(
        "# Physical Access Changes Estimated Reliability\n\n"
        "> Working manuscript - author action required.\n\n"
        "## Abstract\n\n"
        + " ".join("evidence" for _ in range(150))
        + "\n\n## 1. Introduction\n\n"
        + "Bearing access changes the deployment estimate [@First]. " * 300
        + "\n\n## 2. Results\n\n"
        + "The paired physical-bearing interval remains positive. " * 300
        + "\n\n## 3. Discussion\n\n"
        + "The estimand remains access-specific. " * 300
        + "\n\n## 4. Conclusion\n\nThe protocol changes reported reliability.\n",
        encoding="utf-8",
    )
    bibliography = root / "references.bib"
    bibliography.write_text(
        "@article{First, author={A. Author}, title={Evidence}, "
        "journal={Reliability Journal}, year={2026}, doi={10.1000/first}}\n",
        encoding="utf-8",
    )
    artifact_directory = root / "artifacts"
    artifact_directory.mkdir()
    output_records = []
    figures = []
    for name, title in EXPECTED_FIGURES:
        figure = artifact_directory / name
        figure_canvas = canvas.Canvas(str(figure), pagesize=A4, invariant=1)
        figure_canvas.drawString(72, 760, title)
        figure_canvas.showPage()
        figure_canvas.save()
        figures.append(figure)
        output_records.append(
            {"path": name, "bytes": figure.stat().st_size, "sha256": sha256_file(figure)}
        )
    for index in range(37):
        extra = artifact_directory / f"extra-{index:02d}.txt"
        extra.write_text(f"validated output {index}\n", encoding="utf-8")
        output_records.append(
            {
                "path": extra.name,
                "bytes": extra.stat().st_size,
                "sha256": sha256_file(extra),
            }
        )
    artifact_manifest = artifact_directory / "bearing_artifact_manifest.json"
    _write_json(
        artifact_manifest,
        {
            "deterministic": True,
            "generator_version": "smartvalve-bearing-paper-artifacts-test",
            "outputs": output_records,
        },
    )
    artifact_manifest_sha256 = sha256_file(artifact_manifest)
    artifact_validation = root / "artifact-validation.json"
    _write_json(
        artifact_validation,
        {
            "status": "passed_independent_bearing_paper_artifact_validation",
            "refit_performed": False,
            "manifest_sha256": artifact_manifest_sha256,
            "output_count": 42,
            "submission_pdf_count": 5,
            "raw_dataset_files_in_manifest": False,
        },
    )
    manuscript_validation = root / "manuscript-validation.json"
    _write_json(
        manuscript_validation,
        {
            "status": "passed_independent_empirical_manuscript_validation",
            "refit_performed": False,
            "submission_ready": False,
            "manuscript_sha256": sha256_file(manuscript),
            "artifact_manifest_sha256": artifact_manifest_sha256,
        },
    )
    project_root = Path(__file__).resolve().parents[1]
    release_manifest = root / "release-manifest.json"
    _write_json(
        release_manifest,
        {
            "release_version": "smartvalve-bearing-evidence-release-test",
            "raw_dataset_files_included": False,
            "human_submission_fields_included": False,
            "files": [
                {
                    "path": relative,
                    "bytes": (project_root / relative).stat().st_size,
                    "sha256": sha256_file(project_root / relative),
                }
                for relative in RELEASE_BOUND_SOURCE_PATHS
            ],
        },
    )
    release_validation = root / "release-validation.json"
    _write_json(
        release_validation,
        {
            "status": "passed_independent_deterministic_release_validation",
            "manifest_sha256": sha256_file(release_manifest),
            "raw_dataset_files_included": False,
            "human_submission_fields_included": False,
            "normalized_archive_metadata": True,
            "independent_bearing_paper_artifact_validation_included": True,
            "independent_empirical_manuscript_validation_included": True,
            "independent_final_local_quality_validation_included": True,
            "preoutcome_raw_prediction_topology_manifest_included": True,
            "independent_raw_prediction_topology_validation_included": True,
            "technical_manuscript_submission_ready": False,
        },
    )
    pdf = root / "empirical-preflight.pdf"
    report = root / "empirical-preflight-report.json"
    render_ress_pdf(
        manuscript_path=manuscript,
        bibliography_path=bibliography,
        output_path=pdf,
        report_path=report,
        figure_pdfs=figures,
        working_preflight=True,
    )
    return {
        "pdf": pdf,
        "report": report,
        "manuscript": manuscript,
        "bibliography": bibliography,
        "artifact_manifest": artifact_manifest,
        "artifact_validation": artifact_validation,
        "manuscript_validation": manuscript_validation,
        "release_manifest": release_manifest,
        "release_validation": release_validation,
    }


def _validate(paths: dict[str, Path]) -> dict[str, Any]:
    return validate_ress_empirical_pdf_preflight(
        pdf_path=paths["pdf"],
        expected_pdf_sha256=sha256_file(paths["pdf"]),
        report_path=paths["report"],
        expected_report_sha256=sha256_file(paths["report"]),
        manuscript_path=paths["manuscript"],
        expected_manuscript_sha256=sha256_file(paths["manuscript"]),
        bibliography_path=paths["bibliography"],
        expected_bibliography_sha256=sha256_file(paths["bibliography"]),
        artifact_manifest_path=paths["artifact_manifest"],
        expected_artifact_manifest_sha256=sha256_file(paths["artifact_manifest"]),
        artifact_validation_path=paths["artifact_validation"],
        expected_artifact_validation_sha256=sha256_file(paths["artifact_validation"]),
        manuscript_validation_path=paths["manuscript_validation"],
        expected_manuscript_validation_sha256=sha256_file(
            paths["manuscript_validation"]
        ),
        release_manifest_path=paths["release_manifest"],
        expected_release_manifest_sha256=sha256_file(paths["release_manifest"]),
        release_validation_path=paths["release_validation"],
        expected_release_validation_sha256=sha256_file(paths["release_validation"]),
    )


def test_empirical_pdf_preflight_validation_binds_all_five_figures(tmp_path: Path) -> None:
    result = _validate(_fixture(tmp_path))

    assert result["status"] == (
        "passed_independent_ress_empirical_pdf_preflight_validation"
    )
    assert result["validated_main_figure_count"] == 5
    assert result["ordered_figure_titles_verified"] is True
    assert result["human_visual_review_complete"] is False
    assert result["submission_ready"] is False


def test_empirical_pdf_preflight_validation_rejects_report_figure_reordering(
    tmp_path: Path,
) -> None:
    paths = _fixture(tmp_path)
    report = json.loads(paths["report"].read_text(encoding="utf-8"))
    report["main_figure_pdfs"] = list(reversed(report["main_figure_pdfs"]))
    _write_json(paths["report"], report)

    with pytest.raises(ValueError, match="report field changed: main_figure_pdfs"):
        _validate(paths)


def test_empirical_pdf_preflight_validation_rejects_upstream_gate_drift(
    tmp_path: Path,
) -> None:
    paths = _fixture(tmp_path)
    validation = json.loads(paths["artifact_validation"].read_text(encoding="utf-8"))
    validation["output_count"] = 41
    _write_json(paths["artifact_validation"], validation)

    with pytest.raises(ValueError, match="validation field changed: output_count"):
        _validate(paths)


def test_empirical_pdf_preflight_validation_cli_writes_locked_report(
    tmp_path: Path,
) -> None:
    paths = _fixture(tmp_path)
    output = tmp_path / "validation.json"
    command = [sys.executable, "scripts/validate_ress_pdf.py"]
    for name in (
        "pdf",
        "report",
        "manuscript",
        "bibliography",
        "artifact_manifest",
        "artifact_validation",
        "manuscript_validation",
        "release_manifest",
        "release_validation",
    ):
        argument_name = name.replace("_", "-")
        command.extend(
            [
                f"--{argument_name}",
                str(paths[name]),
                f"--{argument_name}-sha256",
                sha256_file(paths[name]),
            ]
        )
    command.extend(["--output", str(output)])

    result = subprocess.run(
        command,
        cwd=Path(__file__).resolve().parents[1],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    value = json.loads(output.read_text(encoding="utf-8"))
    assert value["status"] == (
        "passed_independent_ress_empirical_pdf_preflight_validation"
    )
    assert json.loads(result.stdout) == value


def test_empirical_pdf_preflight_validation_rejects_postrelease_source_drift(
    tmp_path: Path,
) -> None:
    paths = _fixture(tmp_path)
    manifest = json.loads(paths["release_manifest"].read_text(encoding="utf-8"))
    manifest["files"][0]["sha256"] = "0" * 64
    _write_json(paths["release_manifest"], manifest)
    validation = json.loads(paths["release_validation"].read_text(encoding="utf-8"))
    validation["manifest_sha256"] = sha256_file(paths["release_manifest"])
    _write_json(paths["release_validation"], validation)

    with pytest.raises(ValueError, match="release-bound PDF source identity changed"):
        _validate(paths)


def test_empirical_pdf_preflight_validation_rejects_public_human_fields(
    tmp_path: Path,
) -> None:
    paths = _fixture(tmp_path)
    manifest = json.loads(paths["release_manifest"].read_text(encoding="utf-8"))
    manifest["human_submission_fields_included"] = True
    _write_json(paths["release_manifest"], manifest)
    validation = json.loads(paths["release_validation"].read_text(encoding="utf-8"))
    validation["manifest_sha256"] = sha256_file(paths["release_manifest"])
    _write_json(paths["release_validation"], validation)

    with pytest.raises(ValueError, match="does not prohibit human submission fields"):
        _validate(paths)
