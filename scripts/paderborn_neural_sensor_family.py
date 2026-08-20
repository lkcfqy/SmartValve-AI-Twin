#!/usr/bin/env python3
"""Run one sealed neural Paderborn sensor-family protocol audit."""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict
from pathlib import Path
from typing import Any

import numpy as np
import paderborn_neural_protocol_contrast as base
import pandas as pd
import torch

from smartvalve.config import project_root
from smartvalve.data.paderborn_features import (
    MAIN_SIGNAL_FEATURE_FAMILIES,
    main_signal_feature_family_names,
)
from smartvalve.experiments.cranfield_causal_audit import AUDIT_SEEDS
from smartvalve.experiments.paderborn_evaluation import (
    METHODS,
    load_sealed_configurations,
)
from smartvalve.experiments.paderborn_protocol_contrast import (
    BOOTSTRAP_DRAWS,
    PROBABILITY_COLUMNS,
    PROTOCOLS,
    RANDOM_SEED,
    attach_common_cells,
    build_protocol_model_folds,
    ensemble_seed_predictions,
    paired_bearing_bootstrap,
    protocol_effect_table,
    protocol_rank_concordance,
    score_oof_predictions,
)

RUN_VERSION = "smartvalve-paderborn-neural-sensor-family-0.1.0"
EXPECTED_FEATURE_SHA256 = "c5caf0cfc408057ae4bfaebef37abdf597135620105ec62e17f3aece6800aff4"
EXPECTED_SENSOR_SEAL_SHA256 = (
    "f70d2ab0e3aa6cecdff8dc43e7147fe1391272cc369f8f166c217f0035e3c266"
)
EXPECTED_PROSPECTIVE_SEAL_SHA256 = (
    "b907e1e0e6876e1e35166a526a6d019df83e1587246784588fb0bda44a71efe1"
)
EXPECTED_DEVELOPMENT_HASHES = {
    "pirl_metrics_sha256": "90bf71655ef2dbee9ab46ba2cb614f4c100d4553b6b4e94ffe5db140e21f72f7",
    "dg_metrics_sha256": "7d885242f5bd74bed650488c7d4dbd4483ab1153ec330914d98edf838a46827b",
}
EXPECTED_FITS = 40 * len(METHODS) * len(AUDIT_SEEDS)
EXPECTED_PREDICTIONS = 2_319 * len(PROTOCOLS) * len(METHODS) * len(AUDIT_SEEDS)


def _checkpoint(
    output_directory: Path,
    protocol: str,
    prediction_frames: list[pd.DataFrame],
    fit_records: list[dict[str, Any]],
    traces: list[dict[str, Any]],
) -> None:
    pd.concat(prediction_frames, ignore_index=True).to_parquet(
        output_directory / f"checkpoint_through_{protocol}_predictions.parquet",
        index=False,
    )
    base._write_csv(output_directory / "checkpoint_fit_log.csv", pd.DataFrame(fit_records))
    base._write_json(output_directory / "checkpoint_training_traces.json", traces)


def _train_all_protocols(
    protocol_folds: dict[str, tuple],
    configurations: dict,
    candidate_ids: dict[str, str],
    *,
    feature_family: str,
    device: str,
    output_directory: Path,
) -> tuple[pd.DataFrame, pd.DataFrame, list[dict[str, Any]]]:
    prediction_frames: list[pd.DataFrame] = []
    fit_records: list[dict[str, Any]] = []
    traces: list[dict[str, Any]] = []
    completed = 0
    for protocol in PROTOCOLS:
        protocol_predictions = []
        for method in METHODS:
            for seed in AUDIT_SEEDS:
                for model_fold in protocol_folds[protocol]:
                    probabilities, fit_record, trace = base._fit_target(
                        model_fold,
                        configurations[method],
                        method=method,
                        seed=int(seed),
                        device=device,
                    )
                    target = pd.DataFrame(
                        {
                            "protocol": protocol,
                            "method": method,
                            "seed": int(seed),
                            "fold_id": model_fold.fold.fold_id,
                            "row_index": model_fold.target_global_indices,
                            "probability_healthy": probabilities[:, 0],
                            "probability_outer": probabilities[:, 1],
                            "probability_inner": probabilities[:, 2],
                        }
                    )
                    protocol_predictions.append(target)
                    fit_record["feature_family"] = feature_family
                    fit_record["feature_count"] = len(model_fold.fold.feature_names)
                    fit_record["candidate_id"] = candidate_ids[method]
                    trace["feature_family"] = feature_family
                    traces.append(trace)
                    fit_records.append(fit_record)
                    completed += 1
                    print(
                        json.dumps(
                            {
                                "event": "neural_sensor_fit_complete",
                                "completed": completed,
                                "expected": EXPECTED_FITS,
                                **fit_record,
                            },
                            sort_keys=True,
                        ),
                        flush=True,
                    )
        protocol_frame = pd.concat(protocol_predictions, ignore_index=True)
        prediction_frames.append(protocol_frame)
        _checkpoint(
            output_directory,
            protocol,
            prediction_frames,
            fit_records,
            traces,
        )
    if len(fit_records) != EXPECTED_FITS:
        raise ValueError("neural sensor-family fit count changed")
    return (
        pd.concat(prediction_frames, ignore_index=True),
        pd.DataFrame(fit_records),
        traces,
    )


