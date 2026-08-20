"""Probe two documented, value-blind SciPy recovery paths for one frozen MAT."""

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

from scipy.io import loadmat, whosmat
from scipy.io.matlab import varmats_from_mat

from smartvalve.config import project_root
from smartvalve.data.paderborn import paderborn_cache_directory
from smartvalve.data.paderborn_mat import inspect_named_main_channel_structure
from smartvalve.experiments.paderborn_feature_run import _load_archive_lock
from smartvalve.experiments.paderborn_structure_probe import _load_and_validate_seal
from smartvalve.experiments.rar_toolchain_validation import UNRAR_BYTES, UNRAR_SHA256

PROBE_VERSION = "paderborn-single-mat-root-recovery-probe-0.1.0"
AMENDMENT_VERSION = "smartvalve-paderborn-mat-recovery-amendment-0.1.0"
ARCHIVE_NAME = "KA08.rar"
FILENAME = "N15_M01_F10_KA08_2.mat"
MEMBER_CANDIDATES = (FILENAME, f"KA08/{FILENAME}")
EXPECTED_MAT_BYTES = 8_714_872
EXPECTED_MAT_SHA256 = "e137cbb2368caa8bd56889eff8609d2569d2c196a85107e16aa4740437f2ccb3"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(4 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _validate_amendment(path: Path, expected_sha256: str, root: Path) -> None:
    if _sha256(path) != expected_sha256:
        raise ValueError("MAT-recovery amendment SHA-256 mismatch")
    amendment = json.loads(path.read_text(encoding="utf-8"))
    if (
        amendment.get("schema_version") != AMENDMENT_VERSION
        or amendment.get("status") != "authorized_single_mat_root_recovery_probe"
    ):
        raise ValueError("MAT-recovery amendment does not authorize execution")
    if amendment.get("authorization") != {
        "archive": ARCHIVE_NAME,
        "filename": FILENAME,
        "member_candidates": list(MEMBER_CANDIDATES),
        "expected_bytes": EXPECTED_MAT_BYTES,
        "expected_sha256": EXPECTED_MAT_SHA256,
        "strategies": ["loadmat_variable_names", "varmats_split_root"],
        "signal_values_or_statistics_permitted": False,
        "features_or_model_outcomes_permitted": False,
    }:
        raise ValueError("MAT-recovery amendment authorization has drifted")
    required = {
        "protocol": "research/protocols/paderborn_mat_recovery_amendment_v0.1.md",
        "full_inventory": (
            "artifacts/research/runs/"
            "EXP-400-FULL-STRUCTURE-INVENTORY__20260818T135002.829285Z__"
            "fault-tolerant-2560-mat-shape-dtype-inventory/outputs/"
            "full_structure_inventory.json"
        ),
        "recovery_script": "scripts/paderborn_mat_recovery_probe.py",
        "recovery_tests": "tests/test_paderborn_mat_recovery_probe.py",
    }
    records = amendment.get("artifacts", {})
    if set(records) != set(required):
        raise ValueError("MAT-recovery amendment artifact roles have drifted")
    for role, expected_path in required.items():
        record = records[role]
        relative = Path(str(record.get("path", "")))
        if (
            relative.is_absolute()
            or ".." in relative.parts
            or relative.as_posix() != expected_path
        ):
            raise ValueError("MAT-recovery amendment artifact path is invalid")
        artifact = (root / relative).resolve(strict=True)
        if root != artifact and root not in artifact.parents:
            raise ValueError("MAT-recovery amendment artifact escapes the project root")
        if artifact.stat().st_size != record.get("bytes") or _sha256(
            artifact
        ) != record.get("sha256"):
            raise ValueError("MAT-recovery amendment artifact changed")


def _extract_exact_member(
    *, unrar_binary: Path, archive: Path, temporary: Path
) -> tuple[Path, str, list[dict[str, Any]]]:
    attempts = []
    for index, member in enumerate(MEMBER_CANDIDATES):
        destination = temporary / f"attempt-{index}"
        destination.mkdir()
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
                f"{destination}{os.sep}",
            ),
            cwd=temporary,
            check=False,
            capture_output=True,
            text=True,
            timeout=120,
        )
        attempts.append(
            {
                "member_candidate": member,
                "exit_code": completed.returncode,
                "stdout_bytes": len(completed.stdout.encode()),
                "stderr_bytes": len(completed.stderr.encode()),
            }
        )
        files = [item for item in destination.rglob("*") if item.is_file()]
        if completed.returncode != 0:
            if files:
                raise ValueError("failed recovery extraction left unexpected files")
            continue
        if len(files) != 1:
            raise ValueError("recovery extraction did not yield exactly one file")
        extracted = files[0]
        if (
            not stat.S_ISREG(extracted.lstat().st_mode)
            or extracted.name != FILENAME
            or extracted.resolve(strict=True).parent != destination.resolve(strict=True)
        ):
            raise ValueError("recovery extraction yielded an unsafe entry")
        return extracted, member, attempts
    raise RuntimeError("neither exact recovery member path resolved")


def _root_structure(payload: dict[str, Any]) -> dict[str, Any]:
    roots = {key: value for key, value in payload.items() if not key.startswith("__")}
    stem = Path(FILENAME).stem
    if set(roots) != {stem}:
        raise ValueError("recovery payload does not contain exactly the filename root")
    return {
        "root_key": stem,
        "channels": inspect_named_main_channel_structure(roots[stem]),
        "values_or_statistics_emitted": False,
    }


def load_with_variable_names(path: Path) -> dict[str, Any]:
    payload = loadmat(path, variable_names=[path.stem], simplify_cells=True)
    return _root_structure(payload)


