from __future__ import annotations

import json
from pathlib import Path

import pytest

from smartvalve.data.paderborn import ARCHIVE_NAMES
from smartvalve.data.paderborn_features import (
    MAIN_SIGNAL_CHANNELS,
    MAIN_SIGNAL_ENDPOINT_POLICY,
    MAXIMUM_STORED_SAMPLES_PER_MAIN_SIGNAL,
    MINIMUM_STORED_SAMPLES_PER_MAIN_SIGNAL,
    PADERBORN_SAMPLING_HZ,
    SAMPLES_PER_MAIN_SIGNAL,
    STORED_SAMPLES_PER_MAIN_SIGNAL,
    STRUCTURALLY_EXCLUDED_FILENAMES,
    expected_measurement_filenames,
    main_signal_feature_names,
    retained_measurement_filenames,
)
from smartvalve.experiments.paderborn_feature_run import (
    FEATURE_AMENDMENT_VERSION,
    _load_and_validate_feature_amendment,
    _structural_exclusion_record,
    _validate_probe,
    validate_extracted_archive,
)
from smartvalve.experiments.paderborn_structure_probe import (
    EXPECTED_AMENDED_SCOPE,
    PROBE_VERSION,
)


def _sha256(path: Path) -> str:
    import hashlib

    return hashlib.sha256(path.read_bytes()).hexdigest()


def _artifact_record(root: Path, relative: str) -> dict[str, object]:
    path = root / relative
    return {
        "path": relative,
        "bytes": path.stat().st_size,
        "sha256": _sha256(path),
    }


def test_extracted_archive_accepts_exact_nested_mat_inventory(tmp_path: Path) -> None:
    root = tmp_path / "extracted"
    nested = root / "K001" / "nested"
    nested.mkdir(parents=True)
    expected = (
        "N15_M07_F10_K001_1.mat",
        "N15_M07_F10_K001_2.mat",
    )
    for name in expected:
        (nested / name).write_bytes(b"synthetic")

    observed = validate_extracted_archive(root, "K001", expected_filenames=expected)

    assert [path.name for path in observed.measurements] == list(expected)
    assert observed.quarantined_non_mat == ()


def test_extracted_archive_quarantines_non_mat_and_rejects_wrong_bearing(
    tmp_path: Path,
) -> None:
    root = tmp_path / "extracted"
    root.mkdir()
    expected = ("N15_M07_F10_K001_1.mat",)
    (root / expected[0]).write_bytes(b"synthetic")
    (root / "readme.txt").write_text("extra", encoding="utf-8")
    observed = validate_extracted_archive(root, "K001", expected_filenames=expected)

    assert [path.name for path in observed.measurements] == list(expected)
    assert [path.name for path in observed.quarantined_non_mat] == ["readme.txt"]

    (root / "readme.txt").unlink()
    wrong = "N15_M07_F10_K002_1.mat"
    with pytest.raises(ValueError, match="inventory differs"):
        validate_extracted_archive(root, "K001", expected_filenames=(wrong,))


def test_structural_exclusion_is_exact_and_hash_audited(tmp_path: Path) -> None:
    excluded = tmp_path / STRUCTURALLY_EXCLUDED_FILENAMES[0]
    excluded.write_bytes(b"locked malformed MAT fixture")

    record = _structural_exclusion_record(excluded, member_path=f"KA08/{excluded.name}")

    assert record["filename"] == excluded.name
    assert record["bytes"] == excluded.stat().st_size
    assert record["sha256"] == _sha256(excluded)
    assert record["stored_samples_per_channel"] is None
    assert record["feature_status"] == "structurally_excluded_unreadable_mat"

    unexpected = tmp_path / "N15_M01_F10_KA08_3.mat"
    unexpected.write_bytes(b"synthetic")
    with pytest.raises(ValueError, match="unfrozen"):
        _structural_exclusion_record(unexpected, member_path=unexpected.name)


def test_bulk_feature_gate_requires_matching_successful_probe(tmp_path: Path) -> None:
    probe = tmp_path / "probe.json"
    seal_sha256 = "a" * 64
    probe.write_text(
        json.dumps(
            {
                "probe_version": PROBE_VERSION,
                "status": "sealed_single_mat_structure_probe_passed",
                "prospective_seal": {"sha256": seal_sha256},
                "structure_probe_amendment": {
                    "scope": EXPECTED_AMENDED_SCOPE,
                },
                "measurement": {
                    "structure": {
                        "channels": {
                            channel: {
                                "stored_shape": [STORED_SAMPLES_PER_MAIN_SIGNAL],
                                "shape": [STORED_SAMPLES_PER_MAIN_SIGNAL],
                                "samples": STORED_SAMPLES_PER_MAIN_SIGNAL,
                                "dtype": "float64",
                            }
                            for channel in MAIN_SIGNAL_CHANNELS
                        }
                    }
                },
                "authorization_transition": {
                    "probe_validation_passed": True,
                    "bulk_extraction_now_permitted_by_seal": True,
                    "model_outcome_access_permitted": False,
                },
                "access_attestation": {
                    "signal_features_computed": False,
                    "model_outcomes_inspected": False,
                },
            }
        )
        + "\n",
        encoding="utf-8",
    )

    result = _validate_probe(probe, _sha256(probe), seal_sha256)

    assert result["authorization_transition"]["bulk_extraction_now_permitted_by_seal"] is True
    with pytest.raises(ValueError, match="different prospective seal"):
        _validate_probe(probe, _sha256(probe), "b" * 64)


