#!/usr/bin/env python3
"""Independently recompute and validate sealed Paderborn sensor-audit artifacts."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from smartvalve.experiments.paderborn_protocol_contrast import RANDOM_SEED
from smartvalve.experiments.paderborn_sensor_audit import (
    bootstrap_sensor_family_fault_predictions,
    score_bearing_reidentification_predictions,
    score_sensor_family_fault_predictions,
    sensor_gap_differences,
)

EXPECTED_ARTIFACT_HASHES = {
    "aggregate_metrics.csv": "394d96e68677280345b719d9832ef9f86d0e4a44ef5aeae54c8d4d6c83bd39a2",
    "bearing_reidentification_metrics.csv": (
        "9930457ec11a9d8c6b847d181b92a1ef768e20c20eda876c43bfa02feb58a0bc"
    ),
    "bearing_reidentification_predictions.parquet": (
        "7fa8087875031121d61f50f74f2e852c23d0ced31a79056b428af698119c2492"
    ),
    "bootstrap_draw_plan.csv": "2c161da87938a9736353c1e9c300dd3a58a78fedd6840553bb7bad7da8933d0f",
    "bootstrap_draws.csv": "1892ba55e94ac538bd49ee17843816737368e02c73a55958fdfc78fb848ce7d5",
    "bootstrap_summary.csv": "5cd2a6c89397163938bf8cd4671f5d8d29252edb8b18189d2a2d746a8e9b425a",
    "cell_metrics.csv": "69aa2f43646e09674cf50f60e2242a327efb713a8d5213e08060883ed2b7d9d1",
    "predictions.parquet": "bb62dd7dfc3db122d3590057361e7eab66546c772839b27785c597377bf1e83c",
    "protocol_effects.csv": "763a2214d94decabbe2aa20e7b914940223d9800894f19ccee0e0897dbb0d21a",
    "ranking_concordance.csv": "d2808ec8c0f27f191f24583e11a5040a6979590044635eca5096c02b639a3c8a",
    "sensor_gap_difference_draws.csv": (
        "0698579915b1677a59e8b67939ef9913da7cd5a6e605b88e3e79b090a835ddb2"
    ),
    "sensor_gap_differences.csv": (
        "5abdacf4ade4033bc4d46c510d376bcadf2f3ce04e098dfdc190c6f80ce6043a"
    ),
}
EXPECTED_EXP433_PREDICTIONS_SHA256 = (
    "1cfa977620c34c28625cb2e132d68cb7f280aa2efff542af8835aa0bb21dd024"
)
TOLERANCE = 1e-11


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _verify_hash(path: Path, expected: str) -> None:
    if not path.is_file():
        raise FileNotFoundError(path)
    observed = _sha256(path)
    if observed != expected:
        raise ValueError(f"artifact hash changed for {path.name}: {observed}")


def _frame_difference(expected: pd.DataFrame, observed: pd.DataFrame, role: str) -> float:
    if list(expected.columns) != list(observed.columns) or len(expected) != len(observed):
        raise ValueError(f"{role} topology changed")
    maximum = 0.0
    for column in expected:
        left = expected[column]
        right = observed[column]
        if pd.api.types.is_numeric_dtype(left) and pd.api.types.is_numeric_dtype(right):
            left_values = left.to_numpy(dtype=float)
            right_values = right.to_numpy(dtype=float)
            if not np.array_equal(np.isnan(left_values), np.isnan(right_values)):
                raise ValueError(f"{role} NaN pattern changed in {column}")
            difference = np.abs(left_values - right_values)
            finite = difference[np.isfinite(difference)]
            maximum = max(maximum, float(finite.max()) if len(finite) else 0.0)
        elif not left.astype(str).equals(right.astype(str)):
            raise ValueError(f"{role} text values changed in {column}")
    if maximum > TOLERANCE:
        raise ValueError(f"{role} numeric difference {maximum} exceeds tolerance")
    return maximum


def _write_json(path: Path, value: Any) -> None:
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--artifacts", type=Path, required=True)
    parser.add_argument("--exp433-predictions", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    return parser


def main() -> int:
    arguments = build_parser().parse_args()
    for filename, expected_hash in EXPECTED_ARTIFACT_HASHES.items():
        _verify_hash(arguments.artifacts / filename, expected_hash)
    _verify_hash(arguments.exp433_predictions, EXPECTED_EXP433_PREDICTIONS_SHA256)

    predictions = pd.read_parquet(arguments.artifacts / "predictions.parquet")
    aggregate, cells, effects, concordance = score_sensor_family_fault_predictions(
        predictions
    )
    bootstrap, bootstrap_draws, draw_plan = bootstrap_sensor_family_fault_predictions(
        predictions,
        draws=2_000,
        random_seed=RANDOM_SEED,
    )
    differences, difference_draws = sensor_gap_differences(
        bootstrap,
        bootstrap_draws,
    )
    reidentification_predictions = pd.read_parquet(
        arguments.artifacts / "bearing_reidentification_predictions.parquet"
    )
    reidentification = score_bearing_reidentification_predictions(
        reidentification_predictions
    )

    recomputed = {
        "aggregate_metrics.csv": aggregate,
        "cell_metrics.csv": cells,
        "protocol_effects.csv": effects,
        "ranking_concordance.csv": concordance,
        "bootstrap_summary.csv": bootstrap,
        "bootstrap_draws.csv": bootstrap_draws,
        "bootstrap_draw_plan.csv": draw_plan,
        "sensor_gap_differences.csv": differences,
        "sensor_gap_difference_draws.csv": difference_draws,
        "bearing_reidentification_metrics.csv": reidentification,
    }
    maximum_differences = {
        filename: _frame_difference(
            pd.read_csv(arguments.artifacts / filename),
            frame,
            filename,
        )
        for filename, frame in recomputed.items()
    }

    fusion = (
        predictions.loc[predictions["feature_family"] == "fusion"]
        .drop(columns="feature_family")
        .reset_index(drop=True)
    )
    exp433 = pd.read_parquet(arguments.exp433_predictions).reset_index(drop=True)
    pd.testing.assert_frame_equal(fusion, exp433, check_exact=True)

    result = {
        "status": "passed",
        "tolerance": TOLERANCE,
        "artifact_hashes_verified": EXPECTED_ARTIFACT_HASHES,
        "recomputed_maximum_absolute_differences": maximum_differences,
        "exp433_fusion_prediction_parity": {
            "rows": len(fusion),
            "columns": list(fusion.columns),
            "exact": True,
            "exp433_sha256": EXPECTED_EXP433_PREDICTIONS_SHA256,
        },
    }
    arguments.output.parent.mkdir(parents=True, exist_ok=True)
    _write_json(arguments.output, result)
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