def load_with_split_root(path: Path) -> tuple[dict[str, Any], list[str]]:
    with path.open("rb") as handle:
        variables = varmats_from_mat(handle)
    names = [name for name, _ in variables]
    root_matches = [stream for name, stream in variables if name == path.stem]
    if len(root_matches) != 1:
        raise ValueError("split MAT does not contain exactly one filename root")
    payload = loadmat(root_matches[0], simplify_cells=True)
    return _root_structure(payload), names


def _attempt(name: str, operation: Any) -> tuple[dict[str, Any], dict[str, Any] | None]:
    try:
        result = operation()
    except Exception as error:  # noqa: BLE001 - probe records documented strategies
        return {
            "strategy": name,
            "status": "failed",
            "error_type": type(error).__name__,
            "error_message": str(error),
        }, None
    structure, names = result if isinstance(result, tuple) else (result, None)
    record = {"strategy": name, "status": "passed", "structure": structure}
    if names is not None:
        record["top_level_variable_names"] = names
    return record, structure


def run_probe(
    *,
    prospective_seal: Path,
    prospective_seal_sha256: str,
    recovery_amendment: Path,
    recovery_amendment_sha256: str,
    unrar_binary: Path,
    output: Path,
) -> dict[str, Any]:
    root = project_root().resolve()
    prospective_seal = prospective_seal.resolve(strict=True)
    seal = _load_and_validate_seal(prospective_seal, prospective_seal_sha256)
    recovery_amendment = recovery_amendment.resolve(strict=True)
    _validate_amendment(recovery_amendment, recovery_amendment_sha256, root)
    _, lock = _load_archive_lock(root, seal)
    locked = next(row for row in lock["archives"] if row["filename"] == ARCHIVE_NAME)
    archive = (paderborn_cache_directory() / ARCHIVE_NAME).resolve(strict=True)
    if archive.stat().st_size != locked["bytes"] or _sha256(archive) != locked["sha256"]:
        raise ValueError("KA08 archive differs from the prospective lock")
    unrar_binary = unrar_binary.resolve(strict=True)
    if (
        not unrar_binary.is_file()
        or unrar_binary.stat().st_size != UNRAR_BYTES
        or _sha256(unrar_binary) != UNRAR_SHA256
    ):
        raise ValueError("unrar binary differs from the frozen toolchain")

    with tempfile.TemporaryDirectory(prefix="smartvalve-ka08-recovery-") as name:
        extracted, selected_member, extraction_attempts = _extract_exact_member(
            unrar_binary=unrar_binary,
            archive=archive,
            temporary=Path(name),
        )
        if (
            extracted.stat().st_size != EXPECTED_MAT_BYTES
            or _sha256(extracted) != EXPECTED_MAT_SHA256
        ):
            raise ValueError("recovery MAT differs from the full structural inventory")
        try:
            whos = whosmat(extracted)
            whos_record: dict[str, Any] = {
                "status": "passed",
                "variables": [
                    {"name": item[0], "shape": list(item[1]), "class": item[2]}
                    for item in whos
                ],
            }
        except Exception as error:  # noqa: BLE001 - structural probe records failure
            whos_record = {
                "status": "failed",
                "error_type": type(error).__name__,
                "error_message": str(error),
            }
        attempts = []
        structures = []
        for strategy, operation in (
            ("loadmat_variable_names", lambda: load_with_variable_names(extracted)),
            ("varmats_split_root", lambda: load_with_split_root(extracted)),
        ):
            record, structure = _attempt(strategy, operation)
            attempts.append(record)
            if structure is not None:
                structures.append(structure)

    if len(structures) == 2 and structures[0] != structures[1]:
        raise ValueError("documented recovery strategies produced different structures")
    passed = [record["strategy"] for record in attempts if record["status"] == "passed"]
    result = {
        "probe_version": PROBE_VERSION,
        "generated_at": datetime.now(UTC).isoformat(),
        "status": (
            "single_mat_root_recovery_passed"
            if passed
            else "single_mat_root_recovery_failed"
        ),
        "inputs": {
            "prospective_seal_sha256": prospective_seal_sha256,
            "recovery_amendment_sha256": recovery_amendment_sha256,
            "archive": ARCHIVE_NAME,
            "archive_sha256": locked["sha256"],
            "filename": FILENAME,
            "mat_bytes": EXPECTED_MAT_BYTES,
            "mat_sha256": EXPECTED_MAT_SHA256,
        },
        "extraction": {
            "selected_member": selected_member,
            "attempts": extraction_attempts,
            "temporary_file_retained": False,
        },
        "whosmat": whos_record,
        "strategy_attempts": attempts,
        "passed_strategies": passed,
        "access_attestation": {
            "signal_values_loaded_by_reader": True,
            "signal_values_or_statistics_emitted": False,
            "features_computed": False,
            "model_fitted": False,
            "model_outcomes_inspected": False,
        },
    }
    output = output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary_output = output.with_suffix(output.suffix + ".tmp")
    temporary_output.write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    temporary_output.replace(output)
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--prospective-seal", type=Path, required=True)
    parser.add_argument("--prospective-seal-sha256", required=True)
    parser.add_argument("--recovery-amendment", type=Path, required=True)
    parser.add_argument("--recovery-amendment-sha256", required=True)
    parser.add_argument("--unrar-binary", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = run_probe(
        prospective_seal=args.prospective_seal,
        prospective_seal_sha256=args.prospective_seal_sha256,
        recovery_amendment=args.recovery_amendment,
        recovery_amendment_sha256=args.recovery_amendment_sha256,
        unrar_binary=args.unrar_binary,
        output=args.output,
    )
    print(
        json.dumps(
            {
                "status": result["status"],
                "passed_strategies": result["passed_strategies"],
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
