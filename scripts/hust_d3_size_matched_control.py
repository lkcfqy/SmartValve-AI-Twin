#!/usr/bin/env python3
"""Run the pre-outcome-sealed HUST equal-source-volume access control."""

from __future__ import annotations

import argparse
import hashlib
import json
from dataclasses import asdict
from pathlib import Path
from typing import Any

import hust_d3_neural_evaluation as primary
import paderborn_neural_protocol_contrast as training
import pandas as pd
import torch

from smartvalve.config import project_root
from smartvalve.experiments.cranfield_causal_audit import AUDIT_SEEDS
from smartvalve.experiments.hust_evaluation import (
    ensemble_hust_seed_windows,
    hust_confusion_counts,
)
from smartvalve.experiments.hust_protocol import attach_hust_common_cells
from smartvalve.experiments.hust_size_matched_control import (
    REFERENCE_PROTOCOL,
    SIZE_MATCHED_PROTOCOL,
    aggregate_hust_size_matched_records,
    bootstrap_hust_size_matched_comparison,
    build_hust_size_matched_model_folds,
    hust_size_matched_gate,
    hust_size_matched_rank_concordance,
    score_hust_size_matched_comparison,
)
from smartvalve.experiments.paderborn_evaluation import (
    METHODS,
    load_sealed_configurations,
)

