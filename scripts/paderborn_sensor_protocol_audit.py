#!/usr/bin/env python3
"""Run the sealed classical Paderborn multi-sensor protocol audit."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

import pandas as pd

from smartvalve.data.paderborn_features import MAIN_SIGNAL_FEATURE_FAMILIES
from smartvalve.experiments.paderborn_protocol_contrast import (
    BOOTSTRAP_DRAWS,
    MODEL_NAMES,
    PROTOCOLS,
    RANDOM_SEED,
)
from smartvalve.experiments.paderborn_sensor_audit import (
    SCHEMA_VERSION,
    bootstrap_sensor_family_fault_predictions,
    generate_bearing_reidentification_predictions,
    generate_sensor_family_fault_predictions,
    score_bearing_reidentification_predictions,
    score_sensor_family_fault_predictions,
    sensor_gap_differences,
)

EXPECTED_FEATURE_SHA256 = "c5caf0cfc408057ae4bfaebef37abdf597135620105ec62e17f3aece6800aff4"
EXPECTED_SEAL_SHA256 = "f70d2ab0e3aa6cecdff8dc43e7147fe1391272cc369f8f166c217f0035e3c266"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _verify(path: Path, expected: str, role: str) -> str:
    if not path.is_file():
        raise FileNotFoundError(f"missing {role}: {path}")
    observed = _sha256(path)
    if observed != expected:
        raise ValueError(f"{role} SHA-256 changed: expected {expected}, observed {observed}")
    return observed


def _write_csv(path: Path, frame: pd.DataFrame) -> None:
    frame.to_csv(path, index=False, float_format="%.12g", lineterminator="\n")


def _write_json(path: Path, value: Any) -> None:
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _findings(
    aggregate: pd.DataFrame,
    bootstrap: pd.DataFrame,
    gap_differences: pd.DataFrame,
    reidentification: pd.DataFrame,
) -> dict[str, Any]:
    family_protocol_leaders: dict[str, dict[str, Any]] = {}
    for (family, protocol), rows in aggregate.groupby(
        ["feature_family", "protocol"], sort=True, observed=True
    ):
        leader = rows.sort_values(
            ["pooled_macro_f1", "method"], ascending=[False, True], kind="stable"
        ).iloc[0]
        family_protocol_leaders[f"{family}|{protocol}"] = {
            "method": str(leader["method"]),
            "pooled_macro_f1": float(leader["pooled_macro_f1"]),
            "minimum_cell_macro_f1": float(leader["minimum_cell_macro_f1"]),
        }

    random_gaps = bootstrap.loc[
        bootstrap["comparison_protocol"] == "measurement_random"
    ]
    family_gap_ranges = {
        str(family): {
            "minimum": float(rows["effect_comparison_minus_reference"].min()),
            "maximum": float(rows["effect_comparison_minus_reference"].max()),
        }
        for family, rows in random_gaps.groupby(
            "feature_family", sort=True, observed=True
        )
    }
    reidentification_leaders = {}
    for family, rows in reidentification.groupby(
        "feature_family", sort=True, observed=True
    ):
        leader = rows.sort_values(
            ["macro_f1", "method"], ascending=[False, True], kind="stable"
        ).iloc[0]
        reidentification_leaders[str(family)] = {
            "method": str(leader["method"]),
            "macro_f1": float(leader["macro_f1"]),
            "accuracy": float(leader["accuracy"]),
        }
    vibration_current = gap_differences.loc[
        (gap_differences["left_feature_family"] == "vibration")
        & (gap_differences["right_feature_family"] == "motor_current")
    ].sort_values("method", kind="stable")
    return {
        "family_protocol_leaders": family_protocol_leaders,
        "measurement_random_minus_crossed_gap_ranges": family_gap_ranges,
        "vibration_minus_current_gap_difference": {
            str(row.method): {
                "estimate": float(row.gap_difference_left_minus_right),
                "interval": [
                    float(row.bootstrap_lower_95),
                    float(row.bootstrap_upper_95),
                ],
            }
            for row in vibration_current.itertuples(index=False)
        },
        "cross_setting_bearing_reidentification_leaders": reidentification_leaders,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--features", type=Path, required=True)
    parser.add_argument("--seal", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--bootstrap-draws", type=int, default=BOOTSTRAP_DRAWS)
    return parser


def main() -> int:
    arguments = build_parser().parse_args()
    input_hashes = {
        "features": _verify(
            arguments.features,
            EXPECTED_FEATURE_SHA256,
            "EXP-406 primary feature matrix",
        ),
        "seal": _verify(
            arguments.seal,
            EXPECTED_SEAL_SHA256,
            "multi-sensor protocol audit seal",
        ),
    }
    arguments.output_dir.mkdir(parents=True, exist_ok=True)
    if any(arguments.output_dir.iterdir()):
        raise ValueError("output directory must be empty")
    frame = pd.read_parquet(arguments.features)

    predictions, fit_log = generate_sensor_family_fault_predictions(frame)
    aggregate, cells, effects, concordance = score_sensor_family_fault_predictions(
        predictions
    )
    bootstrap, bootstrap_draws, draw_plan = bootstrap_sensor_family_fault_predictions(
        predictions,
        draws=arguments.bootstrap_draws,
        random_seed=RANDOM_SEED,
    )
    gap_differences, gap_difference_draws = sensor_gap_differences(
        bootstrap,
        bootstrap_draws,
    )
    reidentification_predictions, reidentification_fit_log = (
        generate_bearing_reidentification_predictions(frame)
    )
    reidentification = score_bearing_reidentification_predictions(
        reidentification_predictions
    )

    tables = {
        "fit_log.csv": fit_log,
        "aggregate_metrics.csv": aggregate,
        "cell_metrics.csv": cells,
        "protocol_effects.csv": effects,
        "ranking_concordance.csv": concordance,
        "bootstrap_summary.csv": bootstrap,
        "bootstrap_draws.csv": bootstrap_draws,
        "bootstrap_draw_plan.csv": draw_plan,
        "sensor_gap_differences.csv": gap_differences,
        "sensor_gap_difference_draws.csv": gap_difference_draws,
        "bearing_reidentification_fit_log.csv": reidentification_fit_log,
        "bearing_reidentification_metrics.csv": reidentification,
    }
    predictions.to_parquet(arguments.output_dir / "predictions.parquet", index=False)
    reidentification_predictions.to_parquet(
        arguments.output_dir / "bearing_reidentification_predictions.parquet",
        index=False,
    )
    for filename, table in tables.items():
        _write_csv(arguments.output_dir / filename, table)

    output_files = [
        "predictions.parquet",
        "bearing_reidentification_predictions.parquet",
        *tables,
    ]
    output_hashes = {
        filename: _sha256(arguments.output_dir / filename)
        for filename in sorted(output_files)
    }
    expected_fault_rows = (
        len(frame) * len(MAIN_SIGNAL_FEATURE_FAMILIES) * len(PROTOCOLS) * len(MODEL_NAMES)
    )
    expected_reidentification_rows = (
        len(frame) * len(MAIN_SIGNAL_FEATURE_FAMILIES) * len(MODEL_NAMES)
    )
    if len(predictions) != expected_fault_rows:
        raise ValueError("sensor fault prediction topology changed")
    if len(reidentification_predictions) != expected_reidentification_rows:
        raise ValueError("bearing re-identification topology changed")
    summary = {
        "schema_version": SCHEMA_VERSION,
        "status": "retrospective_development_not_confirmatory",
        "inputs_sha256": input_hashes,
        "design": {
            "row_count": len(frame),
            "feature_families": list(MAIN_SIGNAL_FEATURE_FAMILIES),
            "protocols": list(PROTOCOLS),
            "models": list(MODEL_NAMES),
            "fault_prediction_rows": len(predictions),
            "bearing_reidentification_prediction_rows": len(
                reidentification_predictions
            ),
            "bootstrap_draws": arguments.bootstrap_draws,
            "bootstrap_unit": "bearing_code_stratified_by_truth_shared_plan",
            "configuration_search": "none",
        },
        "findings": _findings(
            aggregate,
            bootstrap,
            gap_differences,
            reidentification,
        ),
        "output_sha256": output_hashes,
    }
    _write_json(arguments.output_dir / "sensor_protocol_audit_summary.json", summary)
    print(json.dumps(summary["findings"], ensure_ascii=False, indent=2, sort_keys=True))
    print(json.dumps(output_hashes, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
