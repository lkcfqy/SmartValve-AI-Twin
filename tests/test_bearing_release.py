from __future__ import annotations

import json
import os
import tarfile
from pathlib import Path

import pytest

from smartvalve.config import project_root
from smartvalve.experiments.bearing_release import (
    ARCHIVE_NAME,
    ARCHIVE_ROOT,
    DEFAULT_DOCUMENTS,
    DEFAULT_SOURCE_GLOBS,
    DEFAULT_SUPPORT_FILES,
    HUMAN_SUBMISSION_FIELDS_PATH,
    RAW_DATA_SUFFIXES,
    RELEASE_VERSION,
    build_release_archive,
    sha256_file,
    validate_release_archive,
)


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _fixture(root: Path, *, raw_suffix: bool = False) -> Path:
    result = root / "artifacts" / "run" / "outputs"
    result.mkdir(parents=True)
    output_name = "signal.npy" if raw_suffix else "predictions.parquet"
    _write(result / output_name, "locked result\n")
    summary = {
        "status": "complete",
        "output_sha256": {output_name: sha256_file(result / output_name)},
    }
    summary_path = result / "raw_architecture_sensitivity_summary.json"
    _write(summary_path, json.dumps(summary, sort_keys=True) + "\n")
    validation_path = root / "artifacts" / "validation.json"
    _write(
        validation_path,
        json.dumps(
            {
                "status": "passed_independent_no_refit_recomputation",
                "refit_performed": False,
            },
            sort_keys=True,
        )
        + "\n",
    )
    generated = root / "paper" / "generated"
    _write(generated / "bearing_figure.svg", "<svg xmlns='http://www.w3.org/2000/svg'/>\n")
    _write(root / "src" / "model.py", "VALUE = 1\n")
    _write(root / "requirements.lock", "numpy==2.0.0\n")
    artifact_manifest = {
        "deterministic": True,
        "inputs": {
            "raw_summary": {
                "path": summary_path.relative_to(root).as_posix(),
                "sha256": sha256_file(summary_path),
            },
            "raw_validation": {
                "path": validation_path.relative_to(root).as_posix(),
                "sha256": sha256_file(validation_path),
            },
        },
        "outputs": [
            {
                "path": "bearing_figure.svg",
                "bytes": (generated / "bearing_figure.svg").stat().st_size,
                "sha256": sha256_file(generated / "bearing_figure.svg"),
            }
        ],
    }
    manifest_path = generated / "bearing_artifact_manifest.json"
    _write(manifest_path, json.dumps(artifact_manifest, sort_keys=True) + "\n")
    artifact_validation = root / "artifacts" / "paper-validation" / "validation.json"
    _write(
        artifact_validation,
        json.dumps(
            {
                "status": "passed_independent_bearing_paper_artifact_validation",
                "refit_performed": False,
                "manifest_sha256": sha256_file(manifest_path),
                "input_count": 28,
                "output_count": 42,
                "svg_count": 5,
                "submission_pdf_count": 5,
                "raw_dataset_files_in_manifest": False,
            },
            sort_keys=True,
        )
        + "\n",
    )
    template = root / "paper" / "BEARING_MANUSCRIPT.md"
    empirical = root / "artifacts" / "manuscript" / "BEARING_MANUSCRIPT_EMPIRICAL_FINAL.md"
    render_report = root / "artifacts" / "manuscript" / "render_report.json"
    manuscript_validation = root / "artifacts" / "manuscript-validation" / "validation.json"
    _write(template, "# Working manuscript template\n")
    _write(empirical, "# Empirically final manuscript; human fields pending\n")
    report_value = {
        "status": "rendered_empirical_final_human_fields_pending",
        "submission_ready": False,
        "rendered_sha256": sha256_file(empirical),
        "template_sha256": sha256_file(template),
        "artifact_manifest_sha256": sha256_file(manifest_path),
    }
    _write(render_report, json.dumps(report_value, sort_keys=True) + "\n")
    validation_value = {
        "status": "passed_independent_empirical_manuscript_validation",
        "refit_performed": False,
        "submission_ready": False,
        "manuscript_sha256": sha256_file(empirical),
        "render_report_sha256": sha256_file(render_report),
        "template_sha256": sha256_file(template),
        "artifact_manifest_sha256": sha256_file(manifest_path),
    }
    _write(manuscript_validation, json.dumps(validation_value, sort_keys=True) + "\n")
    quality = root / "artifacts" / "final-quality" / "outputs"
    quality_log = quality / "quality.log"
    _write(quality_log, "all eight checks passed\n")
    quality_summary = quality / "final_quality_gate_summary.json"
    quality_summary_value = {
        "status": "passed_final_local_quality_gate",
        "expected_test_count": 380,
        "pytest_counts": {"tests": 380, "failures": 0, "errors": 0, "skipped": 0},
        "coverage_percent": 78.125,
        "output_sha256": {"quality.log": sha256_file(quality_log)},
        "empirical_model_refit_performed": False,
        "clean_checkout_claimed": False,
        "independent_reproduction_claimed": False,
        "human_review_claimed": False,
        "submission_ready": False,
    }
    _write(quality_summary, json.dumps(quality_summary_value, sort_keys=True) + "\n")
    quality_validation = root / "artifacts" / "final-quality-validation" / "validation.json"
    quality_validation_value = {
        "status": "passed_independent_final_local_quality_validation",
        "quality_summary_sha256": sha256_file(quality_summary),
        "verified_check_count": 8,
        "verified_expected_test_count": 380,
        "verified_test_count": 380,
        "verified_skipped_count": 0,
        "verified_coverage_percent": 78.125,
        "empirical_model_refit_performed": False,
        "clean_checkout_claimed": False,
        "independent_reproduction_claimed": False,
        "human_review_claimed": False,
        "submission_ready": False,
    }
    _write(quality_validation, json.dumps(quality_validation_value, sort_keys=True) + "\n")
    topology_manifest = (
        root
        / "artifacts"
        / "raw-topology-manifest"
        / "outputs"
        / "expected_topology_manifest.json"
    )
    expected_key_sets = {
        "window_predictions": {"count": 166_968, "sha256": "1" * 64},
        "seed_recording_predictions": {"count": 41_742, "sha256": "2" * 64},
        "ensemble_recording_predictions": {"count": 13_914, "sha256": "3" * 64},
        "fits": {"count": 270, "sha256": "4" * 64},
        "training_traces": {"count": 270, "sha256": "5" * 64},
    }
    _write(
        topology_manifest,
        json.dumps(
            {
                "status": "frozen_outcome_blind_expected_raw_prediction_topology",
                "expected_key_sets": expected_key_sets,
            },
            sort_keys=True,
        )
        + "\n",
    )
    topology_validation = (
        root / "artifacts" / "raw-topology-validation" / "outputs" / "validation.json"
    )
    _write(
        topology_validation,
        json.dumps(
            {
                "status": "passed_independent_raw_prediction_topology_validation",
                "input_sha256": {"expected_manifest": sha256_file(topology_manifest)},
                "validated_key_sets": expected_key_sets,
                "refit_performed": False,
                "aggregate_metrics_recomputed": False,
                "gate_outcome_read": False,
            },
            sort_keys=True,
        )
        + "\n",
    )
    return manifest_path


