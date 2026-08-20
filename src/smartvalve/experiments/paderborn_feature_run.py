"""Stream sealed Paderborn archives into the frozen 72-feature representation."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import stat
import subprocess
import tempfile
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from smartvalve.config import project_root
from smartvalve.data.paderborn import (
    ARCHIVE_NAMES,
    BEARING_METADATA,
    OPERATING_SETTINGS,
    paderborn_cache_directory,
)
from smartvalve.data.paderborn_features import (
    MAIN_SIGNAL_CHANNELS,
    MAIN_SIGNAL_ENDPOINT_POLICY,
    MAXIMUM_STORED_SAMPLES_PER_MAIN_SIGNAL,
    MINIMUM_STORED_SAMPLES_PER_MAIN_SIGNAL,
    PADERBORN_SAMPLING_HZ,
    SAMPLES_PER_MAIN_SIGNAL,
    STORED_SAMPLES_PER_MAIN_SIGNAL,
    STRUCTURALLY_EXCLUDED_FILENAMES,
    PaderbornMeasurementKey,
    expected_measurement_filenames,
    main_signal_feature_names,
    measurement_filename,
    parse_measurement_filename,
    retained_measurement_filenames,
)
from smartvalve.data.paderborn_mat import extract_measurement_features_with_length
from smartvalve.experiments.paderborn_domain import (
    build_paderborn_model_folds,
    validate_paderborn_feature_frame,
)
from smartvalve.experiments.paderborn_structure_probe import (
    EXPECTED_AMENDED_SCOPE,
    PROBE_VERSION,
    _load_and_validate_seal,
)
from smartvalve.experiments.rar_toolchain_validation import (
    UNRAR_BYTES,
    UNRAR_SHA256,
)

RUN_VERSION = "paderborn-sealed-streaming-features-0.2.0"
FEATURE_AMENDMENT_VERSION = "smartvalve-paderborn-feature-contract-amendment-0.5.0"
EXPECTED_PROBE_STATUS = "sealed_single_mat_structure_probe_passed"
MAT_FILES_PER_ARCHIVE = len(OPERATING_SETTINGS) * 20


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(4 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _text_digest(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _artifact(path: Path, **counts: int) -> dict[str, Any]:
    return {
        "path": path.name,
        **counts,
        "bytes": path.stat().st_size,
        "sha256": _sha256(path),
    }


def _load_archive_lock(root: Path, seal: dict[str, Any]) -> tuple[Path, dict[str, Any]]:
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
    archives = lock.get("archives")
    if not isinstance(archives, list) or [row.get("filename") for row in archives] != list(
        ARCHIVE_NAMES
    ):
        raise ValueError("archive lock differs from the frozen 32-archive order")
    return path, lock


def _validate_probe(path: Path, expected_sha256: str, expected_seal_sha256: str) -> dict[str, Any]:
    if _sha256(path) != expected_sha256:
        raise ValueError("Paderborn structure-probe SHA-256 mismatch")
    probe = json.loads(path.read_text(encoding="utf-8"))
    if probe.get("probe_version") != PROBE_VERSION or probe.get("status") != EXPECTED_PROBE_STATUS:
        raise ValueError("Paderborn structure probe did not pass the frozen contract")
    if probe.get("prospective_seal", {}).get("sha256") != expected_seal_sha256:
        raise ValueError("Paderborn probe references a different prospective seal")
    if probe.get("structure_probe_amendment", {}).get("scope") != EXPECTED_AMENDED_SCOPE:
        raise ValueError("Paderborn probe does not carry the structure-only amendment")
    transition = probe.get("authorization_transition", {})
    if (
        transition.get("probe_validation_passed") is not True
        or transition.get("bulk_extraction_now_permitted_by_seal") is not True
        or transition.get("model_outcome_access_permitted") is not False
    ):
        raise ValueError("Paderborn probe does not authorize bulk feature extraction")
    access = probe.get("access_attestation", {})
    if (
        access.get("signal_features_computed") is not False
        or access.get("model_outcomes_inspected") is not False
    ):
        raise ValueError("Paderborn probe crossed the frozen access boundary")
    structure = probe.get("measurement", {}).get("structure", {})
    channels = structure.get("channels", {})
    if set(channels) != set(MAIN_SIGNAL_CHANNELS):
        raise ValueError("Paderborn probe has a different main-channel set")
    for channel in MAIN_SIGNAL_CHANNELS:
        metadata = channels[channel]
        if (
            metadata.get("stored_shape") != [STORED_SAMPLES_PER_MAIN_SIGNAL]
            or metadata.get("shape") != [STORED_SAMPLES_PER_MAIN_SIGNAL]
            or metadata.get("samples") != STORED_SAMPLES_PER_MAIN_SIGNAL
            or metadata.get("dtype") != "float64"
        ):
            raise ValueError(f"Paderborn probe structure changed for {channel}")
    return probe


def _validate_amendment_artifact(*, root: Path, record: Any, expected_path: str) -> None:
    if not isinstance(record, dict):
        raise ValueError("feature-contract amendment artifact record is missing")
    relative = Path(str(record.get("path", "")))
    if relative.is_absolute() or ".." in relative.parts or relative.as_posix() != expected_path:
        raise ValueError("feature-contract amendment artifact path is invalid")
    path = (root / relative).resolve(strict=True)
    if root != path and root not in path.parents:
        raise ValueError("feature-contract amendment artifact escapes the project root")
    if path.stat().st_size != record.get("bytes") or _sha256(path) != record.get("sha256"):
        raise ValueError("feature-contract amendment artifact changed")


def _load_and_validate_feature_amendment(
    *,
    path: Path,
    expected_sha256: str,
    root: Path,
    prospective_seal: Path,
    prospective_seal_sha256: str,
    structure_probe: Path,
    structure_probe_sha256: str,
) -> dict[str, Any]:
    if _sha256(path) != expected_sha256:
        raise ValueError("feature-contract amendment SHA-256 mismatch")
    amendment = json.loads(path.read_text(encoding="utf-8"))
    if (
        amendment.get("schema_version") != FEATURE_AMENDMENT_VERSION
        or amendment.get("status") != "authorized_outcome_blind_bulk_feature_extraction"
    ):
        raise ValueError("feature-contract amendment does not authorize extraction")
    if amendment.get("original_seal") != {
        "path": prospective_seal.relative_to(root).as_posix(),
        "sha256": prospective_seal_sha256,
    }:
        raise ValueError("feature-contract amendment references a different seal")
    if amendment.get("structure_probe") != {
        "path": structure_probe.relative_to(root).as_posix(),
        "sha256": structure_probe_sha256,
    }:
        raise ValueError("feature-contract amendment references a different probe")
    if amendment.get("predecessor_amendment") != {
        "path": "research/protocols/paderborn_feature_contract_amendment_v0.4.json",
        "sha256": "fe731f62c37a7730f677d171b36b981590d87ae7307e23116d25074d9ad11a6e",
    }:
        raise ValueError("feature-contract amendment predecessor has drifted")
    if amendment.get("structure_inventory") != {
        "path": (
            "artifacts/research/runs/EXP-400-FULL-STRUCTURE-INVENTORY__"
            "20260818T135002.829285Z__fault-tolerant-2560-mat-shape-dtype-"
            "inventory/outputs/full_structure_inventory.json"
        ),
        "sha256": "da1252d65af1dd99fa3b7cf410317905c62f72668fc0e5f6305c59f208a83895",
    }:
        raise ValueError("feature-contract amendment structure inventory has drifted")
    if amendment.get("structure_inventory_amendment") != {
        "path": "research/protocols/paderborn_structure_inventory_amendment_v0.3.json",
        "sha256": "d59b33bebf439409d08d581530fe5d14ac344f7bf7d4c64219a51dcb582c0bfc",
    }:
        raise ValueError("feature-contract structure-inventory authority has drifted")
    if amendment.get("mat_recovery_probe") != {
        "path": (
            "artifacts/research/runs/EXP-403-MAT-RECOVERY-PROBE__"
            "20260818T135759.607969Z__documented-root-isolation-on-ka08-"
            "failure/outputs/mat_recovery_probe.json"
        ),
        "sha256": "d9e7eebb77ba3647f6e15e2e43ed6cc677a50e2f3e244916f5ffce74e502b437",
    }:
        raise ValueError("feature-contract MAT recovery probe has drifted")
    if amendment.get("mat_recovery_amendment") != {
        "path": "research/protocols/paderborn_mat_recovery_amendment_v0.1.json",
        "sha256": "bba4325a4a835e5471c7c9f46da4548b27240d14bfe125591224d1a3259dc025",
    }:
        raise ValueError("feature-contract MAT recovery authority has drifted")
    contract = amendment.get("feature_contract", {})
    if contract != {
        "channels": list(MAIN_SIGNAL_CHANNELS),
        "sampling_hz": PADERBORN_SAMPLING_HZ,
        "probe_stored_samples_per_channel": STORED_SAMPLES_PER_MAIN_SIGNAL,
        "observed_minimum_stored_samples_per_channel": (MINIMUM_STORED_SAMPLES_PER_MAIN_SIGNAL),
        "observed_maximum_stored_samples_per_channel": (MAXIMUM_STORED_SAMPLES_PER_MAIN_SIGNAL),
        "within_measurement_channel_lengths_must_match": True,
        "retained_samples_per_channel": SAMPLES_PER_MAIN_SIGNAL,
        "endpoint_policy": MAIN_SIGNAL_ENDPOINT_POLICY,
        "feature_count": len(main_signal_feature_names()),
        "structurally_excluded_filenames": list(STRUCTURALLY_EXCLUDED_FILENAMES),
    }:
        raise ValueError("feature-contract amendment changed the endpoint policy")
    authorization = amendment.get("authorization", {})
    if (
        authorization.get("archive_count") != len(ARCHIVE_NAMES)
        or authorization.get("locked_measurement_count") != len(expected_measurement_filenames())
        or authorization.get("retained_measurement_count") != len(retained_measurement_filenames())
        or authorization.get("structurally_excluded_measurement_count")
        != len(STRUCTURALLY_EXCLUDED_FILENAMES)
        or authorization.get("bulk_extraction_permitted") is not True
        or authorization.get("feature_computation_permitted") is not True
        or authorization.get("model_fitting_permitted") is not False
        or authorization.get("model_outcome_access_permitted") is not False
        or authorization.get("target_guided_reselection_permitted") is not False
    ):
        raise ValueError("feature-contract amendment authorization has drifted")
    if amendment.get("non_mat_policy") != {
        "exact_expected_mat_inventory_required": True,
        "regular_non_mat_files": "hash_record_and_quarantine_without_parsing",
        "links_and_special_files": "reject",
        "quarantined_files_may_influence_features_or_models": False,
    }:
        raise ValueError("feature-contract amendment non-MAT policy has drifted")
    attestation = amendment.get("attestation", {})
    if (
        attestation.get("structure_only_information_used_for_final_rule") is not True
        or attestation.get("signal_values_or_statistics_observed") is not False
        or attestation.get("persisted_feature_values_observed") is not False
        or attestation.get("model_outcomes_inspected") is not False
    ):
        raise ValueError("feature-contract amendment attestation has drifted")
    required_artifacts = {
        "amendment_protocol": ("research/protocols/paderborn_feature_contract_amendment_v0.5.md"),
        "structure_probe_metadata": (
            "artifacts/research/runs/"
            "EXP-378-PADERBORN-PROBE-RERUN__20260818T131429.982867Z__"
            "amendment-gated-same-mat-structure-probe/metadata.json"
        ),
        "structure_inventory_metadata": (
            "artifacts/research/runs/"
            "EXP-400-FULL-STRUCTURE-INVENTORY__20260818T135002.829285Z__"
            "fault-tolerant-2560-mat-shape-dtype-inventory/metadata.json"
        ),
        "mat_recovery_probe_metadata": (
            "artifacts/research/runs/"
            "EXP-403-MAT-RECOVERY-PROBE__20260818T135759.607969Z__"
            "documented-root-isolation-on-ka08-failure/metadata.json"
        ),
        "feature_contract_source": "src/smartvalve/data/paderborn_features.py",
        "mat_parser_source": "src/smartvalve/data/paderborn_mat.py",
        "feature_run_source": ("src/smartvalve/experiments/paderborn_feature_run.py"),
        "partition_source": "src/smartvalve/experiments/paderborn_partitions.py",
        "domain_source": "src/smartvalve/experiments/paderborn_domain.py",
        "feature_contract_tests": "tests/test_paderborn_features.py",
        "mat_parser_tests": "tests/test_paderborn_mat.py",
        "feature_run_tests": "tests/test_paderborn_feature_run.py",
        "partition_tests": "tests/test_paderborn_partitions.py",
        "domain_tests": "tests/test_paderborn_domain.py",
    }
    records = amendment.get("artifacts", {})
    if set(records) != set(required_artifacts):
        raise ValueError("feature-contract amendment artifact roles have drifted")
    for role, expected_path in required_artifacts.items():
        _validate_amendment_artifact(root=root, record=records[role], expected_path=expected_path)
    return amendment


@dataclass(frozen=True)
class ValidatedArchive:
    measurements: tuple[Path, ...]
    quarantined_non_mat: tuple[Path, ...]


def expected_filenames_for_bearing(bearing_code: str) -> tuple[str, ...]:
    return tuple(
        measurement_filename(PaderbornMeasurementKey(setting.code, bearing_code, measurement_index))
        for setting in OPERATING_SETTINGS
        for measurement_index in range(1, 21)
    )


def validate_extracted_archive(
    extraction_root: Path,
    bearing_code: str,
    *,
    expected_filenames: tuple[str, ...] | None = None,
) -> ValidatedArchive:
    """Require the exact MAT set and isolate regular non-MAT metadata files."""

    expected = set(expected_filenames or expected_filenames_for_bearing(bearing_code))
    entries = list(extraction_root.rglob("*"))
    for path in entries:
        mode = path.lstat().st_mode
        if stat.S_ISLNK(mode) or (not stat.S_ISDIR(mode) and not stat.S_ISREG(mode)):
            raise ValueError("Paderborn extraction contains a link or special file")
    files = [path for path in entries if path.is_file()]
    mat_files = [path for path in files if path.suffix.casefold() == ".mat"]
    quarantined = [path for path in files if path.suffix.casefold() != ".mat"]
    names = [path.name for path in mat_files]
    if len(names) != len(set(names)) or set(names) != expected:
        raise ValueError("Paderborn archive member inventory differs from the frozen filenames")
    for path in mat_files:
        key = parse_measurement_filename(path.name)
        if key.bearing_code != bearing_code:
            raise ValueError("Paderborn archive contains a measurement for another bearing")
        resolved = path.resolve(strict=True)
        root = extraction_root.resolve(strict=True)
        if root != resolved and root not in resolved.parents:
            raise ValueError("Paderborn archive member escaped the extraction root")
    root = extraction_root.resolve(strict=True)
    for path in quarantined:
        resolved = path.resolve(strict=True)
        if root != resolved and root not in resolved.parents:
            raise ValueError("Paderborn quarantined file escaped the extraction root")
    return ValidatedArchive(
        measurements=tuple(sorted(mat_files, key=lambda path: path.name)),
        quarantined_non_mat=tuple(
            sorted(quarantined, key=lambda path: path.relative_to(extraction_root).as_posix())
        ),
    )


def _extract_archive(
    unrar_binary: Path, archive: Path, destination: Path
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        (
            str(unrar_binary),
            "x",
            "-idq",
            "-o-",
            "-p-",
            str(archive),
            f"{destination}{os.sep}",
        ),
        cwd=destination.parent,
        check=False,
        capture_output=True,
        text=True,
        timeout=900,
    )


def _feature_record(path: Path, *, member_path: str) -> tuple[dict[str, Any], dict[str, Any]]:
    key = parse_measurement_filename(path.name)
    bearing = next(item for item in BEARING_METADATA if item.code == key.bearing_code)
    setting = next(item for item in OPERATING_SETTINGS if item.code == key.setting_code)
    features, stored_samples = extract_measurement_features_with_length(path)
    feature_values = {
        name: float(value)
        for name, value in zip(main_signal_feature_names(), features, strict=True)
    }
    record = {
        "filename": path.name,
        "bearing_code": key.bearing_code,
        "setting_code": key.setting_code,
        "measurement_index": key.measurement_index,
        "truth": bearing.primary_label,
        "damage_origin": bearing.damage_origin,
        "component": bearing.component,
        "damage_extent": bearing.damage_extent,
        "speed_rpm": setting.speed_rpm,
        "torque_nm": setting.torque_nm,
        "radial_force_n": setting.radial_force_n,
        **feature_values,
    }
    inventory = {
        "archive_filename": f"{key.bearing_code}.rar",
        "archive_member_path": member_path,
        "filename": path.name,
        "bytes": path.stat().st_size,
        "sha256": _sha256(path),
        "stored_samples_per_channel": stored_samples,
        "retained_samples_per_channel": SAMPLES_PER_MAIN_SIGNAL,
        "feature_status": "included",
    }
    return record, inventory


def _structural_exclusion_record(path: Path, *, member_path: str) -> dict[str, Any]:
    key = parse_measurement_filename(path.name)
    if path.name not in STRUCTURALLY_EXCLUDED_FILENAMES:
        raise ValueError("unfrozen Paderborn structural exclusion")
    return {
        "archive_filename": f"{key.bearing_code}.rar",
        "archive_member_path": member_path,
        "filename": path.name,
        "bytes": path.stat().st_size,
        "sha256": _sha256(path),
        "stored_samples_per_channel": None,
        "retained_samples_per_channel": None,
        "feature_status": "structurally_excluded_unreadable_mat",
    }


def run_feature_extraction(
    *,
    prospective_seal: Path,
    expected_seal_sha256: str,
    structure_probe: Path,
    expected_structure_probe_sha256: str,
    feature_contract_amendment: Path,
    expected_feature_contract_amendment_sha256: str,
    unrar_binary: Path,
    output_directory: Path,
    root: Path | None = None,
    archive_cache: Path | None = None,
) -> dict[str, Any]:
    root = (root or project_root()).resolve()
    prospective_seal = prospective_seal.resolve(strict=True)
    seal = _load_and_validate_seal(prospective_seal, expected_seal_sha256)
    structure_probe = structure_probe.resolve(strict=True)
    _validate_probe(structure_probe, expected_structure_probe_sha256, expected_seal_sha256)
    feature_contract_amendment = feature_contract_amendment.resolve(strict=True)
    _load_and_validate_feature_amendment(
        path=feature_contract_amendment,
        expected_sha256=expected_feature_contract_amendment_sha256,
        root=root,
        prospective_seal=prospective_seal,
        prospective_seal_sha256=expected_seal_sha256,
        structure_probe=structure_probe,
        structure_probe_sha256=expected_structure_probe_sha256,
    )
    archive_lock_path, archive_lock = _load_archive_lock(root, seal)
    archive_records = {row["filename"]: row for row in archive_lock["archives"]}
    unrar_binary = unrar_binary.resolve(strict=True)
    if (
        not unrar_binary.is_file()
        or unrar_binary.stat().st_size != UNRAR_BYTES
        or _sha256(unrar_binary) != UNRAR_SHA256
    ):
        raise ValueError("unrar binary differs from the frozen toolchain")
    archive_cache = (archive_cache or paderborn_cache_directory()).resolve(strict=True)
    output_directory = output_directory.resolve()
    output_directory.mkdir(parents=True, exist_ok=True)

    features = []
    inventory = []
    quarantined_inventory = []
    extraction_traces = []
    for archive_number, archive_name in enumerate(ARCHIVE_NAMES, start=1):
        bearing_code = archive_name.removesuffix(".rar")
        archive = (archive_cache / archive_name).resolve(strict=True)
        if archive.parent != archive_cache or not archive.is_file():
            raise FileNotFoundError(f"missing locked Paderborn archive: {archive_name}")
        locked = archive_records[archive_name]
        if archive.stat().st_size != locked["bytes"] or _sha256(archive) != locked["sha256"]:
            raise ValueError(f"Paderborn archive differs from lock: {archive_name}")
        with tempfile.TemporaryDirectory(prefix=f"smartvalve-{bearing_code}-") as temporary_name:
            temporary = Path(temporary_name)
            destination = temporary / "extracted"
            destination.mkdir()
            completed = _extract_archive(unrar_binary, archive, destination)
            trace = {
                "archive_filename": archive_name,
                "archive_bytes": archive.stat().st_size,
                "archive_sha256": locked["sha256"],
                "exit_code": completed.returncode,
                "stdout_bytes": len(completed.stdout.encode("utf-8")),
                "stdout_sha256": _text_digest(completed.stdout),
                "stderr_bytes": len(completed.stderr.encode("utf-8")),
                "stderr_sha256": _text_digest(completed.stderr),
            }
            extraction_traces.append(trace)
            if completed.returncode != 0:
                raise RuntimeError(f"unrar extraction failed for {archive_name}")
            validated = validate_extracted_archive(destination, bearing_code)
            paths = validated.measurements
            if len(paths) != MAT_FILES_PER_ARCHIVE:
                raise AssertionError("validated archive has the wrong MAT count")
            for path in paths:
                member_path = path.relative_to(destination).as_posix()
                if path.name in STRUCTURALLY_EXCLUDED_FILENAMES:
                    inventory.append(_structural_exclusion_record(path, member_path=member_path))
                    continue
                record, inventory_record = _feature_record(path, member_path=member_path)
                features.append(record)
                inventory.append(inventory_record)
            for path in validated.quarantined_non_mat:
                quarantined_inventory.append(
                    {
                        "archive_filename": archive_name,
                        "archive_member_path": path.relative_to(destination).as_posix(),
                        "bytes": path.stat().st_size,
                        "sha256": _sha256(path),
                        "handling": "quarantined_not_parsed_not_used",
                    }
                )
        print(
            json.dumps(
                {
                    "event": "paderborn_archive_features_complete",
                    "archive_number": archive_number,
                    "archive_count": len(ARCHIVE_NAMES),
                    "archive_filename": archive_name,
                    "locked_measurement_count": MAT_FILES_PER_ARCHIVE,
                    "retained_measurement_count": sum(
                        name not in STRUCTURALLY_EXCLUDED_FILENAMES
                        for name in expected_filenames_for_bearing(bearing_code)
                    ),
                }
            ),
            flush=True,
        )

    feature_frame = pd.DataFrame(features)
    inventory_frame = pd.DataFrame(inventory)
    all_expected = expected_measurement_filenames()
    retained_expected = retained_measurement_filenames()
    expected_order = {name: index for index, name in enumerate(all_expected)}
    if set(feature_frame["filename"]) != set(retained_expected) or len(feature_frame) != len(
        retained_expected
    ):
        raise ValueError("retained Paderborn features differ from the amended corpus")
    if set(inventory_frame["filename"]) != set(all_expected) or len(inventory_frame) != len(
        all_expected
    ):
        raise ValueError("Paderborn MAT inventory differs from the locked corpus")
    feature_frame["_order"] = feature_frame["filename"].map(expected_order)
    feature_frame = (
        feature_frame.sort_values("_order", kind="stable")
        .drop(columns="_order")
        .reset_index(drop=True)
    )
    inventory_frame["_order"] = inventory_frame["filename"].map(expected_order)
    inventory_frame = (
        inventory_frame.sort_values("_order", kind="stable")
        .drop(columns="_order")
        .reset_index(drop=True)
    )
    included_inventory = inventory_frame.loc[
        inventory_frame["feature_status"] == "included"
    ].reset_index(drop=True)
    if not np.array_equal(feature_frame["filename"], included_inventory["filename"]):
        raise ValueError("Paderborn feature and member inventories are misaligned")
    excluded_inventory = inventory_frame.loc[
        inventory_frame["feature_status"] == "structurally_excluded_unreadable_mat"
    ]
    if tuple(excluded_inventory["filename"]) != STRUCTURALLY_EXCLUDED_FILENAMES:
        raise ValueError("Paderborn structural exclusion inventory has drifted")
    primary = feature_frame.loc[feature_frame["truth"] != "compound"].reset_index(drop=True)
    validate_paderborn_feature_frame(primary)
    model_folds = build_paderborn_model_folds(primary)

    feature_path = output_directory / "feature_matrix.parquet"
    primary_path = output_directory / "primary_feature_matrix.parquet"
    inventory_path = output_directory / "mat_inventory.parquet"
    traces_path = output_directory / "extraction_traces.json"
    quarantined_path = output_directory / "quarantined_non_mat.json"
    feature_frame.to_parquet(feature_path, index=False)
    primary.to_parquet(primary_path, index=False)
    inventory_frame.to_parquet(inventory_path, index=False)
    traces_path.write_text(
        json.dumps(extraction_traces, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    quarantined_path.write_text(
        json.dumps(quarantined_inventory, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    metrics = {
        "run_version": RUN_VERSION,
        "generated_at": datetime.now(UTC).isoformat(),
        "status": "sealed_paderborn_features_complete_without_model_outcome_access",
        "input": {
            "prospective_seal": str(prospective_seal),
            "prospective_seal_sha256": expected_seal_sha256,
            "structure_probe": str(structure_probe),
            "structure_probe_sha256": expected_structure_probe_sha256,
            "feature_contract_amendment": str(feature_contract_amendment),
            "feature_contract_amendment_sha256": (expected_feature_contract_amendment_sha256),
            "archive_lock": str(archive_lock_path),
            "archive_lock_sha256": _sha256(archive_lock_path),
            "unrar_binary": str(unrar_binary),
            "unrar_binary_sha256": _sha256(unrar_binary),
        },
        "corpus": {
            "archive_count": len(ARCHIVE_NAMES),
            "measurement_count": len(feature_frame),
            "locked_mat_count": len(inventory_frame),
            "structurally_excluded_mat_count": len(excluded_inventory),
            "structurally_excluded_filenames": list(STRUCTURALLY_EXCLUDED_FILENAMES),
            "primary_measurement_count": len(primary),
            "compound_measurement_count": int((feature_frame["truth"] == "compound").sum()),
            "feature_count": len(main_signal_feature_names()),
            "model_fold_count": len(model_folds),
            "quarantined_non_mat_count": len(quarantined_inventory),
            "feature_names": list(main_signal_feature_names()),
            "minimum_stored_samples_per_channel": (MINIMUM_STORED_SAMPLES_PER_MAIN_SIGNAL),
            "maximum_stored_samples_per_channel": (MAXIMUM_STORED_SAMPLES_PER_MAIN_SIGNAL),
            "within_measurement_channel_lengths_must_match": True,
            "retained_samples_per_channel": SAMPLES_PER_MAIN_SIGNAL,
            "endpoint_policy": MAIN_SIGNAL_ENDPOINT_POLICY,
            "operating_settings": [asdict(setting) for setting in OPERATING_SETTINGS],
        },
        "artifacts": {
            "feature_matrix": _artifact(feature_path, rows=len(feature_frame)),
            "primary_feature_matrix": _artifact(primary_path, rows=len(primary)),
            "mat_inventory": _artifact(inventory_path, rows=len(inventory_frame)),
            "extraction_traces": _artifact(traces_path, archives=len(extraction_traces)),
            "quarantined_non_mat": _artifact(quarantined_path, files=len(quarantined_inventory)),
        },
        "access_attestation": {
            "archives_opened": len(ARCHIVE_NAMES),
            "archive_members_extracted": len(inventory_frame),
            "feature_measurements_computed": len(feature_frame),
            "structurally_excluded_measurements": len(excluded_inventory),
            "full_signal_values_loaded": True,
            "signal_features_computed": True,
            "model_fitted": False,
            "model_outcomes_inspected": False,
            "target_guided_reselection_performed": False,
            "quarantined_non_mat_files_used": False,
        },
    }
    metrics_path = output_directory / "metrics.json"
    metrics_path.write_text(
        json.dumps(metrics, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return metrics


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--prospective-seal", type=Path, required=True)
    parser.add_argument("--prospective-seal-sha256", required=True)
    parser.add_argument("--structure-probe", type=Path, required=True)
    parser.add_argument("--structure-probe-sha256", required=True)
    parser.add_argument("--feature-contract-amendment", type=Path, required=True)
    parser.add_argument("--feature-contract-amendment-sha256", required=True)
    parser.add_argument("--unrar-binary", type=Path, required=True)
    parser.add_argument("--output-directory", type=Path, required=True)
    args = parser.parse_args()
    result = run_feature_extraction(
        prospective_seal=args.prospective_seal,
        expected_seal_sha256=args.prospective_seal_sha256,
        structure_probe=args.structure_probe,
        expected_structure_probe_sha256=args.structure_probe_sha256,
        feature_contract_amendment=args.feature_contract_amendment,
        expected_feature_contract_amendment_sha256=(args.feature_contract_amendment_sha256),
        unrar_binary=args.unrar_binary,
        output_directory=args.output_directory,
    )
    print(json.dumps(result["corpus"], ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
