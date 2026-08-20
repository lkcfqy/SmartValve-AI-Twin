"""Execute the sealed, single-file Paderborn structure probe without listing archives."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import stat
import subprocess
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from smartvalve.config import project_root
from smartvalve.data.paderborn import paderborn_cache_directory
from smartvalve.data.paderborn_mat import inspect_main_channel_structure
from smartvalve.experiments.prospective_seal import SEAL_VERSION
from smartvalve.experiments.rar_toolchain_validation import (
    UNRAR_BYTES,
    UNRAR_SHA256,
)

PROBE_VERSION = "paderborn-sealed-structure-probe-0.1.0"
AMENDMENT_VERSION = "smartvalve-paderborn-structure-probe-amendment-0.1.0"
PROBE_ARCHIVE = "K001.rar"
PROBE_FILENAME = "N15_M07_F10_K001_1.mat"
PROBE_MEMBER_CANDIDATES = (PROBE_FILENAME, f"K001/{PROBE_FILENAME}")
EXPECTED_SEAL_STATUS = "sealed_pre_d2_ready_for_protocol_governed_structure_probe"
EXPECTED_INITIAL_SCOPE = "single_mat_key_shape_dtype_probe_only"
EXPECTED_AMENDED_SCOPE = "same_single_mat_key_shape_dtype_probe_only"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(4 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _digest_bytes(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _load_and_validate_seal(path: Path, expected_sha256: str) -> dict[str, Any]:
    if _sha256(path) != expected_sha256:
        raise ValueError("prospective seal SHA-256 mismatch")
    seal = json.loads(path.read_text(encoding="utf-8"))
    if seal.get("schema_version") != SEAL_VERSION or seal.get("status") != EXPECTED_SEAL_STATUS:
        raise ValueError("prospective seal does not authorize the structure probe")
    authorization = seal.get("authorization", {})
    if (
        authorization.get("initial_scope") != EXPECTED_INITIAL_SCOPE
        or authorization.get("bulk_extraction_requires_probe_validation") is not True
        or authorization.get("target_outcome_guided_reselection_forbidden") is not True
    ):
        raise ValueError("prospective seal authorization has drifted")
    attestation = seal.get("attestation", {})
    if (
        attestation.get("archive_contents_opened") is not False
        or attestation.get("signal_features_computed") is not False
        or attestation.get("paderborn_model_outcomes_inspected") is not False
    ):
        raise ValueError("prospective seal is not pre-outcome")
    return seal


def _validated_relative_artifact(
    *, root: Path, record: Any, expected_path: str | None = None
) -> Path:
    if not isinstance(record, dict):
        raise ValueError("structure-probe amendment artifact record is missing")
    relative = Path(str(record.get("path", "")))
    if (
        relative.is_absolute()
        or ".." in relative.parts
        or (expected_path is not None and relative.as_posix() != expected_path)
    ):
        raise ValueError("structure-probe amendment artifact path is invalid")
    path = (root / relative).resolve(strict=True)
    if root != path and root not in path.parents:
        raise ValueError("structure-probe amendment artifact escapes the project root")
    if path.stat().st_size != record.get("bytes") or _sha256(path) != record.get(
        "sha256"
    ):
        raise ValueError("structure-probe amendment artifact changed")
    return path


def _load_and_validate_amendment(
    *,
    path: Path,
    expected_sha256: str,
    root: Path,
    prospective_seal: Path,
    prospective_seal_sha256: str,
) -> dict[str, Any]:
    if _sha256(path) != expected_sha256:
        raise ValueError("structure-probe amendment SHA-256 mismatch")
    amendment = json.loads(path.read_text(encoding="utf-8"))
    if (
        amendment.get("schema_version") != AMENDMENT_VERSION
        or amendment.get("status")
        != "authorized_single_same_member_structure_rerun"
    ):
        raise ValueError("structure-probe amendment does not authorize a rerun")

    original_seal = amendment.get("original_seal", {})
    sealed_relative = prospective_seal.relative_to(root).as_posix()
    if original_seal != {
        "path": sealed_relative,
        "sha256": prospective_seal_sha256,
    }:
        raise ValueError("structure-probe amendment references a different seal")

    authorization = amendment.get("authorization", {})
    if (
        authorization.get("scope") != EXPECTED_AMENDED_SCOPE
        or authorization.get("archive") != PROBE_ARCHIVE
        or authorization.get("filename") != PROBE_FILENAME
        or authorization.get("member_candidates") != list(PROBE_MEMBER_CANDIDATES)
        or authorization.get("max_additional_extractions") != 1
        or authorization.get("bulk_extraction_permitted") is not False
        or authorization.get("model_outcome_access_permitted") is not False
    ):
        raise ValueError("structure-probe amendment authorization has drifted")

    attestation = amendment.get("attestation", {})
    if (
        attestation.get("failed_probe_observed_only_length_mismatch") is not True
        or attestation.get("exact_actual_shapes_observed") is not False
        or attestation.get("values_or_statistics_emitted") is not False
        or attestation.get("signal_features_computed") is not False
        or attestation.get("model_outcomes_inspected") is not False
    ):
        raise ValueError("structure-probe amendment attestation has drifted")

    required_artifacts = {
        "amendment_protocol": (
            "research/protocols/paderborn_structure_probe_amendment_v0.1.md"
        ),
        "failed_probe_metadata": (
            "artifacts/research/runs/"
            "EXP-375-PADERBORN-PROBE__20260818T131002.236178Z__"
            "sealed-single-mat-structure-probe/metadata.json"
        ),
        "failed_probe_stderr": (
            "artifacts/research/runs/"
            "EXP-375-PADERBORN-PROBE__20260818T131002.236178Z__"
            "sealed-single-mat-structure-probe/stderr.log"
        ),
        "structure_inspector_source": "src/smartvalve/data/paderborn_mat.py",
        "structure_probe_source": (
            "src/smartvalve/experiments/paderborn_structure_probe.py"
        ),
        "structure_inspector_tests": "tests/test_paderborn_mat.py",
        "structure_probe_tests": "tests/test_paderborn_structure_probe.py",
    }
    records = amendment.get("artifacts", {})
    if set(records) != set(required_artifacts):
        raise ValueError("structure-probe amendment artifact roles have drifted")
    for role, expected_path in required_artifacts.items():
        _validated_relative_artifact(
            root=root, record=records[role], expected_path=expected_path
        )
    return amendment


def _validate_archive_lock(root: Path, seal: dict[str, Any]) -> dict[str, Any]:
    record = seal.get("artifacts", {}).get("paderborn_archive_lock")
    if not isinstance(record, dict):
        raise ValueError("prospective seal has no archive-lock artifact")
    relative = Path(str(record.get("path", "")))
    if relative.is_absolute() or ".." in relative.parts:
        raise ValueError("sealed archive-lock path is not project-relative")
    path = (root / relative).resolve(strict=True)
    if root != path and root not in path.parents:
        raise ValueError("sealed archive-lock path escapes the project root")
    if path.stat().st_size != record.get("bytes") or _sha256(path) != record.get("sha256"):
        raise ValueError("sealed archive-lock artifact changed")
    lock = json.loads(path.read_text(encoding="utf-8"))
    matches = [
        entry
        for entry in lock.get("archives", [])
        if entry.get("filename") == PROBE_ARCHIVE
    ]
    if len(matches) != 1:
        raise ValueError("archive lock does not contain exactly one K001 entry")
    return matches[0]


def _command_record(completed: subprocess.CompletedProcess[str], member: str) -> dict[str, Any]:
    return {
        "member_candidate": member,
        "exit_code": completed.returncode,
        "stdout_bytes": len(completed.stdout.encode("utf-8")),
        "stdout_sha256": _digest_bytes(completed.stdout),
        "stderr_bytes": len(completed.stderr.encode("utf-8")),
        "stderr_sha256": _digest_bytes(completed.stderr),
    }


def extract_exact_probe_member(
    *,
    unrar_binary: Path,
    archive: Path,
    temporary_root: Path,
) -> tuple[Path, str, list[dict[str, Any]]]:
    """Try only two frozen exact paths; never invoke an archive-list command."""

    attempts = []
    for index, member in enumerate(PROBE_MEMBER_CANDIDATES):
        extraction_root = temporary_root / f"attempt-{index}"
        extraction_root.mkdir()
        completed = subprocess.run(
            (
                str(unrar_binary),
                "x",
                "-ep",
                "-idq",
                "-o-",
                "-p-",
                str(archive),
                member,
                f"{extraction_root}{os.sep}",
            ),
            cwd=temporary_root,
            check=False,
            capture_output=True,
            text=True,
            timeout=120,
        )
        attempts.append(_command_record(completed, member))
        entries = list(extraction_root.rglob("*"))
        files = [entry for entry in entries if entry.is_file() or entry.is_symlink()]
        if completed.returncode != 0:
            if files:
                raise ValueError("failed exact-member extraction left unexpected files")
            continue
        if len(files) != 1:
            raise ValueError("exact-member extraction did not yield exactly one file")
        extracted = files[0]
        mode = extracted.lstat().st_mode
        if not stat.S_ISREG(mode) or extracted.name != PROBE_FILENAME:
            raise ValueError("exact-member extraction yielded an unsafe or unexpected entry")
        if extracted.resolve(strict=True).parent != extraction_root.resolve(strict=True):
            raise ValueError("probe extraction escaped the flattened destination")
        return extracted, member, attempts
    raise RuntimeError("neither frozen exact member path resolved in K001.rar")


def run_structure_probe(
    *,
    prospective_seal: Path,
    expected_seal_sha256: str,
    structure_amendment: Path,
    expected_amendment_sha256: str,
    unrar_binary: Path,
    output: Path,
    root: Path | None = None,
    archive_cache: Path | None = None,
) -> dict[str, Any]:
    root = (root or project_root()).resolve()
    prospective_seal = prospective_seal.resolve(strict=True)
    seal = _load_and_validate_seal(prospective_seal, expected_seal_sha256)
    structure_amendment = structure_amendment.resolve(strict=True)
    _load_and_validate_amendment(
        path=structure_amendment,
        expected_sha256=expected_amendment_sha256,
        root=root,
        prospective_seal=prospective_seal,
        prospective_seal_sha256=expected_seal_sha256,
    )
    archive_record = _validate_archive_lock(root, seal)

    unrar_binary = unrar_binary.resolve(strict=True)
    if (
        not unrar_binary.is_file()
        or unrar_binary.stat().st_size != UNRAR_BYTES
        or _sha256(unrar_binary) != UNRAR_SHA256
    ):
        raise ValueError("unrar binary differs from the frozen toolchain")
    archive_cache = (archive_cache or paderborn_cache_directory()).resolve(strict=True)
    archive = (archive_cache / PROBE_ARCHIVE).resolve(strict=True)
    if archive.parent != archive_cache or not archive.is_file():
        raise ValueError("sealed K001 archive is missing from the fixed cache")
    if (
        archive.stat().st_size != int(archive_record["bytes"])
        or _sha256(archive) != archive_record["sha256"]
    ):
        raise ValueError("K001 archive differs from the prospective lock")

    with tempfile.TemporaryDirectory(prefix="smartvalve-paderborn-probe-") as name:
        extracted, selected_member, attempts = extract_exact_probe_member(
            unrar_binary=unrar_binary,
            archive=archive,
            temporary_root=Path(name),
        )
        mat_bytes = extracted.stat().st_size
        mat_sha256 = _sha256(extracted)
        structure = inspect_main_channel_structure(extracted)

    result = {
        "probe_version": PROBE_VERSION,
        "generated_at": datetime.now(UTC).isoformat(),
        "status": "sealed_single_mat_structure_probe_passed",
        "prospective_seal": {
            "path": str(prospective_seal),
            "sha256": expected_seal_sha256,
        },
        "structure_probe_amendment": {
            "path": str(structure_amendment),
            "sha256": expected_amendment_sha256,
            "scope": EXPECTED_AMENDED_SCOPE,
        },
        "archive": {
            "filename": PROBE_ARCHIVE,
            "bytes": archive.stat().st_size,
            "sha256": archive_record["sha256"],
            "members_listed": False,
        },
        "extraction": {
            "candidate_paths": list(PROBE_MEMBER_CANDIDATES),
            "selected_member_path": selected_member,
            "path_flattening_enabled": True,
            "attempts": attempts,
            "extracted_files": 1,
            "temporary_file_retained": False,
        },
        "measurement": {
            "filename": PROBE_FILENAME,
            "bytes": mat_bytes,
            "sha256": mat_sha256,
            "structure": structure,
        },
        "authorization_transition": {
            "initial_scope_consumed": EXPECTED_INITIAL_SCOPE,
            "probe_validation_passed": True,
            "bulk_extraction_now_permitted_by_seal": True,
            "model_outcome_access_permitted": False,
        },
        "access_attestation": {
            "archives_opened": [PROBE_ARCHIVE],
            "archive_members_listed": False,
            "mat_files_extracted": 1,
            "signal_values_loaded_by_mat_reader": True,
            "value_dependent_validation_performed": False,
            "values_or_statistics_emitted": False,
            "signal_features_computed": False,
            "model_outcomes_inspected": False,
        },
    }
    output = output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_suffix(output.suffix + ".tmp")
    temporary.write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    temporary.replace(output)
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--prospective-seal", type=Path, required=True)
    parser.add_argument("--prospective-seal-sha256", required=True)
    parser.add_argument("--structure-amendment", type=Path, required=True)
    parser.add_argument("--structure-amendment-sha256", required=True)
    parser.add_argument("--unrar-binary", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = run_structure_probe(
        prospective_seal=args.prospective_seal,
        expected_seal_sha256=args.prospective_seal_sha256,
        structure_amendment=args.structure_amendment,
        expected_amendment_sha256=args.structure_amendment_sha256,
        unrar_binary=args.unrar_binary,
        output=args.output,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
