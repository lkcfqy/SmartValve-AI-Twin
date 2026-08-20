"""Build the immutable pre-D2 execution seal without opening prospective archives."""

from __future__ import annotations

import argparse
import json
import re
from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path

from smartvalve.config import project_root
from smartvalve.data.paderborn import ARCHIVE_NAMES

SPEC_VERSION = "smartvalve-prospective-seal-spec-0.1.0"
SEAL_VERSION = "smartvalve-prospective-seal-0.1.0"
SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")
METHODS = ("erm", "coral", "vrex", "groupdro", "dann", "lisa", "matchdg", "ccdg")
SEEDS = (11, 23, 37, 53, 71)
REQUIRED_ARTIFACT_ROLES = frozenset(
    {
        "frozen_paderborn_protocol",
        "paderborn_archive_lock",
        "paderborn_lock_verification",
        "cranfield_normal_data",
        "cranfield_lack_lubrication_data",
        "cranfield_backlash_data",
        "uci_feature_matrix",
        "pirl_development_metrics",
        "pirl_development_predictions",
        "dg_expected_manifest",
        "dg_selection_metrics",
        "dg_selection_predictions",
        "dg_artifact_validation",
        "source_selective_protocol",
        "source_selective_metrics",
        "source_selective_decisions",
        "development_selective_bootstrap_metrics",
        "pirl_ablation_metrics",
        "paderborn_split_manifest",
        "paderborn_model_fold_manifest",
        "paderborn_parser_source",
        "paderborn_feature_source",
        "paderborn_partition_source",
        "paderborn_bootstrap_source",
        "confirmatory_family_source",
        "paderborn_evaluation_source",
        "paderborn_expected_manifest",
        "paderborn_artifact_validation_source",
        "paderborn_selective_source",
        "paderborn_selective_expected_manifest",
        "paderborn_selective_artifact_validation_source",
    }
)
EXPECTED_STATISTICS = {
    "bootstrap_replicates": 2000,
    "bootstrap_seed": 20260818,
    "confidence_level": 0.95,
    "confirmatory_endpoints": [
        "minimum_setting_macro_f1",
        "selective_risk_at_50_percent_coverage",
    ],
    "family_size": 6,
    "multiple_testing": "holm",
    "minimum_material_effect": 0.01,
    "d2_resampling_unit": "bearing_identity",
    "d2_class_stratified": True,
}
EXPECTED_ATTESTATION = {
    "archive_contents_opened": False,
    "signal_features_computed": False,
    "paderborn_model_outcomes_inspected": False,
    "method_reselection_after_d2_forbidden": True,
}


def _digest(path: Path) -> str:
    hasher = sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def _resolve_relative(root: Path, value: object) -> Path:
    if not isinstance(value, str) or not value:
        raise ValueError("sealed artifact paths must be non-empty strings")
    relative = Path(value)
    if relative.is_absolute() or ".." in relative.parts:
        raise ValueError(f"sealed artifact path is not project-relative: {value}")
    resolved = (root / relative).resolve()
    if resolved != root and root not in resolved.parents:
        raise ValueError(f"sealed artifact escapes the project root: {value}")
    return resolved


def _execution_tree_fingerprint(root: Path) -> dict[str, object]:
    paths: set[Path] = set()
    for directory in ("src", "tests", "research/scripts"):
        base = root / directory
        if base.is_dir():
            paths.update(
                path
                for path in base.rglob("*.py")
                if "__pycache__" not in path.parts
            )
    for relative in ("pyproject.toml", "Makefile"):
        path = root / relative
        if path.is_file():
            paths.add(path)
    hasher = sha256()
    records = []
    for path in sorted(paths, key=lambda item: item.relative_to(root).as_posix()):
        relative = path.relative_to(root).as_posix()
        digest = _digest(path)
        hasher.update(relative.encode("utf-8"))
        hasher.update(b"\0")
        hasher.update(digest.encode("ascii"))
        hasher.update(b"\0")
        records.append({"path": relative, "bytes": path.stat().st_size, "sha256": digest})
    if not records:
        raise ValueError("execution tree contains no source files")
    return {"sha256": hasher.hexdigest(), "file_count": len(records), "files": records}