def _manuscript_arguments(root: Path) -> dict[str, Path]:
    return {
        "artifact_validation": root / "artifacts" / "paper-validation" / "validation.json",
        "empirical_manuscript": root
        / "artifacts"
        / "manuscript"
        / "BEARING_MANUSCRIPT_EMPIRICAL_FINAL.md",
        "manuscript_render_report": root / "artifacts" / "manuscript" / "render_report.json",
        "manuscript_validation": root
        / "artifacts"
        / "manuscript-validation"
        / "validation.json",
        "final_quality_summary": root
        / "artifacts"
        / "final-quality"
        / "outputs"
        / "final_quality_gate_summary.json",
        "final_quality_validation": root
        / "artifacts"
        / "final-quality-validation"
        / "validation.json",
        "raw_topology_manifest": root
        / "artifacts"
        / "raw-topology-manifest"
        / "outputs"
        / "expected_topology_manifest.json",
        "raw_topology_validation": root
        / "artifacts"
        / "raw-topology-validation"
        / "outputs"
        / "validation.json",
    }


def test_release_archive_is_deterministic_and_contains_no_raw_data(tmp_path: Path) -> None:
    root = tmp_path / "project"
    root.mkdir()
    artifact_manifest = _fixture(root)

    first = build_release_archive(
        project_root=root,
        artifact_manifest=artifact_manifest,
        **_manuscript_arguments(root),
        output_directory=tmp_path / "release-1",
        document_paths=(),
        source_globs=("src/**/*.py",),
        support_paths=("requirements.lock",),
    )
    second = build_release_archive(
        project_root=root,
        artifact_manifest=artifact_manifest,
        **_manuscript_arguments(root),
        output_directory=tmp_path / "release-2",
        document_paths=(),
        source_globs=("src/**/*.py",),
        support_paths=("requirements.lock",),
    )

    assert first["archive_sha256"] == second["archive_sha256"]
    assert first["manifest_sha256"] == second["manifest_sha256"]
    assert first["raw_dataset_files_included"] is False
    assert first["human_submission_fields_included"] is False
    assert first["reproduction_source_included"] is True
    with tarfile.open(tmp_path / "release-1" / ARCHIVE_NAME, mode="r:gz") as archive:
        names = archive.getnames()
        assert names == sorted(names)
        assert f"{ARCHIVE_ROOT}/release_manifest.json" in names
        assert f"{ARCHIVE_ROOT}/artifacts/run/outputs/predictions.parquet" in names
        assert (
            f"{ARCHIVE_ROOT}/artifacts/manuscript/BEARING_MANUSCRIPT_EMPIRICAL_FINAL.md"
            in names
        )
        assert f"{ARCHIVE_ROOT}/artifacts/paper-validation/validation.json" in names
        assert f"{ARCHIVE_ROOT}/artifacts/manuscript-validation/validation.json" in names
        assert (
            f"{ARCHIVE_ROOT}/artifacts/final-quality/outputs/final_quality_gate_summary.json"
            in names
        )
        assert f"{ARCHIVE_ROOT}/artifacts/final-quality-validation/validation.json" in names
        assert (
            f"{ARCHIVE_ROOT}/artifacts/raw-topology-manifest/outputs/"
            "expected_topology_manifest.json"
        ) in names
        assert (
            f"{ARCHIVE_ROOT}/artifacts/raw-topology-validation/outputs/validation.json"
            in names
        )
        assert f"{ARCHIVE_ROOT}/src/model.py" in names
        assert f"{ARCHIVE_ROOT}/requirements.lock" in names
        assert f"{ARCHIVE_ROOT}/{HUMAN_SUBMISSION_FIELDS_PATH}" not in names
        assert not any(Path(name).suffix in {".mat", ".npy", ".rar", ".zip"} for name in names)

    validation = validate_release_archive(
        archive_path=tmp_path / "release-1" / ARCHIVE_NAME,
        manifest_path=tmp_path / "release-1" / "release_manifest.json",
        checksum_path=tmp_path / "release-1" / f"{ARCHIVE_NAME}.sha256",
        expected_archive_sha256=first["archive_sha256"],
        expected_manifest_sha256=first["manifest_sha256"],
    )
    assert validation["status"] == "passed_independent_deterministic_release_validation"
    assert validation["verified_file_count"] == first["file_count"]
    assert validation["independent_final_local_quality_validation_included"] is True
    assert validation["preoutcome_raw_prediction_topology_manifest_included"] is True
    assert validation["independent_raw_prediction_topology_validation_included"] is True
    assert validation["human_submission_fields_included"] is False