def _validate_predictions(predictions: pd.DataFrame) -> dict[str, Any]:
    if len(predictions) != EXPECTED_PREDICTIONS:
        raise ValueError("neural sensor-family prediction count changed")
    key = ["protocol", "method", "seed", "row_index"]
    if predictions.duplicated(key).any():
        raise ValueError("neural sensor-family predictions contain duplicate keys")
    counts = predictions.groupby(["protocol", "method", "seed"], observed=True).size()
    if len(counts) != len(PROTOCOLS) * len(METHODS) * len(AUDIT_SEEDS):
        raise ValueError("neural sensor-family prediction group count changed")
    if not (counts == 2_319).all():
        raise ValueError("a neural sensor-family group does not predict every row")
    probabilities = predictions.loc[:, PROBABILITY_COLUMNS].to_numpy(dtype=float)
    maximum_error = float(np.max(np.abs(probabilities.sum(axis=1) - 1.0)))
    if not np.isfinite(probabilities).all() or maximum_error > 2e-6:
        raise ValueError("neural sensor-family probabilities are invalid")
    return {
        "prediction_rows": len(predictions),
        "protocol_method_seed_groups": len(counts),
        "maximum_probability_sum_error": maximum_error,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--features", type=Path, required=True)
    parser.add_argument("--sensor-seal", type=Path, required=True)
    parser.add_argument("--prospective-seal", type=Path, required=True)
    parser.add_argument(
        "--feature-family",
        choices=MAIN_SIGNAL_FEATURE_FAMILIES[:-1],
        required=True,
    )
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--device", default="cuda:0")
    parser.add_argument("--bootstrap-draws", type=int, default=BOOTSTRAP_DRAWS)
    return parser


def main() -> int:
    arguments = build_parser().parse_args()
    input_hashes = {
        "features": base._verify_file(
            arguments.features,
            EXPECTED_FEATURE_SHA256,
            "EXP-406 primary features",
        ),
        "sensor_seal": base._verify_file(
            arguments.sensor_seal,
            EXPECTED_SENSOR_SEAL_SHA256,
            "multi-sensor protocol seal",
        ),
        "prospective_seal": base._verify_file(
            arguments.prospective_seal,
            EXPECTED_PROSPECTIVE_SEAL_SHA256,
            "D2 prospective seal",
        ),
    }
    arguments.output_dir.mkdir(parents=True, exist_ok=True)
    if any(arguments.output_dir.iterdir()):
        raise ValueError("output directory must be empty")
    if arguments.device.startswith("cuda") and not torch.cuda.is_available():
        raise RuntimeError("the sealed neural sensor audit requires CUDA")
    if arguments.device.startswith("cuda"):
        torch.cuda.init()

    root = project_root().resolve()
    frame = attach_common_cells(pd.read_parquet(arguments.features).reset_index(drop=True))
    prospective_seal = json.loads(arguments.prospective_seal.read_text(encoding="utf-8"))
    configurations, candidate_ids, development_hashes = load_sealed_configurations(
        root,
        prospective_seal,
    )
    if development_hashes != EXPECTED_DEVELOPMENT_HASHES:
        raise ValueError("D0/D1 selected-configuration references changed")
    if tuple(configurations) != METHODS or set(candidate_ids) != set(METHODS):
        raise ValueError("the frozen nine-method configuration order changed")
    feature_names = main_signal_feature_family_names(arguments.feature_family)
    protocol_folds = build_protocol_model_folds(
        frame,
        random_seed=RANDOM_SEED,
        feature_names=feature_names,
    )
    configuration_record = {
        "run_version": RUN_VERSION,
        "feature_family": arguments.feature_family,
        "feature_names": list(feature_names),
        "methods": list(METHODS),
        "seeds": [int(seed) for seed in AUDIT_SEEDS],
        "candidate_ids": candidate_ids,
        "configurations": {method: asdict(configurations[method]) for method in METHODS},
        "development_hashes": development_hashes,
    }
    base._write_json(
        arguments.output_dir / "frozen_configurations.json",
        configuration_record,
    )

    raw_predictions, fit_log, traces = _train_all_protocols(
        protocol_folds,
        configurations,
        candidate_ids,
        feature_family=arguments.feature_family,
        device=arguments.device,
        output_directory=arguments.output_dir,
    )
    predictions = base._attach_metadata(raw_predictions, frame)
    topology = _validate_predictions(predictions)
    predictions = predictions.sort_values(
        ["protocol", "method", "seed", "row_index"], kind="stable"
    ).reset_index(drop=True)
    ensemble = ensemble_seed_predictions(
        predictions,
        expected_seeds=tuple(int(seed) for seed in AUDIT_SEEDS),
    )
    aggregate, cells = score_oof_predictions(ensemble)
    effects = protocol_effect_table(aggregate)
    concordance = protocol_rank_concordance(aggregate)
    bootstrap, bootstrap_draws, draw_plan = paired_bearing_bootstrap(
        ensemble,
        draws=arguments.bootstrap_draws,
        random_seed=RANDOM_SEED,
    )
    method_minus_erm = base._method_minus_erm(aggregate)
    rank_shifts = base._rank_shifts(aggregate)

    tables = {
        "fit_log.csv": fit_log,
        "aggregate_metrics.csv": aggregate,
        "cell_metrics.csv": cells,
        "protocol_effects.csv": effects,
        "ranking_concordance.csv": concordance,
        "bootstrap_summary.csv": bootstrap,
        "bootstrap_draws.csv": bootstrap_draws,
        "bootstrap_draw_plan.csv": draw_plan,
        "method_minus_erm.csv": method_minus_erm,
        "rank_shifts.csv": rank_shifts,
    }
    predictions.to_parquet(arguments.output_dir / "predictions.parquet", index=False)
    ensemble.to_parquet(arguments.output_dir / "ensemble_predictions.parquet", index=False)
    base._write_json(arguments.output_dir / "training_traces.json", traces)
    for filename, table in tables.items():
        base._write_csv(arguments.output_dir / filename, table)
    output_files = [
        "frozen_configurations.json",
        "predictions.parquet",
        "ensemble_predictions.parquet",
        "training_traces.json",
        *tables,
    ]
    output_hashes = {
        filename: base._sha256(arguments.output_dir / filename)
        for filename in sorted(output_files)
    }
    summary = {
        "run_version": RUN_VERSION,
        "status": "retrospective_development_not_confirmatory",
        "inputs_sha256": input_hashes,
        "design": {
            "feature_family": arguments.feature_family,
            "feature_count": len(feature_names),
            "row_count": len(frame),
            "protocols": list(PROTOCOLS),
            "methods": list(METHODS),
            "seeds": [int(seed) for seed in AUDIT_SEEDS],
            "fit_count": len(fit_log),
            "bootstrap_draws": arguments.bootstrap_draws,
            "bootstrap_unit": "bearing_code_stratified_by_truth",
            "configuration_search": "none",
        },
        "integrity": topology,
        "findings": base._summary_findings(
            aggregate,
            bootstrap,
            concordance,
            rank_shifts,
        ),
        "output_sha256": output_hashes,
    }
    base._write_json(
        arguments.output_dir / "neural_sensor_family_summary.json",
        summary,
    )
    print(json.dumps(summary["findings"], ensure_ascii=False, indent=2, sort_keys=True))
    print(json.dumps(output_hashes, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