def _validate_decision(value: object) -> dict[str, object]:
    if not isinstance(value, dict):
        raise ValueError("seal decision must be an object")
    expected_scalar = {
        "headline_method": "pirl_ratio_v0.2",
        "baseline_method": "erm",
        "development_datasets": ["cranfield", "uci_hydraulic"],
        "prospective_dataset": "paderborn",
        "target_access": "P0",
        "seeds": list(SEEDS),
        "comparison_methods": list(METHODS),
    }
    for key, expected in expected_scalar.items():
        if value.get(key) != expected:
            raise ValueError(f"seal decision changes frozen field {key}")
    configurations = value.get("selected_configurations")
    expected_configuration_keys = {"pirl", *METHODS}
    if not isinstance(configurations, dict) or set(configurations) != expected_configuration_keys:
        raise ValueError("seal decision does not contain every selected configuration")
    if any(not isinstance(item, str) or not item for item in configurations.values()):
        raise ValueError("selected configurations must be non-empty strings")
    return value


def _validate_archive_lock(path: Path) -> dict[str, object]:
    lock = json.loads(path.read_text(encoding="utf-8"))
    archives = lock.get("archives")
    if (
        lock.get("archive_count") != len(ARCHIVE_NAMES)
        or not isinstance(archives, list)
        or len(archives) != len(ARCHIVE_NAMES)
    ):
        raise ValueError("Paderborn lock does not contain exactly 32 archives")
    filenames = [item.get("filename") for item in archives if isinstance(item, dict)]
    if len(filenames) != len(archives) or set(filenames) != set(ARCHIVE_NAMES):
        raise ValueError("Paderborn lock archive names differ from the official inventory")
    total_bytes = 0
    for item in archives:
        digest = item.get("sha256")
        byte_count = item.get("bytes")
        if not isinstance(digest, str) or not SHA256_PATTERN.fullmatch(digest):
            raise ValueError("Paderborn lock contains an invalid archive digest")
        if not isinstance(byte_count, int) or byte_count <= 0:
            raise ValueError("Paderborn lock contains an invalid archive byte count")
        total_bytes += byte_count
    if lock.get("total_bytes") != total_bytes:
        raise ValueError("Paderborn lock total bytes do not equal its archive entries")
    flags = lock.get("prospective_seal")
    expected_flags = {
        "archive_contents_opened": False,
        "signal_features_computed": False,
        "model_outcomes_inspected": False,
        "evaluation_protocol_required_before_open": True,
    }
    if flags != expected_flags:
        raise ValueError("Paderborn archive lock no longer has its original prospective seal")
    return {
        "archive_count": len(archives),
        "total_bytes": total_bytes,
        "archive_name_sha256": sha256(
            "\n".join(sorted(filenames)).encode("utf-8")
        ).hexdigest(),
        "archive_digest_sha256": sha256(
            "\n".join(
                f"{item['filename']}:{item['sha256']}" for item in sorted(
                    archives, key=lambda record: str(record["filename"])
                )
            ).encode("utf-8")
        ).hexdigest(),
        "prospective_seal": flags,
    }


def _validate_frozen_protocol(path: Path, *, label: str) -> None:
    text = path.read_text(encoding="utf-8")
    if re.search(r"\bDRAFT\b", text, flags=re.IGNORECASE):
        raise ValueError(f"{label} still contains a DRAFT marker")
    status_declares_frozen = re.search(
        r"status:\s*(?:\*\*)?frozen", text, flags=re.IGNORECASE
    )
    dated_freeze_declaration = re.search(
        r"^\s*-\s*frozen:\s*\S+", text, flags=re.IGNORECASE | re.MULTILINE
    )
    if not status_declares_frozen and not dated_freeze_declaration:
        raise ValueError(f"{label} does not declare frozen status")


