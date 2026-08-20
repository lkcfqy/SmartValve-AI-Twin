"""Metadata-only expected topology for the sealed HUST D3 replication."""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from smartvalve.config import project_root
from smartvalve.data.hust import (
    HUST_INVENTORY_SHA256,
    HUST_LABELS,
    HUST_WINDOWS_PER_RECORDING,
    hust_feature_names,
    select_hust_primary_inventory,
)
from smartvalve.experiments.cranfield_causal_audit import AUDIT_SEEDS
from smartvalve.experiments.dg_expected_manifest import canonical_key_record
from smartvalve.experiments.hust_evaluation import HUST_BOOTSTRAP_DRAWS
from smartvalve.experiments.hust_protocol import (
    HUST_PROTOCOLS,
    HUST_RANDOM_SEED,
    attach_hust_common_cells,
    build_hust_protocol_model_folds,
    build_hust_protocol_splits,
)
from smartvalve.experiments.paderborn_evaluation import (
    METHODS,
    load_sealed_configurations,
)

SCHEMA_VERSION = "smartvalve-hust-d3-expected-manifest-0.1.0"
EXPECTED_FACTORIAL_SEAL_SHA256 = "eb66d23601ba21fe70b125d503ec56c51fbcfc2f5c59d6d1f2bf4335485428ef"
EXPECTED_PROSPECTIVE_SEAL_SHA256 = (
    "b907e1e0e6876e1e35166a526a6d019df83e1587246784588fb0bda44a71efe1"
)
DOWNLOAD_TEMPLATE = (
    "https://data.mendeley.com/public-files/datasets/cbv7jyx4p9/files/{file_id}/file_downloaded"
)
EXPECTED_COUNTS = {
    "recordings": 45,
    "physical_bearings": 15,
    "window_rows": 450,
    "protocols": 4,
    "folds": 28,
    "fit_count": 1_260,
    "dann_auxiliary_states": 140,
    "seed_window_predictions": 81_000,
    "ensemble_window_predictions": 16_200,
    "recording_predictions": 1_620,
    "aggregate_metrics": 36,
    "cell_metrics": 540,
    "protocol_effects": 135,
    "ranking_concordance": 12,
    "bootstrap_summary": 27,
    "bootstrap_draws": 135_000,
    "bootstrap_draw_plan": 5_000,
    "rank_shifts": 54,
    "method_minus_erm": 108,
    "confusion_counts": 324,
    "recording_diagnostics": 36,
}
KEY_SCHEMAS = {
    "training_fits": ("protocol", "method", "seed", "fold_id"),
    "seed_window_predictions": (
        "protocol",
        "method",
        "seed",
        "fold_id",
        "row_index",
        "filename",
        "bearing_code",
        "specification_group",
        "load_w",
        "truth",
        "window_index",
    ),
    "ensemble_window_predictions": ("protocol", "method", "row_index"),
    "recording_predictions": ("protocol", "method", "filename"),
}
SOURCE_PATHS = (
    "research/HUST_D3_FACTORIAL_SEAL.md",
    "research/HUST_D3_PREACCESS_CLARIFICATION.md",
    "scripts/acquire_hust_d3_primary.py",
    "scripts/extract_hust_d3_features.py",
    "scripts/hust_d3_expected_manifest.py",
    "scripts/hust_d3_neural_evaluation.py",
    "scripts/seal_hust_d3_execution.py",
    "scripts/validate_hust_d3_artifacts.py",
    "src/smartvalve/data/hust.py",
    "src/smartvalve/experiments/hust_protocol.py",
    "src/smartvalve/experiments/hust_evaluation.py",
    "src/smartvalve/experiments/hust_expected_manifest.py",
    "src/smartvalve/experiments/hust_artifact_validation.py",
    "tests/test_hust_d3_protocol.py",
    "tests/test_hust_evaluation.py",
    "tests/test_hust_expected_manifest.py",
    "tests/test_hust_artifact_validation.py",
)


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def verify_sha256(path: Path, expected: str, role: str) -> str:
    if not path.is_file():
        raise FileNotFoundError(path)
    observed = file_sha256(path)
    if observed != expected:
        raise ValueError(f"{role} SHA-256 changed: expected {expected}, observed {observed}")
    return observed