def test_release_rejects_a_tampered_summary_output(tmp_path: Path) -> None:
    root = tmp_path / "project"
    root.mkdir()
    artifact_manifest = _fixture(root)
    _write(root / "artifacts" / "run" / "outputs" / "predictions.parquet", "tampered\n")

    with pytest.raises(ValueError, match="SHA-256 changed"):
        build_release_archive(
            project_root=root,
            artifact_manifest=artifact_manifest,
            **_manuscript_arguments(root),
            output_directory=tmp_path / "release",
            document_paths=(),
            source_globs=(),
            support_paths=(),
        )


def test_release_rejects_a_tampered_empirical_manuscript(tmp_path: Path) -> None:
    root = tmp_path / "project"
    root.mkdir()
    artifact_manifest = _fixture(root)
    manuscript = _manuscript_arguments(root)["empirical_manuscript"]
    _write(manuscript, "tampered empirical manuscript\n")

    with pytest.raises(ValueError, match="validation hash changed: manuscript_sha256"):
        build_release_archive(
            project_root=root,
            artifact_manifest=artifact_manifest,
            **_manuscript_arguments(root),
            output_directory=tmp_path / "release",
            document_paths=(),
            source_globs=(),
            support_paths=(),
        )


def test_release_rejects_a_tampered_artifact_validation(tmp_path: Path) -> None:
    root = tmp_path / "project"
    root.mkdir()
    artifact_manifest = _fixture(root)
    validation = _manuscript_arguments(root)["artifact_validation"]
    value = json.loads(validation.read_text(encoding="utf-8"))
    value["output_count"] = 38
    _write(validation, json.dumps(value, sort_keys=True) + "\n")

    with pytest.raises(ValueError, match="artifact validation field changed: output_count"):
        build_release_archive(
            project_root=root,
            artifact_manifest=artifact_manifest,
            **_manuscript_arguments(root),
            output_directory=tmp_path / "release",
            document_paths=(),
            source_globs=(),
            support_paths=(),
        )


