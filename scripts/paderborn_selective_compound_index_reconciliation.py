"""Bind the disclosed selective-validator failure before row-index reconciliation."""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import paderborn_compound_index_reconciliation as reconciliation

from smartvalve.config import project_root

SPEC_VERSION = "smartvalve-paderborn-selective-index-reconciliation-addendum-0.1.0"
EXPECTED_ATTESTATION = {
    "unmodified_selective_validator_failed_first": True,
    "failure_preceded_selective_metric_interpretation": True,
    "failure_field": "compound_predictions.row_index",
    "model_outputs_modified": False,
    "performance_dependent_logic": False,
}


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
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


def _resolve_record(root: Path, record: object, *, label: str) -> Path:
    if not isinstance(record, dict) or set(record) != {"path", "bytes", "sha256"}:
        raise ValueError(f"invalid selective reconciliation record: {label}")
    relative = Path(str(record["path"]))
    if relative.is_absolute() or ".." in relative.parts:
        raise ValueError(f"selective reconciliation path is not project-relative: {label}")
    path = (root / relative).resolve(strict=True)
    if root != path and root not in path.parents:
        raise ValueError(f"selective reconciliation path escapes project root: {label}")
    if path.stat().st_size != int(record["bytes"]) or _sha256(path) != record["sha256"]:
        raise ValueError(f"selective reconciliation input changed: {label}")
    return path


def _load_addendum(
    path: Path,
    *,
    expected_sha256: str,
    root: Path,
) -> tuple[dict[str, Any], dict[str, Path]]:
    path = path.resolve(strict=True)
    if _sha256(path) != expected_sha256:
        raise ValueError("selective reconciliation addendum SHA-256 mismatch")
    spec = _read_json(path)
    if (
        spec.get("schema_version") != SPEC_VERSION
        or spec.get("status") != "authorized_after_matching_unmodified_validator_failure"
        or spec.get("attestation") != EXPECTED_ATTESTATION
    ):
        raise ValueError("selective reconciliation addendum is not authorized")
    records = spec.get("artifacts")
    if not isinstance(records, dict):
        raise ValueError("selective reconciliation addendum has no artifacts")
    resolved = {
        label: _resolve_record(root, record, label=label)
        for label, record in records.items()
    }
    if resolved.get("selective_reconciliation_source") != Path(__file__).resolve():
        raise ValueError("selective reconciliation addendum references another wrapper")
    if resolved.get("base_reconciliation_source") != Path(reconciliation.__file__).resolve():
        raise ValueError("selective reconciliation addendum references another base reconciler")
    failure_metadata = _read_json(resolved["failed_selective_validation_metadata"])
    failure_text = resolved["failed_selective_validation_stderr"].read_text(encoding="utf-8")
    if (
        failure_metadata.get("status") != "failed"
        or failure_metadata.get("exit_code") != 1
        or "Paderborn selective artifact key set differs: compound_predictions"
        not in failure_text
    ):
        raise ValueError("unmodified selective-validator failure is not the disclosed defect")
    return spec, resolved


def run_selective_reconciliation(
    *,
    artifact_output_directory: Path,
    expected_manifest: Path,
    expected_manifest_sha256: str,
    base_reconciliation_spec: Path,
    base_reconciliation_spec_sha256: str,
    selective_addendum: Path,
    selective_addendum_sha256: str,
    output: Path,
    root: Path | None = None,
) -> dict[str, Any]:
    root = (root or project_root()).resolve()
    _, paths = _load_addendum(
        selective_addendum,
        expected_sha256=selective_addendum_sha256,
        root=root,
    )
    artifact_output_directory = artifact_output_directory.resolve(strict=True)
    expected_manifest = expected_manifest.resolve(strict=True)
    base_reconciliation_spec = base_reconciliation_spec.resolve(strict=True)
    if paths.get("selective_metrics") != (
        artifact_output_directory / "metrics.json"
    ).resolve(strict=True):
        raise ValueError("selective addendum references another evaluation")
    if paths.get("selective_expected_manifest") != expected_manifest:
        raise ValueError("selective addendum references another manifest")
    if paths.get("base_reconciliation_spec") != base_reconciliation_spec:
        raise ValueError("selective addendum references another base reconciliation spec")

    result = reconciliation.run_reconciliation(
        mode="selective",
        artifact_output_directory=artifact_output_directory,
        expected_manifest=expected_manifest,
        expected_manifest_sha256=expected_manifest_sha256,
        reconciliation_spec=base_reconciliation_spec,
        reconciliation_spec_sha256=base_reconciliation_spec_sha256,
        output=output,
        root=root,
    )
    result["generated_at"] = datetime.now(UTC).isoformat()
    result["reconciliation"]["selective_addendum"] = {
        "path": str(selective_addendum.resolve()),
        "sha256": selective_addendum_sha256,
    }
    result["reconciliation"]["failed_selective_validator_record"] = {
        name: {"path": str(paths[name]), "sha256": _sha256(paths[name])}
        for name in (
            "failed_selective_validation_command",
            "failed_selective_validation_metadata",
            "failed_selective_validation_stderr",
        )
    }
    result["reconciliation"]["unmodified_selective_validator_failed_first"] = True
    _write_json(output, result)
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--artifact-output-directory", type=Path, required=True)
    parser.add_argument("--expected-manifest", type=Path, required=True)
    parser.add_argument("--expected-manifest-sha256", required=True)
    parser.add_argument("--base-reconciliation-spec", type=Path, required=True)
    parser.add_argument("--base-reconciliation-spec-sha256", required=True)
    parser.add_argument("--selective-addendum", type=Path, required=True)
    parser.add_argument("--selective-addendum-sha256", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = run_selective_reconciliation(
        artifact_output_directory=args.artifact_output_directory,
        expected_manifest=args.expected_manifest,
        expected_manifest_sha256=args.expected_manifest_sha256,
        base_reconciliation_spec=args.base_reconciliation_spec,
        base_reconciliation_spec_sha256=args.base_reconciliation_spec_sha256,
        selective_addendum=args.selective_addendum,
        selective_addendum_sha256=args.selective_addendum_sha256,
        output=args.output,
    )
    print(
        json.dumps(
            {
                "status": result["status"],
                "validation_version": result["validation_version"],
                "unmodified_selective_validator_failed_first": True,
                "model_outputs_modified": False,
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
