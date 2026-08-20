#!/usr/bin/env python3
"""Aggregate and contrast the three sealed Paderborn neural sensor audits."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

import numpy as np
import paderborn_neural_protocol_contrast as base
import pandas as pd

from smartvalve.data.paderborn_features import MAIN_SIGNAL_FEATURE_FAMILIES
from smartvalve.experiments.paderborn_neural_sensor_attribution import (
    SCHEMA_VERSION,
    bootstrap_neural_sensor_score_differences,
    neural_sensor_rank_concordance,
    validate_neural_sensor_ensemble,
)
from smartvalve.experiments.paderborn_protocol_contrast import BOOTSTRAP_DRAWS
from smartvalve.experiments.paderborn_sensor_audit import (
    bootstrap_sensor_family_fault_predictions,
    score_sensor_family_fault_predictions,
    sensor_gap_differences,
)

EXPECTED_SENSOR_SEAL_SHA256 = "f70d2ab0e3aa6cecdff8dc43e7147fe1391272cc369f8f166c217f0035e3c266"
FAMILY_SUMMARIES = {
    "vibration": "neural_sensor_family_summary.json",
    "motor_current": "neural_sensor_family_summary.json",
    "fusion": "neural_protocol_contrast_summary.json",
}


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


def _frame_difference(left: pd.DataFrame, right: pd.DataFrame, role: str) -> float:
    if list(left.columns) != list(right.columns) or len(left) != len(right):
        raise ValueError(f"{role} topology changed")
    maximum = 0.0
    for column in left:
        if pd.api.types.is_numeric_dtype(left[column]) and pd.api.types.is_numeric_dtype(
            right[column]
        ):
            values = np.abs(
                left[column].to_numpy(dtype=float) - right[column].to_numpy(dtype=float)
            )
            finite = values[np.isfinite(values)]
            maximum = max(maximum, float(finite.max()) if len(finite) else 0.0)
        elif (
            not left[column]
            .fillna("<NA>")
            .astype(str)
            .equals(right[column].fillna("<NA>").astype(str))
        ):
            raise ValueError(f"{role} identity values changed in {column}")
    if maximum > 1e-11:
        raise ValueError(f"{role} numerical drift exceeds tolerance: {maximum}")
    return maximum


def _load_family(
    family: str,
    directory: Path,
) -> tuple[dict[str, Any], pd.DataFrame, pd.DataFrame, pd.DataFrame, dict[str, Any]]:
    summary_path = directory / FAMILY_SUMMARIES[family]
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    if summary.get("status") != "retrospective_development_not_confirmatory":
        raise ValueError(f"neural sensor family is not complete: {family}")
    design = summary.get("design", {})
    if family != "fusion" and design.get("feature_family") != family:
        raise ValueError(f"neural sensor run contains another family: {family}")
    for filename, expected in summary.get("output_sha256", {}).items():
        _verify(directory / filename, str(expected), f"{family} {filename}")
    seed_predictions = pd.read_parquet(directory / "predictions.parquet")
    ensemble = pd.read_parquet(directory / "ensemble_predictions.parquet")
    fits = pd.read_csv(directory / "fit_log.csv")
    configurations = json.loads(
        (directory / "frozen_configurations.json").read_text(encoding="utf-8")
    )
    if len(seed_predictions) != 417_420 or len(ensemble) != 83_484:
        raise ValueError(f"neural sensor prediction topology changed: {family}")
    for frame in (seed_predictions, ensemble):
        frame.insert(0, "feature_family", family)
    if "feature_family" not in fits:
        fits.insert(0, "feature_family", family)
    elif not fits["feature_family"].eq(family).all():
        raise ValueError(f"neural sensor fit family changed: {family}")
    return summary, seed_predictions, ensemble, fits, configurations


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--vibration-dir", type=Path, required=True)
    parser.add_argument("--motor-current-dir", type=Path, required=True)
    parser.add_argument("--fusion-dir", type=Path, required=True)
    parser.add_argument("--sensor-seal", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--bootstrap-draws", type=int, default=BOOTSTRAP_DRAWS)
    return parser


def main() -> int:
    arguments = build_parser().parse_args()
    if arguments.bootstrap_draws != BOOTSTRAP_DRAWS:
        raise ValueError("neural sensor attribution must use the sealed bootstrap draw count")
    sensor_seal_hash = _verify(
        arguments.sensor_seal,
        EXPECTED_SENSOR_SEAL_SHA256,
        "Paderborn sensor protocol seal",
    )
    arguments.output_dir.mkdir(parents=True, exist_ok=True)
    if any(arguments.output_dir.iterdir()):
        raise ValueError("output directory must be empty")
    directories = {
        "vibration": arguments.vibration_dir,
        "motor_current": arguments.motor_current_dir,
        "fusion": arguments.fusion_dir,
    }
    loaded = {
        family: _load_family(family, directories[family]) for family in MAIN_SIGNAL_FEATURE_FAMILIES
    }
    reference_configurations = loaded["fusion"][4]["configurations"]
    reference_candidates = loaded["fusion"][4]["candidate_ids"]
    for family in MAIN_SIGNAL_FEATURE_FAMILIES:
        configurations = loaded[family][4]
        if (
            configurations["configurations"] != reference_configurations
            or configurations["candidate_ids"] != reference_candidates
        ):
            raise ValueError("neural sensor families use different selected configurations")

    ensemble = (
        pd.concat(
            [loaded[family][2] for family in MAIN_SIGNAL_FEATURE_FAMILIES],
            ignore_index=True,
        )
        .sort_values(["feature_family", "protocol", "method", "row_index"], kind="stable")
        .reset_index(drop=True)
    )
    fits = pd.concat(
        [loaded[family][3] for family in MAIN_SIGNAL_FEATURE_FAMILIES],
        ignore_index=True,
    )
    validate_neural_sensor_ensemble(ensemble)
    aggregate, cells, effects, concordance = score_sensor_family_fault_predictions(ensemble)
    bootstrap, bootstrap_draws, draw_plan = bootstrap_sensor_family_fault_predictions(
        ensemble,
        draws=arguments.bootstrap_draws,
    )
    gap_differences, gap_difference_draws = sensor_gap_differences(
        bootstrap,
        bootstrap_draws,
    )
    score_differences, score_difference_draws = bootstrap_neural_sensor_score_differences(
        ensemble, draw_plan
    )
    sensor_rank_concordance = neural_sensor_rank_concordance(aggregate)

    validation_differences = {}
    artifact_names = {
        "aggregate_metrics.csv": aggregate,
        "cell_metrics.csv": cells,
        "protocol_effects.csv": effects,
        "ranking_concordance.csv": concordance,
        "bootstrap_summary.csv": bootstrap,
        "bootstrap_draws.csv": bootstrap_draws,
    }
    for family in MAIN_SIGNAL_FEATURE_FAMILIES:
        for filename, recomputed in artifact_names.items():
            family_rows = (
                recomputed.loc[recomputed["feature_family"] == family]
                .drop(columns="feature_family")
                .reset_index(drop=True)
            )
            saved = pd.read_csv(directories[family] / filename)
            validation_differences[f"{family}/{filename}"] = _frame_difference(
                family_rows,
                saved,
                f"{family} {filename}",
            )
        saved_plan = pd.read_csv(directories[family] / "bootstrap_draw_plan.csv")
        validation_differences[f"{family}/bootstrap_draw_plan.csv"] = _frame_difference(
            draw_plan,
            saved_plan,
            f"{family} bootstrap draw plan",
        )

    ensemble.to_parquet(arguments.output_dir / "combined_ensemble_predictions.parquet", index=False)
    tables = {
        "combined_fit_log.csv": fits,
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
        "sensor_rank_concordance.csv": sensor_rank_concordance,
    }
    for filename, table in tables.items():
        base._write_csv(arguments.output_dir / filename, table)
    output_files = ["combined_ensemble_predictions.parquet", *tables]
    output_hashes = {
        filename: _sha256(arguments.output_dir / filename) for filename in sorted(output_files)
    }
    random_crossed = gap_differences.loc[
        gap_differences["comparison_protocol"] == "measurement_random"
    ]
    findings = {
        "random_minus_crossed_gap_by_family_and_method": {
            family: {
                str(row.method): float(row.effect_comparison_minus_reference)
                for row in bootstrap.loc[
                    (bootstrap["feature_family"] == family)
                    & (bootstrap["comparison_protocol"] == "measurement_random")
                ].itertuples(index=False)
            }
            for family in MAIN_SIGNAL_FEATURE_FAMILIES
        },
        "sensor_gap_difference_interval_excludes_zero": int(
            (
                (random_crossed["bootstrap_lower_95"] > 0)
                | (random_crossed["bootstrap_upper_95"] < 0)
            ).sum()
        ),
        "sensor_score_difference_interval_excludes_zero": int(
            (
                (score_differences["bootstrap_lower_95"] > 0)
                | (score_differences["bootstrap_upper_95"] < 0)
            ).sum()
        ),
    }
    summary = {
        "schema_version": SCHEMA_VERSION,
        "status": "complete_retrospective_neural_sensor_attribution",
        "sensor_seal_sha256": sensor_seal_hash,
        "source_runs": {
            family: {
                "directory": str(directories[family].resolve()),
                "summary_sha256": _sha256(directories[family] / FAMILY_SUMMARIES[family]),
                "fit_rows_in_source_run": len(loaded[family][3]),
                "referenced_protocol_method_seed_models": 1_800,
            }
            for family in MAIN_SIGNAL_FEATURE_FAMILIES
        },
        "design": {
            "feature_families": list(MAIN_SIGNAL_FEATURE_FAMILIES),
            "ensemble_prediction_rows": len(ensemble),
            "bootstrap_draws": arguments.bootstrap_draws,
            "bootstrap_unit": "bearing_code_stratified_by_truth_shared_plan",
            "configuration_search": "none",
        },
        "source_artifact_recomputation_maximum_difference": validation_differences,
        "findings": findings,
        "output_sha256": output_hashes,
    }
    base._write_json(
        arguments.output_dir / "neural_sensor_attribution_summary.json",
        summary,
    )
    print(json.dumps(findings, ensure_ascii=False, indent=2, sort_keys=True))
    print(json.dumps(output_hashes, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
