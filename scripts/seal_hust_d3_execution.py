#!/usr/bin/env python3
"""Seal HUST D3 after structural feature checks and before any model outcome."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from smartvalve.config import project_root
from smartvalve.data.hust import hust_feature_names
from smartvalve.experiments.hust_expected_manifest import (
    EXPECTED_COUNTS,
    EXPECTED_FACTORIAL_SEAL_SHA256,
    EXPECTED_PROSPECTIVE_SEAL_SHA256,
    file_sha256,
    verify_sha256,
)
from smartvalve.experiments.hust_expected_manifest import (
    SCHEMA_VERSION as EXPECTED_MANIFEST_SCHEMA,
)
from smartvalve.experiments.hust_protocol import attach_hust_common_cells

RUN_VERSION = "smartvalve-hust-d3-execution-seal-0.1.0"
AMENDED_SOURCE = "scripts/seal_hust_d3_execution.py"


def _write_json(path: Path, value: Any) -> None:
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _verify_recorded_sources(manifest: dict[str, Any], root: Path) -> dict[str, dict[str, Any]]:
    records = manifest.get("source_artifacts")
    if not isinstance(records, dict) or not records:
        raise ValueError("HUST expected manifest has no source-artifact lock")
    amendments = {}
    for relative, record in records.items():
        path = (root / relative).resolve(strict=True)
        if root != path and root not in path.parents:
            raise ValueError("HUST source-artifact path escapes project root")
        if relative == AMENDED_SOURCE:
            observed = {"bytes": path.stat().st_size, "sha256": file_sha256(path)}
            if observed == record:
                raise ValueError("HUST execution amendment did not change its declared source")
            amendments[relative] = {"preaccess": record, "amended": observed}
            continue
        if path.stat().st_size != record.get("bytes") or file_sha256(path) != record.get("sha256"):
            raise ValueError(f"HUST source artifact changed after manifest: {relative}")
    if set(amendments) != {AMENDED_SOURCE}:
        raise ValueError("HUST execution amendment source exception changed")
    return amendments


def _validate_expected_artifacts(directory: Path, manifest: dict[str, Any]) -> None:
    for filename, expected in manifest.get("metadata_artifacts_sha256", {}).items():
        verify_sha256(directory / filename, str(expected), f"HUST expected {filename}")


def _validate_feature_artifacts(
    feature_directory: Path,
    expected_directory: Path,
) -> tuple[pd.DataFrame, dict[str, Any], dict[str, str]]:
    summary_path = feature_directory / "feature_summary.json"
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    if (
        summary.get("status") != "features_complete_no_model_outcomes"
        or summary.get("recordings") != EXPECTED_COUNTS["recordings"]
        or summary.get("physical_bearings") != EXPECTED_COUNTS["physical_bearings"]
        or summary.get("rows") != EXPECTED_COUNTS["window_rows"]
        or summary.get("features") != len(hust_feature_names())
    ):
        raise ValueError("HUST feature summary differs from the sealed dimensions")
    filenames = ("feature_matrix.parquet", "mat_structure.csv", "split_topology.csv")
    hashes = {}
    for filename in filenames:
        expected = str(summary.get("output_sha256", {}).get(filename, ""))
        hashes[filename] = verify_sha256(
            feature_directory / filename, expected, f"HUST feature {filename}"
        )
    frame = attach_hust_common_cells(pd.read_parquet(feature_directory / "feature_matrix.parquet"))
    features = frame.loc[:, hust_feature_names()].to_numpy(dtype=float)
    if features.shape != (450, 24) or not np.isfinite(features).all():
        raise ValueError("HUST feature matrix violates structural/finite checks")

    expected_metadata = pd.read_csv(expected_directory / "window_metadata_manifest.csv")
    actual_metadata = frame.reset_index(drop=True)
    actual_metadata.insert(0, "row_index", np.arange(len(actual_metadata), dtype=int))
    actual_metadata = actual_metadata.loc[:, expected_metadata.columns]
    pd.testing.assert_frame_equal(
        actual_metadata,
        expected_metadata,
        check_dtype=False,
        check_like=False,
    )
    expected_splits = pd.read_csv(expected_directory / "split_manifest.csv")
    actual_splits = pd.read_csv(feature_directory / "split_topology.csv")
    shared = [column for column in actual_splits if column in expected_splits]
    if set(shared) != set(actual_splits):
        raise ValueError("HUST extracted split topology has an unexpected column")
    pd.testing.assert_frame_equal(
        actual_splits.reset_index(drop=True),
        expected_splits.loc[:, shared].reset_index(drop=True),
        check_dtype=False,
    )
    structures = pd.read_csv(feature_directory / "mat_structure.csv")
    if (
        len(structures) != 45
        or structures["filename"].nunique() != 45
        or not structures["sample_count"].eq(512_000).all()
        or not structures["window_count"].eq(10).all()
        or not structures["feature_count"].eq(24).all()
    ):
        raise ValueError("HUST MAT structural inventory differs from the seal")
    hashes["feature_summary.json"] = file_sha256(summary_path)
    return frame, summary, hashes


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--inventory", type=Path, required=True)
    parser.add_argument("--factorial-seal", type=Path, required=True)
    parser.add_argument("--clarification", type=Path, required=True)
    parser.add_argument("--execution-amendment", type=Path, required=True)
    parser.add_argument("--execution-amendment-sha256", required=True)
    parser.add_argument("--prospective-seal", type=Path, required=True)
    parser.add_argument("--expected-manifest-dir", type=Path, required=True)
    parser.add_argument("--expected-manifest-sha256", required=True)
    parser.add_argument("--feature-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    return parser


def main() -> int:
    arguments = build_parser().parse_args()
    root = project_root().resolve()
    expected_path = arguments.expected_manifest_dir / "expected_manifest.json"
    expected_hash = verify_sha256(
        expected_path,
        arguments.expected_manifest_sha256,
        "HUST expected manifest",
    )
    manifest = json.loads(expected_path.read_text(encoding="utf-8"))
    if (
        manifest.get("schema_version") != EXPECTED_MANIFEST_SCHEMA
        or manifest.get("status") != "sealed_metadata_only_before_hust_signal_access"
        or manifest.get("expected_counts") != EXPECTED_COUNTS
    ):
        raise ValueError("HUST expected manifest identity or counts changed")
    input_hashes = manifest.get("input_sha256", {})
    verify_sha256(
        arguments.inventory,
        str(input_hashes.get("official_inventory")),
        "HUST official inventory",
    )
    verify_sha256(
        arguments.factorial_seal,
        EXPECTED_FACTORIAL_SEAL_SHA256,
        "HUST factorial seal",
    )
    verify_sha256(
        arguments.prospective_seal,
        EXPECTED_PROSPECTIVE_SEAL_SHA256,
        "D0/D1 prospective configuration seal",
    )
    verify_sha256(
        arguments.clarification,
        str(input_hashes.get("preaccess_clarification")),
        "HUST pre-access clarification",
    )
    amendment_hash = verify_sha256(
        arguments.execution_amendment,
        arguments.execution_amendment_sha256,
        "HUST execution-only amendment 001",
    )
    amended_sources = _verify_recorded_sources(manifest, root)
    _validate_expected_artifacts(arguments.expected_manifest_dir, manifest)
    frame, feature_summary, feature_hashes = _validate_feature_artifacts(
        arguments.feature_dir,
        arguments.expected_manifest_dir,
    )
    if arguments.output.exists():
        raise ValueError("HUST execution-seal output already exists")
    arguments.output.parent.mkdir(parents=True, exist_ok=True)
    seal = {
        "schema_version": RUN_VERSION,
        "status": "sealed_after_features_before_model_outcomes",
        "original_factorial_seal_sha256": EXPECTED_FACTORIAL_SEAL_SHA256,
        "preaccess_clarification_sha256": input_hashes["preaccess_clarification"],
        "execution_amendment": {
            "path": str(arguments.execution_amendment.resolve()),
            "sha256": amendment_hash,
            "failed_run": "EXP-442-HUST-D3-EXECUTION-SEAL",
            "authorized_source_overrides": amended_sources,
        },
        "prospective_configuration_seal_sha256": EXPECTED_PROSPECTIVE_SEAL_SHA256,
        "expected_manifest": {
            "path": str(expected_path.resolve()),
            "sha256": expected_hash,
        },
        "feature_matrix": {
            "path": str((arguments.feature_dir / "feature_matrix.parquet").resolve()),
            "sha256": feature_hashes["feature_matrix.parquet"],
            "rows": len(frame),
            "features": len(hust_feature_names()),
        },
        "feature_artifacts": feature_hashes,
        "feature_input_sha256": feature_summary["inputs_sha256"],
        "expected_metadata_artifacts_sha256": manifest["metadata_artifacts_sha256"],
        "source_artifacts": manifest["source_artifacts"],
        "attestation": {
            "official_primary_mat_files_downloaded": 45,
            "official_primary_mat_files_opened_for_structural_extraction": 45,
            "model_fits_completed": 0,
            "model_predictions_emitted": 0,
            "model_outcomes_inspected": False,
            "signal_descriptive_statistics_inspected": False,
            "configuration_reselection_performed": False,
            "target_guided_feature_or_protocol_change_performed": False,
        },
        "authorization": {
            "one_shot_hust_d3_model_evaluation_permitted": True,
            "configuration_search_permitted": False,
            "rerun_after_valid_completion_permitted": False,
        },
    }
    _write_json(arguments.output, seal)
    print(
        json.dumps(
            {
                "status": seal["status"],
                "feature_matrix_sha256": seal["feature_matrix"]["sha256"],
                "expected_manifest_sha256": expected_hash,
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
