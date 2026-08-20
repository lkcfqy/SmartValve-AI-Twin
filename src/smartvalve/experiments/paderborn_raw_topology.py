"""Outcome-blind expected topology and post-fit audit for the raw sensitivity run."""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from sklearn.model_selection import StratifiedKFold

from smartvalve.experiments.dg_expected_manifest import canonical_key_record
from smartvalve.experiments.paderborn_expected_manifest import metadata_only_indices
from smartvalve.experiments.paderborn_partitions import build_paderborn_partitions
from smartvalve.experiments.paderborn_protocol_contrast import PROBABILITY_COLUMNS
from smartvalve.experiments.paderborn_raw_sensitivity import (
    RAW_MODELS,
    RAW_PROTOCOLS,
    RAW_SEEDS,
    WINDOWS_PER_RECORD,
)
from smartvalve.experiments.paderborn_splits import PADERBORN_IDENTITY_FOLDS

MANIFEST_VERSION = "smartvalve-paderborn-raw-topology-manifest-0.1.0"
VALIDATION_VERSION = "smartvalve-paderborn-raw-topology-validation-0.1.0"
RANDOM_SEED = 20_260_819
RANDOM_FOLD_COUNT = 6
EXPECTED_WINDOW_OFFSETS = (0, 82_603, 165_205, 247_808)
BASE_METADATA = (
    "filename",
    "bearing_code",
    "setting_code",
    "measurement_index",
    "truth",
)
PHYSICAL_METADATA = (
    *BASE_METADATA,
    "identity_fold_id",
    "evaluation_cell",
)
KEY_SCHEMAS = {
    "window_predictions": (
        "protocol",
        "method",
        "seed",
        "fold_id",
        "window_row_index",
        "row_index",
        "window_index",
        *PHYSICAL_METADATA,
    ),
    "seed_recording_predictions": (
        "protocol",
        "method",
        "seed",
        "fold_id",
        "row_index",
        *PHYSICAL_METADATA,
    ),
    "ensemble_recording_predictions": (
        "protocol",
        "method",
        "fold_id",
        "row_index",
        *PHYSICAL_METADATA,
    ),
    "fits": (
        "protocol",
        "method",
        "seed",
        "fold_id",
        "source_record_count",
        "source_window_count",
        "target_record_count",
        "target_window_count",
        "quarantine_record_count",
    ),
    "training_traces": ("protocol", "method", "seed", "fold_id"),
}


