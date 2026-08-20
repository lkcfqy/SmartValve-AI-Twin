#!/usr/bin/env python3
"""Independently recompute raw-architecture sensitivity artifacts without fitting."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from numbers import Real
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from smartvalve.experiments import paderborn_raw_validation as independent_validation
from smartvalve.experiments.hust_artifact_validation import _assert_frame_equal
from smartvalve.experiments.paderborn_raw_validation import (
    MODELS,
    PROBABILITY_COLUMNS,
    PROTOCOLS,
    SEEDS,
    VALIDATION_CALCULATION_VERSION,
    WINDOWS_PER_RECORD,
    aggregate_windows_independently,
    bootstrap_protocol_effects_independently,
    ensemble_seeds_independently,
    evaluate_gate_independently,
    score_predictions_independently,
)

VALIDATION_VERSION = "smartvalve-paderborn-raw-sensitivity-validation-0.2.0"
EXPECTED_COUNTS = {
    "fits": 270,
    "window_predictions": 166_968,
    "seed_recording_predictions": 41_742,
    "ensemble_recording_predictions": 13_914,
    "aggregate_metrics": 6,
    "cell_metrics": 144,
    "bootstrap_summary": 3,
    "bootstrap_draws": 6_000,
    "bootstrap_draw_plan": 2_000,
}
EXPECTED_OUTPUTS = {
    "aggregate_metrics.csv",
    "bootstrap_draw_plan.csv",
    "bootstrap_draws.csv",
    "bootstrap_summary.csv",
    "cell_metrics.csv",
    "ensemble_recording_predictions.parquet",
    "fit_log.csv",
    "seed_recording_predictions.parquet",
    "training_traces.json",
    "window_predictions.parquet",
}


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


def _assert_findings(
    recomputed: dict[str, object],
    saved: dict[str, object],
    *,
    tolerance: float = 1e-12,
) -> float:
    if set(recomputed) != set(saved):
        raise ValueError("raw sensitivity finding keys changed")
    maximum = 0.0
    for key in sorted(recomputed):
        left = recomputed[key]
        right = saved[key]
        if isinstance(left, bool) or isinstance(right, bool):
            if type(left) is not bool or type(right) is not bool or left != right:
                raise ValueError(f"raw sensitivity boolean finding changed: {key}")
        elif isinstance(left, Real) and isinstance(right, Real):
            left_value = float(left)
            right_value = float(right)
            if math.isnan(left_value) or math.isnan(right_value):
                if not (math.isnan(left_value) and math.isnan(right_value)):
                    raise ValueError(f"raw sensitivity NaN finding changed: {key}")
            else:
                difference = abs(left_value - right_value)
                maximum = max(maximum, difference)
                if difference > tolerance:
                    raise ValueError(f"raw sensitivity numeric finding changed: {key}")
        elif left != right:
            raise ValueError(f"raw sensitivity finding changed: {key}")
    return maximum


def validate(
    *,
    result_directory: Path,
    summary_sha256: str,
    seal_path: Path,
    seal_sha256: str,
    features_sha256: str,
    raw_window_summary_sha256: str,
    output_path: Path,
) -> dict[str, Any]:
    """Verify hashes and reproduce all post-fit outputs from saved probabilities."""

    summary_path = result_directory / "raw_architecture_sensitivity_summary.json"
    _verify(summary_path, summary_sha256, "raw sensitivity summary")
    _verify(seal_path, seal_sha256, "raw sensitivity seal")
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    design = summary.get("design", {})
    if (
        summary.get("status") != "complete_retrospective_raw_architecture_sensitivity"
        or summary.get("seal_sha256") != seal_sha256
        or summary.get("inputs_sha256", {}).get("features") != features_sha256
        or summary.get("inputs_sha256", {}).get("raw_window_summary")
        != raw_window_summary_sha256
        or design.get("models") != list(MODELS)
        or design.get("protocols") != list(PROTOCOLS)
        or design.get("seeds") != list(SEEDS)
        or design.get("record_count") != 2_319
        or design.get("windows_per_record") != WINDOWS_PER_RECORD
        or design.get("window_size") != 8_192
        or design.get("epochs") != 50
        or design.get("batch_size") != 128
        or design.get("fit_count") != EXPECTED_COUNTS["fits"]
        or design.get("bootstrap_draws") != EXPECTED_COUNTS["bootstrap_draw_plan"]
        or design.get("bootstrap_unit") != "bearing_code_stratified_by_truth"
        or design.get("configuration_search") != "none"
    ):
        raise ValueError("raw sensitivity summary identity changed")
    output_sha256 = summary.get("output_sha256")
    if not isinstance(output_sha256, dict) or set(output_sha256) != EXPECTED_OUTPUTS:
        raise ValueError("raw sensitivity summary output inventory changed")
    for filename, expected in output_sha256.items():
        _verify(result_directory / filename, str(expected), f"raw sensitivity {filename}")

    window_predictions = pd.read_parquet(result_directory / "window_predictions.parquet")
    saved_seed_recordings = pd.read_parquet(
        result_directory / "seed_recording_predictions.parquet"
    )
    saved_ensemble = pd.read_parquet(
        result_directory / "ensemble_recording_predictions.parquet"
    )
    fit_log = pd.read_csv(result_directory / "fit_log.csv")
    traces = json.loads((result_directory / "training_traces.json").read_text(encoding="utf-8"))
    seed_recordings = aggregate_windows_independently(
        window_predictions,
        windows_per_record=WINDOWS_PER_RECORD,
    )
    ensemble = ensemble_seeds_independently(seed_recordings, expected_seeds=SEEDS)
    aggregate, cells = score_predictions_independently(ensemble)
    bootstrap, bootstrap_draws, bootstrap_plan = bootstrap_protocol_effects_independently(
        ensemble,
        draws=2_000,
    )
    comparisons = {
        "seed_recording_predictions": (seed_recordings, saved_seed_recordings),
        "ensemble_recording_predictions": (ensemble, saved_ensemble),
        "aggregate_metrics": (
            aggregate,
            pd.read_csv(result_directory / "aggregate_metrics.csv"),
        ),
        "cell_metrics": (cells, pd.read_csv(result_directory / "cell_metrics.csv")),
        "bootstrap_summary": (
            bootstrap,
            pd.read_csv(result_directory / "bootstrap_summary.csv"),
        ),
        "bootstrap_draws": (
            bootstrap_draws,
            pd.read_csv(result_directory / "bootstrap_draws.csv"),
        ),
        "bootstrap_draw_plan": (
            bootstrap_plan,
            pd.read_csv(result_directory / "bootstrap_draw_plan.csv"),
        ),
    }
    maximum_differences = {
        name: _assert_frame_equal(
            recomputed.reset_index(drop=True),
            saved.reset_index(drop=True),
            name=f"raw sensitivity {name}",
        )
        for name, (recomputed, saved) in comparisons.items()
    }
    observed_counts = {
        "fits": len(fit_log),
        "window_predictions": len(window_predictions),
        "seed_recording_predictions": len(seed_recordings),
        "ensemble_recording_predictions": len(ensemble),
        "aggregate_metrics": len(aggregate),
        "cell_metrics": len(cells),
        "bootstrap_summary": len(bootstrap),
        "bootstrap_draws": len(bootstrap_draws),
        "bootstrap_draw_plan": len(bootstrap_plan),
    }
    if observed_counts != EXPECTED_COUNTS or len(traces) != EXPECTED_COUNTS["fits"]:
        raise ValueError("raw sensitivity artifact counts changed")
    if (
        fit_log["model_state_sha256"].nunique() != EXPECTED_COUNTS["fits"]
        or set(fit_log["method"].astype(str)) != set(MODELS)
        or set(fit_log["protocol"].astype(str)) != set(PROTOCOLS)
        or set(fit_log["seed"].astype(int)) != set(SEEDS)
    ):
        raise ValueError("raw sensitivity fit identities changed")
    probability_values = window_predictions.loc[:, PROBABILITY_COLUMNS].to_numpy(dtype=float)
    maximum_probability_error = float(
        np.max(np.abs(probability_values.sum(axis=1) - 1.0))
    )
    if maximum_probability_error > 2e-6:
        raise ValueError("raw sensitivity probabilities do not sum to one")
    findings = dict(evaluate_gate_independently(bootstrap))
    saved_findings = summary.get("findings")
    if not isinstance(saved_findings, dict):
        raise ValueError("raw sensitivity findings are not a JSON object")
    findings_difference = _assert_findings(findings, saved_findings)
    validation = {
        "schema_version": VALIDATION_VERSION,
        "status": "passed_independent_no_refit_recomputation",
        "input_sha256": {
            "summary": summary_sha256,
            "seal": seal_sha256,
            "features": features_sha256,
            "raw_window_summary": raw_window_summary_sha256,
            "window_predictions": _sha256(
                result_directory / "window_predictions.parquet"
            ),
        },
        "calculation_implementation": {
            "version": VALIDATION_CALCULATION_VERSION,
            "shared_producer_calculation_code": False,
            "module_sha256": _sha256(Path(independent_validation.__file__).resolve()),
            "cli_sha256": _sha256(Path(__file__).resolve()),
        },
        "validated_counts": observed_counts,
        "maximum_absolute_numeric_difference": maximum_differences,
        "findings_maximum_absolute_numeric_difference": findings_difference,
        "maximum_probability_sum_error": maximum_probability_error,
        "findings": findings,
        "refit_performed": False,
    }
    if output_path.exists():
        raise ValueError("raw sensitivity validation output already exists")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(validation, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return validation


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--result-dir", type=Path, required=True)
    parser.add_argument("--summary-sha256", required=True)
    parser.add_argument("--seal", type=Path, required=True)
    parser.add_argument("--seal-sha256", required=True)
    parser.add_argument("--features-sha256", required=True)
    parser.add_argument("--raw-window-summary-sha256", required=True)
    parser.add_argument("--output", type=Path, required=True)
    return parser


def main() -> int:
    arguments = build_parser().parse_args()
    result = validate(
        result_directory=arguments.result_dir,
        summary_sha256=arguments.summary_sha256,
        seal_path=arguments.seal,
        seal_sha256=arguments.seal_sha256,
        features_sha256=arguments.features_sha256,
        raw_window_summary_sha256=arguments.raw_window_summary_sha256,
        output_path=arguments.output,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
