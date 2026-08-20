#!/usr/bin/env python3
"""Independently recompute the combined Paderborn neural sensor attribution."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from smartvalve.experiments.paderborn_neural_sensor_attribution import (
    SCHEMA_VERSION,
    bootstrap_neural_sensor_score_differences,
    neural_sensor_rank_concordance,
    validate_neural_sensor_ensemble,
)
from smartvalve.experiments.paderborn_sensor_audit import (
    bootstrap_sensor_family_fault_predictions,
    score_sensor_family_fault_predictions,
    sensor_gap_differences,
)

VALIDATION_VERSION = f"{SCHEMA_VERSION}-validation-0.1.0"


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


def _difference(left: pd.DataFrame, right: pd.DataFrame, role: str) -> float:
    if list(left.columns) != list(right.columns) or len(left) != len(right):
        raise ValueError(f"{role} topology changed")
    maximum = 0.0
    for column in left:
        if pd.api.types.is_numeric_dtype(left[column]) and pd.api.types.is_numeric_dtype(
            right[column]
        ):
            left_values = left[column].to_numpy(dtype=float)
            right_values = right[column].to_numpy(dtype=float)
            if not np.array_equal(np.isnan(left_values), np.isnan(right_values)):
                raise ValueError(f"{role} NaN pattern changed in {column}")
            differences = np.abs(left_values - right_values)
            finite = differences[np.isfinite(differences)]
            maximum = max(maximum, float(finite.max()) if len(finite) else 0.0)
        elif (
            not left[column]
            .fillna("<NA>")
            .astype(str)
            .equals(right[column].fillna("<NA>").astype(str))
        ):
            raise ValueError(f"{role} identity values changed in {column}")
    if maximum > 1e-11:
        raise ValueError(f"{role} numeric drift exceeds tolerance: {maximum}")
    return maximum


def _write_json(path: Path, value: Any) -> None:
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--result-dir", type=Path, required=True)
    parser.add_argument("--summary-sha256", required=True)
    parser.add_argument("--output", type=Path, required=True)
    return parser


def main() -> int:
    arguments = build_parser().parse_args()
    summary_path = arguments.result_dir / "neural_sensor_attribution_summary.json"
    _verify(summary_path, arguments.summary_sha256, "neural sensor attribution summary")
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    if (
        summary.get("schema_version") != SCHEMA_VERSION
        or summary.get("status") != "complete_retrospective_neural_sensor_attribution"
    ):
        raise ValueError("neural sensor attribution summary identity changed")
    for filename, expected in summary.get("output_sha256", {}).items():
        _verify(arguments.result_dir / filename, str(expected), filename)

    ensemble = pd.read_parquet(arguments.result_dir / "combined_ensemble_predictions.parquet")
    validate_neural_sensor_ensemble(ensemble)
    aggregate, cells, effects, concordance = score_sensor_family_fault_predictions(ensemble)
    draws = int(summary["design"]["bootstrap_draws"])
    bootstrap, bootstrap_draws, draw_plan = bootstrap_sensor_family_fault_predictions(
        ensemble,
        draws=draws,
    )
    gap_differences, gap_difference_draws = sensor_gap_differences(
        bootstrap,
        bootstrap_draws,
    )
    score_differences, score_difference_draws = bootstrap_neural_sensor_score_differences(
        ensemble, draw_plan
    )
    rank_concordance = neural_sensor_rank_concordance(aggregate)
    recomputed = {
        "aggregate_metrics.csv": aggregate,
        "cell_metrics.csv": cells,
        "protocol_effects.csv": effects,
        "ranking_concordance.csv": concordance,
        "bootstrap_summary.csv": bootstrap,
        "bootstrap_draws.csv": bootstrap_draws,
        "bootstrap_draw_plan.csv": draw_plan,
        "sensor_gap_differences.csv": gap_differences,
        "sensor_gap_difference_draws.csv": gap_difference_draws,
        "sensor_score_differences.csv": score_differences,
        "sensor_score_difference_draws.csv": score_difference_draws,
        "sensor_rank_concordance.csv": rank_concordance,
    }
    differences = {}
    for filename, frame in recomputed.items():
        saved = pd.read_csv(arguments.result_dir / filename)
        differences[filename] = _difference(frame, saved, filename)
    validation = {
        "schema_version": VALIDATION_VERSION,
        "status": "passed_independent_no_refit_recomputation",
        "input_sha256": {
            "summary": arguments.summary_sha256,
            "combined_ensemble_predictions": _sha256(
                arguments.result_dir / "combined_ensemble_predictions.parquet"
            ),
        },
        "maximum_absolute_numeric_difference": differences,
        "validated_ensemble_rows": len(ensemble),
        "refit_performed": False,
    }
    if arguments.output.exists():
        raise ValueError("validation output already exists")
    arguments.output.parent.mkdir(parents=True, exist_ok=True)
    _write_json(arguments.output, validation)
    print(json.dumps(validation, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
