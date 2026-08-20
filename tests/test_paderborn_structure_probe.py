from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path

import numpy as np
import pytest
from scipy.io import savemat

from smartvalve.data.paderborn import ARCHIVE_NAMES
from smartvalve.data.paderborn_features import SAMPLES_PER_MAIN_SIGNAL
from smartvalve.experiments.paderborn_structure_probe import (
    AMENDMENT_VERSION,
    run_structure_probe,
)
from smartvalve.experiments.prospective_seal import SEAL_VERSION


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value) + "\n", encoding="utf-8")


def _artifact_record(root: Path, relative: str) -> dict[str, object]:
    path = root / relative
    return {
        "path": relative,
        "bytes": path.stat().st_size,
        "sha256": _sha256(path),
    }


def _synthetic_mat(path: Path) -> None:
    values = np.arange(SAMPLES_PER_MAIN_SIGNAL, dtype=np.float64)
    root = {
        "Y": [
            {"Name": "vibration_1", "Data": values},
            {"Name": "phase_current_1", "Data": values},
            {"Name": "phase_current_2", "Data": values},
        ]
    }
    savemat(path, {path.stem: root})


def _sealed_fixture(tmp_path: Path) -> tuple[Path, Path, Path, Path, Path]:
    root = tmp_path / "root"
    cache = tmp_path / "cache"
    root.mkdir()
    cache.mkdir()
    archive = cache / "K001.rar"
    archive.write_bytes(b"synthetic locked archive")
    entries = []
    for name in ARCHIVE_NAMES:
        if name == "K001.rar":
            byte_count = archive.stat().st_size
            digest = _sha256(archive)
        else:
            byte_count = 1
            digest = "0" * 64
        entries.append({"filename": name, "bytes": byte_count, "sha256": digest})
    lock_path = root / "lock.json"
    _write_json(
        lock_path,
        {
            "archive_count": len(entries),
            "total_bytes": sum(entry["bytes"] for entry in entries),
            "archives": entries,
        },
    )
    source_mat = tmp_path / "N15_M07_F10_K001_1.mat"
    _synthetic_mat(source_mat)
    fake_unrar = tmp_path / "fake-unrar"
    fake_unrar.write_text(
        "#!/usr/bin/env python3\n"
        "import pathlib, shutil, sys\n"
        "member = sys.argv[-2]\n"
        "destination = pathlib.Path(sys.argv[-1])\n"
        "if member.startswith('K001/'):\n"
        "    destination.mkdir(parents=True, exist_ok=True)\n"
        f"    shutil.copyfile({str(source_mat)!r}, destination / {source_mat.name!r})\n"
        "    raise SystemExit(0)\n"
        "raise SystemExit(10)\n",
        encoding="utf-8",
    )
    fake_unrar.chmod(0o755)
    seal_path = root / "seal.json"
    _write_json(
        seal_path,
        {
            "schema_version": SEAL_VERSION,
            "status": "sealed_pre_d2_ready_for_protocol_governed_structure_probe",
            "authorization": {
                "initial_scope": "single_mat_key_shape_dtype_probe_only",
                "bulk_extraction_requires_probe_validation": True,
                "target_outcome_guided_reselection_forbidden": True,
            },
            "attestation": {
                "archive_contents_opened": False,
                "signal_features_computed": False,
                "paderborn_model_outcomes_inspected": False,
            },
            "artifacts": {
                "paderborn_archive_lock": {
                    "path": "lock.json",
                    "bytes": lock_path.stat().st_size,
                    "sha256": _sha256(lock_path),
                }
            },
        },
    )
    artifact_paths = {
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
    for relative in artifact_paths.values():
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(f"frozen fixture for {relative}\n", encoding="utf-8")
    amendment_path = root / "amendment.json"
    _write_json(
        amendment_path,
        {
            "schema_version": AMENDMENT_VERSION,
            "status": "authorized_single_same_member_structure_rerun",
            "original_seal": {
                "path": seal_path.relative_to(root).as_posix(),
                "sha256": _sha256(seal_path),
            },
            "authorization": {
                "scope": "same_single_mat_key_shape_dtype_probe_only",
                "archive": "K001.rar",
                "filename": "N15_M07_F10_K001_1.mat",
                "member_candidates": [
                    "N15_M07_F10_K001_1.mat",
                    "K001/N15_M07_F10_K001_1.mat",
                ],
                "max_additional_extractions": 1,
                "bulk_extraction_permitted": False,
                "model_outcome_access_permitted": False,
            },
            "attestation": {
                "failed_probe_observed_only_length_mismatch": True,
                "exact_actual_shapes_observed": False,
                "values_or_statistics_emitted": False,
                "signal_features_computed": False,
                "model_outcomes_inspected": False,
            },
            "artifacts": {
                role: _artifact_record(root, relative)
                for role, relative in artifact_paths.items()
            },
        },
    )
    return root, cache, fake_unrar, seal_path, amendment_path


def test_sealed_structure_probe_extracts_only_exact_predeclared_mat(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root, cache, fake_unrar, seal_path, amendment_path = _sealed_fixture(tmp_path)
    monkeypatch.setattr(
        "smartvalve.experiments.paderborn_structure_probe.UNRAR_BYTES",
        fake_unrar.stat().st_size,
    )
    monkeypatch.setattr(
        "smartvalve.experiments.paderborn_structure_probe.UNRAR_SHA256",
        _sha256(fake_unrar),
    )

    result = run_structure_probe(
        prospective_seal=seal_path,
        expected_seal_sha256=_sha256(seal_path),
        structure_amendment=amendment_path,
        expected_amendment_sha256=_sha256(amendment_path),
        unrar_binary=fake_unrar,
        output=tmp_path / "probe.json",
        root=root,
        archive_cache=cache,
    )

    assert result["status"] == "sealed_single_mat_structure_probe_passed"
    assert result["archive"]["members_listed"] is False
    assert result["extraction"]["selected_member_path"].startswith("K001/")
    assert [attempt["exit_code"] for attempt in result["extraction"]["attempts"]] == [10, 0]
    assert result["measurement"]["structure"]["values_or_statistics_emitted"] is False
    assert result["access_attestation"]["mat_files_extracted"] == 1
    assert result["access_attestation"]["signal_features_computed"] is False


def test_structure_probe_rejects_seal_hash_drift(tmp_path: Path) -> None:
    root, cache, fake_unrar, seal_path, amendment_path = _sealed_fixture(tmp_path)

    with pytest.raises(ValueError, match="seal SHA-256"):
        run_structure_probe(
            prospective_seal=seal_path,
            expected_seal_sha256="0" * 64,
            structure_amendment=amendment_path,
            expected_amendment_sha256=_sha256(amendment_path),
            unrar_binary=fake_unrar,
            output=tmp_path / "probe.json",
            root=root,
            archive_cache=cache,
        )


def test_structure_probe_rejects_amendment_hash_drift(tmp_path: Path) -> None:
    root, cache, fake_unrar, seal_path, amendment_path = _sealed_fixture(tmp_path)

    with pytest.raises(ValueError, match="amendment SHA-256"):
        run_structure_probe(
            prospective_seal=seal_path,
            expected_seal_sha256=_sha256(seal_path),
            structure_amendment=amendment_path,
            expected_amendment_sha256="0" * 64,
            unrar_binary=fake_unrar,
            output=tmp_path / "probe.json",
            root=root,
            archive_cache=cache,
        )


def test_structure_probe_candidate_paths_are_not_environment_controlled() -> None:
    assert "PADERBORN_MEMBER" not in os.environ