def test_release_rejects_a_tampered_final_quality_validation(tmp_path: Path) -> None:
    root = tmp_path / "project"
    root.mkdir()
    artifact_manifest = _fixture(root)
    validation = _manuscript_arguments(root)["final_quality_validation"]
    value = json.loads(validation.read_text(encoding="utf-8"))
    value["verified_check_count"] = 7
    _write(validation, json.dumps(value, sort_keys=True) + "\n")

    with pytest.raises(ValueError, match="quality validation check count changed"):
        build_release_archive(
            project_root=root,
            artifact_manifest=artifact_manifest,
            **_manuscript_arguments(root),
            output_directory=tmp_path / "release",
            document_paths=(),
            source_globs=(),
            support_paths=(),
        )


def test_release_rejects_a_tampered_raw_topology_validation(tmp_path: Path) -> None:
    root = tmp_path / "project"
    root.mkdir()
    artifact_manifest = _fixture(root)
    validation = _manuscript_arguments(root)["raw_topology_validation"]
    value = json.loads(validation.read_text(encoding="utf-8"))
    value["gate_outcome_read"] = True
    _write(validation, json.dumps(value, sort_keys=True) + "\n")

    with pytest.raises(
        ValueError,
        match="raw prediction-topology validation field changed: gate_outcome_read",
    ):
        build_release_archive(
            project_root=root,
            artifact_manifest=artifact_manifest,
            **_manuscript_arguments(root),
            output_directory=tmp_path / "release",
            document_paths=(),
            source_globs=(),
            support_paths=(),
        )


def test_release_rejects_raw_or_archive_data(tmp_path: Path) -> None:
    root = tmp_path / "project"
    root.mkdir()
    artifact_manifest = _fixture(root, raw_suffix=True)

    with pytest.raises(ValueError, match="raw or archive data are prohibited"):
        build_release_archive(
            project_root=root,
            artifact_manifest=artifact_manifest,
            **_manuscript_arguments(root),
            output_directory=tmp_path / "release",
            document_paths=(),
            source_globs=(),
            support_paths=(),
        )


def test_release_rejects_human_submission_fields_from_public_archive(
    tmp_path: Path,
) -> None:
    root = tmp_path / "project"
    root.mkdir()
    artifact_manifest = _fixture(root)
    _write(root / HUMAN_SUBMISSION_FIELDS_PATH, "private author contact fields\n")

    with pytest.raises(ValueError, match="human submission fields are prohibited"):
        build_release_archive(
            project_root=root,
            artifact_manifest=artifact_manifest,
            **_manuscript_arguments(root),
            output_directory=tmp_path / "release",
            document_paths=(HUMAN_SUBMISSION_FIELDS_PATH,),
            source_globs=(),
            support_paths=(),
        )


def test_release_rejects_a_source_glob_that_can_escape_project(tmp_path: Path) -> None:
    root = tmp_path / "project"
    root.mkdir()
    artifact_manifest = _fixture(root)

    with pytest.raises(ValueError, match="source glob must stay inside"):
        build_release_archive(
            project_root=root,
            artifact_manifest=artifact_manifest,
            **_manuscript_arguments(root),
            output_directory=tmp_path / "release",
            document_paths=(),
            source_globs=("../*.py",),
            support_paths=(),
        )


