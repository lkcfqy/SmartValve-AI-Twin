"""Reconcile one sealed Paderborn compound row-index coordinate defect."""

from __future__ import annotations

import argparse
import hashlib
import json
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pandas as pd

from smartvalve.config import project_root
from smartvalve.data.paderborn_features import (
    STRUCTURALLY_EXCLUDED_FILENAMES,
    expected_measurement_filenames,
)
from smartvalve.experiments import (
    paderborn_artifact_validation as base_validation,
)
from smartvalve.experiments import (
    paderborn_selective_artifact_validation as selective_validation,
)
from smartvalve.experiments.dg_expected_manifest import canonical_key_record
from smartvalve.experiments.paderborn_expected_manifest import (
    KEY_SCHEMAS as BASE_KEY_SCHEMAS,
)
from smartvalve.experiments.paderborn_selective_expected_manifest import (
    KEY_SCHEMAS as SELECTIVE_KEY_SCHEMAS,
)

SPEC_VERSION = "smartvalve-paderborn-compound-index-reconciliation-spec-0.1.0"
RECONCILIATION_VERSION = "paderborn-compound-index-reconciliation-0.1.0"
BASE_COMPOUND_KEYS = frozenset({"compound_predictions"})
SELECTIVE_COMPOUND_KEYS = frozenset(
    {"compound_predictions", "compound_ensemble_predictions", "compound_decisions"}
)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, value: Any) -> None:
    path = path.resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


def _resolve_record(root: Path, record: object, *, label: str) -> Path:
    if not isinstance(record, dict) or set(record) != {"path", "bytes", "sha256"}:
        raise ValueError(f"invalid reconciliation record: {label}")
    relative = Path(str(record["path"]))
    if relative.is_absolute() or ".." in relative.parts:
        raise ValueError(f"reconciliation path is not project-relative: {label}")
    path = (root / relative).resolve(strict=True)
    if root != path and root not in path.parents:
        raise ValueError(f"reconciliation path escapes project root: {label}")
    if path.stat().st_size != int(record["bytes"]) or _sha256(path) != record["sha256"]:
        raise ValueError(f"reconciliation input changed: {label}")
    return path


def _load_spec(
    spec_path: Path,
    *,
    expected_sha256: str,
    mode: str,
    root: Path,
) -> tuple[dict[str, Any], dict[str, Path]]:
    spec_path = spec_path.resolve(strict=True)
    if _sha256(spec_path) != expected_sha256:
        raise ValueError("reconciliation-spec SHA-256 mismatch")
    spec = _read_json(spec_path)
    if (
        spec.get("schema_version") != SPEC_VERSION
        or spec.get("status") != "authorized_post_outcome_structural_validation_only"
        or mode not in spec.get("authorized_modes", [])
    ):
        raise ValueError("reconciliation spec is not authorized for this mode")
    expected_attestation = {
        "d2_performance_interpreted_before_amendment": False,
        "model_outputs_modified": False,
        "model_retraining_authorized": False,
        "performance_dependent_logic": False,
        "selection_or_endpoint_change_authorized": False,
    }
    if spec.get("attestation") != expected_attestation:
        raise ValueError("reconciliation attestation changed")
    if spec.get("excluded_filenames") != list(STRUCTURALLY_EXCLUDED_FILENAMES):
        raise ValueError("reconciliation structural exclusion changed")
    records = spec.get("artifacts")
    if not isinstance(records, dict):
        raise ValueError("reconciliation artifacts are missing")
    paths = {
        label: _resolve_record(root, record, label=label)
        for label, record in records.items()
    }
    if paths.get("reconciliation_source") != Path(__file__).resolve():
        raise ValueError("reconciliation spec references another source")
    if paths.get("reconciliation_protocol") is None:
        raise ValueError("reconciliation protocol is not bound")
    return spec, paths


def _derive_index_mapping(feature_matrix: Path) -> tuple[dict[int, int], dict[str, Any]]:
    expected = expected_measurement_filenames()
    excluded = set(STRUCTURALLY_EXCLUDED_FILENAMES)
    retained = tuple(filename for filename in expected if filename not in excluded)
    feature = pd.read_parquet(feature_matrix)
    required = {"filename", "truth"}
    if not required.issubset(feature.columns):
        raise ValueError("feature matrix omits reconciliation metadata")
    if tuple(feature["filename"].astype(str)) != retained:
        raise ValueError("feature matrix is not the compact retained filename sequence")
    if len(feature) != len(expected) - len(excluded):
        raise ValueError("feature matrix has an unexpected retained row count")
    original_by_name = {filename: index for index, filename in enumerate(expected)}
    compound = feature.loc[feature["truth"].astype(str) == "compound", ["filename"]].copy()
    if len(compound) != 240:
        raise ValueError("feature matrix compound cohort changed")
    mapping = {
        int(compact_index): int(original_by_name[str(row.filename)])
        for compact_index, row in compound.iterrows()
    }
    offsets = {original - compact for compact, original in mapping.items()}
    if offsets != {1}:
        raise ValueError("compound compact/original mapping is not the disclosed +1 defect")
    excluded_indices = [original_by_name[name] for name in STRUCTURALLY_EXCLUDED_FILENAMES]
    if excluded_indices != [1001]:
        raise ValueError("frozen exclusion no longer has original index 1001")
    return mapping, {
        "locked_filename_count": len(expected),
        "retained_feature_rows": len(feature),
        "compound_measurements": len(compound),
        "excluded_original_indices": excluded_indices,
        "first_compound_compact_index": min(mapping),
        "last_compound_compact_index": max(mapping),
        "first_compound_original_index": min(mapping.values()),
        "last_compound_original_index": max(mapping.values()),
        "uniform_original_minus_compact_offset": next(iter(offsets)),
    }