RUN_VERSION = "smartvalve-hust-d3-size-matched-control-0.1.0"
EXPECTED_FITS = 15 * len(METHODS) * len(AUDIT_SEEDS)
EXPECTED_SEED_WINDOW_PREDICTIONS = 450 * len(METHODS) * len(AUDIT_SEEDS)
EXPECTED_COUNTS = {
    "fit_count": 675,
    "dann_auxiliary_states": 75,
    "seed_window_predictions": 20_250,
    "ensemble_window_predictions": 4_050,
    "size_matched_recording_predictions": 405,
    "combined_recording_predictions": 810,
    "aggregate_metrics": 18,
    "cell_metrics": 270,
    "ranking_concordance": 2,
    "bootstrap_summary": 9,
    "bootstrap_draws": 45_000,
    "bootstrap_draw_plan": 5_000,
    "rank_shifts": 18,
    "confusion_counts": 162,
    "recording_diagnostics": 18,
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


def _checkpoint(
    output_directory: Path,
    method: str,
    prediction_frames: list[pd.DataFrame],
    fits: list[dict[str, Any]],
    traces: list[dict[str, Any]],
) -> None:
    pd.concat(prediction_frames, ignore_index=True).to_parquet(
        output_directory / f"checkpoint_through_{method}_predictions.parquet",
        index=False,
    )
    training._write_csv(output_directory / "checkpoint_fit_log.csv", pd.DataFrame(fits))
    training._write_json(output_directory / "checkpoint_training_traces.json", traces)


def _train(
    folds: tuple,
    configurations: dict,
    candidate_ids: dict[str, str],
    *,
    device: str,
    output_directory: Path,
) -> tuple[pd.DataFrame, pd.DataFrame, list[dict[str, Any]]]:
    prediction_frames: list[pd.DataFrame] = []
    fits: list[dict[str, Any]] = []
    traces: list[dict[str, Any]] = []
    completed = 0
    for method in METHODS:
        method_predictions = []
        for seed in AUDIT_SEEDS:
            for model_fold in folds:
                probabilities, fit_record, trace = training._fit_target(
                    model_fold,
                    configurations[method],
                    method=method,
                    seed=int(seed),
                    device=device,
                )
                method_predictions.append(
                    pd.DataFrame(
                        {
                            "protocol": SIZE_MATCHED_PROTOCOL,
                            "method": method,
                            "seed": int(seed),
                            "fold_id": model_fold.fold.fold_id,
                            "row_index": model_fold.target_global_indices,
                            "probability_healthy": probabilities[:, 0],
                            "probability_outer": probabilities[:, 1],
                            "probability_inner": probabilities[:, 2],
                        }
                    )
                )
                fit_record["candidate_id"] = candidate_ids[method]
                fit_record["feature_count"] = len(model_fold.fold.feature_names)
                fits.append(fit_record)
                traces.append(trace)
                completed += 1
                print(
                    json.dumps(
                        {
                            "event": "hust_d3_size_matched_fit_complete",
                            "completed": completed,
                            "expected": EXPECTED_FITS,
                            **fit_record,
                        },
                        sort_keys=True,
                    ),
                    flush=True,
                )
        prediction_frames.append(pd.concat(method_predictions, ignore_index=True))
        _checkpoint(output_directory, method, prediction_frames, fits, traces)
    if len(fits) != EXPECTED_FITS:
        raise ValueError("HUST size-matched fit count changed")
    return pd.concat(prediction_frames, ignore_index=True), pd.DataFrame(fits), traces


def _validate_primary_result(directory: Path) -> tuple[dict[str, Any], pd.DataFrame]:
    metadata = json.loads((directory / "../metadata.json").resolve().read_text(encoding="utf-8"))
    if metadata.get("status") != "complete" or metadata.get("exit_code") != 0:
        raise ValueError("primary HUST recorded run is not complete")
    summary_path = directory / "hust_d3_summary.json"
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    design = summary.get("design", {})
    if (
        summary.get("run_version") != primary.RUN_VERSION
        or design.get("fit_count") != 1_260
        or design.get("recording_predictions") != 1_620
        or design.get("methods") != list(METHODS)
        or design.get("seeds") != [int(seed) for seed in AUDIT_SEEDS]
    ):
        raise ValueError("primary HUST summary identity or counts changed")
    for filename, expected_hash in summary.get("output_sha256", {}).items():
        _verify(directory / filename, expected_hash, f"primary HUST output {filename}")
    records = pd.read_parquet(directory / "recording_predictions.parquet")
    crossed = records.loc[records["protocol"] == REFERENCE_PROTOCOL].reset_index(drop=True)
    if len(crossed) != 405 or crossed.groupby("method", observed=True).size().ne(45).any():
        raise ValueError("primary HUST crossed recording predictions changed")
    return summary, crossed


def _rank_shifts(aggregate: pd.DataFrame) -> pd.DataFrame:
    records = []
    values = aggregate.set_index(["protocol", "method"])
    for method in METHODS:
        for metric in ("pooled_macro_f1", "mean_cell_macro_f1"):
            rank_column = f"rank_{metric}"
            comparison = float(values.loc[(SIZE_MATCHED_PROTOCOL, method), rank_column])
            reference = float(values.loc[(REFERENCE_PROTOCOL, method), rank_column])
            records.append(
                {
                    "comparison_protocol": SIZE_MATCHED_PROTOCOL,
                    "reference_protocol": REFERENCE_PROTOCOL,
                    "method": method,
                    "rank_endpoint": metric,
                    "comparison_rank": comparison,
                    "crossed_rank": reference,
                    "rank_change_comparison_minus_crossed": comparison - reference,
                }
            )
    return pd.DataFrame(records)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--features", type=Path, required=True)
    parser.add_argument("--expected-manifest", type=Path, required=True)
    parser.add_argument("--execution-seal", type=Path, required=True)
    parser.add_argument("--execution-seal-sha256", required=True)
    parser.add_argument("--prospective-seal", type=Path, required=True)
    parser.add_argument("--primary-result-dir", type=Path, required=True)
    parser.add_argument("--control-seal", type=Path, required=True)
    parser.add_argument("--control-seal-sha256", required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--device", default="cuda:0")
    parser.add_argument("--bootstrap-draws", type=int, default=5_000)
    return parser


def main() -> int:
    arguments = build_parser().parse_args()
    execution = primary._validate_execution_seal(
        arguments.execution_seal,
        expected_sha256=arguments.execution_seal_sha256,
        feature_path=arguments.features,
        expected_manifest_path=arguments.expected_manifest,
    )
    _verify(
        arguments.prospective_seal,
        primary.EXPECTED_PROSPECTIVE_SEAL_SHA256,
        "D0/D1 prospective configuration seal",
    )
    expected = json.loads(arguments.expected_manifest.read_text(encoding="utf-8"))
    primary._validate_expected_manifest(expected)
    control_seal_sha256 = _verify(
        arguments.control_seal,
        arguments.control_seal_sha256,
        "HUST size-matched control seal",
    )
    if arguments.bootstrap_draws != 5_000:
        raise ValueError("HUST size-matched bootstrap draw count must remain 5000")
    arguments.output_dir.mkdir(parents=True, exist_ok=True)
    if any(arguments.output_dir.iterdir()):
        raise ValueError("output directory must be empty")
    if arguments.device.startswith("cuda") and not torch.cuda.is_available():
        raise RuntimeError("sealed HUST size-matched control requires CUDA")
    if arguments.device.startswith("cuda"):
        torch.cuda.init()

    primary_summary, crossed_records = _validate_primary_result(arguments.primary_result_dir)
    frame = attach_hust_common_cells(pd.read_parquet(arguments.features).reset_index(drop=True))
    prospective = json.loads(arguments.prospective_seal.read_text(encoding="utf-8"))
    configurations, candidate_ids, development_hashes = load_sealed_configurations(
        project_root().resolve(), prospective
    )
    if (
        development_hashes != primary.EXPECTED_DEVELOPMENT_HASHES
        or tuple(configurations) != METHODS
        or candidate_ids != expected["configuration"]["candidate_ids"]
        or {method: asdict(configurations[method]) for method in METHODS}
        != expected["configuration"]["selected_configurations"]
    ):
        raise ValueError("HUST size-matched configurations differ from the primary seal")
    folds = build_hust_size_matched_model_folds(frame)
    training._write_json(
        arguments.output_dir / "frozen_configurations.json",
        {
            "run_version": RUN_VERSION,
            "methods": list(METHODS),
            "seeds": [int(seed) for seed in AUDIT_SEEDS],
            "candidate_ids": candidate_ids,
            "configurations": {method: asdict(configurations[method]) for method in METHODS},
            "development_hashes": development_hashes,
            "execution_seal_sha256": arguments.execution_seal_sha256,
            "control_seal_sha256": control_seal_sha256,
        },
    )
    raw, fit_log, traces = _train(
        folds,
        configurations,
        candidate_ids,
        device=arguments.device,
        output_directory=arguments.output_dir,
    )
    predictions = (
        primary._attach_metadata(raw, frame)
        .sort_values(["method", "seed", "row_index"], kind="stable")
        .reset_index(drop=True)
    )
    if len(predictions) != EXPECTED_SEED_WINDOW_PREDICTIONS:
        raise ValueError("HUST size-matched seed-window prediction count changed")
    window_ensemble = ensemble_hust_seed_windows(
        predictions,
        expected_seeds=tuple(int(seed) for seed in AUDIT_SEEDS),
    )
    size_records = aggregate_hust_size_matched_records(window_ensemble)
    combined_records = pd.concat((size_records, crossed_records), ignore_index=True)
    aggregate, cells = score_hust_size_matched_comparison(size_records, crossed_records)
    concordance = hust_size_matched_rank_concordance(aggregate)
    bootstrap, bootstrap_draws, draw_plan = bootstrap_hust_size_matched_comparison(
        combined_records,
        draws=arguments.bootstrap_draws,
    )
    rank_shifts = _rank_shifts(aggregate)
    confusion = hust_confusion_counts(combined_records)
    diagnostics = primary._record_diagnostics(combined_records)
    observed_counts = {
        "fit_count": len(fit_log),
        "dann_auxiliary_states": int(
            fit_log.loc[fit_log["method"] == "dann", "auxiliary_state_sha256"].notna().sum()
        ),
        "seed_window_predictions": len(predictions),
        "ensemble_window_predictions": len(window_ensemble),
        "size_matched_recording_predictions": len(size_records),
        "combined_recording_predictions": len(combined_records),
        "aggregate_metrics": len(aggregate),
        "cell_metrics": len(cells),
        "ranking_concordance": len(concordance),
        "bootstrap_summary": len(bootstrap),
        "bootstrap_draws": len(bootstrap_draws),
        "bootstrap_draw_plan": len(draw_plan),
        "rank_shifts": len(rank_shifts),
        "confusion_counts": len(confusion),
        "recording_diagnostics": len(diagnostics),
    }
    if observed_counts != EXPECTED_COUNTS:
        raise ValueError(
            f"HUST size-matched output counts changed: {observed_counts} != {EXPECTED_COUNTS}"
        )

    predictions.to_parquet(arguments.output_dir / "seed_window_predictions.parquet", index=False)
    window_ensemble.to_parquet(
        arguments.output_dir / "ensemble_window_predictions.parquet", index=False
    )
    size_records.to_parquet(
        arguments.output_dir / "size_matched_recording_predictions.parquet", index=False
    )
    combined_records.to_parquet(
        arguments.output_dir / "combined_recording_predictions.parquet", index=False
    )
    training._write_json(arguments.output_dir / "training_traces.json", traces)
    tables = {
        "fit_log.csv": fit_log,
        "aggregate_metrics.csv": aggregate,
        "cell_metrics.csv": cells,
        "ranking_concordance.csv": concordance,
        "bootstrap_summary.csv": bootstrap,
        "bootstrap_draws.csv": bootstrap_draws,
        "bootstrap_draw_plan.csv": draw_plan,
        "rank_shifts.csv": rank_shifts,
        "confusion_counts.csv": confusion,
        "recording_diagnostics.csv": diagnostics,
    }
    for filename, table in tables.items():
        training._write_csv(arguments.output_dir / filename, table)
    output_files = [
        "frozen_configurations.json",
        "seed_window_predictions.parquet",
        "ensemble_window_predictions.parquet",
        "size_matched_recording_predictions.parquet",
        "combined_recording_predictions.parquet",
        "training_traces.json",
        *tables,
    ]
    hashes = {
        filename: _sha256(arguments.output_dir / filename) for filename in sorted(output_files)
    }
    summary = {
        "run_version": RUN_VERSION,
        "status": "outcome_blind_equal_source_volume_control",
        "control_seal_sha256": control_seal_sha256,
        "execution_seal_sha256": arguments.execution_seal_sha256,
        "primary_hust_summary_sha256": _sha256(
            arguments.primary_result_dir / "hust_d3_summary.json"
        ),
        "primary_hust_output_sha256": primary_summary["output_sha256"],
        "design": {
            "source_recordings_per_fold": 24,
            "target_recordings_per_fold": 3,
            "inaccessible_recordings_per_fold": 18,
            "folds": 15,
            "methods": list(METHODS),
            "seeds": [int(seed) for seed in AUDIT_SEEDS],
            "fit_count": len(fit_log),
            "bootstrap_draws": arguments.bootstrap_draws,
        },
        "findings": hust_size_matched_gate(aggregate, concordance),
        "output_sha256": hashes,
        "execution_seal": execution,
    }
    training._write_json(arguments.output_dir / "hust_d3_size_matched_summary.json", summary)
    print(json.dumps(summary["findings"], indent=2, sort_keys=True))
    print(json.dumps(hashes, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
