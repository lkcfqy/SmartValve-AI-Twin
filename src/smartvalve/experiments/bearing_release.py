"""Build a deterministic, raw-data-free evidence archive for the bearing paper."""

from __future__ import annotations

import gzip
import io
import json
import tarfile
from collections.abc import Iterable, Mapping
from hashlib import sha256
from pathlib import Path
from typing import Any

from smartvalve.experiments.final_quality_gate import CHECK_IDS

RELEASE_VERSION = "smartvalve-bearing-evidence-release-0.11.3"
ARCHIVE_NAME = "smartvalve-bearing-evidence.tar.gz"
ARCHIVE_ROOT = "smartvalve-bearing-evidence"
HUMAN_SUBMISSION_FIELDS_PATH = "paper/RESS_HUMAN_SUBMISSION_FIELDS.md"
RAW_DATA_SUFFIXES = {".mat", ".npy", ".part", ".rar", ".zip"}
DEFAULT_SOURCE_GLOBS = (
    "src/**/*.py",
    "scripts/*.py",
    "research/scripts/*.py",
    "tests/*.py",
    "artifacts/research/launch/run_*.sh",
    "paper/generated/*",
    "artifacts/benchmark/*/*",
    "artifacts/validation/cranfield/*",
)
DEFAULT_SUPPORT_FILES = (
    ".dockerignore",
    ".github/workflows/ci.yml",
    ".gitignore",
    "Dockerfile",
    "LICENSE",
    "Makefile",
    "README.md",
    "build-requirements.in",
    "build-requirements.lock",
    "pyproject.toml",
    "requirements-ci.lock",
    "requirements-research.lock",
    "requirements.lock",
)
DEFAULT_DOCUMENTS = (
    "DATA_LICENSE_NOTICE.md",
    "THIRD_PARTY_NOTICES.md",
    "paper/BEARING_MANUSCRIPT.md",
    "paper/BEARING_DISCUSSION.md",
    "paper/BEARING_METHODS.md",
    "paper/BEARING_RESULTS.md",
    "paper/MANUSCRIPT_OUTLINE.md",
    "paper/METHODS.md",
    "paper/NOVELTY_MATRIX.md",
    "paper/README.md",
    "paper/RELATED_WORK.md",
    "paper/REPRODUCIBILITY.md",
    "paper/RESS_SUBMISSION_PACKET.md",
    "paper/RESULTS.md",
    "paper/SUBMISSION_STRATEGY.md",
    "paper/TITLE_ABSTRACT.md",
    "paper/references.bib",
    "research/ADVERSARIAL_REVIEW.md",
    "research/AI_ASSISTANCE_RECORD.md",
    "research/BEARING_RELEASE_AMENDMENT_001.md",
    "research/BEARING_RELEASE_AMENDMENT_002.md",
    "research/BEARING_RELEASE_AMENDMENT_003.md",
    "research/BEARING_VISUAL_QA.md",
    "research/CLEAN_REPRODUCTION_PROTOCOL.md",
    "research/EXPERIMENT_INCIDENTS.md",
    "research/EXPERIMENT_LEDGER.md",
    "research/EXTERNAL_REVIEW_PACKET.md",
    "research/HUST_D3_EXECUTION_AMENDMENT_001.md",
    "research/HUST_D3_FACTORIAL_SEAL.md",
    "research/HUST_D3_PREACCESS_CLARIFICATION.md",
    "research/HUST_D3_RUNTIME_DEPENDENCY_ADDENDUM_002.md",
    "research/HUST_D3_SIZE_MATCHED_CONTROL_SEAL.md",
    "research/HUST_POSTHOC_INFLUENCE_AUDIT_PLAN.md",
    "research/LITERATURE_SEARCH_LOG.md",
    "research/PADERBORN_NEURAL_PROTOCOL_CONTRAST_SEAL.md",
    "research/PADERBORN_PROTOCOL_CONTRAST_SEAL.md",
    "research/PADERBORN_RAW_ARCHITECTURE_SENSITIVITY_SEAL.md",
    "research/PADERBORN_RAW_VALIDATOR_AMENDMENT_001.md",
    "research/PADERBORN_RAW_TOPOLOGY_AUDIT_PLAN.md",
    "research/PADERBORN_SENSOR_PROTOCOL_AUDIT_SEAL.md",
    "research/PAPER_READINESS_CHECKLIST.md",
    "research/TOP_TIER_REVIEW_RISKS.md",
    "research/TOP_TIER_UPGRADE_PLAN.md",
)


