"""Inventory only keys, shapes, and dtypes in all frozen Paderborn archives."""

from __future__ import annotations

import argparse
import hashlib
import json
import stat
import tempfile
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from smartvalve.config import project_root
from smartvalve.data.paderborn import ARCHIVE_NAMES, paderborn_cache_directory
from smartvalve.data.paderborn_mat import inspect_main_channel_structure
from smartvalve.experiments.paderborn_feature_run import (
    MAT_FILES_PER_ARCHIVE,
    _extract_archive,
    _load_and_validate_feature_amendment,
    _load_archive_lock,
    _validate_probe,
    validate_extracted_archive,
)
from smartvalve.experiments.paderborn_structure_probe import _load_and_validate_seal
from smartvalve.experiments.rar_toolchain_validation import UNRAR_BYTES, UNRAR_SHA256

INVENTORY_VERSION = "paderborn-full-corpus-structure-inventory-0.3.0"
AMENDMENT_VERSION = "smartvalve-paderborn-structure-inventory-amendment-0.3.0"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(4 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _validated_artifact(root: Path, record: Any, expected_path: str) -> None:
    if not isinstance(record, dict):
        raise ValueError("structure-inventory amendment artifact record is missing")
    relative = Path(str(record.get("path", "")))
    if (
        relative.is_absolute()
        or ".." in relative.parts
        or relative.as_posix() != expected_path
    ):
        raise ValueError("structure-inventory amendment artifact path is invalid")
    path = (root / relative).resolve(strict=True)
    if root != path and root not in path.parents:
        raise ValueError("structure-inventory amendment artifact escapes the project root")
    if path.stat().st_size != record.get("bytes") or _sha256(path) != record.get(
        "sha256"
    ):
        raise ValueError("structure-inventory amendment artifact changed")


def validate_inventory_amendment(
    *,
    path: Path,
    expected_sha256: str,
    root: Path,
    prospective_seal: Path,
    prospective_seal_sha256: str,
    structure_probe: Path,
    structure_probe_sha256: str,
    feature_amendment: Path,
    feature_amendment_sha256: str,
) -> dict[str, Any]:
    if _sha256(path) != expected_sha256:
        raise ValueError("structure-inventory amendment SHA-256 mismatch")
    amendment = json.loads(path.read_text(encoding="utf-8"))
    if (
        amendment.get("schema_version") != AMENDMENT_VERSION
        or amendment.get("status") != "authorized_full_corpus_shape_dtype_inventory_only"
    ):
        raise ValueError("structure-inventory amendment does not authorize execution")
    bindings = {
        "original_seal": (prospective_seal, prospective_seal_sha256),
        "structure_probe": (structure_probe, structure_probe_sha256),
        "feature_amendment": (feature_amendment, feature_amendment_sha256),
    }
    for role, (bound_path, bound_sha256) in bindings.items():
        if amendment.get(role) != {
            "path": bound_path.relative_to(root).as_posix(),
            "sha256": bound_sha256,
        }:
            raise ValueError(f"structure-inventory amendment changed {role}")
    authorization = amendment.get("authorization", {})
    if authorization != {
        "archive_count": len(ARCHIVE_NAMES),
        "expected_mat_count": len(ARCHIVE_NAMES) * MAT_FILES_PER_ARCHIVE,
        "emitted_fields": [
            "archive",
            "filename",
            "member_path",
            "bytes",
            "sha256",
            "root_key",
            "semantic_name",
            "semantic_path",
            "stored_shape",
            "shape",
            "dtype",
            "samples",
            "structure_status",
            "error_type",
            "error_message",
        ],
        "signal_values_or_statistics_permitted": False,
        "feature_computation_permitted": False,
        "model_fitting_or_outcomes_permitted": False,
    }:
        raise ValueError("structure-inventory authorization has drifted")
    required = {
        "protocol": (
            "research/protocols/paderborn_structure_inventory_amendment_v0.3.md"
        ),
        "failed_bulk_metadata": (
            "artifacts/research/runs/"
            "EXP-397-FULL-STRUCTURE-INVENTORY__20260818T134608.145907Z__"
            "amendment-gated-2560-mat-shape-dtype-inventory/metadata.json"
        ),
        "failed_bulk_stderr": (
            "artifacts/research/runs/"
            "EXP-397-FULL-STRUCTURE-INVENTORY__20260818T134608.145907Z__"
            "amendment-gated-2560-mat-shape-dtype-inventory/stderr.log"
        ),
        "inventory_script": "scripts/paderborn_archive_structure_inventory.py",
        "inventory_tests": "tests/test_paderborn_archive_structure_inventory.py",
    }
    records = amendment.get("artifacts", {})
    if set(records) != set(required):
        raise ValueError("structure-inventory amendment artifact roles have drifted")
    for role, expected_path in required.items():
        _validated_artifact(root, records[role], expected_path)
    return amendment


def structure_signature(structure: dict[str, Any]) -> str:
    channels = structure["channels"]
    signature = [
        {
            "channel": channel,
            "shape": channels[channel]["shape"],
            "dtype": channels[channel]["dtype"],
            "samples": channels[channel]["samples"],
        }
        for channel in sorted(channels)
    ]
    return json.dumps(signature, sort_keys=True, separators=(",", ":"))


def summarize_signatures(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    counts = Counter(
        record["structure_signature"]
        for record in records
        if record["structure_status"] == "parsed"
    )
    return [
        {"structure_signature": signature, "measurement_count": count}
        for signature, count in sorted(counts.items())
    ]


def run_inventory(
    *,
    prospective_seal: Path,
    prospective_seal_sha256: str,
    structure_probe: Path,
    structure_probe_sha256: str,
    feature_amendment: Path,
    feature_amendment_sha256: str,
    inventory_amendment: Path,
    inventory_amendment_sha256: str,
    unrar_binary: Path,
    output: Path,
) -> dict[str, Any]:
    root = project_root().resolve()
    prospective_seal = prospective_seal.resolve(strict=True)
    structure_probe = structure_probe.resolve(strict=True)
    feature_amendment = feature_amendment.resolve(strict=True)
    inventory_amendment = inventory_amendment.resolve(strict=True)
    seal = _load_and_validate_seal(prospective_seal, prospective_seal_sha256)
    _validate_probe(structure_probe, structure_probe_sha256, prospective_seal_sha256)
    _load_and_validate_feature_amendment(
        path=feature_amendment,
        expected_sha256=feature_amendment_sha256,
        root=root,
        prospective_seal=prospective_seal,
        prospective_seal_sha256=prospective_seal_sha256,
        structure_probe=structure_probe,
        structure_probe_sha256=structure_probe_sha256,
    )
    validate_inventory_amendment(
        path=inventory_amendment,
        expected_sha256=inventory_amendment_sha256,
        root=root,
        prospective_seal=prospective_seal,
        prospective_seal_sha256=prospective_seal_sha256,
        structure_probe=structure_probe,
        structure_probe_sha256=structure_probe_sha256,
        feature_amendment=feature_amendment,
        feature_amendment_sha256=feature_amendment_sha256,
    )
    _, archive_lock = _load_archive_lock(root, seal)
    archive_records = {row["filename"]: row for row in archive_lock["archives"]}
    unrar_binary = unrar_binary.resolve(strict=True)
    if (
        not unrar_binary.is_file()
        or unrar_binary.stat().st_size != UNRAR_BYTES
        or _sha256(unrar_binary) != UNRAR_SHA256
    ):
        raise ValueError("unrar binary differs from the frozen toolchain")

    records: list[dict[str, Any]] = []
    quarantined: list[dict[str, Any]] = []
    archive_cache = paderborn_cache_directory().resolve(strict=True)
    for archive_number, archive_name in enumerate(ARCHIVE_NAMES, start=1):
        bearing_code = archive_name.removesuffix(".rar")
        locked = archive_records[archive_name]
        archive = (archive_cache / archive_name).resolve(strict=True)
        if (
            archive.parent != archive_cache
            or archive.stat().st_size != locked["bytes"]
            or _sha256(archive) != locked["sha256"]
        ):
            raise ValueError(f"{archive_name} differs from the prospective lock")
        with tempfile.TemporaryDirectory(
            prefix=f"smartvalve-{bearing_code}-structure-"
        ) as name:
            temporary = Path(name)
            destination = temporary / "extracted"
            destination.mkdir()
            completed = _extract_archive(unrar_binary, archive, destination)
            if completed.returncode != 0:
                raise RuntimeError(
                    f"unrar extraction failed for {archive_name} structure inventory"
                )
            validated = validate_extracted_archive(destination, bearing_code)
            if len(validated.measurements) != MAT_FILES_PER_ARCHIVE:
                raise AssertionError(
                    f"{archive_name} structure inventory has the wrong MAT count"
                )
            for measurement in validated.measurements:
                base_record = {
                    "archive": archive_name,
                    "filename": measurement.name,
                    "member_path": measurement.relative_to(destination).as_posix(),
                    "bytes": measurement.stat().st_size,
                    "sha256": _sha256(measurement),
                }
                try:
                    structure = inspect_main_channel_structure(measurement)
                except Exception as error:  # noqa: BLE001 - inventory must continue
                    records.append(
                        {
                            **base_record,
                            "structure_status": "parse_failed",
                            "error_type": type(error).__name__,
                            "error_message": str(error),
                        }
                    )
                else:
                    records.append(
                        {
                            **base_record,
                            "structure_status": "parsed",
                            "root_key": structure["root_key"],
                            "channels": structure["channels"],
                            "structure_signature": structure_signature(structure),
                        }
                    )
            for item in validated.quarantined_non_mat:
                mode = item.lstat().st_mode
                if not stat.S_ISREG(mode):
                    raise ValueError(
                        f"{archive_name} quarantine contains a non-regular file"
                    )
                quarantined.append(
                    {
                        "archive": archive_name,
                        "member_path": item.relative_to(destination).as_posix(),
                        "bytes": item.stat().st_size,
                        "sha256": _sha256(item),
                        "handling": "quarantined_not_parsed_not_used",
                    }
                )
        print(
            json.dumps(
                {
                    "event": "paderborn_archive_structure_complete",
                    "archive_number": archive_number,
                    "archive_count": len(ARCHIVE_NAMES),
                    "archive_filename": archive_name,
                    "measurement_count": MAT_FILES_PER_ARCHIVE,
                }
            ),
            flush=True,
        )

    if len(records) != len(ARCHIVE_NAMES) * MAT_FILES_PER_ARCHIVE:
        raise AssertionError("full structure inventory has the wrong MAT count")

    result = {
        "inventory_version": INVENTORY_VERSION,
        "generated_at": datetime.now(UTC).isoformat(),
        "status": "full_corpus_shape_dtype_inventory_complete_without_features_or_models",
        "inputs": {
            "prospective_seal_sha256": prospective_seal_sha256,
            "structure_probe_sha256": structure_probe_sha256,
            "feature_amendment_sha256": feature_amendment_sha256,
            "inventory_amendment_sha256": inventory_amendment_sha256,
            "archive_count": len(ARCHIVE_NAMES),
            "archive_lock_total_bytes": archive_lock["total_bytes"],
        },
        "measurement_count": len(records),
        "parsed_measurement_count": sum(
            record["structure_status"] == "parsed" for record in records
        ),
        "parse_failed_measurement_count": sum(
            record["structure_status"] == "parse_failed" for record in records
        ),
        "structure_signatures": summarize_signatures(records),
        "measurements": records,
        "quarantined_non_mat": quarantined,
        "access_attestation": {
            "archive_members_listed_by_unrar": False,
            "mat_values_loaded_by_reader": True,
            "signal_values_or_value_statistics_emitted": False,
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
    parser.add_argument("--structure-probe", type=Path, required=True)
    parser.add_argument("--structure-probe-sha256", required=True)
    parser.add_argument("--feature-amendment", type=Path, required=True)
    parser.add_argument("--feature-amendment-sha256", required=True)
    parser.add_argument("--inventory-amendment", type=Path, required=True)
    parser.add_argument("--inventory-amendment-sha256", required=True)
    parser.add_argument("--unrar-binary", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = run_inventory(
        prospective_seal=args.prospective_seal,
        prospective_seal_sha256=args.prospective_seal_sha256,
        structure_probe=args.structure_probe,
        structure_probe_sha256=args.structure_probe_sha256,
        feature_amendment=args.feature_amendment,
        feature_amendment_sha256=args.feature_amendment_sha256,
        inventory_amendment=args.inventory_amendment,
        inventory_amendment_sha256=args.inventory_amendment_sha256,
        unrar_binary=args.unrar_binary,
        output=args.output,
    )
    print(
        json.dumps(
            {
                "status": result["status"],
                "archive_count": result["inputs"]["archive_count"],
                "measurement_count": result["measurement_count"],
                "parsed_measurement_count": result["parsed_measurement_count"],
                "parse_failed_measurement_count": result[
                    "parse_failed_measurement_count"
                ],
                "structure_signatures": result["structure_signatures"],
                "quarantined_non_mat_count": len(result["quarantined_non_mat"]),
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