def sha256_file(path: Path) -> str:
    """Hash a file in bounded chunks."""

    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(4 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _verify(path: Path, expected: str, role: str) -> str:
    if not path.is_file():
        raise FileNotFoundError(path)
    observed = sha256_file(path)
    if observed != expected:
        raise ValueError(f"{role} SHA-256 changed: expected {expected}, observed {observed}")
    return observed


def _attach_identity_cells(metadata: pd.DataFrame) -> pd.DataFrame:
    lookup = {
        bearing: fold.fold_id
        for fold in PADERBORN_IDENTITY_FOLDS
        for bearing in fold.bearing_codes
    }
    result = metadata.reset_index(drop=True).copy()
    result["identity_fold_id"] = result["bearing_code"].map(lookup)
    if result["identity_fold_id"].isna().any():
        raise ValueError("raw topology metadata contains an unknown bearing identity")
    result["identity_fold_id"] = result["identity_fold_id"].astype(str)
    result["evaluation_cell"] = (
        result["identity_fold_id"] + "|setting=" + result["setting_code"].astype(str)
    )
    if result["evaluation_cell"].nunique() != 24:
        raise ValueError("raw topology metadata does not contain 24 physical cells")
    return result


def authoritative_metadata(features_path: Path) -> pd.DataFrame:
    """Read only provenance columns and compare them with the metadata-only cohort."""

    observed = pd.read_parquet(features_path, columns=list(BASE_METADATA)).reset_index(drop=True)
    expected, _ = metadata_only_indices()
    expected = expected.loc[:, BASE_METADATA].reset_index(drop=True)
    if len(observed) != 2_319 or len(expected) != len(observed):
        raise ValueError("raw topology authoritative record count changed")
    for column in BASE_METADATA:
        left = observed[column].to_numpy()
        right = expected[column].to_numpy()
        if column == "measurement_index":
            equal = np.array_equal(left.astype(np.int64), right.astype(np.int64))
        else:
            equal = np.array_equal(left.astype(str), right.astype(str))
        if not equal:
            raise ValueError(f"raw topology feature metadata changed: {column}")
    return _attach_identity_cells(expected)


def validate_window_index(window_index: pd.DataFrame, metadata: pd.DataFrame) -> pd.DataFrame:
    """Verify every record has the four frozen windows and exact physical metadata."""

    required = {
        "window_row_index",
        "row_index",
        "window_index",
        "sample_offset",
        *BASE_METADATA,
    }
    missing = required - set(window_index)
    if missing:
        raise ValueError(f"raw topology window index lacks columns: {sorted(missing)}")
    ordered = window_index.sort_values("window_row_index", kind="stable").reset_index(drop=True)
    expected_rows = len(metadata) * WINDOWS_PER_RECORD
    if len(ordered) != expected_rows or not np.array_equal(
        ordered["window_row_index"].to_numpy(dtype=np.int64),
        np.arange(expected_rows, dtype=np.int64),
    ):
        raise ValueError("raw topology window-row coordinates changed")
    if set(ordered["row_index"].astype(int)) != set(range(len(metadata))):
        raise ValueError("raw topology window index does not cover every record")
    for _, rows in ordered.groupby("row_index", sort=True, observed=True):
        if not np.array_equal(
            rows["window_index"].to_numpy(dtype=np.int64),
            np.arange(WINDOWS_PER_RECORD, dtype=np.int64),
        ) or not np.array_equal(
            rows["sample_offset"].to_numpy(dtype=np.int64),
            np.asarray(EXPECTED_WINDOW_OFFSETS, dtype=np.int64),
        ):
            raise ValueError("raw topology per-record window positions changed")
    row_coordinates = ordered["row_index"].to_numpy(dtype=np.int64)
    expected_metadata = metadata.iloc[row_coordinates].reset_index(drop=True)
    for column in BASE_METADATA:
        left = ordered[column].to_numpy()
        right = expected_metadata[column].to_numpy()
        if column == "measurement_index":
            equal = np.array_equal(left.astype(np.int64), right.astype(np.int64))
        else:
            equal = np.array_equal(left.astype(str), right.astype(str))
        if not equal:
            raise ValueError(f"raw topology window metadata changed: {column}")
    return ordered


def _protocol_partitions(metadata: pd.DataFrame) -> dict[str, list[dict[str, Any]]]:
    row_count = len(metadata)
    all_rows = np.arange(row_count, dtype=np.int64)
    random_folds: list[dict[str, Any]] = []
    splitter = StratifiedKFold(
        n_splits=RANDOM_FOLD_COUNT,
        shuffle=True,
        random_state=RANDOM_SEED,
    )
    for fold_number, (_, target) in enumerate(
        splitter.split(np.zeros(row_count), metadata["truth"].to_numpy(dtype=str))
    ):
        target = np.sort(target.astype(np.int64, copy=False))
        random_folds.append(
            {
                "fold_id": f"random={fold_number}",
                "source": np.setdiff1d(all_rows, target, assume_unique=True),
                "target": target,
                "quarantine": np.empty(0, dtype=np.int64),
            }
        )
    crossed_folds = [
        {
            "fold_id": partition.fold_id,
            "source": partition.source_indices.astype(np.int64, copy=False),
            "target": partition.target_indices.astype(np.int64, copy=False),
            "quarantine": partition.quarantine_indices.astype(np.int64, copy=False),
        }
        for partition in build_paderborn_partitions(metadata)
    ]
    result = {
        "measurement_random": random_folds,
        "crossed_holdout": crossed_folds,
    }
    if tuple(result) != RAW_PROTOCOLS or (len(random_folds), len(crossed_folds)) != (6, 24):
        raise ValueError("raw topology protocol family changed")
    for protocol, folds in result.items():
        target_counts = np.zeros(row_count, dtype=np.int64)
        for fold in folds:
            coordinates = np.concatenate(
                (fold["source"], fold["target"], fold["quarantine"])
            )
            if len(coordinates) != row_count or len(np.unique(coordinates)) != row_count:
                raise ValueError(f"raw topology {protocol} fold is not a partition")
            target_counts[fold["target"]] += 1
        if not np.all(target_counts == 1):
            raise ValueError(f"raw topology {protocol} does not target each record once")
    return result


def build_expected_key_sets(
    metadata: pd.DataFrame,
    window_index: pd.DataFrame,
) -> tuple[dict[str, dict[str, Any]], list[dict[str, Any]]]:
    """Build outcome-free expected keys for all predictions, fits, and traces."""

    partitions = _protocol_partitions(metadata)
    rows: dict[str, list[tuple[Any, ...]]] = {name: [] for name in KEY_SCHEMAS}
    fold_records = []
    for protocol in RAW_PROTOCOLS:
        for fold in partitions[protocol]:
            source = fold["source"]
            target = fold["target"]
            quarantine = fold["quarantine"]
            fold_records.append(
                {
                    "protocol": protocol,
                    "fold_id": fold["fold_id"],
                    "source_record_count": len(source),
                    "source_window_count": len(source) * WINDOWS_PER_RECORD,
                    "target_record_count": len(target),
                    "target_window_count": len(target) * WINDOWS_PER_RECORD,
                    "quarantine_record_count": len(quarantine),
                }
            )
            target_windows = window_index.loc[
                window_index["row_index"].isin(target)
            ].sort_values("window_row_index", kind="stable")
            for method in RAW_MODELS:
                for seed in RAW_SEEDS:
                    fit_key = (
                        protocol,
                        method,
                        seed,
                        fold["fold_id"],
                        len(source),
                        len(source) * WINDOWS_PER_RECORD,
                        len(target),
                        len(target) * WINDOWS_PER_RECORD,
                        len(quarantine),
                    )
                    rows["fits"].append(fit_key)
                    rows["training_traces"].append(fit_key[:4])
                    for window in target_windows.itertuples(index=False):
                        physical = metadata.iloc[int(window.row_index)]
                        rows["window_predictions"].append(
                            (
                                protocol,
                                method,
                                seed,
                                fold["fold_id"],
                                int(window.window_row_index),
                                int(window.row_index),
                                int(window.window_index),
                                *(physical[column] for column in PHYSICAL_METADATA),
                            )
                        )
                    for row_index in target:
                        physical = metadata.iloc[int(row_index)]
                        record_key = (
                            protocol,
                            method,
                            seed,
                            fold["fold_id"],
                            int(row_index),
                            *(physical[column] for column in PHYSICAL_METADATA),
                        )
                        rows["seed_recording_predictions"].append(record_key)
                        if seed == RAW_SEEDS[0]:
                            rows["ensemble_recording_predictions"].append(
                                (record_key[0], record_key[1], *record_key[3:])
                            )
    return (
        {
            name: canonical_key_record(values, KEY_SCHEMAS[name])
            for name, values in rows.items()
        },
        fold_records,
    )


def build_expected_manifest(
    *,
    metadata: pd.DataFrame,
    window_index: pd.DataFrame,
    features_path: Path,
    features_sha256: str,
    raw_window_summary_path: Path,
    raw_window_summary_sha256: str,
    seal_path: Path,
    seal_sha256: str,
) -> dict[str, Any]:
    key_sets, folds = build_expected_key_sets(metadata, window_index)
    return {
        "manifest_version": MANIFEST_VERSION,
        "status": "frozen_outcome_blind_expected_raw_prediction_topology",
        "role": (
            "expected keys and physical metadata only; contains no probability, prediction, "
            "score, interval, model state, or gate outcome"
        ),
        "inputs": {
            "features": str(features_path.resolve()),
            "features_sha256": features_sha256,
            "raw_window_summary": str(raw_window_summary_path.resolve()),
            "raw_window_summary_sha256": raw_window_summary_sha256,
            "window_index_sha256": sha256_file(
                raw_window_summary_path.parent / "window_index.parquet"
            ),
            "seal": str(seal_path.resolve()),
            "seal_sha256": seal_sha256,
        },
        "configuration": {
            "models": list(RAW_MODELS),
            "protocols": list(RAW_PROTOCOLS),
            "seeds": list(RAW_SEEDS),
            "records": len(metadata),
            "windows_per_record": WINDOWS_PER_RECORD,
            "window_offsets": list(EXPECTED_WINDOW_OFFSETS),
            "random_seed": RANDOM_SEED,
            "random_folds": RANDOM_FOLD_COUNT,
            "crossed_folds": 24,
        },
        "folds": folds,
        "expected_key_sets": key_sets,
    }


def run_expected_manifest(
    *,
    features_path: Path,
    features_sha256: str,
    raw_window_directory: Path,
    raw_window_summary_sha256: str,
    seal_path: Path,
    seal_sha256: str,
    output_path: Path,
) -> dict[str, Any]:
    _verify(features_path, features_sha256, "raw topology feature matrix")
    _verify(seal_path, seal_sha256, "raw topology seal")
    summary_path = raw_window_directory / "raw_window_summary.json"
    _verify(summary_path, raw_window_summary_sha256, "raw topology window summary")
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    if summary.get("status") != "complete_hash_locked_paderborn_raw_window_artifact":
        raise ValueError("raw topology window artifact is incomplete")
    for filename, expected in summary.get("output_sha256", {}).items():
        _verify(raw_window_directory / filename, str(expected), f"raw topology {filename}")
    metadata = authoritative_metadata(features_path)
    window_index = validate_window_index(
        pd.read_parquet(raw_window_directory / "window_index.parquet"), metadata
    )
    manifest = build_expected_manifest(
        metadata=metadata,
        window_index=window_index,
        features_path=features_path,
        features_sha256=features_sha256,
        raw_window_summary_path=summary_path,
        raw_window_summary_sha256=raw_window_summary_sha256,
        seal_path=seal_path,
        seal_sha256=seal_sha256,
    )
    if output_path.exists():
        raise ValueError("raw topology expected manifest already exists")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return manifest


def _frame_key_record(frame: pd.DataFrame, name: str) -> dict[str, Any]:
    schema = KEY_SCHEMAS[name]
    missing = set(schema) - set(frame)
    if missing:
        raise ValueError(f"raw topology {name} lacks columns: {sorted(missing)}")
    return canonical_key_record(
        frame.loc[:, schema].itertuples(index=False, name=None),
        schema,
    )


def _trace_key_record(traces: Any) -> tuple[dict[str, Any], float]:
    if not isinstance(traces, list):
        raise ValueError("raw topology training traces are not a list")
    keys = []
    maximum_learning_rate_increase = 0.0
    for trace in traces:
        if not isinstance(trace, dict):
            raise ValueError("raw topology training trace is not an object")
        keys.append(
            (
                trace.get("protocol"),
                trace.get("model"),
                trace.get("seed"),
                trace.get("fold_id"),
            )
        )
        epochs = trace.get("epochs")
        if not isinstance(epochs, list) or len(epochs) != 50:
            raise ValueError("raw topology trace does not contain 50 epochs")
        epoch_numbers = [int(item.get("epoch", -1)) for item in epochs]
        if epoch_numbers != list(range(1, 51)):
            raise ValueError("raw topology epoch numbering changed")
        losses = np.asarray([item.get("source_training_loss") for item in epochs], dtype=float)
        rates = np.asarray([item.get("learning_rate") for item in epochs], dtype=float)
        if (
            not np.isfinite(losses).all()
            or (losses < 0).any()
            or not np.isfinite(rates).all()
            or (rates <= 0).any()
            or (rates > 0.001 + 1e-15).any()
        ):
            raise ValueError("raw topology training trace contains invalid source diagnostics")
        maximum_learning_rate_increase = max(
            maximum_learning_rate_increase,
            float(np.diff(rates).max(initial=0.0)),
        )
    if maximum_learning_rate_increase > 1e-15:
        raise ValueError("raw topology learning rate increased under the frozen scheduler")
    return (
        canonical_key_record(keys, KEY_SCHEMAS["training_traces"]),
        maximum_learning_rate_increase,
    )


def _probability_health(frame: pd.DataFrame, name: str) -> float:
    missing = set(PROBABILITY_COLUMNS) - set(frame)
    if missing:
        raise ValueError(f"raw topology {name} lacks probability columns")
    values = frame.loc[:, PROBABILITY_COLUMNS].to_numpy(dtype=float)
    if not np.isfinite(values).all() or (values < -1e-12).any() or (values > 1 + 1e-12).any():
        raise ValueError(f"raw topology {name} contains invalid probabilities")
    error = float(np.max(np.abs(values.sum(axis=1) - 1.0)))
    if error > 2e-6:
        raise ValueError(f"raw topology {name} probabilities do not sum to one")
    return error


def validate_result_topology(
    *,
    result_directory: Path,
    result_summary_sha256: str,
    expected_manifest_path: Path,
    expected_manifest_sha256: str,
    features_path: Path,
    features_sha256: str,
    raw_window_directory: Path,
    raw_window_summary_sha256: str,
    seal_path: Path,
    seal_sha256: str,
    output_path: Path,
) -> dict[str, Any]:
    """Compare every post-fit key with a pre-outcome expected-key manifest."""

    _verify(expected_manifest_path, expected_manifest_sha256, "raw topology expected manifest")
    _verify(features_path, features_sha256, "raw topology feature matrix")
    _verify(seal_path, seal_sha256, "raw topology seal")
    raw_summary_path = raw_window_directory / "raw_window_summary.json"
    _verify(raw_summary_path, raw_window_summary_sha256, "raw topology window summary")
    manifest = json.loads(expected_manifest_path.read_text(encoding="utf-8"))
    if (
        manifest.get("manifest_version") != MANIFEST_VERSION
        or manifest.get("status") != "frozen_outcome_blind_expected_raw_prediction_topology"
        or manifest.get("inputs", {}).get("features_sha256") != features_sha256
        or manifest.get("inputs", {}).get("raw_window_summary_sha256")
        != raw_window_summary_sha256
        or manifest.get("inputs", {}).get("seal_sha256") != seal_sha256
    ):
        raise ValueError("raw topology expected manifest identity changed")
    result_summary_path = result_directory / "raw_architecture_sensitivity_summary.json"
    _verify(result_summary_path, result_summary_sha256, "raw topology result summary")
    result_summary = json.loads(result_summary_path.read_text(encoding="utf-8"))
    if (
        result_summary.get("status") != "complete_retrospective_raw_architecture_sensitivity"
        or result_summary.get("seal_sha256") != seal_sha256
        or result_summary.get("inputs_sha256", {}).get("features") != features_sha256
        or result_summary.get("inputs_sha256", {}).get("raw_window_summary")
        != raw_window_summary_sha256
    ):
        raise ValueError("raw topology result summary identity changed")
    for filename, expected in result_summary.get("output_sha256", {}).items():
        _verify(result_directory / filename, str(expected), f"raw topology result {filename}")

    window_predictions = pd.read_parquet(result_directory / "window_predictions.parquet")
    seed_predictions = pd.read_parquet(
        result_directory / "seed_recording_predictions.parquet"
    )
    ensemble_predictions = pd.read_parquet(
        result_directory / "ensemble_recording_predictions.parquet"
    )
    fit_log = pd.read_csv(result_directory / "fit_log.csv")
    traces = json.loads((result_directory / "training_traces.json").read_text(encoding="utf-8"))
    observed_key_sets = {
        "window_predictions": _frame_key_record(window_predictions, "window_predictions"),
        "seed_recording_predictions": _frame_key_record(
            seed_predictions, "seed_recording_predictions"
        ),
        "ensemble_recording_predictions": _frame_key_record(
            ensemble_predictions, "ensemble_recording_predictions"
        ),
        "fits": _frame_key_record(fit_log, "fits"),
    }
    trace_record, learning_rate_increase = _trace_key_record(traces)
    observed_key_sets["training_traces"] = trace_record
    expected_key_sets = manifest.get("expected_key_sets")
    if not isinstance(expected_key_sets, dict):
        raise ValueError("raw topology expected key sets are absent")
    for name in KEY_SCHEMAS:
        if observed_key_sets[name] != expected_key_sets.get(name):
            raise ValueError(f"raw topology key set changed: {name}")
    state_hashes = fit_log.get("model_state_sha256")
    if (
        state_hashes is None
        or state_hashes.nunique() != expected_key_sets["fits"]["count"]
        or not state_hashes.astype(str)
        .map(lambda item: bool(re.fullmatch(r"[0-9a-f]{64}", item)))
        .all()
    ):
        raise ValueError("raw topology model-state identities changed")
    for column in ("duration_seconds", "parameter_count", "peak_cuda_memory_bytes"):
        values = fit_log[column].to_numpy(dtype=float)
        if not np.isfinite(values).all() or (values < 0).any():
            raise ValueError(f"raw topology fit diagnostic is invalid: {column}")
    probability_errors = {
        "window_predictions": _probability_health(window_predictions, "window predictions"),
        "seed_recording_predictions": _probability_health(
            seed_predictions, "seed recording predictions"
        ),
        "ensemble_recording_predictions": _probability_health(
            ensemble_predictions, "ensemble recording predictions"
        ),
    }
    if output_path.exists():
        raise ValueError("raw topology validation output already exists")
    validation = {
        "schema_version": VALIDATION_VERSION,
        "status": "passed_independent_raw_prediction_topology_validation",
        "input_sha256": {
            "result_summary": result_summary_sha256,
            "expected_manifest": expected_manifest_sha256,
            "features": features_sha256,
            "raw_window_summary": raw_window_summary_sha256,
            "seal": seal_sha256,
        },
        "validated_key_sets": observed_key_sets,
        "maximum_probability_sum_error": probability_errors,
        "maximum_learning_rate_increase": learning_rate_increase,
        "refit_performed": False,
        "aggregate_metrics_recomputed": False,
        "gate_outcome_read": False,
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(validation, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return validation