def _mapped_key_record(
    value: pd.DataFrame | list[dict[str, Any]],
    name: str,
    *,
    schemas: dict[str, tuple[str, ...]],
    mapping: dict[int, int],
) -> dict[str, Any]:
    if not isinstance(value, pd.DataFrame):
        raise ValueError("compound row-index reconciliation requires a table")
    columns = schemas[name]
    missing = set(columns) - set(value)
    if missing:
        raise ValueError(f"compound artifact is missing keys: {sorted(missing)}")
    adjusted = value.loc[:, list(columns)].copy()
    compact = adjusted["row_index"].astype(int)
    if not set(compact).issubset(mapping):
        raise ValueError("compound artifact contains a row outside the feature mapping")
    adjusted["row_index"] = compact.map(mapping)
    return canonical_key_record(
        adjusted.itertuples(index=False, name=None),
        columns,
    )


def _raw_key_record(
    value: pd.DataFrame,
    name: str,
    schemas: dict[str, tuple[str, ...]],
) -> dict[str, Any]:
    columns = schemas[name]
    return canonical_key_record(
        value.loc[:, list(columns)].itertuples(index=False, name=None),
        columns,
    )


def _base_compound_evidence(
    directory: Path,
    manifest: dict[str, Any],
    mapping: dict[int, int],
) -> dict[str, Any]:
    metrics = _read_json(directory / "metrics.json")
    record = metrics["artifacts"]["compound_predictions"]
    frame = pd.read_parquet(directory / str(record["path"]))
    identity = frame.loc[
        :,
        ["row_index", "filename", "bearing_code", "setting_code", "measurement_index"],
    ].drop_duplicates()
    if len(identity) != len(mapping):
        raise ValueError("compound identity projection does not contain exactly 240 rows")
    compact_by_filename = {
        str(row.filename): int(row.row_index) for row in identity.itertuples(index=False)
    }
    if len(compact_by_filename) != len(mapping):
        raise ValueError("compound filename identities are not unique")
    expected_names = expected_measurement_filenames()
    expected_compact_by_filename = {
        expected_names[original]: compact for compact, original in mapping.items()
    }
    if compact_by_filename != expected_compact_by_filename:
        raise ValueError("compound artifact does not address the compact feature rows")
    raw = _raw_key_record(frame, "compound_predictions", BASE_KEY_SCHEMAS)
    reconciled = _mapped_key_record(
        frame,
        "compound_predictions",
        schemas=BASE_KEY_SCHEMAS,
        mapping=mapping,
    )
    expected = manifest["expected_key_sets"]["compound_predictions"]
    if raw == expected or reconciled != expected:
        raise ValueError("base compound mismatch is not exactly the disclosed coordinate defect")
    return {
        "artifact_rows": len(frame),
        "unique_compound_identities": len(identity),
        "raw_compact_key_set": raw,
        "reconciled_original_index_key_set": reconciled,
        "sealed_manifest_key_set": expected,
        "all_non_index_identity_fields_unchanged": True,
    }


def _selective_compound_evidence(
    directory: Path,
    manifest: dict[str, Any],
    mapping: dict[int, int],
) -> dict[str, Any]:
    metrics = _read_json(directory / "metrics.json")
    evidence: dict[str, Any] = {}
    for artifact_name in sorted(SELECTIVE_COMPOUND_KEYS):
        record = metrics["artifacts"][artifact_name]
        frame = pd.read_parquet(directory / str(record["path"]))
        raw = _raw_key_record(frame, artifact_name, SELECTIVE_KEY_SCHEMAS)
        reconciled = _mapped_key_record(
            frame,
            artifact_name,
            schemas=SELECTIVE_KEY_SCHEMAS,
            mapping=mapping,
        )
        expected = manifest["expected_key_sets"][artifact_name]
        if raw == expected or reconciled != expected:
            raise ValueError(
                f"selective compound mismatch is not the disclosed defect: {artifact_name}"
            )
        evidence[artifact_name] = {
            "rows": len(frame),
            "raw_compact_key_set": raw,
            "reconciled_original_index_key_set": reconciled,
            "sealed_manifest_key_set": expected,
        }
    return evidence


