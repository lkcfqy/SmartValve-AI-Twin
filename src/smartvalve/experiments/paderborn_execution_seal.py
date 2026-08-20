"""Seal the amended Paderborn D2 execution after features and before model outcomes."""

from __future__ import annotations

import argparse
import json
import re
from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path
from typing import Any

from smartvalve.config import project_root
from smartvalve.experiments.prospective_seal import (
    EXPECTED_STATISTICS,
    _execution_tree_fingerprint,
    _validate_decision,
    _validate_frozen_protocol,
)

SPEC_VERSION = "smartvalve-paderborn-d2-execution-seal-spec-0.1.0"
SEAL_VERSION = "smartvalve-paderborn-d2-execution-seal-0.1.0"
SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")
EXPECTED_ATTESTATION = {
    "archive_contents_opened": True,
    "signal_features_computed": True,
    "independent_feature_validation_passed": True,
    "paderborn_models_fitted": False,
    "paderborn_model_outcomes_inspected": False,
    "target_guided_reselection_performed": False,
    "method_reselection_after_d2_forbidden": True,
}
EXPECTED_TOPOLOGY = {
    "locked_measurements": 2560,
    "retained_measurements": 2559,
    "primary_measurements": 2319,
    "compound_measurements": 240,
    "structurally_excluded_measurements": 1,
    "outer_folds": 24,
    "base_models": 1080,
    "base_target_predictions": 104355,
    "base_compound_predictions": 259200,
    "selective_inner_models": 720,
    "selective_source_oof_predictions": 347850,
    "selective_target_predictions": 23190,
    "selective_compound_decisions": 1382400,
}
REQUIRED_ARTIFACT_ROLES = frozenset(
    {
        "original_prospective_seal",
        "execution_amendment_protocol",
        "feature_contract_amendment",
        "feature_metrics",
        "feature_validation",
        "amended_split_manifest",
        "amended_model_fold_manifest",
        "amended_expected_manifest",
        "amended_selective_expected_manifest",
        "paderborn_features_source",
        "paderborn_mat_parser_source",
        "paderborn_feature_validator_source",
        "paderborn_partitions_source",
        "paderborn_domain_source",
        "paderborn_evaluation_source",
        "paderborn_expected_manifest_source",
        "paderborn_artifact_validation_source",
        "paderborn_selective_source",
        "paderborn_selective_expected_manifest_source",
        "paderborn_selective_artifact_validation_source",
        "paderborn_bootstrap_source",
        "confirmatory_family_source",
        "split_manifest_script",
        "model_fold_manifest_script",
        "execution_seal_source",
        "feature_validation_tests",
        "partition_tests",
        "domain_tests",
        "evaluation_tests",
        "expected_manifest_tests",
        "selective_tests",
        "execution_seal_tests",
    }
)


def _digest(path: Path) -> str:
    hasher = sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(4 * 1024 * 1024), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def _resolve_relative(root: Path, value: object) -> Path:
    if not isinstance(value, str) or not value:
        raise ValueError("execution-seal paths must be non-empty strings")
    relative = Path(value)
    if relative.is_absolute() or ".." in relative.parts:
        raise ValueError("execution-seal artifact path is not project-relative")
    path = (root / relative).resolve(strict=True)
    if root != path and root not in path.parents:
        raise ValueError("execution-seal artifact escapes the project root")
    return path


def _validate_artifacts(root: Path, value: object) -> dict[str, dict[str, object]]:
    if not isinstance(value, dict) or set(value) != REQUIRED_ARTIFACT_ROLES:
        missing = sorted(REQUIRED_ARTIFACT_ROLES - set(value or {}))
        extra = sorted(set(value or {}) - REQUIRED_ARTIFACT_ROLES)
        raise ValueError(f"execution-seal artifact roles changed: missing={missing}, extra={extra}")
    records: dict[str, dict[str, object]] = {}
    seen: set[Path] = set()
    for role in sorted(value):
        declared = value[role]
        if not isinstance(declared, dict) or set(declared) != {"path", "bytes", "sha256"}:
            raise ValueError(f"execution-seal artifact record is invalid: {role}")
        path = _resolve_relative(root, declared["path"])
        if path in seen:
            raise ValueError("execution-seal roles cannot reuse an artifact path")
        seen.add(path)
        digest = _digest(path)
        if (
            declared.get("bytes") != path.stat().st_size
            or declared.get("sha256") != digest
            or not SHA256_PATTERN.fullmatch(str(declared.get("sha256", "")))
        ):
            raise ValueError(f"execution-seal artifact changed: {role}")
        records[role] = {
            "path": path.relative_to(root).as_posix(),
            "bytes": path.stat().st_size,
            "sha256": digest,
        }
    return records