def metadata_window_frame(primary: pd.DataFrame) -> pd.DataFrame:
    """Create the complete window identity frame without opening a signal file."""

    records = []
    features = hust_feature_names()
    for row in primary.itertuples(index=False):
        for window_index in range(HUST_WINDOWS_PER_RECORDING):
            record: dict[str, Any] = {
                "filename": str(row.filename),
                "bearing_code": str(row.bearing_code),
                "specification_group": int(row.specification_group),
                "load_w": int(row.load_w),
                "truth": str(row.truth),
                "window_index": window_index,
            }
            record.update(dict.fromkeys(features, 0.0))
            records.append(record)
    return attach_hust_common_cells(pd.DataFrame(records))


def _string_set_sha256(values: pd.Series) -> str:
    payload = "\n".join(sorted(values.astype(str))) + "\n"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _split_manifest(frame: pd.DataFrame) -> pd.DataFrame:
    folds = build_hust_protocol_model_folds(frame, random_seed=HUST_RANDOM_SEED)
    splits = build_hust_protocol_splits(frame, random_seed=HUST_RANDOM_SEED)
    records = []
    for protocol in HUST_PROTOCOLS:
        for split, model_fold in zip(splits[protocol], folds[protocol], strict=True):
            partitions = {
                name: frame.iloc[indices]
                for name, indices in (
                    ("source", split.source_indices),
                    ("target", split.target_indices),
                    ("quarantine", split.quarantine_indices),
                )
            }
            records.append(
                {
                    "protocol": protocol,
                    "fold_id": split.fold_id,
                    **{f"{name}_windows": len(rows) for name, rows in partitions.items()},
                    **{
                        f"{name}_recordings": rows["filename"].nunique()
                        for name, rows in partitions.items()
                    },
                    **{
                        f"{name}_filenames_sha256": _string_set_sha256(
                            rows.drop_duplicates("filename")["filename"]
                        )
                        for name, rows in partitions.items()
                    },
                    "source_nuisance_pairs": len(model_fold.fold.nuisance_pairs),
                    "source_fault_pairs": len(model_fold.fold.fault_pairs),
                }
            )
    result = pd.DataFrame(records)
    if len(result) != EXPECTED_COUNTS["folds"]:
        raise ValueError("HUST expected fold count changed")
    return result


def _expected_keys(frame: pd.DataFrame) -> dict[str, dict[str, Any]]:
    splits = build_hust_protocol_splits(frame, random_seed=HUST_RANDOM_SEED)
    rows: dict[str, list[tuple[Any, ...]]] = {name: [] for name in KEY_SCHEMAS}
    for protocol in HUST_PROTOCOLS:
        for split in splits[protocol]:
            target = frame.iloc[split.target_indices]
            for method in METHODS:
                rows["recording_predictions"].extend(
                    (protocol, method, str(filename))
                    for filename in target["filename"].drop_duplicates()
                )
                rows["ensemble_window_predictions"].extend(
                    (protocol, method, int(row_index)) for row_index in split.target_indices
                )
                for seed in AUDIT_SEEDS:
                    rows["training_fits"].append((protocol, method, int(seed), split.fold_id))
                    rows["seed_window_predictions"].extend(
                        (
                            protocol,
                            method,
                            int(seed),
                            split.fold_id,
                            int(row_index),
                            str(metadata.filename),
                            str(metadata.bearing_code),
                            int(metadata.specification_group),
                            int(metadata.load_w),
                            str(metadata.truth),
                            int(metadata.window_index),
                        )
                        for row_index, metadata in zip(
                            split.target_indices,
                            target.itertuples(index=False),
                            strict=True,
                        )
                    )
    result = {
        name: canonical_key_record(values, KEY_SCHEMAS[name]) for name, values in rows.items()
    }
    count_links = {
        "training_fits": "fit_count",
        "seed_window_predictions": "seed_window_predictions",
        "ensemble_window_predictions": "ensemble_window_predictions",
        "recording_predictions": "recording_predictions",
    }
    for name, count_name in count_links.items():
        if result[name]["count"] != EXPECTED_COUNTS[count_name]:
            raise ValueError(f"HUST expected key count changed: {name}")
    return result


