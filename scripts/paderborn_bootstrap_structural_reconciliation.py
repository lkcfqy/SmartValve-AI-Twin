"""Run the frozen bearing bootstrap after reconciling one excluded pure measurement."""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from smartvalve.config import project_root
from smartvalve.data.paderborn import (
    OPERATING_SETTINGS,
    PRIMARY_BEARING_CODES,
)
from smartvalve.data.paderborn_features import (
    STRUCTURALLY_EXCLUDED_FILENAMES,
    parse_measurement_filename,
)
from smartvalve.experiments import paderborn_bootstrap as sealed
from smartvalve.experiments.cranfield_causal_audit import AUDIT_SEEDS
from smartvalve.experiments.paderborn_partitions import MEASUREMENT_INDICES

SPEC_VERSION = "smartvalve-paderborn-bootstrap-structural-reconciliation-spec-0.1.0"
BOOTSTRAP_VERSION = "paderborn-paired-bearing-cluster-bootstrap-0.2.0"
EXPECTED_ATTESTATION = {
    "descriptive_d2_results_interpreted_before_amendment": True,
    "d2_bootstrap_outcomes_generated_before_amendment": False,
    "statistical_design_changed": False,
    "model_or_decision_outputs_modified": False,
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
        raise ValueError(f"invalid bootstrap reconciliation record: {label}")
    relative = Path(str(record["path"]))
    if relative.is_absolute() or ".." in relative.parts:
        raise ValueError(f"bootstrap reconciliation path is not project-relative: {label}")
    path = (root / relative).resolve(strict=True)
    if root != path and root not in path.parents:
        raise ValueError(f"bootstrap reconciliation path escapes project root: {label}")
    if path.stat().st_size != int(record["bytes"]) or _sha256(path) != record["sha256"]:
        raise ValueError(f"bootstrap reconciliation input changed: {label}")
    return path


def _load_spec(
    path: Path,
    *,
    expected_sha256: str,
    root: Path,
) -> tuple[dict[str, Any], dict[str, Path]]:
    path = path.resolve(strict=True)
    if _sha256(path) != expected_sha256:
        raise ValueError("bootstrap reconciliation spec SHA-256 mismatch")
    spec = _read_json(path)
    if (
        spec.get("schema_version") != SPEC_VERSION
        or spec.get("status") != "authorized_before_any_d2_bootstrap_statistic"
        or spec.get("attestation") != EXPECTED_ATTESTATION
        or spec.get("excluded_filenames") != list(STRUCTURALLY_EXCLUDED_FILENAMES)
    ):
        raise ValueError("bootstrap reconciliation spec is not authorized")
    records = spec.get("artifacts")
    if not isinstance(records, dict):
        raise ValueError("bootstrap reconciliation spec has no artifacts")
    paths = {
        label: _resolve_record(root, record, label=label)
        for label, record in records.items()
    }
    if paths.get("reconciliation_source") != Path(__file__).resolve():
        raise ValueError("bootstrap reconciliation spec references another source")
    if paths.get("sealed_bootstrap_source") != Path(sealed.__file__).resolve():
        raise ValueError("bootstrap reconciliation spec references another sealed runner")
    failure = _read_json(paths["failed_bootstrap_metadata"])
    failure_text = paths["failed_bootstrap_stderr"].read_text(encoding="utf-8")
    if (
        failure.get("status") != "failed"
        or failure.get("exit_code") != 1
        or "Paderborn predictions do not contain the exact pure measurement set"
        not in failure_text
    ):
        raise ValueError("failed bootstrap record is not the disclosed structural assertion")
    for label, expected_status in (
        ("base_validation", "passed_against_sealed_metadata_only_paderborn_manifest"),
        ("selective_validation", "passed_against_sealed_paderborn_selective_manifest"),
    ):
        if _read_json(paths[label]).get("status") != expected_status:
            raise ValueError(f"bootstrap input lacks passed {label}")
    return spec, paths


def _retained_expected_keys() -> tuple[set[tuple[str, str, int]], tuple[str, str, int]]:
    if len(STRUCTURALLY_EXCLUDED_FILENAMES) != 1:
        raise ValueError("bootstrap reconciliation requires the frozen singleton exclusion")
    missing = parse_measurement_filename(STRUCTURALLY_EXCLUDED_FILENAMES[0])
    missing_key = (
        missing.bearing_code,
        missing.setting_code,
        int(missing.measurement_index),
    )
    expected = {
        (bearing, setting.code, measurement)
        for bearing in PRIMARY_BEARING_CODES
        for setting in OPERATING_SETTINGS
        for measurement in MEASUREMENT_INDICES
    }
    if missing_key not in expected:
        raise ValueError("structural exclusion is not a pure Paderborn measurement")
    expected.remove(missing_key)
    if len(expected) != 2_319:
        raise ValueError("retained Paderborn physical key count changed")
    return expected, missing_key


def reconciled_physical_measurements(predictions: pd.DataFrame) -> pd.DataFrame:
    """Apply the sealed physical checks to the exact retained 2,319-row cohort."""

    physical_columns = [
        "block_id",
        "bearing_code",
        "setting_code",
        "measurement_index",
        "environment_id",
        "truth",
        "fold_id",
        "row_index",
    ]
    grouped = predictions.groupby("block_id", sort=True, observed=True)
    if (grouped[physical_columns[1:]].nunique(dropna=False) != 1).any().any():
        raise ValueError("a Paderborn physical block changes metadata across paired models")
    physical = (
        predictions.loc[:, physical_columns]
        .drop_duplicates("block_id")
        .sort_values("block_id", kind="stable")
        .reset_index(drop=True)
    )
    expected_keys, _ = _retained_expected_keys()
    actual_keys = set(
        physical.loc[
            :, ["bearing_code", "setting_code", "measurement_index"]
        ].itertuples(index=False, name=None)
    )
    if actual_keys != expected_keys or len(physical) != 2_319:
        raise ValueError("Paderborn predictions differ from the exact retained measurement set")
    row_indices = physical["row_index"].to_numpy(dtype=np.int64)
    if not np.array_equal(np.sort(row_indices), np.arange(2_319)):
        raise ValueError("Paderborn retained row_index is not compact global 0-based")
    expected_block_ids = (
        physical.loc[:, ["bearing_code", "setting_code", "measurement_index"]]
        .astype(str)
        .agg("|".join, axis=1)
        .to_numpy(dtype=str)
    )
    if not np.array_equal(expected_block_ids, physical["block_id"].to_numpy(dtype=str)):
        raise ValueError("Paderborn block_id differs from its physical measurement key")

    label_map = sealed._official_label_map()
    expected_truth = physical["bearing_code"].map(label_map)
    if expected_truth.isna().any() or not np.array_equal(
        expected_truth.to_numpy(dtype=str), physical["truth"].to_numpy(dtype=str)
    ):
        raise ValueError("Paderborn prediction labels differ from frozen metadata")
    if not np.array_equal(
        physical["environment_id"].to_numpy(dtype=str),
        physical["setting_code"].to_numpy(dtype=str),
    ):
        raise ValueError("Paderborn environment_id must equal the operating setting")

    fold_map = sealed._official_fold_map()
    expected_folds = np.asarray(
        [
            fold_map[(bearing, setting)]
            for bearing, setting in physical.loc[
                :, ["bearing_code", "setting_code"]
            ].itertuples(index=False, name=None)
        ],
        dtype=str,
    )
    if not np.array_equal(expected_folds, physical["fold_id"].to_numpy(dtype=str)):
        raise ValueError("Paderborn target rows do not match the frozen 24-fold manifest")
    paired_counts = predictions.groupby(
        ["method", "seed", "block_id"], sort=False, observed=True
    ).size()
    expected_paired_rows = len(sealed.METHODS) * len(AUDIT_SEEDS) * 2_319
    if len(predictions) != expected_paired_rows or not paired_counts.eq(1).all():
        raise ValueError("each retained block must occur once per paired method and seed")
    return physical


def run_reconciled_bootstrap(
    *,
    target_predictions: Path,
    selection_decisions: Path,
    output_directory: Path,
    reconciliation_spec: Path,
    reconciliation_spec_sha256: str,
    replicates: int,
    seed: int,
    root: Path | None = None,
) -> dict[str, Any]:
    root = (root or project_root()).resolve()
    spec, paths = _load_spec(
        reconciliation_spec,
        expected_sha256=reconciliation_spec_sha256,
        root=root,
    )
    target_predictions = target_predictions.resolve(strict=True)
    selection_decisions = selection_decisions.resolve(strict=True)
    if paths.get("target_predictions") != target_predictions:
        raise ValueError("bootstrap reconciliation spec references other predictions")
    if paths.get("selection_decisions") != selection_decisions:
        raise ValueError("bootstrap reconciliation spec references other decisions")
    if replicates != sealed.BOOTSTRAP_REPLICATES or seed != sealed.BOOTSTRAP_SEED:
        raise ValueError("bootstrap correction cannot change replicate count or seed")

    original = sealed._physical_measurements
    sealed._physical_measurements = reconciled_physical_measurements
    try:
        metrics = sealed.run_paderborn_bootstrap(
            target_predictions,
            selection_decisions,
            output_directory,
            replicates=replicates,
            seed=seed,
        )
    finally:
        sealed._physical_measurements = original

    filtered_predictions, filtered_decisions = sealed._validate_inputs(
        pd.read_parquet(target_predictions),
        pd.read_parquet(selection_decisions),
    )
    sealed._validate_metadata_parity(filtered_predictions, filtered_decisions)
    physical = reconciled_physical_measurements(filtered_predictions)
    counts = physical.groupby("bearing_code", sort=True, observed=True).size()
    expected_keys, missing_key = _retained_expected_keys()
    if len(counts) != 29 or sorted(counts.tolist()) != [79, *([80] * 28)]:
        raise ValueError("retained per-bearing cluster sizes changed")

    metrics["bootstrap_version"] = BOOTSTRAP_VERSION
    metrics["generated_at"] = datetime.now(UTC).isoformat()
    metrics["protocol_document"] = str(paths["reconciliation_protocol"].relative_to(root))
    metrics["input"].update(
        {
            "base_validation": str(paths["base_validation"]),
            "base_validation_sha256": _sha256(paths["base_validation"]),
            "selective_validation": str(paths["selective_validation"]),
            "selective_validation_sha256": _sha256(paths["selective_validation"]),
            "failed_bootstrap_metadata": str(paths["failed_bootstrap_metadata"]),
            "failed_bootstrap_metadata_sha256": _sha256(paths["failed_bootstrap_metadata"]),
        }
    )
    metrics["configuration"]["identity_payload"] = (
        "all retained measurements for each sampled bearing; one disclosed unreadable MAT excluded"
    )
    metrics["contract"] = {
        "pure_bearings": 29,
        "locked_pure_measurements": 2_320,
        "physical_measurements": len(expected_keys),
        "settings": [setting.code for setting in OPERATING_SETTINGS],
        "nominal_measurements_per_bearing_setting": len(MEASUREMENT_INDICES),
        "minimum_retained_measurements_per_bearing": int(counts.min()),
        "maximum_retained_measurements_per_bearing": int(counts.max()),
        "structurally_excluded_measurements": 1,
        "structurally_excluded_key": {
            "bearing_code": missing_key[0],
            "setting_code": missing_key[1],
            "measurement_index": missing_key[2],
        },
    }
    metrics["reconciliation"] = {
        "classification": "post_outcome_pre_bootstrap_statistic_structural_amendment",
        "specification": {
            "path": str(reconciliation_spec.resolve()),
            "sha256": reconciliation_spec_sha256,
        },
        "protocol": {
            "path": str(paths["reconciliation_protocol"]),
            "sha256": _sha256(paths["reconciliation_protocol"]),
        },
        "sealed_bootstrap_source": {
            "path": str(paths["sealed_bootstrap_source"]),
            "sha256": _sha256(paths["sealed_bootstrap_source"]),
        },
        "failed_bootstrap_record": {
            name: {"path": str(paths[name]), "sha256": _sha256(paths[name])}
            for name in (
                "failed_bootstrap_command",
                "failed_bootstrap_metadata",
                "failed_bootstrap_stderr",
            )
        },
        "retained_physical_key_count": len(expected_keys),
        "per_bearing_cluster_size_counts": {
            str(int(size)): int((counts == size).sum()) for size in sorted(counts.unique())
        },
        "d2_bootstrap_outcomes_generated_before_amendment": False,
        "statistical_design_changed": False,
        "model_or_decision_outputs_modified": False,
        "source_spec_attestation": spec["attestation"],
    }
    _write_json(output_directory / "metrics.json", metrics)
    return metrics


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--target-predictions", type=Path, required=True)
    parser.add_argument("--selection-decisions", type=Path, required=True)
    parser.add_argument("--output-directory", type=Path, required=True)
    parser.add_argument("--reconciliation-spec", type=Path, required=True)
    parser.add_argument("--reconciliation-spec-sha256", required=True)
    parser.add_argument("--replicates", type=int, default=sealed.BOOTSTRAP_REPLICATES)
    parser.add_argument("--seed", type=int, default=sealed.BOOTSTRAP_SEED)
    args = parser.parse_args()
    result = run_reconciled_bootstrap(
        target_predictions=args.target_predictions,
        selection_decisions=args.selection_decisions,
        output_directory=args.output_directory,
        reconciliation_spec=args.reconciliation_spec,
        reconciliation_spec_sha256=args.reconciliation_spec_sha256,
        replicates=args.replicates,
        seed=args.seed,
    )
    print(json.dumps(result["paired_comparisons"], ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