def _read(root: Path, records: dict[str, dict[str, object]], role: str) -> Any:
    path = root / str(records[role]["path"])
    return json.loads(path.read_text(encoding="utf-8"))


def _validate_chain(root: Path, artifacts: dict[str, dict[str, object]]) -> None:
    original = _read(root, artifacts, "original_prospective_seal")
    if (
        original.get("schema_version") != "smartvalve-prospective-seal-0.1.0"
        or original.get("status") != "sealed_pre_d2_ready_for_protocol_governed_structure_probe"
    ):
        raise ValueError("original Paderborn prospective seal is invalid")
    amendment = _read(root, artifacts, "feature_contract_amendment")
    if (
        amendment.get("schema_version") != "smartvalve-paderborn-feature-contract-amendment-0.5.0"
        or amendment.get("status") != "authorized_outcome_blind_bulk_feature_extraction"
    ):
        raise ValueError("final Paderborn feature amendment is invalid")
    metrics = _read(root, artifacts, "feature_metrics")
    if (
        metrics.get("status") != "sealed_paderborn_features_complete_without_model_outcome_access"
        or metrics.get("input", {}).get("feature_contract_amendment_sha256")
        != artifacts["feature_contract_amendment"]["sha256"]
        or metrics.get("access_attestation", {}).get("model_fitted") is not False
        or metrics.get("access_attestation", {}).get("model_outcomes_inspected") is not False
    ):
        raise ValueError("Paderborn feature metrics crossed the pre-model boundary")
    validation = _read(root, artifacts, "feature_validation")
    if (
        validation.get("status") != "passed_before_paderborn_model_outcome_access"
        or validation.get("input", {}).get("feature_metrics_sha256")
        != artifacts["feature_metrics"]["sha256"]
        or validation.get("access_attestation", {}).get("model_fitted") is not False
        or validation.get("access_attestation", {}).get("model_outcomes_inspected") is not False
    ):
        raise ValueError("Paderborn feature validation did not preserve outcome blindness")

    split = _read(root, artifacts, "amended_split_manifest")
    if (
        split.get("schema_version") != "smartvalve-paderborn-split-manifest-0.2.0"
        or split.get("seal", {}).get("signal_features_used_to_define_partitions") is not False
        or split.get("seal", {}).get("model_outcomes_inspected") is not False
    ):
        raise ValueError("amended Paderborn split manifest is invalid")
    folds = _read(root, artifacts, "amended_model_fold_manifest")
    if (
        folds.get("manifest_version") != "paderborn-model-fold-schema-0.2.0"
        or folds.get("all_measurements_target_exactly_once") is not True
        or folds.get("pure_measurements") != 2319
        or folds.get("signal_features_used_to_define_folds") is not False
        or folds.get("model_outcomes_inspected") is not False
    ):
        raise ValueError("amended Paderborn model-fold manifest is invalid")

    expected = _read(root, artifacts, "amended_expected_manifest")
    counts = expected.get("expected_key_sets", {})
    if (
        expected.get("manifest_version") != "paderborn-prospective-expected-key-manifest-0.2.0"
        or counts.get("training_models", {}).get("count") != 1080
        or counts.get("target_predictions", {}).get("count") != 104355
        or counts.get("compound_predictions", {}).get("count") != 259200
    ):
        raise ValueError("amended Paderborn expected manifest is invalid")
    expected_input = expected.get("input", {})
    role_by_field = {
        "protocol_document": "execution_amendment_protocol",
        "split_manifest": "amended_split_manifest",
        "model_fold_manifest": "amended_model_fold_manifest",
        "feature_contract_amendment": "feature_contract_amendment",
        "feature_validation": "feature_validation",
    }
    for field, role in role_by_field.items():
        if expected_input.get(f"{field}_sha256") != artifacts[role]["sha256"]:
            raise ValueError(f"amended expected manifest input drift: {field}")
    if (
        expected_input.get("signal_features_used_to_define_topology") is not False
        or expected_input.get("model_outcomes_inspected_before_manifest") is not False
    ):
        raise ValueError("amended expected manifest crossed the outcome boundary")

    selective = _read(root, artifacts, "amended_selective_expected_manifest")
    selective_counts = selective.get("expected_key_sets", {})
    if (
        selective.get("manifest_version") != "paderborn-selective-expected-key-manifest-0.2.0"
        or selective.get("input", {}).get("base_expected_manifest_sha256")
        != artifacts["amended_expected_manifest"]["sha256"]
        or selective_counts.get("training_models", {}).get("count") != 720
        or selective_counts.get("source_oof_predictions", {}).get("count") != 347850
        or selective_counts.get("target_predictions", {}).get("count") != 23190
        or selective_counts.get("compound_decisions", {}).get("count") != 1382400
    ):
        raise ValueError("amended Paderborn selective expected manifest is invalid")