def sha256_file(path: Path) -> str:
    """Return the SHA-256 digest of a file without loading it all into memory."""

    digest = sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(4 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _relative_file(root: Path, path: Path) -> tuple[Path, str]:
    resolved = path.resolve(strict=True)
    try:
        relative = resolved.relative_to(root).as_posix()
    except ValueError as error:
        raise ValueError(f"release input is outside the project root: {resolved}") from error
    if not resolved.is_file():
        raise ValueError(f"release input is not a file: {relative}")
    return resolved, relative


def _locked_file(
    root: Path,
    relative: str,
    expected_sha256: str,
    *,
    expected_bytes: int | None = None,
) -> tuple[Path, str]:
    if Path(relative).is_absolute():
        raise ValueError(f"release manifest path must be relative: {relative}")
    path, normalized = _relative_file(root, root / relative)
    if normalized != Path(relative).as_posix():
        raise ValueError(f"release manifest path is not normalized: {relative}")
    if expected_bytes is not None and path.stat().st_size != expected_bytes:
        raise ValueError(f"release input byte count changed: {relative}")
    observed = sha256_file(path)
    if observed != expected_sha256:
        raise ValueError(
            f"release input SHA-256 changed for {relative}: expected {expected_sha256}, "
            f"observed {observed}"
        )
    return path, normalized


def _json_object(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"JSON release input is not an object: {path}")
    return value


def _validate_artifact_validation_package(
    *,
    root: Path,
    artifact_manifest_path: Path,
    artifact_validation: Path,
) -> Path:
    validation_path, _ = _relative_file(root, artifact_validation)
    validation = _json_object(validation_path)
    expected_fields = {
        "status": "passed_independent_bearing_paper_artifact_validation",
        "refit_performed": False,
        "manifest_sha256": sha256_file(artifact_manifest_path),
        "input_count": 28,
        "output_count": 42,
        "svg_count": 5,
        "submission_pdf_count": 5,
        "raw_dataset_files_in_manifest": False,
    }
    for name, expected in expected_fields.items():
        if validation.get(name) != expected:
            raise ValueError(f"bearing paper artifact validation field changed: {name}")
    return validation_path


def _validate_empirical_manuscript_package(
    *,
    root: Path,
    artifact_manifest_path: Path,
    empirical_manuscript: Path,
    manuscript_render_report: Path,
    manuscript_validation: Path,
) -> tuple[Path, Path, Path]:
    manuscript_path, _ = _relative_file(root, empirical_manuscript)
    report_path, _ = _relative_file(root, manuscript_render_report)
    validation_path, _ = _relative_file(root, manuscript_validation)
    report = _json_object(report_path)
    validation = _json_object(validation_path)
    if validation.get("status") != "passed_independent_empirical_manuscript_validation":
        raise ValueError("empirical manuscript has not passed independent validation")
    if validation.get("refit_performed") is not False:
        raise ValueError("empirical manuscript validation must declare refit_performed=false")
    if validation.get("submission_ready") is not False:
        raise ValueError("technical evidence manuscript must retain submission_ready=false")
    expected_hashes = {
        "manuscript_sha256": sha256_file(manuscript_path),
        "render_report_sha256": sha256_file(report_path),
        "template_sha256": sha256_file(root / "paper" / "BEARING_MANUSCRIPT.md"),
        "artifact_manifest_sha256": sha256_file(artifact_manifest_path),
    }
    for name, expected in expected_hashes.items():
        if validation.get(name) != expected:
            raise ValueError(f"empirical manuscript validation hash changed: {name}")
    if report.get("status") != "rendered_empirical_final_human_fields_pending":
        raise ValueError("empirical manuscript render report status changed")
    if report.get("submission_ready") is not False:
        raise ValueError("empirical manuscript render report must retain submission_ready=false")
    if report.get("rendered_sha256") != expected_hashes["manuscript_sha256"]:
        raise ValueError("empirical manuscript render report output hash changed")
    if report.get("template_sha256") != expected_hashes["template_sha256"]:
        raise ValueError("empirical manuscript render report template hash changed")
    if report.get("artifact_manifest_sha256") != expected_hashes["artifact_manifest_sha256"]:
        raise ValueError("empirical manuscript render report artifact-manifest hash changed")
    return manuscript_path, report_path, validation_path


def _validate_final_quality_package(
    *,
    root: Path,
    final_quality_summary: Path,
    final_quality_validation: Path,
) -> tuple[Path, Path, list[Path]]:
    summary_path, _ = _relative_file(root, final_quality_summary)
    validation_path, _ = _relative_file(root, final_quality_validation)
    summary = _json_object(summary_path)
    validation = _json_object(validation_path)
    if summary.get("status") != "passed_final_local_quality_gate":
        raise ValueError("final local quality gate has not passed")
    if validation.get("status") != "passed_independent_final_local_quality_validation":
        raise ValueError("final local quality gate lacks independent validation")
    if validation.get("quality_summary_sha256") != sha256_file(summary_path):
        raise ValueError("final quality validation summary hash changed")
    if int(validation.get("verified_check_count", -1)) != len(CHECK_IDS):
        raise ValueError("final quality validation check count changed")
    pytest_counts = summary.get("pytest_counts")
    expected_test_count = int(summary.get("expected_test_count", 0))
    if (
        not isinstance(pytest_counts, Mapping)
        or expected_test_count < 1
        or int(pytest_counts.get("tests", -1)) != expected_test_count
        or int(validation.get("verified_expected_test_count", -1)) != expected_test_count
        or int(validation.get("verified_test_count", -1)) != expected_test_count
        or int(pytest_counts.get("failures", -1)) != 0
        or int(pytest_counts.get("errors", -1)) != 0
        or int(pytest_counts.get("skipped", -1)) != 0
        or float(summary.get("coverage_percent", -1)) < 75.0
    ):
        raise ValueError("final quality summary thresholds changed")
    expected_scope = {
        "empirical_model_refit_performed": False,
        "clean_checkout_claimed": False,
        "independent_reproduction_claimed": False,
        "human_review_claimed": False,
        "submission_ready": False,
    }
    for name, expected in expected_scope.items():
        if summary.get(name) is not expected or validation.get(name) is not expected:
            raise ValueError(f"final quality evidence scope changed: {name}")
    output_hashes = summary.get("output_sha256")
    if not isinstance(output_hashes, Mapping) or not output_hashes:
        raise ValueError("final quality summary has no output hash map")
    outputs = []
    for filename, expected_sha256 in sorted(output_hashes.items()):
        path = summary_path.parent / str(filename)
        relative = path.resolve(strict=True).relative_to(root).as_posix()
        locked, _ = _locked_file(root, relative, str(expected_sha256))
        outputs.append(locked)
    return summary_path, validation_path, outputs


def _validate_raw_topology_package(
    *,
    root: Path,
    raw_topology_manifest: Path,
    raw_topology_validation: Path,
) -> tuple[Path, Path]:
    manifest_path, _ = _relative_file(root, raw_topology_manifest)
    validation_path, _ = _relative_file(root, raw_topology_validation)
    manifest = _json_object(manifest_path)
    validation = _json_object(validation_path)
    if manifest.get("status") != "frozen_outcome_blind_expected_raw_prediction_topology":
        raise ValueError("raw prediction-topology manifest status changed")
    expected_key_sets = manifest.get("expected_key_sets")
    validated_key_sets = validation.get("validated_key_sets")
    if not isinstance(expected_key_sets, Mapping) or validated_key_sets != expected_key_sets:
        raise ValueError("raw prediction-topology validated key sets changed")
    expected_counts = {
        "window_predictions": 166_968,
        "seed_recording_predictions": 41_742,
        "ensemble_recording_predictions": 13_914,
        "fits": 270,
        "training_traces": 270,
    }
    for name, expected in expected_counts.items():
        item = expected_key_sets.get(name)
        if not isinstance(item, Mapping) or int(item.get("count", -1)) != expected:
            raise ValueError(f"raw prediction-topology expected count changed: {name}")
    expected_fields = {
        "status": "passed_independent_raw_prediction_topology_validation",
        "refit_performed": False,
        "aggregate_metrics_recomputed": False,
        "gate_outcome_read": False,
    }
    for name, expected in expected_fields.items():
        if validation.get(name) != expected:
            raise ValueError(f"raw prediction-topology validation field changed: {name}")
    input_hashes = validation.get("input_sha256")
    if (
        not isinstance(input_hashes, Mapping)
        or input_hashes.get("expected_manifest") != sha256_file(manifest_path)
    ):
        raise ValueError("raw prediction-topology validation manifest hash changed")
    return manifest_path, validation_path


def _add_file(
    records: dict[str, dict[str, Any]],
    *,
    root: Path,
    path: Path,
    role: str,
) -> None:
    resolved, relative = _relative_file(root, path)
    if resolved.suffix.lower() in RAW_DATA_SUFFIXES:
        raise ValueError(f"raw or archive data are prohibited from the release: {relative}")
    observed_bytes = resolved.stat().st_size
    observed_sha256 = sha256_file(resolved)
    record = records.setdefault(
        relative,
        {
            "path": relative,
            "bytes": observed_bytes,
            "sha256": observed_sha256,
            "roles": [],
        },
    )
    if record["bytes"] != observed_bytes or record["sha256"] != observed_sha256:
        raise ValueError(f"release input changed while collecting: {relative}")
    if role not in record["roles"]:
        record["roles"].append(role)
        record["roles"].sort()


def collect_release_files(
    *,
    project_root: Path,
    artifact_manifest: Path,
    artifact_validation: Path,
    empirical_manuscript: Path,
    manuscript_render_report: Path,
    manuscript_validation: Path,
    final_quality_summary: Path,
    final_quality_validation: Path,
    raw_topology_manifest: Path,
    raw_topology_validation: Path,
    document_paths: Iterable[str] = DEFAULT_DOCUMENTS,
    source_globs: Iterable[str] = DEFAULT_SOURCE_GLOBS,
    support_paths: Iterable[str] = DEFAULT_SUPPORT_FILES,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """Verify the paper manifest and expand every summary-declared result artifact."""

    root = project_root.resolve(strict=True)
    manifest_path, manifest_relative = _relative_file(root, artifact_manifest)
    manifest = _json_object(manifest_path)
    if manifest.get("deterministic") is not True:
        raise ValueError("bearing artifact manifest is not deterministic")
    inputs = manifest.get("inputs")
    outputs = manifest.get("outputs")
    if not isinstance(inputs, Mapping) or not isinstance(outputs, list):
        raise ValueError("bearing artifact manifest has invalid input/output tables")

    artifact_validation_path = _validate_artifact_validation_package(
        root=root,
        artifact_manifest_path=manifest_path,
        artifact_validation=artifact_validation,
    )
    empirical_paths = _validate_empirical_manuscript_package(
        root=root,
        artifact_manifest_path=manifest_path,
        empirical_manuscript=empirical_manuscript,
        manuscript_render_report=manuscript_render_report,
        manuscript_validation=manuscript_validation,
    )
    quality_summary_path, quality_validation_path, quality_outputs = (
        _validate_final_quality_package(
            root=root,
            final_quality_summary=final_quality_summary,
            final_quality_validation=final_quality_validation,
        )
    )
    topology_manifest_path, topology_validation_path = _validate_raw_topology_package(
        root=root,
        raw_topology_manifest=raw_topology_manifest,
        raw_topology_validation=raw_topology_validation,
    )

    records: dict[str, dict[str, Any]] = {}
    _add_file(
        records,
        root=root,
        path=manifest_path,
        role="bearing_artifact_manifest",
    )
    _add_file(
        records,
        root=root,
        path=artifact_validation_path,
        role="independent_bearing_paper_artifact_validation",
    )
    for path, role in zip(
        empirical_paths,
        (
            "empirical_final_manuscript",
            "empirical_manuscript_render_report",
            "independent_empirical_manuscript_validation",
        ),
        strict=True,
    ):
        _add_file(records, root=root, path=path, role=role)
    _add_file(
        records,
        root=root,
        path=quality_summary_path,
        role="final_local_quality_gate_summary",
    )
    _add_file(
        records,
        root=root,
        path=quality_validation_path,
        role="independent_final_local_quality_validation",
    )
    for path in quality_outputs:
        _add_file(records, root=root, path=path, role="final_local_quality_gate_output")
    _add_file(
        records,
        root=root,
        path=topology_manifest_path,
        role="preoutcome_raw_prediction_topology_manifest",
    )
    _add_file(
        records,
        root=root,
        path=topology_validation_path,
        role="independent_raw_prediction_topology_validation",
    )
    summary_paths: list[Path] = []
    for name, item in sorted(inputs.items()):
        if not isinstance(item, Mapping):
            raise ValueError(f"bearing artifact input is not an object: {name}")
        relative = str(item.get("path", ""))
        expected = str(item.get("sha256", ""))
        path, _ = _locked_file(root, relative, expected)
        _add_file(records, root=root, path=path, role=f"paper_input:{name}")
        if str(name).endswith("_summary"):
            summary_paths.append(path)

    generated_directory = manifest_path.parent
    for item in outputs:
        if not isinstance(item, Mapping):
            raise ValueError("bearing artifact output is not an object")
        output_path = generated_directory / str(item.get("path", ""))
        relative = output_path.resolve(strict=True).relative_to(root).as_posix()
        path, _ = _locked_file(
            root,
            relative,
            str(item.get("sha256", "")),
            expected_bytes=int(item.get("bytes", -1)),
        )
        _add_file(records, root=root, path=path, role="generated_paper_artifact")

    for summary_path in sorted(summary_paths):
        summary = _json_object(summary_path)
        hashes = summary.get("output_sha256")
        if not isinstance(hashes, Mapping) or not hashes:
            raise ValueError(f"paper summary has no output hash map: {summary_path}")
        for filename, expected in sorted(hashes.items()):
            result_path = summary_path.parent / str(filename)
            relative = result_path.resolve(strict=True).relative_to(root).as_posix()
            path, _ = _locked_file(root, relative, str(expected))
            _add_file(
                records,
                root=root,
                path=path,
                role=f"summary_output:{summary_path.name}",
            )

    for relative in document_paths:
        path, _ = _relative_file(root, root / relative)
        _add_file(records, root=root, path=path, role="audit_document")

    for pattern in source_globs:
        if Path(pattern).is_absolute() or ".." in Path(pattern).parts:
            raise ValueError(f"release source glob must stay inside the project: {pattern}")
        for path in sorted(root.glob(pattern)):
            if path.is_file():
                _add_file(records, root=root, path=path, role="reproduction_source")

    generated_directory = root / "paper" / "generated"
    for generated_manifest_path in sorted(generated_directory.glob("*_manifest.json")):
        generated_manifest = _json_object(generated_manifest_path)
        generated_inputs = generated_manifest.get("inputs")
        generated_outputs = generated_manifest.get("outputs")
        if not isinstance(generated_inputs, Mapping) or not isinstance(
            generated_outputs, list
        ):
            raise ValueError(
                f"generated paper manifest has invalid topology: {generated_manifest_path}"
            )
        _add_file(
            records,
            root=root,
            path=generated_manifest_path,
            role="generated_paper_package_manifest",
        )
        for name, item in sorted(generated_inputs.items()):
            if not isinstance(item, Mapping):
                raise ValueError(f"generated paper input is not an object: {name}")
            path, _ = _locked_file(
                root,
                str(item.get("path", "")),
                str(item.get("sha256", "")),
            )
            _add_file(
                records,
                root=root,
                path=path,
                role=f"generated_paper_package_input:{generated_manifest_path.name}",
            )
        for item in generated_outputs:
            if not isinstance(item, Mapping):
                raise ValueError("generated paper output is not an object")
            candidate = generated_directory / str(item.get("path", ""))
            relative = candidate.resolve(strict=True).relative_to(root).as_posix()
            path, _ = _locked_file(
                root,
                relative,
                str(item.get("sha256", "")),
                expected_bytes=int(item.get("bytes", -1)),
            )
            _add_file(
                records,
                root=root,
                path=path,
                role=f"generated_paper_package_output:{generated_manifest_path.name}",
            )

    for relative in support_paths:
        path, _ = _relative_file(root, root / relative)
        _add_file(records, root=root, path=path, role="environment_specification")

    if HUMAN_SUBMISSION_FIELDS_PATH in records:
        raise ValueError(
            "human submission fields are prohibited from the public evidence archive"
        )

    release_manifest = {
        "release_version": RELEASE_VERSION,
        "source_artifact_manifest": {
            "path": manifest_relative,
            "sha256": sha256_file(manifest_path),
        },
        "file_count": len(records),
        "total_uncompressed_bytes": sum(int(item["bytes"]) for item in records.values()),
        "raw_dataset_files_included": False,
        "human_submission_fields_included": False,
        "reproduction_source_included": any(
            "reproduction_source" in item["roles"] for item in records.values()
        ),
        "independent_bearing_paper_artifact_validation_included": True,
        "independent_empirical_manuscript_validation_included": True,
        "independent_final_local_quality_validation_included": True,
        "preoutcome_raw_prediction_topology_manifest_included": True,
        "independent_raw_prediction_topology_validation_included": True,
        "technical_manuscript_submission_ready": False,
        "deterministic_archive_metadata": True,
        "notes": [
            "Paderborn and HUST raw signals are not redistributed.",
            "Dataset-derived artifacts are not relicensed by the repository software licence; "
            "see DATA_LICENSE_NOTICE.md.",
            "Result files expand every output hash declared by the six paper summaries.",
            "Python source, tests, and dependency locks are included with content hashes.",
            "Docker/CI support files, checked-in service benchmark fixtures, and both legacy "
            "generated-paper packages with their hash-locked inputs are included so the release "
            "source can execute the exact no-skip quality topology without the development tree.",
            "The empirical-final manuscript, render report, and independent validation are "
            "included; human-owned submission declarations remain intentionally pending.",
            "The human submission-fields record is excluded because it may contain personal "
            "contact and approval information; authors transfer it separately to the journal.",
            "Final local lint, test, coverage, security, dependency, and diff-check logs plus "
            "their independent validation are included without claiming clean reproduction.",
            "The pre-outcome raw prediction-topology manifest and its independent exact-key "
            "validation are included without reading or recomputing the scientific gate.",
            "Archive member order, timestamps, ownership, and permissions are normalized.",
            "Public upload and licensing remain subject to human author approval.",
        ],
        "files": [records[name] for name in sorted(records)],
    }
    return release_manifest, [records[name] for name in sorted(records)]


def _normalized_tar_info(name: str, size: int) -> tarfile.TarInfo:
    info = tarfile.TarInfo(name=name)
    info.size = size
    info.mtime = 0
    info.uid = 0
    info.gid = 0
    info.uname = ""
    info.gname = ""
    info.mode = 0o644
    return info


def build_release_archive(
    *,
    project_root: Path,
    artifact_manifest: Path,
    artifact_validation: Path,
    empirical_manuscript: Path,
    manuscript_render_report: Path,
    manuscript_validation: Path,
    final_quality_summary: Path,
    final_quality_validation: Path,
    raw_topology_manifest: Path,
    raw_topology_validation: Path,
    output_directory: Path,
    document_paths: Iterable[str] = DEFAULT_DOCUMENTS,
    source_globs: Iterable[str] = DEFAULT_SOURCE_GLOBS,
    support_paths: Iterable[str] = DEFAULT_SUPPORT_FILES,
) -> dict[str, Any]:
    """Create the normalized evidence archive plus an external manifest and checksum."""

    root = project_root.resolve(strict=True)
    release_manifest, files = collect_release_files(
        project_root=root,
        artifact_manifest=artifact_manifest,
        artifact_validation=artifact_validation,
        empirical_manuscript=empirical_manuscript,
        manuscript_render_report=manuscript_render_report,
        manuscript_validation=manuscript_validation,
        final_quality_summary=final_quality_summary,
        final_quality_validation=final_quality_validation,
        raw_topology_manifest=raw_topology_manifest,
        raw_topology_validation=raw_topology_validation,
        document_paths=document_paths,
        source_globs=source_globs,
        support_paths=support_paths,
    )
    output_directory.mkdir(parents=True, exist_ok=True)
    archive_path = output_directory / ARCHIVE_NAME
    manifest_path = output_directory / "release_manifest.json"
    checksum_path = output_directory / f"{ARCHIVE_NAME}.sha256"
    for path in (archive_path, manifest_path, checksum_path):
        if path.exists():
            raise ValueError(f"release output already exists: {path}")

    manifest_bytes = (
        json.dumps(release_manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    ).encode("utf-8")
    manifest_path.write_bytes(manifest_bytes)
    with (
        archive_path.open("wb") as raw_handle,
        gzip.GzipFile(
            filename="",
            mode="wb",
            compresslevel=9,
            fileobj=raw_handle,
            mtime=0,
        ) as gzip_handle,
        tarfile.open(fileobj=gzip_handle, mode="w", format=tarfile.GNU_FORMAT) as archive,
    ):
        items = {str(item["path"]): item for item in files}
        member_names = sorted(["release_manifest.json", *items])
        for member_name in member_names:
            archive_name = f"{ARCHIVE_ROOT}/{member_name}"
            if member_name == "release_manifest.json":
                info = _normalized_tar_info(archive_name, len(manifest_bytes))
                archive.addfile(info, io.BytesIO(manifest_bytes))
            else:
                source = root / str(items[member_name]["path"])
                info = _normalized_tar_info(archive_name, source.stat().st_size)
                with source.open("rb") as handle:
                    archive.addfile(info, handle)

    archive_digest = sha256_file(archive_path)
    checksum_path.write_text(f"{archive_digest}  {ARCHIVE_NAME}\n", encoding="ascii")
    return {
        "status": "complete_deterministic_raw_data_free_evidence_archive",
        "release_version": RELEASE_VERSION,
        "archive": str(archive_path),
        "archive_bytes": archive_path.stat().st_size,
        "archive_sha256": archive_digest,
        "manifest": str(manifest_path),
        "manifest_sha256": sha256_file(manifest_path),
        "checksum": str(checksum_path),
        "file_count": release_manifest["file_count"],
        "raw_dataset_files_included": False,
        "human_submission_fields_included": False,
        "reproduction_source_included": release_manifest["reproduction_source_included"],
        "independent_bearing_paper_artifact_validation_included": True,
        "independent_empirical_manuscript_validation_included": True,
        "independent_final_local_quality_validation_included": True,
        "preoutcome_raw_prediction_topology_manifest_included": True,
        "independent_raw_prediction_topology_validation_included": True,
        "technical_manuscript_submission_ready": False,
    }


def _sha256_stream(handle: Any) -> str:
    digest = sha256()
    for chunk in iter(lambda: handle.read(4 * 1024 * 1024), b""):
        digest.update(chunk)
    return digest.hexdigest()


def validate_release_archive(
    *,
    archive_path: Path,
    manifest_path: Path,
    checksum_path: Path,
    expected_archive_sha256: str,
    expected_manifest_sha256: str,
) -> dict[str, Any]:
    """Independently verify archive bytes, members, hashes, and normalized metadata."""

    archive_path = archive_path.resolve(strict=True)
    manifest_path = manifest_path.resolve(strict=True)
    checksum_path = checksum_path.resolve(strict=True)
    archive_digest = sha256_file(archive_path)
    manifest_digest = sha256_file(manifest_path)
    if archive_digest != expected_archive_sha256:
        raise ValueError("release archive SHA-256 changed")
    if manifest_digest != expected_manifest_sha256:
        raise ValueError("release manifest SHA-256 changed")
    expected_checksum = f"{archive_digest}  {ARCHIVE_NAME}\n"
    if checksum_path.read_text(encoding="ascii") != expected_checksum:
        raise ValueError("release checksum file does not match the archive")

    manifest_bytes = manifest_path.read_bytes()
    manifest = _json_object(manifest_path)
    if manifest.get("release_version") != RELEASE_VERSION:
        raise ValueError("release manifest version changed")
    if manifest.get("raw_dataset_files_included") is not False:
        raise ValueError("release manifest does not prohibit raw dataset files")
    if manifest.get("human_submission_fields_included") is not False:
        raise ValueError("release manifest does not prohibit human submission fields")
    if manifest.get("deterministic_archive_metadata") is not True:
        raise ValueError("release manifest does not require deterministic metadata")
    if manifest.get("independent_bearing_paper_artifact_validation_included") is not True:
        raise ValueError("release manifest omits bearing paper artifact validation")
    if manifest.get("independent_empirical_manuscript_validation_included") is not True:
        raise ValueError("release manifest omits empirical manuscript validation")
    if manifest.get("independent_final_local_quality_validation_included") is not True:
        raise ValueError("release manifest omits final local quality validation")
    if manifest.get("preoutcome_raw_prediction_topology_manifest_included") is not True:
        raise ValueError("release manifest omits the pre-outcome raw topology manifest")
    if manifest.get("independent_raw_prediction_topology_validation_included") is not True:
        raise ValueError("release manifest omits raw prediction-topology validation")
    if manifest.get("technical_manuscript_submission_ready") is not False:
        raise ValueError("release manifest incorrectly marks the technical manuscript submit-ready")
    files = manifest.get("files")
    if not isinstance(files, list) or not files:
        raise ValueError("release manifest has no file records")
    declared: dict[str, Mapping[str, Any]] = {}
    for item in files:
        if not isinstance(item, Mapping):
            raise ValueError("release manifest file record is not an object")
        relative = str(item.get("path", ""))
        if not relative or relative in declared:
            raise ValueError("release manifest contains an empty or duplicate path")
        if Path(relative).is_absolute() or ".." in Path(relative).parts:
            raise ValueError(f"release member path is unsafe: {relative}")
        if Path(relative).suffix.lower() in RAW_DATA_SUFFIXES:
            raise ValueError(f"release manifest declares prohibited raw data: {relative}")
        if relative == HUMAN_SUBMISSION_FIELDS_PATH:
            raise ValueError("release manifest declares prohibited human submission fields")
        declared[relative] = item
    if int(manifest.get("file_count", -1)) != len(declared):
        raise ValueError("release manifest file count changed")
    if int(manifest.get("total_uncompressed_bytes", -1)) != sum(
        int(item.get("bytes", -1)) for item in declared.values()
    ):
        raise ValueError("release manifest byte total changed")

    expected_names = sorted(
        [
            f"{ARCHIVE_ROOT}/release_manifest.json",
            *(f"{ARCHIVE_ROOT}/{relative}" for relative in declared),
        ]
    )
    verified = 0
    with tarfile.open(archive_path, mode="r:gz") as archive:
        members = archive.getmembers()
        if [member.name for member in members] != expected_names:
            raise ValueError("release archive member set or order changed")
        for member in members:
            if not member.isfile():
                raise ValueError(f"release archive contains a non-file member: {member.name}")
            if (
                member.mtime != 0
                or member.uid != 0
                or member.gid != 0
                or member.uname != ""
                or member.gname != ""
                or member.mode != 0o644
            ):
                raise ValueError(f"release archive metadata is not normalized: {member.name}")
            handle = archive.extractfile(member)
            if handle is None:
                raise ValueError(f"release archive member cannot be read: {member.name}")
            relative = member.name.removeprefix(f"{ARCHIVE_ROOT}/")
            if relative == "release_manifest.json":
                if handle.read() != manifest_bytes:
                    raise ValueError("internal and external release manifests differ")
                continue
            item = declared[relative]
            if member.size != int(item.get("bytes", -1)):
                raise ValueError(f"release member byte count changed: {relative}")
            if _sha256_stream(handle) != str(item.get("sha256", "")):
                raise ValueError(f"release member SHA-256 changed: {relative}")
            verified += 1

    if verified != len(declared):
        raise ValueError("release archive verification count changed")
    return {
        "status": "passed_independent_deterministic_release_validation",
        "release_version": RELEASE_VERSION,
        "archive_sha256": archive_digest,
        "manifest_sha256": manifest_digest,
        "verified_file_count": verified,
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
