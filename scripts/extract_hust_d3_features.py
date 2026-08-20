#!/usr/bin/env python3
"""Open verified HUST MAT files once and create the sealed 450-row feature matrix."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from scipy.io import loadmat

from smartvalve.data.hust import (
    HUST_INVENTORY_SHA256,
    HUST_SAMPLES_PER_RECORDING,
    HUST_WINDOWS_PER_RECORDING,
    extract_hust_window_features,
    file_sha256,
    hust_feature_names,
    inspect_hust_signal_vector,
    select_hust_primary_inventory,
)
from smartvalve.experiments.hust_protocol import (
    attach_hust_common_cells,
    build_hust_protocol_splits,
)

RUN_VERSION = "smartvalve-hust-d3-feature-extraction-0.1.0"
EXPECTED_SEAL_SHA256 = "eb66d23601ba21fe70b125d503ec56c51fbcfc2f5c59d6d1f2bf4335485428ef"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
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


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--inventory", type=Path, required=True)
    parser.add_argument("--seal", type=Path, required=True)
    parser.add_argument("--acquisition-dir", type=Path, required=True)
    parser.add_argument("--acquisition-manifest-sha256", required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    return parser


def main() -> int:
    arguments = build_parser().parse_args()
    manifest_path = arguments.acquisition_dir / "acquisition_manifest.csv"
    input_hashes = {
        "inventory": _verify(
            arguments.inventory,
            HUST_INVENTORY_SHA256,
            "EXP-431 official inventory",
        ),
        "seal": _verify(arguments.seal, EXPECTED_SEAL_SHA256, "HUST D3 factorial seal"),
        "acquisition_manifest": _verify(
            manifest_path,
            arguments.acquisition_manifest_sha256,
            "HUST acquisition manifest",
        ),
    }
    arguments.output_dir.mkdir(parents=True, exist_ok=True)
    if any(arguments.output_dir.iterdir()):
        raise ValueError("output directory must be empty")
    primary = select_hust_primary_inventory(pd.read_csv(arguments.inventory))
    acquisition = pd.read_csv(manifest_path).set_index("filename")
    if set(acquisition.index.astype(str)) != set(primary["filename"].astype(str)):
        raise ValueError("HUST acquisition manifest differs from primary inventory")

    feature_frames = []
    structure_records = []
    for number, row in enumerate(primary.itertuples(index=False), start=1):
        path = arguments.acquisition_dir / "mat" / str(row.filename)
        if (
            path.stat().st_size != int(row.bytes)
            or file_sha256(path) != str(row.sha256)
            or str(acquisition.loc[row.filename, "sha256"]) != str(row.sha256)
        ):
            raise ValueError(f"HUST acquisition integrity changed for {row.filename}")
        contents = loadmat(path, verify_compressed_data_integrity=True)
        candidate = inspect_hust_signal_vector(contents)
        features = extract_hust_window_features(candidate.values)
        features.insert(0, "truth", row.truth)
        features.insert(0, "load_w", int(row.load_w))
        features.insert(0, "specification_group", int(row.specification_group))
        features.insert(0, "bearing_code", row.bearing_code)
        features.insert(0, "condition", row.condition)
        features.insert(0, "filename", row.filename)
        feature_frames.append(features)
        structure_records.append(
            {
                "filename": row.filename,
                "sha256": row.sha256,
                "variable_name": candidate.variable_name,
                "original_shape": "x".join(map(str, candidate.original_shape)),
                "original_dtype": candidate.original_dtype,
                "sample_count": len(candidate.values),
                "window_count": len(features),
                "feature_count": len(hust_feature_names()),
            }
        )
        print(
            json.dumps(
                {
                    "event": "hust_mat_structure_validated",
                    "completed": number,
                    **structure_records[-1],
                },
                sort_keys=True,
            ),
            flush=True,
        )
    frame = attach_hust_common_cells(pd.concat(feature_frames, ignore_index=True))
    protocols = build_hust_protocol_splits(frame)
    if (
        len(frame) != 450
        or frame["filename"].nunique() != 45
        or len(hust_feature_names()) != 24
        or not np.isfinite(frame.loc[:, hust_feature_names()].to_numpy(dtype=float)).all()
    ):
        raise ValueError("HUST feature matrix violates its sealed dimensions")
    topology = []
    for protocol, splits in protocols.items():
        for split in splits:
            topology.append(
                {
                    "protocol": protocol,
                    "fold_id": split.fold_id,
                    "source_windows": len(split.source_indices),
                    "target_windows": len(split.target_indices),
                    "quarantine_windows": len(split.quarantine_indices),
                    "source_recordings": frame.iloc[split.source_indices][
                        "filename"
                    ].nunique(),
                    "target_recordings": frame.iloc[split.target_indices][
                        "filename"
                    ].nunique(),
                    "quarantine_recordings": frame.iloc[split.quarantine_indices][
                        "filename"
                    ].nunique(),
                }
            )
    feature_path = arguments.output_dir / "feature_matrix.parquet"
    structure_path = arguments.output_dir / "mat_structure.csv"
    topology_path = arguments.output_dir / "split_topology.csv"
    frame.to_parquet(feature_path, index=False)
    pd.DataFrame(structure_records).to_csv(
        structure_path, index=False, lineterminator="\n"
    )
    pd.DataFrame(topology).to_csv(topology_path, index=False, lineterminator="\n")
    summary = {
        "run_version": RUN_VERSION,
        "status": "features_complete_no_model_outcomes",
        "inputs_sha256": input_hashes,
        "recordings": frame["filename"].nunique(),
        "physical_bearings": frame["bearing_code"].nunique(),
        "rows": len(frame),
        "windows_per_recording": HUST_WINDOWS_PER_RECORDING,
        "samples_per_recording": HUST_SAMPLES_PER_RECORDING,
        "features": len(hust_feature_names()),
        "protocol_fold_counts": {key: len(value) for key, value in protocols.items()},
        "output_sha256": {
            "feature_matrix.parquet": _sha256(feature_path),
            "mat_structure.csv": _sha256(structure_path),
            "split_topology.csv": _sha256(topology_path),
        },
    }
    _write_json(arguments.output_dir / "feature_summary.json", summary)
    print(json.dumps(summary, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
