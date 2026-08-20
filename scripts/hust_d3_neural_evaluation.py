#!/usr/bin/env python3
"""Run the one-shot sealed HUST D3 four-protocol neural evaluation."""

from __future__ import annotations

import argparse
import hashlib
import json
from dataclasses import asdict
from pathlib import Path
from typing import Any

import numpy as np
import paderborn_neural_protocol_contrast as training
import pandas as pd
import torch

from smartvalve.config import project_root
from smartvalve.data.hust import HUST_LABELS
from smartvalve.experiments.cranfield_causal_audit import AUDIT_SEEDS
from smartvalve.experiments.dg_expected_manifest import canonical_key_record
from smartvalve.experiments.hust_evaluation import (
    HUST_BOOTSTRAP_DRAWS,
    aggregate_hust_record_predictions,
    bootstrap_hust_record_predictions,
    ensemble_hust_seed_windows,
    hust_confusion_counts,
    hust_protocol_effect_table,
    hust_rank_concordance,
    hust_replication_gate,
    score_hust_record_predictions,
)
from smartvalve.experiments.hust_expected_manifest import (
    EXPECTED_COUNTS,
    KEY_SCHEMAS,
)
from smartvalve.experiments.hust_expected_manifest import (
    SCHEMA_VERSION as EXPECTED_MANIFEST_SCHEMA,
)
from smartvalve.experiments.hust_protocol import (
    HUST_PROTOCOLS,
    HUST_RANDOM_SEED,
    attach_hust_common_cells,
    build_hust_protocol_model_folds,
)
from smartvalve.experiments.paderborn_evaluation import (
    METHODS,
    load_sealed_configurations,
)
from smartvalve.experiments.paderborn_protocol_contrast import PROBABILITY_COLUMNS

RUN_VERSION = "smartvalve-hust-d3-neural-evaluation-0.1.0"
EXPECTED_ORIGINAL_SEAL_SHA256 = "eb66d23601ba21fe70b125d503ec56c51fbcfc2f5c59d6d1f2bf4335485428ef"
EXPECTED_PROSPECTIVE_SEAL_SHA256 = (
    "b907e1e0e6876e1e35166a526a6d019df83e1587246784588fb0bda44a71efe1"
)
EXPECTED_DEVELOPMENT_HASHES = {
    "pirl_metrics_sha256": "90bf71655ef2dbee9ab46ba2cb614f4c100d4553b6b4e94ffe5db140e21f72f7",
    "dg_metrics_sha256": "7d885242f5bd74bed650488c7d4dbd4483ab1153ec330914d98edf838a46827b",
}
EXPECTED_FITS = 28 * len(METHODS) * len(AUDIT_SEEDS)
EXPECTED_SEED_WINDOW_PREDICTIONS = 450 * len(HUST_PROTOCOLS) * len(METHODS) * len(AUDIT_SEEDS)


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


def _validate_execution_seal(
    path: Path,
    *,
    expected_sha256: str,
    feature_path: Path,
    expected_manifest_path: Path,
) -> dict[str, Any]:
    _verify(path, expected_sha256, "HUST D3 execution seal")
    seal = json.loads(path.read_text(encoding="utf-8"))
    if (
        seal.get("schema_version") != "smartvalve-hust-d3-execution-seal-0.1.0"
        or seal.get("status") != "sealed_after_features_before_model_outcomes"
        or seal.get("original_factorial_seal_sha256") != EXPECTED_ORIGINAL_SEAL_SHA256
    ):
        raise ValueError("HUST D3 execution seal identity changed")
    feature = seal.get("feature_matrix", {})
    expected = seal.get("expected_manifest", {})
    if (
        Path(str(feature.get("path", ""))).resolve() != feature_path.resolve()
        or feature.get("sha256") != _sha256(feature_path)
        or feature.get("rows") != 450
        or feature.get("features") != 24
    ):
        raise ValueError("HUST execution seal references different features")
    if Path(
        str(expected.get("path", ""))
    ).resolve() != expected_manifest_path.resolve() or expected.get("sha256") != _sha256(
        expected_manifest_path
    ):
        raise ValueError("HUST execution seal references another expected manifest")
    return seal


def _validate_expected_manifest(manifest: dict[str, Any]) -> None:
    if (
        manifest.get("schema_version") != EXPECTED_MANIFEST_SCHEMA
        or manifest.get("status") != "sealed_metadata_only_before_hust_signal_access"
        or manifest.get("expected_counts") != EXPECTED_COUNTS
        or manifest.get("class_semantics", {}).get("probability_order") != list(HUST_LABELS)
        or manifest.get("class_semantics", {}).get("condition_order") != ["N", "O", "I"]
    ):
        raise ValueError("HUST expected manifest identity, counts, or class semantics changed")


