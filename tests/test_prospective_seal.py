from __future__ import annotations

import json
from hashlib import sha256
from pathlib import Path

import pytest

from smartvalve.data.paderborn import ARCHIVE_NAMES
from smartvalve.experiments.prospective_seal import (
    EXPECTED_ATTESTATION,
    EXPECTED_STATISTICS,
    METHODS,
    REQUIRED_ARTIFACT_ROLES,
    SEEDS,
    SPEC_VERSION,
    build_prospective_seal,
)


def _digest(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def _write(path: Path, value: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(value, encoding="utf-8")


def _fixture(root: Path) -> tuple[Path, dict[str, object]]:
    _write(root / "src" / "model.py", "VALUE = 1\n")
    _write(root / "tests" / "test_model.py", "def test_value():\n    assert 1 == 1\n")
    _write(root / "research" / "scripts" / "audit.py", "VALUE = 2\n")
    _write(root / "pyproject.toml", "[project]\nname = 'seal-test'\n")
    _write(root / "Makefile", "test:\n\ttrue\n")

    artifact_paths: dict[str, Path] = {}
    for role in sorted(REQUIRED_ARTIFACT_ROLES):
        path = root / "evidence" / f"{role}.txt"
        _write(path, f"immutable evidence for {role}\n")
        artifact_paths[role] = path

    paderborn_protocol = artifact_paths["frozen_paderborn_protocol"]
    selective_protocol = artifact_paths["source_selective_protocol"]
    _write(paderborn_protocol, "# Prospective protocol\n\n- Status: **frozen**\n")
    _write(
        selective_protocol,
        "# Selective protocol — frozen\n\n- Drafted: 2026-08-18\n"
        "- Frozen: 2026-08-18\n- Status: execution authorized\n",
    )

    lock_path = artifact_paths["paderborn_archive_lock"]
    archives = [
        {
            "filename": filename,
            "bytes": index + 1,
            "sha256": sha256(filename.encode("utf-8")).hexdigest(),
        }
        for index, filename in enumerate(ARCHIVE_NAMES)
    ]
    lock = {
        "archive_count": len(archives),
        "total_bytes": sum(item["bytes"] for item in archives),
        "archives": archives,
        "prospective_seal": {
            "archive_contents_opened": False,
            "signal_features_computed": False,
            "model_outcomes_inspected": False,
            "evaluation_protocol_required_before_open": True,
        },
    }
    _write(lock_path, json.dumps(lock))

    artifacts = {
        role: {
            "path": path.relative_to(root).as_posix(),
            "bytes": path.stat().st_size,
            "sha256": _digest(path),
        }
        for role, path in artifact_paths.items()
    }
    spec: dict[str, object] = {
        "schema_version": SPEC_VERSION,
        "decision": {
            "headline_method": "pirl_ratio_v0.2",
            "baseline_method": "erm",
            "development_datasets": ["cranfield", "uci_hydraulic"],
            "prospective_dataset": "paderborn",
            "target_access": "P0",
            "seeds": list(SEEDS),
            "comparison_methods": list(METHODS),
            "selected_configurations": {
                role: f"{role}_frozen_configuration" for role in ("pirl", *METHODS)
            },
        },
        "statistics": EXPECTED_STATISTICS,
        "attestation": EXPECTED_ATTESTATION,
        "artifacts": artifacts,
    }
    spec_path = root / "research" / "protocols" / "final_seal_spec.json"
    _write(spec_path, json.dumps(spec, indent=2))
    return spec_path, spec


def _rewrite_spec(path: Path, spec: dict[str, object]) -> None:
    _write(path, json.dumps(spec, indent=2))


def test_build_prospective_seal_binds_all_inputs_without_archive_access(
    tmp_path: Path,
) -> None:
    spec_path, _ = _fixture(tmp_path)
    output = tmp_path / "outputs" / "final_seal.json"

    seal = build_prospective_seal(spec_path, output, root=tmp_path)

    assert output.is_file()
    assert seal["status"] == "sealed_pre_d2_ready_for_protocol_governed_structure_probe"
    assert len(seal["artifacts"]) == len(REQUIRED_ARTIFACT_ROLES)
    assert seal["paderborn_archive_lock"]["archive_count"] == 32
    assert seal["execution_tree"]["file_count"] == 5
    assert seal["authorization"] == {
        "initial_scope": "single_mat_key_shape_dtype_probe_only",
        "bulk_extraction_requires_probe_validation": True,
        "target_outcome_guided_reselection_forbidden": True,
    }


def test_seal_rejects_digest_drift_or_path_reuse(tmp_path: Path) -> None:
    spec_path, spec = _fixture(tmp_path)
    evidence = tmp_path / str(spec["artifacts"]["pirl_development_metrics"]["path"])
    evidence.write_text("changed after selection\n", encoding="utf-8")
    with pytest.raises(ValueError, match="changed"):
        build_prospective_seal(spec_path, tmp_path / "seal.json", root=tmp_path)

    spec_path, spec = _fixture(tmp_path / "reuse")
    artifacts = spec["artifacts"]
    artifacts["pirl_development_metrics"] = artifacts["pirl_development_predictions"]
    _rewrite_spec(spec_path, spec)
    with pytest.raises(ValueError, match="same path"):
        build_prospective_seal(
            spec_path,
            tmp_path / "reuse" / "seal.json",
            root=tmp_path / "reuse",
        )


def test_seal_rejects_draft_protocol_or_changed_attestation(tmp_path: Path) -> None:
    draft_root = tmp_path / "draft"
    spec_path, spec = _fixture(draft_root)
    record = spec["artifacts"]["frozen_paderborn_protocol"]
    protocol = draft_root / str(record["path"])
    _write(protocol, "# Prospective protocol\n\n- Status: DRAFT, NOT FROZEN\n")
    record["bytes"] = protocol.stat().st_size
    record["sha256"] = _digest(protocol)
    _rewrite_spec(spec_path, spec)
    with pytest.raises(ValueError, match="DRAFT"):
        build_prospective_seal(spec_path, draft_root / "seal.json", root=draft_root)

    attestation_root = tmp_path / "attestation"
    spec_path, spec = _fixture(attestation_root)
    spec["attestation"] = {**EXPECTED_ATTESTATION, "archive_contents_opened": True}
    _rewrite_spec(spec_path, spec)
    with pytest.raises(ValueError, match="attestation"):
        build_prospective_seal(
            spec_path,
            attestation_root / "seal.json",
            root=attestation_root,
        )


def test_seal_rejects_incomplete_roles_and_archive_inventory(tmp_path: Path) -> None:
    role_root = tmp_path / "role"
    spec_path, spec = _fixture(role_root)
    spec["artifacts"].pop("dg_artifact_validation")
    _rewrite_spec(spec_path, spec)
    with pytest.raises(ValueError, match="missing required"):
        build_prospective_seal(spec_path, role_root / "seal.json", root=role_root)

    archive_root = tmp_path / "archive"
    spec_path, spec = _fixture(archive_root)
    record = spec["artifacts"]["paderborn_archive_lock"]
    lock_path = archive_root / str(record["path"])
    lock = json.loads(lock_path.read_text(encoding="utf-8"))
    lock["archives"].pop()
    lock["archive_count"] = len(lock["archives"])
    lock["total_bytes"] = sum(item["bytes"] for item in lock["archives"])
    _write(lock_path, json.dumps(lock))
    record["bytes"] = lock_path.stat().st_size
    record["sha256"] = _digest(lock_path)
    _rewrite_spec(spec_path, spec)
    with pytest.raises(ValueError, match="exactly 32"):
        build_prospective_seal(
            spec_path,
            archive_root / "seal.json",
            root=archive_root,
        )
