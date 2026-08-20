"""Independently validate the sealed Paderborn feature artifacts before D2 fitting."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from smartvalve.data.paderborn import ARCHIVE_NAMES
from smartvalve.data.paderborn_features import (
    MAIN_SIGNAL_ENDPOINT_POLICY,
    MAXIMUM_STORED_SAMPLES_PER_MAIN_SIGNAL,
    MINIMUM_STORED_SAMPLES_PER_MAIN_SIGNAL,
    SAMPLES_PER_MAIN_SIGNAL,
    STRUCTURALLY_EXCLUDED_FILENAMES,
    expected_measurement_filenames,
    main_signal_feature_names,
    retained_measurement_filenames,
)
from smartvalve.experiments.paderborn_domain import (
    build_paderborn_model_folds,
    validate_paderborn_feature_frame,
)

VALIDATION_VERSION = "paderborn-feature-artifact-validation-0.1.0"
EXPECTED_STATUS = "sealed_paderborn_features_complete_without_model_outcome_access"
EXPECTED_EXCLUDED_BYTES = 8_714_872
EXPECTED_EXCLUDED_SHA256 = "e137cbb2368caa8bd56889eff8609d2569d2c196a85107e16aa4740437f2ccb3"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(4 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _artifact_path(metrics_path: Path, record: Any, role: str) -> Path:
    if not isinstance(record, dict):
        raise ValueError(f"missing Paderborn feature artifact: {role}")
    relative = Path(str(record.get("path", "")))
    if relative.is_absolute() or ".." in relative.parts:
        raise ValueError(f"unsafe Paderborn feature artifact path: {role}")
    root = metrics_path.parent.resolve()
    path = (root / relative).resolve(strict=True)
    if root != path and root not in path.parents:
        raise ValueError(f"Paderborn feature artifact escaped its run: {role}")
    if path.stat().st_size != record.get("bytes") or _sha256(path) != record.get("sha256"):
        raise ValueError(f"Paderborn feature artifact changed: {role}")
    return path


def validate_paderborn_feature_artifacts(
    *,
    metrics_path: Path,
    expected_metrics_sha256: str,
    expected_feature_amendment_sha256: str,
) -> dict[str, Any]:
    metrics_path = metrics_path.resolve(strict=True)
    if _sha256(metrics_path) != expected_metrics_sha256:
        raise ValueError("Paderborn feature metrics SHA-256 mismatch")
    metrics = json.loads(metrics_path.read_text(encoding="utf-8"))
    if metrics.get("status") != EXPECTED_STATUS:
        raise ValueError("Paderborn feature run did not report its sealed success status")
    if (
        metrics.get("input", {}).get("feature_contract_amendment_sha256")
        != expected_feature_amendment_sha256
    ):
        raise ValueError("Paderborn features reference a different amendment")
    access = metrics.get("access_attestation", {})
    if (
        access.get("model_fitted") is not False
        or access.get("model_outcomes_inspected") is not False
        or access.get("target_guided_reselection_performed") is not False
        or access.get("quarantined_non_mat_files_used") is not False
    ):
        raise ValueError("Paderborn features crossed the outcome-blind access boundary")

    artifact_records = metrics.get("artifacts", {})
    required_roles = {
        "feature_matrix",
        "primary_feature_matrix",
        "mat_inventory",
        "extraction_traces",
        "quarantined_non_mat",
    }
    if set(artifact_records) != required_roles:
        raise ValueError("Paderborn feature artifact roles changed")
    paths = {
        role: _artifact_path(metrics_path, artifact_records[role], role) for role in required_roles
    }
    full = pd.read_parquet(paths["feature_matrix"]).reset_index(drop=True)
    primary = pd.read_parquet(paths["primary_feature_matrix"]).reset_index(drop=True)
    inventory = pd.read_parquet(paths["mat_inventory"]).reset_index(drop=True)
    traces = json.loads(paths["extraction_traces"].read_text(encoding="utf-8"))
    quarantined = json.loads(paths["quarantined_non_mat"].read_text(encoding="utf-8"))

    all_expected = expected_measurement_filenames()
    retained_expected = retained_measurement_filenames()
    if tuple(full["filename"].astype(str)) != retained_expected:
        raise ValueError("Paderborn feature rows differ from the retained filename order")
    if tuple(inventory["filename"].astype(str)) != all_expected:
        raise ValueError("Paderborn MAT inventory differs from the locked filename order")
    derived_primary = full.loc[full["truth"] != "compound"].reset_index(drop=True)
    if not primary.equals(derived_primary):
        raise ValueError("Paderborn primary matrix is not the exact pure-class subset")
    if len(full) != 2_559 or len(primary) != 2_319 or len(derived_primary) != 2_319:
        raise ValueError("Paderborn retained cohort counts changed")
    if int((full["truth"] == "compound").sum()) != 240:
        raise ValueError("Paderborn compound stress-set count changed")
    if tuple(column for column in full if "__" in column) != main_signal_feature_names():
        raise ValueError("Paderborn feature column order changed")
    validate_paderborn_feature_frame(primary)
    feature_values = full.loc[:, main_signal_feature_names()].to_numpy(dtype=float)
    if not np.isfinite(feature_values).all():
        raise ValueError("Paderborn full feature matrix contains non-finite values")

    included = inventory.loc[inventory["feature_status"] == "included"].reset_index(drop=True)
    excluded = inventory.loc[
        inventory["feature_status"] == "structurally_excluded_unreadable_mat"
    ].reset_index(drop=True)
    if tuple(included["filename"].astype(str)) != retained_expected:
        raise ValueError("Paderborn included inventory differs from feature rows")
    if tuple(excluded["filename"].astype(str)) != STRUCTURALLY_EXCLUDED_FILENAMES:
        raise ValueError("Paderborn structural exclusion set changed")
    if (
        int(excluded.iloc[0]["bytes"]) != EXPECTED_EXCLUDED_BYTES
        or str(excluded.iloc[0]["sha256"]) != EXPECTED_EXCLUDED_SHA256
        or not pd.isna(excluded.iloc[0]["stored_samples_per_channel"])
        or not pd.isna(excluded.iloc[0]["retained_samples_per_channel"])
    ):
        raise ValueError("Paderborn excluded MAT identity or null policy changed")
    stored = included["stored_samples_per_channel"].to_numpy(dtype=np.int64)
    retained = included["retained_samples_per_channel"].to_numpy(dtype=np.int64)
    if (
        stored.min() != MINIMUM_STORED_SAMPLES_PER_MAIN_SIGNAL
        or stored.max() != MAXIMUM_STORED_SAMPLES_PER_MAIN_SIGNAL
        or not np.all(retained == SAMPLES_PER_MAIN_SIGNAL)
    ):
        raise ValueError("Paderborn stored/retained sample contract changed")

    if (
        not isinstance(traces, list)
        or [row.get("archive_filename") for row in traces] != list(ARCHIVE_NAMES)
        or any(row.get("exit_code") != 0 for row in traces)
    ):
        raise ValueError("Paderborn extraction traces changed")
    if (
        not isinstance(quarantined, list)
        or len(quarantined) != 64
        or any(row.get("handling") != "quarantined_not_parsed_not_used" for row in quarantined)
    ):
        raise ValueError("Paderborn non-MAT quarantine changed")

    folds = build_paderborn_model_folds(primary)
    target_counts = np.zeros(len(primary), dtype=np.int64)
    for fold in folds:
        target_counts[fold.target_global_indices] += 1
    if len(folds) != 24 or not np.all(target_counts == 1):
        raise ValueError("Paderborn amended target topology is incomplete")

    corpus = metrics.get("corpus", {})
    expected_corpus = {
        "measurement_count": len(full),
        "locked_mat_count": len(inventory),
        "structurally_excluded_mat_count": len(excluded),
        "primary_measurement_count": len(primary),
        "compound_measurement_count": 240,
        "feature_count": len(main_signal_feature_names()),
        "model_fold_count": len(folds),
        "quarantined_non_mat_count": len(quarantined),
    }
    if any(int(corpus.get(name, -1)) != value for name, value in expected_corpus.items()):
        raise ValueError("Paderborn metrics corpus summary changed")
    if corpus.get("endpoint_policy") != MAIN_SIGNAL_ENDPOINT_POLICY:
        raise ValueError("Paderborn feature normalization policy changed")

    return {
        "validation_version": VALIDATION_VERSION,
        "status": "passed_before_paderborn_model_outcome_access",
        "input": {
            "feature_metrics": str(metrics_path),
            "feature_metrics_sha256": expected_metrics_sha256,
            "feature_amendment_sha256": expected_feature_amendment_sha256,
        },
        "counts": {
            **expected_corpus,
            "outer_fold_count": len(folds),
            "minimum_target_coverage": int(target_counts.min()),
            "maximum_target_coverage": int(target_counts.max()),
        },
        "structural_exclusion": {
            "filenames": list(STRUCTURALLY_EXCLUDED_FILENAMES),
            "bytes": EXPECTED_EXCLUDED_BYTES,
            "sha256": EXPECTED_EXCLUDED_SHA256,
        },
        "artifacts": {
            role: {
                "path": str(paths[role]),
                "bytes": paths[role].stat().st_size,
                "sha256": _sha256(paths[role]),
            }
            for role in sorted(paths)
        },
        "access_attestation": {
            "feature_values_checked_only_for_schema_and_finiteness": True,
            "feature_statistics_emitted": False,
            "model_fitted": False,
            "model_outcomes_inspected": False,
            "target_guided_reselection_performed": False,
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--metrics", type=Path, required=True)
    parser.add_argument("--metrics-sha256", required=True)
    parser.add_argument("--feature-amendment-sha256", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = validate_paderborn_feature_artifacts(
        metrics_path=args.metrics,
        expected_metrics_sha256=args.metrics_sha256,
        expected_feature_amendment_sha256=args.feature_amendment_sha256,
    )
    output = args.output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(result["counts"], ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
