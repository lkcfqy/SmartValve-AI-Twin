"""Independent validation for the empirical RESS working-PDF preflight."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from pypdf import PdfReader

from smartvalve.config import project_root

VALIDATOR_VERSION = "smartvalve-ress-pdf-preflight-validator-0.2.0"
EXPECTED_RENDERER_VERSION = "smartvalve-ress-pdf-renderer-0.1.2"
HUMAN_SUBMISSION_FIELDS_PATH = "paper/RESS_HUMAN_SUBMISSION_FIELDS.md"
RELEASE_BOUND_SOURCE_PATHS = (
    "src/smartvalve/experiments/ress_pdf.py",
    "src/smartvalve/experiments/ress_pdf_validation.py",
    "scripts/render_ress_pdf.py",
    "scripts/validate_ress_pdf.py",
)
EXPECTED_FIGURES = (
    ("bearing_figure_00_access_lattice.pdf", "Physical-access lattice"),
    ("bearing_figure_01_protocol_profiles.pdf", "Paderborn protocol sensitivity"),
    ("bearing_figure_02_gap_forest.pdf", "Accessible-split optimism"),
    ("bearing_figure_03_sensor_gaps.pdf", "Sensor-view protocol gaps"),
    ("bearing_figure_04_hust_equal_volume.pdf", "HUST equal-volume access control"),
)


def sha256_file(path: Path) -> str:
    """Hash a file without loading it into memory."""

    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(4 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _locked_path(path: Path, expected_sha256: str, label: str) -> Path:
    resolved = path.resolve(strict=True)
    observed = sha256_file(resolved)
    if observed != expected_sha256:
        raise ValueError(
            f"{label} SHA-256 changed: expected {expected_sha256}, observed {observed}"
        )
    return resolved


def _json_object(path: Path, label: str) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{label} is not a JSON object")
    return value


def _output_records(manifest: Mapping[str, Any]) -> dict[str, Mapping[str, Any]]:
    outputs = manifest.get("outputs")
    if not isinstance(outputs, list):
        raise ValueError("bearing artifact manifest has no output records")
    records: dict[str, Mapping[str, Any]] = {}
    for item in outputs:
        if not isinstance(item, Mapping):
            raise ValueError("bearing artifact output record is not an object")
        name = str(item.get("path", ""))
        if not name or name in records:
            raise ValueError("bearing artifact output path is empty or duplicated")
        records[name] = item
    return records


def validate_ress_empirical_pdf_preflight(
    *,
    pdf_path: Path,
    expected_pdf_sha256: str,
    report_path: Path,
    expected_report_sha256: str,
    manuscript_path: Path,
    expected_manuscript_sha256: str,
    bibliography_path: Path,
    expected_bibliography_sha256: str,
    artifact_manifest_path: Path,
    expected_artifact_manifest_sha256: str,
    artifact_validation_path: Path,
    expected_artifact_validation_sha256: str,
    manuscript_validation_path: Path,
    expected_manuscript_validation_sha256: str,
    release_manifest_path: Path,
    expected_release_manifest_sha256: str,
    release_validation_path: Path,
    expected_release_validation_sha256: str,
) -> dict[str, Any]:
    """Verify the assembled PDF against all validated upstream identities without rendering."""

    locked = {
        "pdf": _locked_path(pdf_path, expected_pdf_sha256, "RESS empirical PDF"),
        "report": _locked_path(report_path, expected_report_sha256, "RESS PDF report"),
        "manuscript": _locked_path(
            manuscript_path,
            expected_manuscript_sha256,
            "empirical manuscript",
        ),
        "bibliography": _locked_path(
            bibliography_path,
            expected_bibliography_sha256,
            "bibliography",
        ),
        "artifact_manifest": _locked_path(
            artifact_manifest_path,
            expected_artifact_manifest_sha256,
            "bearing artifact manifest",
        ),
        "artifact_validation": _locked_path(
            artifact_validation_path,
            expected_artifact_validation_sha256,
            "bearing artifact validation",
        ),
        "manuscript_validation": _locked_path(
            manuscript_validation_path,
            expected_manuscript_validation_sha256,
            "empirical manuscript validation",
        ),
        "release_manifest": _locked_path(
            release_manifest_path,
            expected_release_manifest_sha256,
            "release manifest",
        ),
        "release_validation": _locked_path(
            release_validation_path,
            expected_release_validation_sha256,
            "release validation",
        ),
    }
    report = _json_object(locked["report"], "RESS PDF report")
    manifest = _json_object(locked["artifact_manifest"], "bearing artifact manifest")
    artifact_validation = _json_object(
        locked["artifact_validation"], "bearing artifact validation"
    )
    manuscript_validation = _json_object(
        locked["manuscript_validation"], "empirical manuscript validation"
    )
    release_manifest = _json_object(locked["release_manifest"], "release manifest")
    release_validation = _json_object(
        locked["release_validation"], "release validation"
    )

    if manifest.get("deterministic") is not True or not str(
        manifest.get("generator_version", "")
    ).startswith("smartvalve-bearing-paper-artifacts-"):
        raise ValueError("bearing artifact manifest identity changed")
    records = _output_records(manifest)
    if len(records) != 42:
        raise ValueError("bearing artifact manifest must contain exactly 42 outputs")

    expected_artifact_fields = {
        "status": "passed_independent_bearing_paper_artifact_validation",
        "refit_performed": False,
        "manifest_sha256": expected_artifact_manifest_sha256,
        "output_count": 42,
        "submission_pdf_count": 5,
        "raw_dataset_files_in_manifest": False,
    }
    for name, expected in expected_artifact_fields.items():
        if artifact_validation.get(name) != expected:
            raise ValueError(f"bearing artifact validation field changed: {name}")

    expected_manuscript_fields = {
        "status": "passed_independent_empirical_manuscript_validation",
        "refit_performed": False,
        "submission_ready": False,
        "manuscript_sha256": expected_manuscript_sha256,
        "artifact_manifest_sha256": expected_artifact_manifest_sha256,
    }
    for name, expected in expected_manuscript_fields.items():
        if manuscript_validation.get(name) != expected:
            raise ValueError(f"empirical manuscript validation field changed: {name}")

    expected_release_fields = {
        "status": "passed_independent_deterministic_release_validation",
        "manifest_sha256": expected_release_manifest_sha256,
        "raw_dataset_files_included": False,
        "human_submission_fields_included": False,
        "normalized_archive_metadata": True,
        "independent_bearing_paper_artifact_validation_included": True,
        "independent_empirical_manuscript_validation_included": True,
        "independent_final_local_quality_validation_included": True,
        "preoutcome_raw_prediction_topology_manifest_included": True,
        "independent_raw_prediction_topology_validation_included": True,
        "technical_manuscript_submission_ready": False,
    }
    for name, expected in expected_release_fields.items():
        if release_validation.get(name) != expected:
            raise ValueError(f"release validation field changed: {name}")

    if release_manifest.get("raw_dataset_files_included") is not False:
        raise ValueError("release manifest does not prohibit raw dataset files")
    if release_manifest.get("human_submission_fields_included") is not False:
        raise ValueError("release manifest does not prohibit human submission fields")
    release_files = release_manifest.get("files")
    if not isinstance(release_files, list):
        raise ValueError("release manifest has no file records")
    release_records: dict[str, Mapping[str, Any]] = {}
    for item in release_files:
        if not isinstance(item, Mapping):
            raise ValueError("release manifest file record is not an object")
        relative = str(item.get("path", ""))
        if not relative or relative in release_records:
            raise ValueError("release manifest path is empty or duplicated")
        if relative == HUMAN_SUBMISSION_FIELDS_PATH:
            raise ValueError("release manifest contains human submission fields")
        release_records[relative] = item
    root = project_root()
    for relative in RELEASE_BOUND_SOURCE_PATHS:
        record = release_records.get(relative)
        if record is None:
            raise ValueError(f"release manifest omits PDF source: {relative}")
        source_path = (root / relative).resolve(strict=True)
        if record.get("sha256") != sha256_file(source_path) or int(
            record.get("bytes", -1)
        ) != source_path.stat().st_size:
            raise ValueError(f"release-bound PDF source identity changed: {relative}")

    artifact_directory = locked["artifact_manifest"].parent
    expected_figure_records: list[dict[str, Any]] = []
    for order, (name, _title) in enumerate(EXPECTED_FIGURES, start=1):
        record = records.get(name)
        if record is None:
            raise ValueError(f"bearing artifact manifest omits expected figure: {name}")
        figure_path = (artifact_directory / name).resolve(strict=True)
        figure_digest = sha256_file(figure_path)
        if record.get("sha256") != figure_digest or int(record.get("bytes", -1)) != (
            figure_path.stat().st_size
        ):
            raise ValueError(f"bearing artifact figure identity changed: {name}")
        figure_reader = PdfReader(figure_path)
        if len(figure_reader.pages) != 1:
            raise ValueError(f"bearing artifact figure is not one page: {name}")
        expected_figure_records.append(
            {
                "order": order,
                "path": figure_path.as_posix(),
                "sha256": figure_digest,
                "bytes": figure_path.stat().st_size,
            }
        )

    expected_report_fields = {
        "status": "rendered_working_visual_preflight",
        "renderer_version": EXPECTED_RENDERER_VERSION,
        "manuscript_sha256": expected_manuscript_sha256,
        "bibliography_sha256": expected_bibliography_sha256,
        "output_sha256": expected_pdf_sha256,
        "output_bytes": locked["pdf"].stat().st_size,
        "blank_page_count": 0,
        "main_figure_pdf_count": 5,
        "main_figure_pdfs": expected_figure_records,
        "working_preflight_watermark": True,
        "machine_render_complete": False,
        "human_visual_review_complete": False,
        "submission_ready": False,
    }
    for name, expected in expected_report_fields.items():
        if report.get(name) != expected:
            raise ValueError(f"RESS PDF report field changed: {name}")
    if int(report.get("forbidden_final_marker_count", 0)) < 1:
        raise ValueError("RESS working preflight lost its explicit non-final marker")

    reader = PdfReader(locked["pdf"])
    if len(reader.pages) != int(report.get("page_count", -1)) or len(reader.pages) < 10:
        raise ValueError("RESS empirical PDF page count changed")
    page_text = [(page.extract_text() or "").strip() for page in reader.pages]
    if any(not text for text in page_text):
        raise ValueError("RESS empirical PDF contains a page without extractable text")
    figure_pages = page_text[-len(EXPECTED_FIGURES) :]
    for page_text_value, (_name, title) in zip(
        figure_pages, EXPECTED_FIGURES, strict=True
    ):
        if title not in " ".join(page_text_value.split()):
            raise ValueError(f"RESS empirical PDF figure order changed: {title}")
    metadata = reader.metadata or {}
    if metadata.get("/Producer") != EXPECTED_RENDERER_VERSION:
        raise ValueError("RESS empirical PDF producer metadata changed")

    return {
        "status": "passed_independent_ress_empirical_pdf_preflight_validation",
        "validator_version": VALIDATOR_VERSION,
        "renderer_version": EXPECTED_RENDERER_VERSION,
        "pdf_sha256": expected_pdf_sha256,
        "report_sha256": expected_report_sha256,
        "artifact_manifest_sha256": expected_artifact_manifest_sha256,
        "release_manifest_sha256": expected_release_manifest_sha256,
        "release_bound_source_count": len(RELEASE_BOUND_SOURCE_PATHS),
        "validated_page_count": len(reader.pages),
        "validated_main_figure_count": len(EXPECTED_FIGURES),
        "ordered_figure_titles_verified": True,
        "empirical_model_refit_performed": False,
        "release_validation_required": True,
        "working_preflight_watermark": True,
        "human_visual_review_complete": False,
        "submission_ready": False,
    }
