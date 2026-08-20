from __future__ import annotations

import json
from hashlib import sha256
from pathlib import Path

import pytest

from smartvalve.experiments.paderborn_execution_seal import (
    EXPECTED_ATTESTATION,
    EXPECTED_TOPOLOGY,
    REQUIRED_ARTIFACT_ROLES,
    SPEC_VERSION,
    build_paderborn_execution_seal,
)
from smartvalve.experiments.prospective_seal import (
    EXPECTED_STATISTICS,
    METHODS,
    SEEDS,
)


def _digest(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def _write(path: Path, value: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(value, encoding="utf-8")


def _decision() -> dict[str, object]:
    return {
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
    }


def _fixture(root: Path) -> tuple[Path, dict[str, object]]:
    _write(root / "src" / "dummy.py", "VALUE = 1\n")
    _write(root / "tests" / "test_dummy.py", "def test_dummy():\n    assert True\n")
    _write(root / "research" / "scripts" / "dummy.py", "VALUE = 2\n")
    _write(root / "pyproject.toml", "[project]\nname='fixture'\n")
    _write(root / "Makefile", "test:\n\ttrue\n")
    paths = {}
    for role in REQUIRED_ARTIFACT_ROLES:
        path = root / "evidence" / f"{role}.txt"
        _write(path, f"fixture for {role}\n")
        paths[role] = path

    decision = _decision()
    _write(
        paths["original_prospective_seal"],
        json.dumps(
            {
                "schema_version": "smartvalve-prospective-seal-0.1.0",
                "status": "sealed_pre_d2_ready_for_protocol_governed_structure_probe",
                "decision": decision,
                "statistics": EXPECTED_STATISTICS,
            }
        ),
    )
    _write(
        paths["execution_amendment_protocol"],
        "# D2 amendment\n\n- Status: frozen before model outcomes\n",
    )
    _write(
        paths["feature_contract_amendment"],
        json.dumps(
            {
                "schema_version": ("smartvalve-paderborn-feature-contract-amendment-0.5.0"),
                "status": "authorized_outcome_blind_bulk_feature_extraction",
            }
        ),
    )
    _write(
        paths["feature_metrics"],
        json.dumps(
            {
                "status": ("sealed_paderborn_features_complete_without_model_outcome_access"),
                "input": {
                    "feature_contract_amendment_sha256": _digest(
                        paths["feature_contract_amendment"]
                    )
                },
                "access_attestation": {
                    "model_fitted": False,
                    "model_outcomes_inspected": False,
                },
            }
        ),
    )
    _write(
        paths["feature_validation"],
        json.dumps(
            {
                "status": "passed_before_paderborn_model_outcome_access",
                "input": {"feature_metrics_sha256": _digest(paths["feature_metrics"])},
                "access_attestation": {
                    "model_fitted": False,
                    "model_outcomes_inspected": False,
                },
            }
        ),
    )
    _write(
        paths["amended_split_manifest"],
        json.dumps(
            {
                "schema_version": "smartvalve-paderborn-split-manifest-0.2.0",
                "seal": {
                    "signal_features_used_to_define_partitions": False,
                    "model_outcomes_inspected": False,
                },
            }
        ),
    )
    _write(
        paths["amended_model_fold_manifest"],
        json.dumps(
            {
                "manifest_version": "paderborn-model-fold-schema-0.2.0",
                "all_measurements_target_exactly_once": True,
                "pure_measurements": 2319,
                "signal_features_used_to_define_folds": False,
                "model_outcomes_inspected": False,
            }
        ),
    )
    expected_input = {
        field: str(paths[role])
        for field, role in {
            "protocol_document": "execution_amendment_protocol",
            "split_manifest": "amended_split_manifest",
            "model_fold_manifest": "amended_model_fold_manifest",
            "feature_contract_amendment": "feature_contract_amendment",
            "feature_validation": "feature_validation",
        }.items()
    }
    for field, role in {
        "protocol_document": "execution_amendment_protocol",
        "split_manifest": "amended_split_manifest",
        "model_fold_manifest": "amended_model_fold_manifest",
        "feature_contract_amendment": "feature_contract_amendment",
        "feature_validation": "feature_validation",
    }.items():
        expected_input[f"{field}_sha256"] = _digest(paths[role])
    expected_input.update(
        {
            "signal_features_used_to_define_topology": False,
            "model_outcomes_inspected_before_manifest": False,
        }
    )
    _write(
        paths["amended_expected_manifest"],
        json.dumps(
            {
                "manifest_version": ("paderborn-prospective-expected-key-manifest-0.2.0"),
                "input": expected_input,
                "expected_key_sets": {
                    "training_models": {"count": 1080},
                    "target_predictions": {"count": 104355},
                    "compound_predictions": {"count": 259200},
                },
            }
        ),
    )
    _write(
        paths["amended_selective_expected_manifest"],
        json.dumps(
            {
                "manifest_version": ("paderborn-selective-expected-key-manifest-0.2.0"),
                "input": {
                    "base_expected_manifest_sha256": _digest(paths["amended_expected_manifest"])
                },
                "expected_key_sets": {
                    "training_models": {"count": 720},
                    "source_oof_predictions": {"count": 347850},
                    "target_predictions": {"count": 23190},
                    "compound_decisions": {"count": 1382400},
                },
            }
        ),
    )

    artifacts = {
        role: {
            "path": path.relative_to(root).as_posix(),
            "bytes": path.stat().st_size,
            "sha256": _digest(path),
        }
        for role, path in paths.items()
    }
    spec: dict[str, object] = {
        "schema_version": SPEC_VERSION,
        "decision": decision,
        "statistics": EXPECTED_STATISTICS,
        "topology": EXPECTED_TOPOLOGY,
        "attestation": EXPECTED_ATTESTATION,
        "artifacts": artifacts,
    }
    spec_path = root / "research" / "protocols" / "execution_seal_spec.json"
    _write(spec_path, json.dumps(spec, indent=2))
    return spec_path, spec


def test_execution_seal_binds_amended_topology_before_model_outcomes(
    tmp_path: Path,
) -> None:
    spec_path, _ = _fixture(tmp_path)
    output = tmp_path / "outputs" / "execution_seal.json"

    seal = build_paderborn_execution_seal(spec_path=spec_path, output_path=output, root=tmp_path)

    assert output.is_file()
    assert seal["status"] == "sealed_after_features_before_paderborn_model_outcomes"
    assert len(seal["artifacts"]) == len(REQUIRED_ARTIFACT_ROLES)
    assert seal["topology"]["base_target_predictions"] == 104355
    assert seal["attestation"]["paderborn_models_fitted"] is False
    assert seal["authorization"]["base_evaluation_permitted"] is True


def test_execution_seal_rejects_artifact_or_attestation_drift(tmp_path: Path) -> None:
    spec_path, spec = _fixture(tmp_path)
    metrics_record = spec["artifacts"]["feature_metrics"]
    metrics_path = tmp_path / str(metrics_record["path"])
    metrics_path.write_text("changed\n", encoding="utf-8")
    with pytest.raises(ValueError, match="changed"):
        build_paderborn_execution_seal(
            spec_path=spec_path,
            output_path=tmp_path / "seal.json",
            root=tmp_path,
        )

    second_root = tmp_path / "attestation"
    spec_path, spec = _fixture(second_root)
    spec["attestation"] = {
        **EXPECTED_ATTESTATION,
        "paderborn_model_outcomes_inspected": True,
    }
    _write(spec_path, json.dumps(spec, indent=2))
    with pytest.raises(ValueError, match="attestation"):
        build_paderborn_execution_seal(
            spec_path=spec_path,
            output_path=second_root / "seal.json",
            root=second_root,
        )