def _source_records(root: Path) -> dict[str, dict[str, Any]]:
    records = {}
    for relative in SOURCE_PATHS:
        path = (root / relative).resolve(strict=True)
        records[relative] = {
            "bytes": path.stat().st_size,
            "sha256": file_sha256(path),
        }
    return records


def build_hust_expected_manifest(
    *,
    inventory: Path,
    factorial_seal: Path,
    prospective_seal: Path,
    clarification: Path,
    expected_clarification_sha256: str,
    output_directory: Path,
    root: Path | None = None,
) -> dict[str, Any]:
    root = (root or project_root()).resolve()
    input_hashes = {
        "official_inventory": verify_sha256(
            inventory, HUST_INVENTORY_SHA256, "HUST official inventory"
        ),
        "factorial_seal": verify_sha256(
            factorial_seal, EXPECTED_FACTORIAL_SEAL_SHA256, "HUST factorial seal"
        ),
        "prospective_configuration_seal": verify_sha256(
            prospective_seal,
            EXPECTED_PROSPECTIVE_SEAL_SHA256,
            "D0/D1 prospective configuration seal",
        ),
        "preaccess_clarification": verify_sha256(
            clarification,
            expected_clarification_sha256,
            "HUST pre-access clarification",
        ),
    }
    output_directory.mkdir(parents=True, exist_ok=True)
    if any(output_directory.iterdir()):
        raise ValueError("output directory must be empty")
    primary = select_hust_primary_inventory(pd.read_csv(inventory))
    frame = metadata_window_frame(primary)
    configurations, candidate_ids, development_hashes = load_sealed_configurations(
        root, json.loads(prospective_seal.read_text(encoding="utf-8"))
    )
    if tuple(configurations) != METHODS:
        raise ValueError("HUST method order differs from the sealed configuration suite")

    file_manifest = primary.loc[
        :,
        [
            "filename",
            "file_id",
            "condition",
            "specification_group",
            "load_w",
            "bearing_code",
            "truth",
            "bytes",
            "sha256",
        ],
    ].copy()
    file_manifest.insert(
        2,
        "download_url",
        file_manifest["file_id"].map(lambda value: DOWNLOAD_TEMPLATE.format(file_id=value)),
    )
    window_manifest = frame.loc[
        :,
        [
            "filename",
            "bearing_code",
            "specification_group",
            "load_w",
            "truth",
            "window_index",
            "evaluation_cell",
        ],
    ].copy()
    window_manifest.insert(0, "row_index", np.arange(len(window_manifest), dtype=int))
    split_manifest = _split_manifest(frame)
    paths = {
        "primary_file_manifest.csv": file_manifest,
        "window_metadata_manifest.csv": window_manifest,
        "split_manifest.csv": split_manifest,
    }
    for filename, table in paths.items():
        table.to_csv(output_directory / filename, index=False, lineterminator="\n")
    output_hashes = {filename: file_sha256(output_directory / filename) for filename in paths}
    manifest = {
        "schema_version": SCHEMA_VERSION,
        "status": "sealed_metadata_only_before_hust_signal_access",
        "role": "expected identities and counts; contains no signal values or model outcomes",
        "input_sha256": input_hashes,
        "signal_access_at_manifest": {
            "mat_files_downloaded": 0,
            "mat_files_opened": 0,
            "signal_bytes_read": 0,
        },
        "class_semantics": {
            "probability_order": list(HUST_LABELS),
            "condition_order": ["N", "O", "I"],
            "mapping": {"N": "healthy", "O": "outer", "I": "inner"},
        },
        "configuration": {
            "protocols": list(HUST_PROTOCOLS),
            "methods": list(METHODS),
            "seeds": [int(seed) for seed in AUDIT_SEEDS],
            "random_seed": HUST_RANDOM_SEED,
            "bootstrap_draws": HUST_BOOTSTRAP_DRAWS,
            "candidate_ids": candidate_ids,
            "selected_configurations": {
                method: asdict(configurations[method]) for method in METHODS
            },
            "development_hashes": development_hashes,
        },
        "expected_counts": EXPECTED_COUNTS,
        "expected_key_sets": _expected_keys(frame),
        "metadata_artifacts_sha256": output_hashes,
        "source_artifacts": _source_records(root),
    }
    (output_directory / "expected_manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return manifest