def test_release_validator_rejects_a_tampered_checksum(tmp_path: Path) -> None:
    root = tmp_path / "project"
    root.mkdir()
    artifact_manifest = _fixture(root)
    output = tmp_path / "release"
    result = build_release_archive(
        project_root=root,
        artifact_manifest=artifact_manifest,
        **_manuscript_arguments(root),
        output_directory=output,
        document_paths=(),
        source_globs=("src/**/*.py",),
        support_paths=("requirements.lock",),
    )
    (output / f"{ARCHIVE_NAME}.sha256").write_text("tampered\n", encoding="ascii")

    with pytest.raises(ValueError, match="checksum file does not match"):
        validate_release_archive(
            archive_path=output / ARCHIVE_NAME,
            manifest_path=output / "release_manifest.json",
            checksum_path=output / f"{ARCHIVE_NAME}.sha256",
            expected_archive_sha256=result["archive_sha256"],
            expected_manifest_sha256=result["manifest_sha256"],
        )


def test_default_release_inputs_exist_and_source_globs_exclude_raw_data() -> None:
    root = project_root()

    assert all((root / relative).is_file() for relative in DEFAULT_DOCUMENTS)
    assert "DATA_LICENSE_NOTICE.md" in DEFAULT_DOCUMENTS
    assert RELEASE_VERSION == "smartvalve-bearing-evidence-release-0.11.3"
    assert "research/BEARING_RELEASE_AMENDMENT_001.md" in DEFAULT_DOCUMENTS
    assert "research/BEARING_RELEASE_AMENDMENT_002.md" in DEFAULT_DOCUMENTS
    assert "research/BEARING_RELEASE_AMENDMENT_003.md" in DEFAULT_DOCUMENTS
    assert "research/BEARING_VISUAL_QA.md" in DEFAULT_DOCUMENTS
    assert "research/CLEAN_REPRODUCTION_PROTOCOL.md" in DEFAULT_DOCUMENTS
    assert "research/EXTERNAL_REVIEW_PACKET.md" in DEFAULT_DOCUMENTS
    assert "paper/RESS_SUBMISSION_PACKET.md" in DEFAULT_DOCUMENTS
    assert HUMAN_SUBMISSION_FIELDS_PATH not in DEFAULT_DOCUMENTS
    assert "research/HUST_POSTHOC_INFLUENCE_AUDIT_PLAN.md" in DEFAULT_DOCUMENTS
    assert "research/PADERBORN_RAW_TOPOLOGY_AUDIT_PLAN.md" in DEFAULT_DOCUMENTS
    assert "research/PADERBORN_RAW_VALIDATOR_AMENDMENT_001.md" in DEFAULT_DOCUMENTS
    clean_reproduction = (
        root / "research/CLEAN_REPRODUCTION_PROTOCOL.md"
    ).read_text(encoding="utf-8")
    assert "SMARTVALVE_EXPECTED_TEST_COUNT" in clean_reproduction
    assert "counts['tests'] == expected" in clean_reproduction
    assert "counts['tests'] >= 385" not in clean_reproduction
    assert 'records/clean-release-validation.json"' in clean_reproduction
    assert all((root / relative).is_file() for relative in DEFAULT_SUPPORT_FILES)
    assert "requirements-research.lock" in DEFAULT_SUPPORT_FILES
    assert "Dockerfile" in DEFAULT_SUPPORT_FILES
    assert ".dockerignore" in DEFAULT_SUPPORT_FILES
    assert ".github/workflows/ci.yml" in DEFAULT_SUPPORT_FILES
    assert "artifacts/research/launch/run_*.sh" in DEFAULT_SOURCE_GLOBS
    assert "research/scripts/*.py" in DEFAULT_SOURCE_GLOBS
    assert "paper/generated/*" in DEFAULT_SOURCE_GLOBS
    assert "artifacts/benchmark/*/*" in DEFAULT_SOURCE_GLOBS
    assert "artifacts/validation/cranfield/*" in DEFAULT_SOURCE_GLOBS
    for relative in (
        "paper/BEARING_DISCUSSION.md",
        "paper/BEARING_METHODS.md",
        "paper/BEARING_RESULTS.md",
        "paper/MANUSCRIPT_OUTLINE.md",
        "paper/METHODS.md",
        "paper/RESULTS.md",
    ):
        assert relative in DEFAULT_DOCUMENTS
    source_paths = [path for pattern in DEFAULT_SOURCE_GLOBS for path in root.glob(pattern)]
    assert source_paths
    assert {
        "artifact_manifest.json",
        "multirig_artifact_manifest.json",
    } <= {path.name for path in source_paths if path.parent.name == "generated"}
    generated_manifests = sorted((root / "paper" / "generated").glob("*_manifest.json"))
    assert len(generated_manifests) == 2
    source_only_ci = os.getenv("SMARTVALVE_SOURCE_ONLY_CI") == "1"
    if source_only_ci:
        assert "artifacts/research/runs/" in (root / ".gitignore").read_text(
            encoding="utf-8"
        )
    for generated_manifest in generated_manifests:
        payload = json.loads(generated_manifest.read_text(encoding="utf-8"))
        for item in payload["inputs"].values():
            relative = item["path"]
            path = root / relative
            if path.is_file():
                continue
            assert source_only_ci
            assert relative.startswith("artifacts/research/runs/")
            assert ".." not in Path(relative).parts
            assert len(item["sha256"]) == 64
            assert all(character in "0123456789abcdef" for character in item["sha256"])
    assert (
        root / "research" / "scripts" / "validate_paderborn_split_manifest.py"
    ) in source_paths
    launch_paths = [
        path
        for path in source_paths
        if path.parent.as_posix().endswith("artifacts/research/launch")
    ]
    assert {path.name for path in launch_paths} == {
        "run_EXP456R1.sh",
        "run_EXP457_after_EXP456R1.sh",
        "run_EXP458_EXP459_after_EXP457.sh",
        "run_EXP460_EXP461_after_EXP459.sh",
        "run_EXP462_EXP463_after_EXP461.sh",
        "run_EXP490_EXP491_after_EXP463.sh",
    }
    pdf_watcher = (
        root / "artifacts/research/launch/run_EXP490_EXP491_after_EXP463.sh"
    ).read_text(encoding="utf-8")
    for relative in (
        "src/smartvalve/experiments/ress_pdf.py",
        "src/smartvalve/experiments/ress_pdf_validation.py",
        "scripts/render_ress_pdf.py",
        "scripts/validate_ress_pdf.py",
    ):
        assert f'"{relative}"' in pdf_watcher
    assert "release-bound live PDF source changed" in pdf_watcher
    assert "hashlib.sha256(path.read_bytes()).hexdigest()" in pdf_watcher
    artifact_watcher = (
        root / "artifacts/research/launch/run_EXP458_EXP459_after_EXP457.sh"
    ).read_text(encoding="utf-8")
    assert "shared_producer_calculation_code" in artifact_watcher
    assert "smartvalve-paderborn-raw-independent-calculations-0.2.0" in artifact_watcher
    assert "d053dc678cd382c603e071e2b1f2a9c0b50ce3beaae8d7e20b63b1bbb5db2a17" in (
        artifact_watcher
    )
    assert "9ae4cd837d9f2383b5bc36f29c4038c096907e9606f6e866018744962cfa7acf" in (
        artifact_watcher
    )
    assert "EXP-457 independent-calculation identity does not authorize artifacts" in (
        artifact_watcher
    )
    assert "EXP-459R1-BEARING-PAPER-VALIDATION" in artifact_watcher
    manuscript_watcher = (
        root / "artifacts/research/launch/run_EXP460_EXP461_after_EXP459.sh"
    ).read_text(encoding="utf-8")
    assert "EXP-459R1-BEARING-PAPER-VALIDATION__*" in manuscript_watcher
    assert "smartvalve-bearing-paper-validator-0.4.1" in manuscript_watcher
    assert "a2a9c26ffbcd8ed7f7964581b5cd35740e910c4be5d8c80babbc0300f4bcdcd9" in (
        manuscript_watcher
    )
    assert "raw_median_summary_csv_difference" in manuscript_watcher
    quality_watcher = (
        root / "artifacts/research/launch/run_EXP462_EXP463_after_EXP461.sh"
    ).read_text(encoding="utf-8")
    assert "EXP-459R1-BEARING-PAPER-VALIDATION__*" in quality_watcher
    assert "smartvalve-bearing-paper-validator-0.4.1" in quality_watcher
    assert "a2a9c26ffbcd8ed7f7964581b5cd35740e910c4be5d8c80babbc0300f4bcdcd9" in (
        quality_watcher
    )
    assert "--expected-test-count 427" in quality_watcher
    assert "--minimum-test-count" not in quality_watcher
    assert 'QUALITY_VALIDATION_FIELDS[3]}" != \'427\'' in quality_watcher
    assert "EXP-459R1-BEARING-PAPER-VALIDATION__*" in pdf_watcher
    assert all(path.name.startswith("run_EXP") and path.suffix == ".sh" for path in launch_paths)
    assert all(path.is_file() for path in source_paths)
    assert not any(path.suffix.lower() in RAW_DATA_SUFFIXES for path in source_paths)