def test_feature_amendment_binds_probe_policy_and_revised_artifacts(
    tmp_path: Path,
) -> None:
    root = tmp_path / "root"
    root.mkdir()
    seal = root / "seal.json"
    probe = root / "probe.json"
    seal.write_text("sealed\n", encoding="utf-8")
    probe.write_text("probed\n", encoding="utf-8")
    predecessor = root / "research/protocols/paderborn_feature_contract_amendment_v0.4.json"
    predecessor.parent.mkdir(parents=True, exist_ok=True)
    predecessor.write_text("predecessor\n", encoding="utf-8")
    artifact_paths = {
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
    for relative in artifact_paths.values():
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(f"frozen fixture for {relative}\n", encoding="utf-8")
    amendment = root / "amendment.json"
    amendment.write_text(
        json.dumps(
            {
                "schema_version": FEATURE_AMENDMENT_VERSION,
                "status": "authorized_outcome_blind_bulk_feature_extraction",
                "original_seal": {
                    "path": seal.relative_to(root).as_posix(),
                    "sha256": _sha256(seal),
                },
                "structure_probe": {
                    "path": probe.relative_to(root).as_posix(),
                    "sha256": _sha256(probe),
                },
                "predecessor_amendment": {
                    "path": predecessor.relative_to(root).as_posix(),
                    "sha256": ("fe731f62c37a7730f677d171b36b981590d87ae7307e23116d25074d9ad11a6e"),
                },
                "structure_inventory": {
                    "path": (
                        "artifacts/research/runs/EXP-400-FULL-STRUCTURE-INVENTORY__"
                        "20260818T135002.829285Z__fault-tolerant-2560-mat-"
                        "shape-dtype-inventory/outputs/full_structure_inventory.json"
                    ),
                    "sha256": ("da1252d65af1dd99fa3b7cf410317905c62f72668fc0e5f6305c59f208a83895"),
                },
                "structure_inventory_amendment": {
                    "path": (
                        "research/protocols/paderborn_structure_inventory_amendment_v0.3.json"
                    ),
                    "sha256": ("d59b33bebf439409d08d581530fe5d14ac344f7bf7d4c64219a51dcb582c0bfc"),
                },
                "mat_recovery_probe": {
                    "path": (
                        "artifacts/research/runs/EXP-403-MAT-RECOVERY-PROBE__"
                        "20260818T135759.607969Z__documented-root-isolation-on-"
                        "ka08-failure/outputs/mat_recovery_probe.json"
                    ),
                    "sha256": ("d9e7eebb77ba3647f6e15e2e43ed6cc677a50e2f3e244916f5ffce74e502b437"),
                },
                "mat_recovery_amendment": {
                    "path": ("research/protocols/paderborn_mat_recovery_amendment_v0.1.json"),
                    "sha256": ("bba4325a4a835e5471c7c9f46da4548b27240d14bfe125591224d1a3259dc025"),
                },
                "feature_contract": {
                    "channels": list(MAIN_SIGNAL_CHANNELS),
                    "sampling_hz": PADERBORN_SAMPLING_HZ,
                    "probe_stored_samples_per_channel": (STORED_SAMPLES_PER_MAIN_SIGNAL),
                    "observed_minimum_stored_samples_per_channel": (
                        MINIMUM_STORED_SAMPLES_PER_MAIN_SIGNAL
                    ),
                    "observed_maximum_stored_samples_per_channel": (
                        MAXIMUM_STORED_SAMPLES_PER_MAIN_SIGNAL
                    ),
                    "within_measurement_channel_lengths_must_match": True,
                    "retained_samples_per_channel": SAMPLES_PER_MAIN_SIGNAL,
                    "endpoint_policy": MAIN_SIGNAL_ENDPOINT_POLICY,
                    "feature_count": len(main_signal_feature_names()),
                    "structurally_excluded_filenames": list(STRUCTURALLY_EXCLUDED_FILENAMES),
                },
                "authorization": {
                    "archive_count": len(ARCHIVE_NAMES),
                    "locked_measurement_count": len(expected_measurement_filenames()),
                    "retained_measurement_count": len(retained_measurement_filenames()),
                    "structurally_excluded_measurement_count": len(STRUCTURALLY_EXCLUDED_FILENAMES),
                    "bulk_extraction_permitted": True,
                    "feature_computation_permitted": True,
                    "model_fitting_permitted": False,
                    "model_outcome_access_permitted": False,
                    "target_guided_reselection_permitted": False,
                },
                "non_mat_policy": {
                    "exact_expected_mat_inventory_required": True,
                    "regular_non_mat_files": ("hash_record_and_quarantine_without_parsing"),
                    "links_and_special_files": "reject",
                    "quarantined_files_may_influence_features_or_models": False,
                },
                "attestation": {
                    "structure_only_information_used_for_final_rule": True,
                    "signal_values_or_statistics_observed": False,
                    "persisted_feature_values_observed": False,
                    "model_outcomes_inspected": False,
                },
                "artifacts": {
                    role: _artifact_record(root, relative)
                    for role, relative in artifact_paths.items()
                },
            }
        )
        + "\n",
        encoding="utf-8",
    )

    result = _load_and_validate_feature_amendment(
        path=amendment,
        expected_sha256=_sha256(amendment),
        root=root,
        prospective_seal=seal,
        prospective_seal_sha256=_sha256(seal),
        structure_probe=probe,
        structure_probe_sha256=_sha256(probe),
    )

    assert result["feature_contract"]["endpoint_policy"] == MAIN_SIGNAL_ENDPOINT_POLICY