def _validate_key_set(
    frame: pd.DataFrame,
    *,
    name: str,
    expected: dict[str, Any],
) -> None:
    columns = KEY_SCHEMAS[name]
    if set(columns) - set(frame):
        raise ValueError(f"HUST {name} output lacks expected-key columns")
    observed = canonical_key_record(
        frame.loc[:, columns].itertuples(index=False, name=None),
        columns,
    )
    if observed != expected:
        raise ValueError(f"HUST {name} keys differ from the pre-access manifest")


def _attach_metadata(predictions: pd.DataFrame, frame: pd.DataFrame) -> pd.DataFrame:
    result = predictions.copy()
    row_indices = result["row_index"].to_numpy(dtype=np.int64)
    if (row_indices < 0).any() or (row_indices >= len(frame)).any():
        raise ValueError("HUST prediction row index falls outside the feature matrix")
    aligned = frame.iloc[row_indices].reset_index(drop=True)
    for column in (
        "filename",
        "bearing_code",
        "specification_group",
        "load_w",
        "truth",
        "window_index",
        "evaluation_cell",
    ):
        result[column] = aligned[column].to_numpy()
    values = result.loc[:, PROBABILITY_COLUMNS].to_numpy(dtype=float)
    result["prediction"] = np.asarray(HUST_LABELS)[values.argmax(axis=1)]
    return result


def _checkpoint(
    output_directory: Path,
    protocol: str,
    prediction_frames: list[pd.DataFrame],
    fits: list[dict[str, Any]],
    traces: list[dict[str, Any]],
) -> None:
    pd.concat(prediction_frames, ignore_index=True).to_parquet(
        output_directory / f"checkpoint_through_{protocol}_predictions.parquet",
        index=False,
    )
    training._write_csv(output_directory / "checkpoint_fit_log.csv", pd.DataFrame(fits))
    training._write_json(output_directory / "checkpoint_training_traces.json", traces)