def _validate_artifacts(root: Path, value: object) -> dict[str, dict[str, object]]:
    if not isinstance(value, dict):
        raise ValueError("seal artifacts must be an object keyed by role")
    missing = REQUIRED_ARTIFACT_ROLES - set(value)
    if missing:
        raise ValueError(f"seal is missing required artifact roles: {sorted(missing)}")
    records: dict[str, dict[str, object]] = {}
    seen_paths: set[str] = set()
    for role in sorted(value):
        declared = value[role]
        if not isinstance(declared, dict) or set(declared) != {"path", "bytes", "sha256"}:
            raise ValueError(f"artifact {role} must declare path, bytes and sha256 only")
        path = _resolve_relative(root, declared["path"])
        if not path.is_file():
            raise ValueError(f"sealed artifact does not exist: {declared['path']}")
        relative = path.relative_to(root).as_posix()
        if relative in seen_paths:
            raise ValueError(f"multiple seal roles reference the same path: {relative}")
        seen_paths.add(relative)
        actual_bytes = path.stat().st_size
        actual_sha256 = _digest(path)
        if declared["bytes"] != actual_bytes or declared["sha256"] != actual_sha256:
            raise ValueError(f"sealed artifact changed: {role}")
        records[role] = {
            "path": relative,
            "bytes": actual_bytes,
            "sha256": actual_sha256,
        }
    return records


def build_prospective_seal(
    spec_path: Path,
    output_path: Path,
    *,
    root: Path | None = None,
) -> dict[str, object]:
    """Validate all frozen inputs and atomically write a pre-D2 seal."""

    root = (root or project_root()).resolve()
    spec_path = spec_path.resolve()
    output_path = output_path.resolve()
    if spec_path == output_path:
        raise ValueError("seal specification and output must be different files")
    spec = json.loads(spec_path.read_text(encoding="utf-8"))
    if spec.get("schema_version") != SPEC_VERSION:
        raise ValueError("prospective seal specification version changed")
    if spec.get("statistics") != EXPECTED_STATISTICS:
        raise ValueError("prospective seal statistics differ from the frozen family")
    if spec.get("attestation") != EXPECTED_ATTESTATION:
        raise ValueError("prospective seal attestation is not pre-outcome and no-reselection safe")
    decision = _validate_decision(spec.get("decision"))
    artifacts = _validate_artifacts(root, spec.get("artifacts"))
    _validate_frozen_protocol(
        root / str(artifacts["frozen_paderborn_protocol"]["path"]),
        label="Paderborn protocol",
    )
    _validate_frozen_protocol(
        root / str(artifacts["source_selective_protocol"]["path"]),
        label="source-selective protocol",
    )
    archive_summary = _validate_archive_lock(
        root / str(artifacts["paderborn_archive_lock"]["path"])
    )
    result: dict[str, object] = {
        "schema_version": SEAL_VERSION,
        "generated_at": datetime.now(UTC).isoformat(),
        "status": "sealed_pre_d2_ready_for_protocol_governed_structure_probe",
        "specification": {
            "path": spec_path.relative_to(root).as_posix(),
            "bytes": spec_path.stat().st_size,
            "sha256": _digest(spec_path),
        },
        "decision": decision,
        "statistics": spec["statistics"],
        "attestation": spec["attestation"],
        "artifacts": artifacts,
        "paderborn_archive_lock": archive_summary,
        "execution_tree": _execution_tree_fingerprint(root),
        "authorization": {
            "initial_scope": "single_mat_key_shape_dtype_probe_only",
            "bulk_extraction_requires_probe_validation": True,
            "target_outcome_guided_reselection_forbidden": True,
        },
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    temporary = output_path.with_suffix(output_path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    temporary.replace(output_path)
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--spec", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = build_prospective_seal(args.spec, args.output)
    print(
        json.dumps(
            {
                "status": result["status"],
                "artifact_count": len(result["artifacts"]),
                "execution_tree_sha256": result["execution_tree"]["sha256"],
                "archive_count": result["paderborn_archive_lock"]["archive_count"],
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