def _run_with_key_reconciliation(
    *,
    mode: str,
    output_directory: Path,
    expected_manifest: Path,
    expected_manifest_sha256: str,
    output: Path,
    mapping: dict[int, int],
) -> tuple[dict[str, Any], dict[str, Any]]:
    manifest = _read_json(expected_manifest)
    if mode == "base":
        module = base_validation
        key_names = BASE_COMPOUND_KEYS
        schemas = BASE_KEY_SCHEMAS
        evidence = _base_compound_evidence(output_directory, manifest, mapping)
        validator: Callable[..., dict[str, Any]] = module.validate_paderborn_artifacts
        keyword = "paderborn_output_directory"
    else:
        module = selective_validation
        key_names = SELECTIVE_COMPOUND_KEYS
        schemas = SELECTIVE_KEY_SCHEMAS
        evidence = _selective_compound_evidence(output_directory, manifest, mapping)
        validator = module.validate_paderborn_selective_artifacts
        keyword = "selective_output_directory"

    original_key_record = module._key_record

    def reconciled_key_record(
        value: pd.DataFrame | list[dict[str, Any]], name: str
    ) -> dict[str, Any]:
        if name not in key_names:
            return original_key_record(value, name)
        return _mapped_key_record(value, name, schemas=schemas, mapping=mapping)

    module._key_record = reconciled_key_record
    try:
        result = validator(
            **{
                keyword: output_directory,
                "expected_manifest": expected_manifest,
                "expected_manifest_sha256": expected_manifest_sha256,
                "output": output,
            }
        )
    finally:
        module._key_record = original_key_record
    return result, evidence


def run_reconciliation(
    *,
    mode: str,
    artifact_output_directory: Path,
    expected_manifest: Path,
    expected_manifest_sha256: str,
    reconciliation_spec: Path,
    reconciliation_spec_sha256: str,
    output: Path,
    root: Path | None = None,
) -> dict[str, Any]:
    root = (root or project_root()).resolve()
    spec, bound_paths = _load_spec(
        reconciliation_spec,
        expected_sha256=reconciliation_spec_sha256,
        mode=mode,
        root=root,
    )
    expected_manifest = expected_manifest.resolve(strict=True)
    if _sha256(expected_manifest) != expected_manifest_sha256:
        raise ValueError("expected-manifest SHA-256 mismatch")
    expected_role = "base_expected_manifest" if mode == "base" else "selective_expected_manifest"
    if bound_paths.get(expected_role) != expected_manifest:
        raise ValueError("reconciliation spec references another expected manifest")
    feature_matrix = bound_paths["feature_matrix"]
    mapping, mapping_evidence = _derive_index_mapping(feature_matrix)
    artifact_output_directory = artifact_output_directory.resolve(strict=True)
    if mode == "base" and bound_paths.get("base_metrics") != (
        artifact_output_directory / "metrics.json"
    ).resolve(strict=True):
        raise ValueError("reconciliation spec references another base result")

    result, artifact_evidence = _run_with_key_reconciliation(
        mode=mode,
        output_directory=artifact_output_directory,
        expected_manifest=expected_manifest,
        expected_manifest_sha256=expected_manifest_sha256,
        output=output,
        mapping=mapping,
    )
    result["validation_version"] = RECONCILIATION_VERSION
    result["generated_at"] = datetime.now(UTC).isoformat()
    result["reconciliation"] = {
        "mode": mode,
        "classification": "post_outcome_structural_validation_amendment",
        "specification": {
            "path": str(reconciliation_spec.resolve()),
            "sha256": reconciliation_spec_sha256,
        },
        "protocol": {
            "path": str(bound_paths["reconciliation_protocol"]),
            "sha256": _sha256(bound_paths["reconciliation_protocol"]),
        },
        "failed_validator_record": {
            name: {"path": str(bound_paths[name]), "sha256": _sha256(bound_paths[name])}
            for name in (
                "failed_base_validation_command",
                "failed_base_validation_metadata",
                "failed_base_validation_stderr",
            )
        },
        "mapping": mapping_evidence,
        "artifacts": artifact_evidence,
        "model_outputs_modified": False,
        "model_retraining_performed": False,
        "performance_dependent_logic": False,
        "only_validation_coordinate_transformed": "compound row_index",
        "source_spec_attestation": spec["attestation"],
    }
    _write_json(output, result)
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=("base", "selective"), required=True)
    parser.add_argument("--artifact-output-directory", type=Path, required=True)
    parser.add_argument("--expected-manifest", type=Path, required=True)
    parser.add_argument("--expected-manifest-sha256", required=True)
    parser.add_argument("--reconciliation-spec", type=Path, required=True)
    parser.add_argument("--reconciliation-spec-sha256", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = run_reconciliation(
        mode=args.mode,
        artifact_output_directory=args.artifact_output_directory,
        expected_manifest=args.expected_manifest,
        expected_manifest_sha256=args.expected_manifest_sha256,
        reconciliation_spec=args.reconciliation_spec,
        reconciliation_spec_sha256=args.reconciliation_spec_sha256,
        output=args.output,
    )
    print(
        json.dumps(
            {
                "status": result["status"],
                "validation_version": result["validation_version"],
                "reconciled_mode": result["reconciliation"]["mode"],
                "model_outputs_modified": False,
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