def _train(
    protocol_folds: dict[str, tuple],
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
    for protocol in HUST_PROTOCOLS:
        protocol_predictions = []
        for method in METHODS:
            for seed in AUDIT_SEEDS:
                for model_fold in protocol_folds[protocol]:
                    probabilities, fit_record, trace = training._fit_target(
                        model_fold,
                        configurations[method],
                        method=method,
                        seed=int(seed),
                        device=device,
                    )
                    protocol_predictions.append(
                        pd.DataFrame(
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
                    )
                    fit_record["candidate_id"] = candidate_ids[method]
                    fit_record["feature_count"] = len(model_fold.fold.feature_names)
                    fits.append(fit_record)
                    traces.append(trace)
                    completed += 1
                    print(
                        json.dumps(
                            {
                                "event": "hust_d3_fit_complete",
                                "completed": completed,
                                "expected": EXPECTED_FITS,
                                **fit_record,
                            },
                            sort_keys=True,
                        ),
                        flush=True,
                    )
        prediction_frames.append(pd.concat(protocol_predictions, ignore_index=True))
        _checkpoint(output_directory, protocol, prediction_frames, fits, traces)
    if len(fits) != EXPECTED_FITS:
        raise ValueError("HUST D3 fit count changed")
    return pd.concat(prediction_frames, ignore_index=True), pd.DataFrame(fits), traces


def _method_minus_erm(aggregate: pd.DataFrame) -> pd.DataFrame:
    records = []
    metrics = ("pooled_macro_f1", "mean_cell_macro_f1", "minimum_cell_macro_f1")
    for protocol, rows in aggregate.groupby("protocol", sort=True, observed=True):
        indexed = rows.set_index("method")
        for method in METHODS:
            for metric in metrics:
                records.append(
                    {
                        "protocol": protocol,
                        "method": method,
                        "reference_method": "erm",
                        "metric": metric,
                        "effect_method_minus_erm": float(
                            indexed.loc[method, metric] - indexed.loc["erm", metric]
                        ),
                    }
                )
    return pd.DataFrame(records)


def _rank_shifts(aggregate: pd.DataFrame) -> pd.DataFrame:
    records = []
    reference = aggregate.loc[aggregate["protocol"] == "crossed_holdout"].set_index("method")
    for protocol in HUST_PROTOCOLS[:-1]:
        comparison = aggregate.loc[aggregate["protocol"] == protocol].set_index("method")
        for method in METHODS:
            for endpoint in ("pooled_macro_f1", "mean_cell_macro_f1"):
                column = f"rank_{endpoint}"
                records.append(
                    {
                        "comparison_protocol": protocol,
                        "reference_protocol": "crossed_holdout",
                        "method": method,
                        "rank_endpoint": endpoint,
                        "comparison_rank": float(comparison.loc[method, column]),
                        "crossed_rank": float(reference.loc[method, column]),
                        "rank_change_comparison_minus_crossed": float(
                            comparison.loc[method, column] - reference.loc[method, column]
                        ),
                    }
                )
    return pd.DataFrame(records)


def _record_diagnostics(records: pd.DataFrame) -> pd.DataFrame:
    return (
        records.groupby(["protocol", "method"], sort=True, observed=True)
        .agg(
            mean_predictive_entropy=("predictive_entropy", "mean"),
            median_predictive_entropy=("predictive_entropy", "median"),
            mean_window_disagreement_rate=("window_disagreement_rate", "mean"),
            maximum_window_disagreement_rate=("window_disagreement_rate", "max"),
        )
        .reset_index()
    )


def _findings(
    aggregate: pd.DataFrame,
    concordance: pd.DataFrame,
    rank_shifts: pd.DataFrame,
) -> dict[str, Any]:
    leaders = {}
    for protocol, rows in aggregate.groupby("protocol", sort=True, observed=True):
        leader = rows.sort_values(
            ["pooled_macro_f1", "method"], ascending=[False, True], kind="stable"
        ).iloc[0]
        leaders[str(protocol)] = {
            "method": str(leader["method"]),
            "pooled_macro_f1": float(leader["pooled_macro_f1"]),
            "minimum_cell_macro_f1": float(leader["minimum_cell_macro_f1"]),
        }
    largest = rank_shifts.iloc[rank_shifts["rank_change_comparison_minus_crossed"].abs().argmax()]
    return {
        "replication_gate": hust_replication_gate(aggregate, concordance),
        "protocol_leaders": leaders,
        "largest_absolute_rank_shift": {
            "protocol": str(largest["comparison_protocol"]),
            "method": str(largest["method"]),
            "endpoint": str(largest["rank_endpoint"]),
            "comparison_rank": float(largest["comparison_rank"]),
            "crossed_rank": float(largest["crossed_rank"]),
        },
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--features", type=Path, required=True)
    parser.add_argument("--expected-manifest", type=Path, required=True)
    parser.add_argument("--execution-seal", type=Path, required=True)
    parser.add_argument("--execution-seal-sha256", required=True)
    parser.add_argument("--prospective-seal", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--device", default="cuda:0")
    parser.add_argument("--bootstrap-draws", type=int, default=HUST_BOOTSTRAP_DRAWS)
    return parser


def main() -> int:
    arguments = build_parser().parse_args()
    execution = _validate_execution_seal(
        arguments.execution_seal,
        expected_sha256=arguments.execution_seal_sha256,
        feature_path=arguments.features,
        expected_manifest_path=arguments.expected_manifest,
    )
    _verify(
        arguments.prospective_seal,
        EXPECTED_PROSPECTIVE_SEAL_SHA256,
        "D0/D1 prospective configuration seal",
    )
    expected = json.loads(arguments.expected_manifest.read_text(encoding="utf-8"))
    _validate_expected_manifest(expected)
    if arguments.bootstrap_draws != expected["configuration"]["bootstrap_draws"]:
        raise ValueError("HUST bootstrap draw count differs from the pre-access manifest")
    arguments.output_dir.mkdir(parents=True, exist_ok=True)
    if any(arguments.output_dir.iterdir()):
        raise ValueError("output directory must be empty")
    if arguments.device.startswith("cuda") and not torch.cuda.is_available():
        raise RuntimeError("sealed HUST D3 requires CUDA")
    if arguments.device.startswith("cuda"):
        torch.cuda.init()

    frame = attach_hust_common_cells(pd.read_parquet(arguments.features).reset_index(drop=True))
    prospective = json.loads(arguments.prospective_seal.read_text(encoding="utf-8"))
    configurations, candidate_ids, development_hashes = load_sealed_configurations(
        project_root().resolve(),
        prospective,
    )
    if development_hashes != EXPECTED_DEVELOPMENT_HASHES or tuple(configurations) != METHODS:
        raise ValueError("HUST D3 configuration references changed")
    if (
        candidate_ids != expected["configuration"]["candidate_ids"]
        or {method: asdict(configurations[method]) for method in METHODS}
        != expected["configuration"]["selected_configurations"]
    ):
        raise ValueError("HUST D3 selected configurations differ from the expected manifest")
    folds = build_hust_protocol_model_folds(frame, random_seed=HUST_RANDOM_SEED)
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
        _attach_metadata(raw, frame)
        .sort_values(["protocol", "method", "seed", "row_index"], kind="stable")
        .reset_index(drop=True)
    )
    if len(predictions) != EXPECTED_SEED_WINDOW_PREDICTIONS:
        raise ValueError("HUST seed-window prediction count changed")
    _validate_key_set(
        fit_log,
        name="training_fits",
        expected=expected["expected_key_sets"]["training_fits"],
    )
    _validate_key_set(
        predictions,
        name="seed_window_predictions",
        expected=expected["expected_key_sets"]["seed_window_predictions"],
    )
    window_ensemble = ensemble_hust_seed_windows(
        predictions,
        expected_seeds=tuple(int(seed) for seed in AUDIT_SEEDS),
    )
    recording_predictions = aggregate_hust_record_predictions(window_ensemble)
    _validate_key_set(
        window_ensemble,
        name="ensemble_window_predictions",
        expected=expected["expected_key_sets"]["ensemble_window_predictions"],
    )
    _validate_key_set(
        recording_predictions,
        name="recording_predictions",
        expected=expected["expected_key_sets"]["recording_predictions"],
    )
    aggregate, cells = score_hust_record_predictions(recording_predictions)
    effects = hust_protocol_effect_table(aggregate)
    concordance = hust_rank_concordance(aggregate)
    bootstrap, bootstrap_draws, draw_plan = bootstrap_hust_record_predictions(
        recording_predictions,
        draws=arguments.bootstrap_draws,
        random_seed=HUST_RANDOM_SEED,
    )
    rank_shifts = _rank_shifts(aggregate)
    method_minus_erm = _method_minus_erm(aggregate)
    confusion = hust_confusion_counts(recording_predictions)
    diagnostics = _record_diagnostics(recording_predictions)
    observed_counts = {
        "fit_count": len(fit_log),
        "dann_auxiliary_states": int(
            fit_log.loc[fit_log["method"] == "dann", "auxiliary_state_sha256"].notna().sum()
        ),
        "seed_window_predictions": len(predictions),
        "ensemble_window_predictions": len(window_ensemble),
        "recording_predictions": len(recording_predictions),
        "aggregate_metrics": len(aggregate),
        "cell_metrics": len(cells),
        "protocol_effects": len(effects),
        "ranking_concordance": len(concordance),
        "bootstrap_summary": len(bootstrap),
        "bootstrap_draws": len(bootstrap_draws),
        "bootstrap_draw_plan": len(draw_plan),
        "rank_shifts": len(rank_shifts),
        "method_minus_erm": len(method_minus_erm),
        "confusion_counts": len(confusion),
        "recording_diagnostics": len(diagnostics),
    }
    for name, observed in observed_counts.items():
        if observed != expected["expected_counts"][name]:
            raise ValueError(f"HUST output count changed for {name}: {observed}")

    predictions.to_parquet(arguments.output_dir / "seed_window_predictions.parquet", index=False)
    window_ensemble.to_parquet(
        arguments.output_dir / "ensemble_window_predictions.parquet", index=False
    )
    recording_predictions.to_parquet(
        arguments.output_dir / "recording_predictions.parquet", index=False
    )
    training._write_json(arguments.output_dir / "training_traces.json", traces)
    tables = {
        "fit_log.csv": fit_log,
        "aggregate_metrics.csv": aggregate,
        "cell_metrics.csv": cells,
        "protocol_effects.csv": effects,
        "ranking_concordance.csv": concordance,
        "bootstrap_summary.csv": bootstrap,
        "bootstrap_draws.csv": bootstrap_draws,
        "bootstrap_draw_plan.csv": draw_plan,
        "rank_shifts.csv": rank_shifts,
        "method_minus_erm.csv": method_minus_erm,
        "confusion_counts.csv": confusion,
        "recording_diagnostics.csv": diagnostics,
    }
    for filename, table in tables.items():
        training._write_csv(arguments.output_dir / filename, table)
    output_files = [
        "frozen_configurations.json",
        "seed_window_predictions.parquet",
        "ensemble_window_predictions.parquet",
        "recording_predictions.parquet",
        "training_traces.json",
        *tables,
    ]
    hashes = {
        filename: _sha256(arguments.output_dir / filename) for filename in sorted(output_files)
    }
    summary = {
        "run_version": RUN_VERSION,
        "status": "one_shot_protocol_prospective_signal_unopened_before_seal",
        "execution_seal": execution,
        "design": {
            "recordings": 45,
            "physical_bearings": 15,
            "window_rows": 450,
            "protocols": list(HUST_PROTOCOLS),
            "methods": list(METHODS),
            "seeds": [int(seed) for seed in AUDIT_SEEDS],
            "fit_count": len(fit_log),
            "seed_window_predictions": len(predictions),
            "recording_predictions": len(recording_predictions),
            "bootstrap_draws": arguments.bootstrap_draws,
            "bootstrap_unit": "bearing_code_stratified_by_truth",
            "configuration_search": "none",
        },
        "findings": _findings(aggregate, concordance, rank_shifts),
        "output_sha256": hashes,
    }
    training._write_json(arguments.output_dir / "hust_d3_summary.json", summary)
    print(json.dumps(summary["findings"], ensure_ascii=False, indent=2, sort_keys=True))
    print(json.dumps(hashes, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
