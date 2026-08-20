"""Run the frozen six-test family with the reconciled D2 physical contract."""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from smartvalve.config import project_root
from smartvalve.experiments import confirmatory_family as sealed

SPEC_VERSION = "smartvalve-paderborn-confirmatory-reconciliation-spec-0.1.0"
FAMILY_VERSION = "smartvalve-six-test-confirmatory-family-0.1.0+reconciliation-0.1.0"
EXPECTED_D2_BOOTSTRAP_VERSION = "paderborn-paired-bearing-cluster-bootstrap-0.2.0"
EXPECTED_ATTESTATION = {
    "raw_d2_endpoints_interpreted_before_adapter": True,
    "holm_family_result_generated_before_adapter": False,
    "family_membership_or_algorithm_changed": False,
    "bootstrap_inputs_modified": False,
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
        raise ValueError(f"invalid confirmatory reconciliation record: {label}")
    relative = Path(str(record["path"]))
    if relative.is_absolute() or ".." in relative.parts:
        raise ValueError(f"confirmatory reconciliation path is not project-relative: {label}")
    path = (root / relative).resolve(strict=True)
    if root != path and root not in path.parents:
        raise ValueError(f"confirmatory reconciliation path escapes project root: {label}")
    if path.stat().st_size != int(record["bytes"]) or _sha256(path) != record["sha256"]:
        raise ValueError(f"confirmatory reconciliation input changed: {label}")
    return path


def _load_spec(
    path: Path,
    *,
    expected_sha256: str,
    root: Path,
) -> tuple[dict[str, Any], dict[str, Path]]:
    path = path.resolve(strict=True)
    if _sha256(path) != expected_sha256:
        raise ValueError("confirmatory reconciliation spec SHA-256 mismatch")
    spec = _read_json(path)
    if (
        spec.get("schema_version") != SPEC_VERSION
        or spec.get("status") != "authorized_before_any_six_test_holm_result"
        or spec.get("attestation") != EXPECTED_ATTESTATION
    ):
        raise ValueError("confirmatory reconciliation spec is not authorized")
    records = spec.get("artifacts")
    if not isinstance(records, dict):
        raise ValueError("confirmatory reconciliation spec has no artifacts")
    paths = {
        label: _resolve_record(root, record, label=label)
        for label, record in records.items()
    }
    if paths.get("reconciliation_source") != Path(__file__).resolve():
        raise ValueError("confirmatory reconciliation spec references another adapter")
    if paths.get("sealed_confirmatory_source") != Path(sealed.__file__).resolve():
        raise ValueError("confirmatory reconciliation spec references another assembler")
    failure = _read_json(paths["failed_confirmatory_metadata"])
    failure_text = paths["failed_confirmatory_stderr"].read_text(encoding="utf-8")
    if (
        failure.get("status") != "failed"
        or failure.get("exit_code") != 1
        or "confirmatory input has an unexpected bootstrap version" not in failure_text
    ):
        raise ValueError("failed confirmatory record is not the disclosed version assertion")
    return spec, paths


def reconciled_configuration_validation(
    metrics: dict[str, Any],
    *,
    paderborn: bool,
    original_validation,
) -> None:
    """Preserve sealed checks while adapting only the disclosed D2 version/count."""

    if not paderborn:
        original_validation(metrics, paderborn=False)
        return
    if metrics.get("bootstrap_version") != EXPECTED_D2_BOOTSTRAP_VERSION:
        raise ValueError("reconciled D2 bootstrap version changed")
    contract = metrics.get("contract")
    if not isinstance(contract, dict):
        raise ValueError("reconciled D2 bootstrap has no physical contract")
    expected_exclusion = {
        "bearing_code": "KA08",
        "setting_code": "N15_M01_F10",
        "measurement_index": 2,
    }
    if (
        contract.get("pure_bearings") != 29
        or contract.get("locked_pure_measurements") != 2_320
        or contract.get("physical_measurements") != 2_319
        or contract.get("structurally_excluded_measurements") != 1
        or contract.get("structurally_excluded_key") != expected_exclusion
    ):
        raise ValueError("reconciled D2 physical contract changed")
    reconciliation = metrics.get("reconciliation")
    if (
        not isinstance(reconciliation, dict)
        or reconciliation.get("d2_bootstrap_outcomes_generated_before_amendment") is not False
        or reconciliation.get("statistical_design_changed") is not False
        or reconciliation.get("model_or_decision_outputs_modified") is not False
    ):
        raise ValueError("D2 bootstrap reconciliation attestation changed")

    proxy = copy.deepcopy(metrics)
    proxy["bootstrap_version"] = sealed.PADERBORN_BOOTSTRAP_VERSION
    proxy["contract"]["physical_measurements"] = 2_320
    original_validation(proxy, paderborn=True)


def run_reconciled_family(
    *,
    development_metrics: Path,
    paderborn_metrics: Path,
    expected_development_sha256: str,
    expected_paderborn_sha256: str,
    reconciliation_spec: Path,
    reconciliation_spec_sha256: str,
    output_directory: Path,
    root: Path | None = None,
) -> dict[str, Any]:
    root = (root or project_root()).resolve()
    spec, paths = _load_spec(
        reconciliation_spec,
        expected_sha256=reconciliation_spec_sha256,
        root=root,
    )
    development_metrics = development_metrics.resolve(strict=True)
    paderborn_metrics = paderborn_metrics.resolve(strict=True)
    if paths.get("development_metrics") != development_metrics:
        raise ValueError("confirmatory spec references other development metrics")
    if paths.get("paderborn_metrics") != paderborn_metrics:
        raise ValueError("confirmatory spec references other Paderborn metrics")

    original = sealed._validate_configuration

    def adapted(metrics: dict[str, Any], *, paderborn: bool) -> None:
        reconciled_configuration_validation(
            metrics,
            paderborn=paderborn,
            original_validation=original,
        )

    sealed._validate_configuration = adapted
    try:
        metrics = sealed.run_confirmatory_family(
            development_metrics,
            paderborn_metrics,
            output_directory,
            expected_development_sha256=expected_development_sha256,
            expected_paderborn_sha256=expected_paderborn_sha256,
        )
    finally:
        sealed._validate_configuration = original

    metrics["family_version"] = FAMILY_VERSION
    metrics["generated_at"] = datetime.now(UTC).isoformat()
    metrics["protocol_document"] = str(paths["reconciliation_protocol"].relative_to(root))
    metrics["reconciliation"] = {
        "classification": "post_outcome_pre_holm_structural_validation_adapter",
        "specification": {
            "path": str(reconciliation_spec.resolve()),
            "sha256": reconciliation_spec_sha256,
        },
        "protocol": {
            "path": str(paths["reconciliation_protocol"]),
            "sha256": _sha256(paths["reconciliation_protocol"]),
        },
        "sealed_confirmatory_source": {
            "path": str(paths["sealed_confirmatory_source"]),
            "sha256": _sha256(paths["sealed_confirmatory_source"]),
        },
        "failed_confirmatory_record": {
            name: {"path": str(paths[name]), "sha256": _sha256(paths[name])}
            for name in (
                "failed_confirmatory_command",
                "failed_confirmatory_metadata",
                "failed_confirmatory_stderr",
            )
        },
        "accepted_d2_bootstrap_version": EXPECTED_D2_BOOTSTRAP_VERSION,
        "accepted_retained_physical_measurements": 2_319,
        "family_membership_or_algorithm_changed": False,
        "bootstrap_inputs_modified": False,
        "source_spec_attestation": spec["attestation"],
    }
    _write_json(output_directory / "metrics.json", metrics)
    return metrics


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--development-metrics", type=Path, required=True)
    parser.add_argument("--paderborn-metrics", type=Path, required=True)
    parser.add_argument("--expected-development-sha256", required=True)
    parser.add_argument("--expected-paderborn-sha256", required=True)
    parser.add_argument("--reconciliation-spec", type=Path, required=True)
    parser.add_argument("--reconciliation-spec-sha256", required=True)
    parser.add_argument("--output-directory", type=Path, required=True)
    args = parser.parse_args()
    result = run_reconciled_family(
        development_metrics=args.development_metrics,
        paderborn_metrics=args.paderborn_metrics,
        expected_development_sha256=args.expected_development_sha256,
        expected_paderborn_sha256=args.expected_paderborn_sha256,
        reconciliation_spec=args.reconciliation_spec,
        reconciliation_spec_sha256=args.reconciliation_spec_sha256,
        output_directory=args.output_directory,
    )
    print(json.dumps(result["summary"], ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