def build_paderborn_execution_seal(
    *, spec_path: Path, output_path: Path, root: Path | None = None
) -> dict[str, Any]:
    root = (root or project_root()).resolve()
    spec_path = spec_path.resolve(strict=True)
    output_path = output_path.resolve()
    if spec_path == output_path:
        raise ValueError("execution-seal specification and output must differ")
    spec = json.loads(spec_path.read_text(encoding="utf-8"))
    if spec.get("schema_version") != SPEC_VERSION:
        raise ValueError("Paderborn execution-seal specification version changed")
    decision = _validate_decision(spec.get("decision"))
    if spec.get("statistics") != EXPECTED_STATISTICS:
        raise ValueError("Paderborn execution statistics changed")
    if spec.get("topology") != EXPECTED_TOPOLOGY:
        raise ValueError("Paderborn amended topology changed")
    if spec.get("attestation") != EXPECTED_ATTESTATION:
        raise ValueError("Paderborn execution attestation crossed the outcome boundary")
    artifacts = _validate_artifacts(root, spec.get("artifacts"))
    _validate_frozen_protocol(
        root / str(artifacts["execution_amendment_protocol"]["path"]),
        label="Paderborn D2 execution amendment",
    )
    _validate_chain(root, artifacts)
    original = _read(root, artifacts, "original_prospective_seal")
    if decision != original.get("decision") or spec["statistics"] != original.get("statistics"):
        raise ValueError("Paderborn execution seal changes the original decision")

    result = {
        "schema_version": SEAL_VERSION,
        "generated_at": datetime.now(UTC).isoformat(),
        "status": "sealed_after_features_before_paderborn_model_outcomes",
        "specification": {
            "path": spec_path.relative_to(root).as_posix(),
            "bytes": spec_path.stat().st_size,
            "sha256": _digest(spec_path),
        },
        "decision": decision,
        "statistics": spec["statistics"],
        "topology": spec["topology"],
        "attestation": spec["attestation"],
        "artifacts": artifacts,
        "execution_tree": _execution_tree_fingerprint(root),
        "authorization": {
            "base_evaluation_permitted": True,
            "base_evaluation_must_complete_before_selective_evaluation": True,
            "selective_evaluation_requires_independently_validated_base": True,
            "target_outcome_guided_reselection_forbidden": True,
            "compound_forced_ground_truth_forbidden": True,
        },
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    temporary = output_path.with_suffix(output_path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    temporary.replace(output_path)
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--spec", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = build_paderborn_execution_seal(spec_path=args.spec, output_path=args.output)
    print(
        json.dumps(
            {
                "status": result["status"],
                "artifact_count": len(result["artifacts"]),
                "execution_tree_sha256": result["execution_tree"]["sha256"],
                "topology": result["topology"],
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
