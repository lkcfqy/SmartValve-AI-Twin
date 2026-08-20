#!/usr/bin/env python3
"""Create a hash-locked four-window vibration artifact from sealed Paderborn archives."""

from __future__ import annotations

import argparse
import hashlib
import json
import tempfile
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from smartvalve.data.paderborn import PRIMARY_BEARING_CODES
from smartvalve.data.paderborn_mat import load_main_channels
from smartvalve.experiments.paderborn_domain import validate_paderborn_feature_frame
from smartvalve.experiments.paderborn_feature_run import (
    _extract_archive,
    expected_filenames_for_bearing,
    validate_extracted_archive,
)
from smartvalve.experiments.paderborn_raw_sensitivity import (
    RAW_SENSITIVITY_VERSION,
    WINDOW_SIZE,
    WINDOWS_PER_RECORD,
    deterministic_window_offsets,
)

ARTIFACT_VERSION = f"{RAW_SENSITIVITY_VERSION}-windows-0.1.0"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(4 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _verify(path: Path, expected: str, role: str) -> str:
    if not path.is_file():
        raise FileNotFoundError(path)
    observed = _sha256(path)
    if observed != expected:
        raise ValueError(f"{role} SHA-256 changed: expected {expected}, observed {observed}")
    return observed


def _write_json(path: Path, value: Any) -> None:
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def build_raw_window_artifact(
    *,
    feature_result_directory: Path,
    feature_summary_sha256: str,
    archive_cache: Path,
    unrar_binary: Path,
    output_directory: Path,
) -> dict[str, Any]:
    """Stream primary archives and retain four deterministic windows per record."""

    summary_path = feature_result_directory / "metrics.json"
    _verify(summary_path, feature_summary_sha256, "Paderborn feature summary")
    feature_summary = json.loads(summary_path.read_text(encoding="utf-8"))
    if feature_summary.get("status") != (
        "sealed_paderborn_features_complete_without_model_outcome_access"
    ):
        raise ValueError("Paderborn feature source is not the sealed completed artifact")
    artifacts = feature_summary.get("artifacts", {})
    for role in ("primary_feature_matrix", "mat_inventory"):
        record = artifacts.get(role)
        if not isinstance(record, dict):
            raise ValueError(f"Paderborn feature summary is missing {role}")
        _verify(
            feature_result_directory / str(record["path"]),
            str(record["sha256"]),
            role,
        )

    archive_lock_path = Path(str(feature_summary["input"]["archive_lock"])).resolve(
        strict=True
    )
    _verify(
        archive_lock_path,
        str(feature_summary["input"]["archive_lock_sha256"]),
        "Paderborn archive lock",
    )
    archive_lock = json.loads(archive_lock_path.read_text(encoding="utf-8"))
    archive_records = {
        str(record["filename"]): record for record in archive_lock.get("archives", [])
    }
    unrar_binary = unrar_binary.resolve(strict=True)
    _verify(
        unrar_binary,
        str(feature_summary["input"]["unrar_binary_sha256"]),
        "Paderborn unrar binary",
    )

    primary_path = feature_result_directory / str(artifacts["primary_feature_matrix"]["path"])
    inventory_path = feature_result_directory / str(artifacts["mat_inventory"]["path"])
    primary = pd.read_parquet(primary_path).reset_index(drop=True)
    validate_paderborn_feature_frame(primary)
    inventory = pd.read_parquet(inventory_path)
    inventory_by_filename = inventory.set_index("filename")
    expected_primary = set(primary["filename"].astype(str))
    if len(expected_primary) != len(primary):
        raise ValueError("Paderborn primary frame contains duplicate filenames")

    output_directory.mkdir(parents=True, exist_ok=True)
    if any(output_directory.iterdir()):
        raise ValueError("raw window output directory must be empty")
    window_path = output_directory / "vibration_windows.npy"
    index_path = output_directory / "window_index.parquet"
    trace_path = output_directory / "extraction_traces.json"
    window_count = len(primary) * WINDOWS_PER_RECORD
    windows = np.lib.format.open_memmap(
        window_path,
        mode="w+",
        dtype=np.float32,
        shape=(window_count, WINDOW_SIZE),
    )
    filename_to_row = {
        str(filename): row_index
        for row_index, filename in enumerate(primary["filename"].astype(str))
    }
    index_records: list[dict[str, Any]] = []
    traces: list[dict[str, Any]] = []
    written_filenames: set[str] = set()
    next_window_row = 0
    archive_cache = archive_cache.resolve(strict=True)

    for archive_number, bearing_code in enumerate(PRIMARY_BEARING_CODES, start=1):
        archive_name = f"{bearing_code}.rar"
        archive = (archive_cache / archive_name).resolve(strict=True)
        if archive.parent != archive_cache:
            raise ValueError("Paderborn archive path escaped the cache")
        lock = archive_records.get(archive_name)
        if not isinstance(lock, dict):
            raise ValueError(f"archive lock is missing {archive_name}")
        if archive.stat().st_size != int(lock["bytes"]):
            raise ValueError(f"Paderborn archive size changed: {archive_name}")
        _verify(archive, str(lock["sha256"]), f"Paderborn archive {archive_name}")
        with tempfile.TemporaryDirectory(prefix=f"smartvalve-raw-{bearing_code}-") as temporary:
            destination = Path(temporary) / "extracted"
            destination.mkdir()
            completed = _extract_archive(unrar_binary, archive, destination)
            if completed.returncode != 0:
                raise RuntimeError(f"unrar extraction failed for {archive_name}")
            validated = validate_extracted_archive(
                destination,
                bearing_code,
                expected_filenames=expected_filenames_for_bearing(bearing_code),
            )
            retained = [path for path in validated.measurements if path.name in expected_primary]
            for path in retained:
                saved_inventory = inventory_by_filename.loc[path.name]
                if saved_inventory["feature_status"] != "included":
                    raise ValueError("raw sensitivity selected an excluded MAT member")
                _verify(path, str(saved_inventory["sha256"]), f"MAT member {path.name}")
                signal = load_main_channels(path)["vibration"].astype(np.float32, copy=False)
                offsets = deterministic_window_offsets(len(signal))
                row_index = filename_to_row[path.name]
                for window_index, offset in enumerate(offsets):
                    values = signal[offset : offset + WINDOW_SIZE]
                    if len(values) != WINDOW_SIZE or not np.isfinite(values).all():
                        raise ValueError("raw sensitivity window is incomplete or non-finite")
                    windows[next_window_row] = values
                    index_records.append(
                        {
                            "window_row_index": next_window_row,
                            "row_index": row_index,
                            "window_index": window_index,
                            "sample_offset": offset,
                            "filename": path.name,
                            "bearing_code": str(primary.iloc[row_index]["bearing_code"]),
                            "setting_code": str(primary.iloc[row_index]["setting_code"]),
                            "measurement_index": int(
                                primary.iloc[row_index]["measurement_index"]
                            ),
                            "truth": str(primary.iloc[row_index]["truth"]),
                        }
                    )
                    next_window_row += 1
                written_filenames.add(path.name)
        traces.append(
            {
                "archive_number": archive_number,
                "archive_count": len(PRIMARY_BEARING_CODES),
                "archive_filename": archive_name,
                "archive_sha256": str(lock["sha256"]),
                "retained_primary_measurements": len(retained),
                "unrar_exit_code": completed.returncode,
                "unrar_stdout_sha256": hashlib.sha256(
                    completed.stdout.encode("utf-8")
                ).hexdigest(),
                "unrar_stderr_sha256": hashlib.sha256(
                    completed.stderr.encode("utf-8")
                ).hexdigest(),
            }
        )
        print(
            json.dumps(
                {
                    "event": "raw_window_archive_complete",
                    "archive_number": archive_number,
                    "archive_count": len(PRIMARY_BEARING_CODES),
                    "archive_filename": archive_name,
                    "windows_written": next_window_row,
                    "windows_expected": window_count,
                },
                sort_keys=True,
            ),
            flush=True,
        )

    windows.flush()
    del windows
    if next_window_row != window_count or written_filenames != expected_primary:
        raise ValueError("raw sensitivity artifact did not cover every primary measurement")
    index = pd.DataFrame(index_records).sort_values("window_row_index", kind="stable")
    if (
        len(index) != window_count
        or index["window_row_index"].tolist() != list(range(window_count))
        or not index.groupby("row_index", observed=True).size().eq(WINDOWS_PER_RECORD).all()
    ):
        raise ValueError("raw sensitivity window index topology changed")
    index.to_parquet(index_path, index=False)
    _write_json(trace_path, traces)
    summary = {
        "schema_version": ARTIFACT_VERSION,
        "status": "complete_hash_locked_paderborn_raw_window_artifact",
        "source": {
            "feature_summary": str(summary_path.resolve()),
            "feature_summary_sha256": feature_summary_sha256,
            "primary_feature_matrix_sha256": str(
                artifacts["primary_feature_matrix"]["sha256"]
            ),
            "mat_inventory_sha256": str(artifacts["mat_inventory"]["sha256"]),
            "archive_lock_sha256": str(
                feature_summary["input"]["archive_lock_sha256"]
            ),
            "unrar_binary_sha256": str(
                feature_summary["input"]["unrar_binary_sha256"]
            ),
        },
        "design": {
            "channel": "vibration_1",
            "record_count": len(primary),
            "windows_per_record": WINDOWS_PER_RECORD,
            "window_size": WINDOW_SIZE,
            "window_offsets": list(deterministic_window_offsets(256_000)),
            "window_count": window_count,
            "dtype": "float32",
            "normalization": "deferred_per_window_per_channel_standardization",
            "outcome_guided_window_selection": False,
        },
        "output_sha256": {
            "vibration_windows.npy": _sha256(window_path),
            "window_index.parquet": _sha256(index_path),
            "extraction_traces.json": _sha256(trace_path),
        },
    }
    _write_json(output_directory / "raw_window_summary.json", summary)
    return summary


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--feature-result-dir", type=Path, required=True)
    parser.add_argument("--feature-summary-sha256", required=True)
    parser.add_argument("--archive-cache", type=Path, required=True)
    parser.add_argument("--unrar-binary", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    return parser


def main() -> int:
    arguments = build_parser().parse_args()
    summary = build_raw_window_artifact(
        feature_result_directory=arguments.feature_result_dir,
        feature_summary_sha256=arguments.feature_summary_sha256,
        archive_cache=arguments.archive_cache,
        unrar_binary=arguments.unrar_binary,
        output_directory=arguments.output_dir,
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
