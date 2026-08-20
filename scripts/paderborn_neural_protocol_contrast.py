#!/usr/bin/env python3
"""Run the frozen nine-method neural Paderborn protocol contrast."""

from __future__ import annotations

import argparse
import hashlib
import json
from dataclasses import asdict, replace
from pathlib import Path
from time import perf_counter
from typing import Any

import numpy as np
import pandas as pd
import torch

from smartvalve.config import project_root
from smartvalve.experiments.cranfield_causal_audit import AUDIT_SEEDS
from smartvalve.experiments.dg_training import (
    BaselineConfig,
    fit_dg_fold,
    predict_dg,
)
from smartvalve.experiments.paderborn_domain import build_paderborn_model_folds
from smartvalve.experiments.paderborn_evaluation import (
    METHODS,
    load_sealed_configurations,
)
from smartvalve.experiments.paderborn_partitions import PADERBORN_LABELS
from smartvalve.experiments.paderborn_protocol_contrast import (
    BOOTSTRAP_DRAWS,
    PROBABILITY_COLUMNS,
    PROTOCOLS,
    RANDOM_SEED,
    SCHEMA_VERSION,
    attach_common_cells,
    build_protocol_model_folds,
    ensemble_seed_predictions,
    paired_bearing_bootstrap,
    protocol_effect_table,
    protocol_rank_concordance,
    score_oof_predictions,
)
from smartvalve.experiments.pirl_sore import TrainingConfig, fit_fold, predict

RUN_VERSION = f"{SCHEMA_VERSION}-neural-0.1.0"
EXPECTED_FEATURE_SHA256 = "c5caf0cfc408057ae4bfaebef37abdf597135620105ec62e17f3aece6800aff4"
EXPECTED_CROSSED_SHA256 = "5e3801e9df4636f180e85ccde060fade77422dfbcb65d5699bf7a93a49d9b400"
EXPECTED_PROSPECTIVE_SEAL_SHA256 = (
    "b907e1e0e6876e1e35166a526a6d019df83e1587246784588fb0bda44a71efe1"
)
EXPECTED_DEVELOPMENT_HASHES = {
    "pirl_metrics_sha256": "90bf71655ef2dbee9ab46ba2cb614f4c100d4553b6b4e94ffe5db140e21f72f7",
    "dg_metrics_sha256": "7d885242f5bd74bed650488c7d4dbd4483ab1153ec330914d98edf838a46827b",
}
TRAINED_PROTOCOLS = PROTOCOLS[:-1]
EXPECTED_NEW_FITS = 16 * len(METHODS) * len(AUDIT_SEEDS)
EXPECTED_SEED_PREDICTIONS = 2_319 * len(PROTOCOLS) * len(METHODS) * len(AUDIT_SEEDS)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _write_json(path: Path, value: Any) -> None:
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _write_csv(path: Path, frame: pd.DataFrame) -> None:
    frame.to_csv(path, index=False, float_format="%.12g", lineterminator="\n")


def _verify_file(path: Path, expected: str, role: str) -> str:
    if not path.is_file():
        raise FileNotFoundError(f"missing {role}: {path}")
    observed = _sha256(path)
    if observed != expected:
        raise ValueError(f"{role} SHA-256 changed: expected {expected}, observed {observed}")
    return observed


def _validate_crossed_fold_parity(frame: pd.DataFrame, protocol_folds: dict[str, tuple]) -> None:
    retrospective = protocol_folds["crossed_holdout"]
    prospective = build_paderborn_model_folds(frame)
    if len(retrospective) != len(prospective):
        raise ValueError("crossed fold count differs from EXP-417")
    for current, frozen in zip(retrospective, prospective, strict=True):
        comparisons = (
            (current.target_global_indices, frozen.target_global_indices, "target"),
            (
                current.quarantine_global_indices,
                frozen.quarantine_global_indices,
                "quarantine",
            ),
            (current.fold.source_features, frozen.fold.source_features, "source features"),
            (current.fold.source_labels, frozen.fold.source_labels, "source labels"),
            (current.fold.nuisance_pairs, frozen.fold.nuisance_pairs, "nuisance pairs"),
            (current.fold.fault_pairs, frozen.fold.fault_pairs, "fault pairs"),
        )
        if current.fold.fold_id != frozen.fold.fold_id:
            raise ValueError("crossed fold identifier differs from EXP-417")
        for observed, expected, role in comparisons:
            if not np.array_equal(observed, expected):
                raise ValueError(f"crossed {role} differ from EXP-417")


def _load_crossed_predictions(path: Path, frame: pd.DataFrame) -> pd.DataFrame:
    source = pd.read_parquet(path)
    expected_methods = set(METHODS)
    expected_seeds = set(int(seed) for seed in AUDIT_SEEDS)
    if (
        len(source) != 104_355
        or set(source["method"].astype(str)) != expected_methods
        or set(source["seed"].astype(int)) != expected_seeds
        or source.groupby(["method", "seed", "fold_id"], observed=True).ngroups != 1_080
    ):
        raise ValueError("EXP-417 crossed prediction topology changed")
    keys = ["method", "seed", "row_index"]
    if source.duplicated(keys).any():
        raise ValueError("EXP-417 contains duplicate crossed row predictions")
    counts = source.groupby(["method", "seed"], observed=True).size()
    if not (counts == len(frame)).all():
        raise ValueError("an EXP-417 model/seed does not predict every row once")
    row_indices = source["row_index"].to_numpy(dtype=np.int64)
    aligned = frame.iloc[row_indices].reset_index(drop=True)
    for column in ("filename", "bearing_code", "setting_code", "measurement_index", "truth"):
        if not np.array_equal(source[column].to_numpy(), aligned[column].to_numpy()):
            raise ValueError(f"EXP-417 {column} differs from the feature matrix")
    probabilities = source.loc[:, PROBABILITY_COLUMNS].to_numpy(dtype=float)
    if not np.isfinite(probabilities).all() or float(
        np.max(np.abs(probabilities.sum(axis=1) - 1.0))
    ) > 2e-6:
        raise ValueError("EXP-417 probabilities are invalid")
    result = source.loc[
        :,
        [
            "method",
            "seed",
            "fold_id",
            "row_index",
            *PROBABILITY_COLUMNS,
        ],
    ].copy()
    result.insert(0, "protocol", "crossed_holdout")
    return result


def _fit_target(
    model_fold: Any,
    configuration: TrainingConfig | BaselineConfig,
    *,
    method: str,
    seed: int,
    device: str,
) -> tuple[np.ndarray, dict[str, Any], dict[str, Any]]:
    final_configuration = replace(configuration, seed=seed)
    if device.startswith("cuda"):
        torch.cuda.reset_peak_memory_stats(0)
    started = perf_counter()
    if method == "pirl_ratio":
        if not isinstance(final_configuration, TrainingConfig):
            raise TypeError("PIRL requires its frozen TrainingConfig")
        fitted = fit_fold(model_fold.fold, final_configuration, device=device)
        bundle = predict(fitted, model_fold.fold.target_features)
    else:
        if not isinstance(final_configuration, BaselineConfig):
            raise TypeError("a DG baseline requires its frozen BaselineConfig")
        fitted = fit_dg_fold(model_fold.fold, final_configuration, device=device)
        bundle = predict_dg(fitted, model_fold.fold.target_features)
    if device.startswith("cuda"):
        torch.cuda.synchronize(0)
    duration = perf_counter() - started
    probabilities = np.asarray(bundle.probabilities, dtype=np.float32)
    if probabilities.shape != (len(model_fold.target_global_indices), len(PADERBORN_LABELS)):
        raise ValueError("neural target probability shape changed")
    if not np.isfinite(probabilities).all() or float(
        np.max(np.abs(probabilities.sum(axis=1) - 1.0))
    ) > 2e-6:
        raise ValueError("neural target probabilities are invalid")
    fit_record = {
        "protocol": model_fold.protocol,
        "fold_id": model_fold.fold.fold_id,
        "method": method,
        "seed": seed,
        "source_count": len(model_fold.fold.source_indices),
        "target_count": len(model_fold.fold.target_indices),
        "quarantine_count": len(model_fold.quarantine_global_indices),
        "source_environment_count": len(np.unique(model_fold.fold.source_environments)),
        "source_nuisance_pair_count": len(model_fold.fold.nuisance_pairs),
        "source_fault_pair_count": len(model_fold.fold.fault_pairs),
        "fit_predict_duration_s": duration,
        "parameter_count_network_only": int(
            sum(parameter.numel() for parameter in fitted.network.parameters())
        ),
        "peak_memory_bytes": (
            int(torch.cuda.max_memory_allocated(0)) if device.startswith("cuda") else None
        ),
        "model_state_sha256": fitted.state_sha256,
        "auxiliary_state_sha256": getattr(fitted, "auxiliary_state_sha256", None),
    }
    trace = {
        "protocol": model_fold.protocol,
        "fold_id": model_fold.fold.fold_id,
        "method": method,
        "seed": seed,
        "configuration": asdict(final_configuration),
        "model_state_sha256": fitted.state_sha256,
        "auxiliary_state_sha256": getattr(fitted, "auxiliary_state_sha256", None),
        "history": fitted.history,
    }
    return probabilities, fit_record, trace


def _train_new_protocols(
    frame: pd.DataFrame,
    protocol_folds: dict[str, tuple],
    configurations: dict[str, TrainingConfig | BaselineConfig],
    candidate_ids: dict[str, str],
    *,
    device: str,
    output_directory: Path,
) -> tuple[pd.DataFrame, pd.DataFrame, list[dict[str, Any]]]:
    prediction_frames = []
    fit_records = []
    traces = []
    completed = 0
    for protocol in TRAINED_PROTOCOLS:
        protocol_predictions = []
        for method in METHODS:
            for seed in AUDIT_SEEDS:
                for model_fold in protocol_folds[protocol]:
                    probabilities, fit_record, trace = _fit_target(
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
                    fit_record["candidate_id"] = candidate_ids[method]
                    fit_records.append(fit_record)
                    traces.append(trace)
                    completed += 1
                    print(
                        json.dumps(
                            {
                                "event": "neural_protocol_fit_complete",
                                "completed": completed,
                                "expected": EXPECTED_NEW_FITS,
                                **fit_record,
                            },
                            sort_keys=True,
                        ),
                        flush=True,
                    )
        protocol_frame = pd.concat(protocol_predictions, ignore_index=True)
        protocol_frame.to_parquet(
            output_directory / f"checkpoint_{protocol}_predictions.parquet",
            index=False,
        )
        prediction_frames.append(protocol_frame)
        _write_csv(output_directory / "checkpoint_fit_log.csv", pd.DataFrame(fit_records))
        _write_json(output_directory / "checkpoint_training_traces.json", traces)
    if len(fit_records) != EXPECTED_NEW_FITS:
        raise ValueError("new neural fit count differs from the frozen 720-fit design")
    return pd.concat(prediction_frames, ignore_index=True), pd.DataFrame(fit_records), traces


def _attach_metadata(predictions: pd.DataFrame, frame: pd.DataFrame) -> pd.DataFrame:
    result = predictions.copy()
    row_indices = result["row_index"].to_numpy(dtype=np.int64)
    if (row_indices < 0).any() or (row_indices >= len(frame)).any():
        raise ValueError("prediction row index falls outside the feature matrix")
    aligned = frame.iloc[row_indices].reset_index(drop=True)
    for column in (
        "filename",
        "bearing_code",
        "setting_code",
        "measurement_index",
        "truth",
        "identity_fold_id",
        "evaluation_cell",
    ):
        result[column] = aligned[column].to_numpy()
    values = result.loc[:, PROBABILITY_COLUMNS].to_numpy(dtype=float)
    result["prediction"] = np.asarray(PADERBORN_LABELS)[values.argmax(axis=1)]
    return result


def _validate_complete_predictions(predictions: pd.DataFrame) -> dict[str, Any]:
    if len(predictions) != EXPECTED_SEED_PREDICTIONS:
        raise ValueError("complete seed prediction count changed")
    key = ["protocol", "method", "seed", "row_index"]
    if predictions.duplicated(key).any():
        raise ValueError("complete predictions contain duplicate seed-level rows")
    if (
        set(predictions["protocol"].astype(str)) != set(PROTOCOLS)
        or set(predictions["method"].astype(str)) != set(METHODS)
        or set(predictions["seed"].astype(int)) != set(AUDIT_SEEDS)
    ):
        raise ValueError("complete predictions change the frozen design axes")
    counts = predictions.groupby(["protocol", "method", "seed"], observed=True).size()
    if not (counts == 2_319).all():
        raise ValueError("a protocol/method/seed does not predict 2,319 rows")
    probabilities = predictions.loc[:, PROBABILITY_COLUMNS].to_numpy(dtype=float)
    maximum_error = float(np.max(np.abs(probabilities.sum(axis=1) - 1.0)))
    if not np.isfinite(probabilities).all() or maximum_error > 2e-6:
        raise ValueError("complete predictions contain invalid probabilities")
    return {
        "prediction_rows": len(predictions),
        "protocol_method_seed_groups": int(
            predictions.groupby(["protocol", "method", "seed"], observed=True).ngroups
        ),
        "maximum_probability_sum_error": maximum_error,
    }


def _method_minus_erm(aggregate: pd.DataFrame) -> pd.DataFrame:
    metrics = (
        "pooled_macro_f1",
        "mean_cell_macro_f1",
        "minimum_cell_macro_f1",
    )
    records = []
    for protocol, rows in aggregate.groupby("protocol", sort=True, observed=True):
        indexed = rows.set_index("method")
        reference = indexed.loc["erm"]
        for method in METHODS:
            for metric in metrics:
                records.append(
                    {
                        "protocol": protocol,
                        "method": method,
                        "reference_method": "erm",
                        "metric": metric,
                        "effect_method_minus_erm": float(
                            indexed.loc[method, metric] - reference[metric]
                        ),
                    }
                )
    return pd.DataFrame(records)


def _rank_shifts(aggregate: pd.DataFrame) -> pd.DataFrame:
    records = []
    reference = aggregate.loc[aggregate["protocol"] == "crossed_holdout"].set_index(
        "method"
    )
    for protocol in PROTOCOLS[:-1]:
        comparison = aggregate.loc[aggregate["protocol"] == protocol].set_index("method")
        for method in METHODS:
            for rank_column in ("rank_pooled_macro_f1", "rank_mean_cell_macro_f1"):
                records.append(
                    {
                        "comparison_protocol": protocol,
                        "reference_protocol": "crossed_holdout",
                        "method": method,
                        "rank_endpoint": rank_column.removeprefix("rank_"),
                        "comparison_rank": float(comparison.loc[method, rank_column]),
                        "crossed_rank": float(reference.loc[method, rank_column]),
                        "rank_change_comparison_minus_crossed": float(
                            comparison.loc[method, rank_column]
                            - reference.loc[method, rank_column]
                        ),
                    }
                )
    return pd.DataFrame(records)


def _summary_findings(
    aggregate: pd.DataFrame,
    bootstrap: pd.DataFrame,
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
    random_effects = bootstrap.loc[
        bootstrap["comparison_protocol"] == "measurement_random"
    ].sort_values("effect_comparison_minus_reference", ascending=False, kind="stable")
    crossed_tau = concordance.loc[
        (concordance["metric"] == "pooled_macro_f1")
        & (concordance["right_protocol"] == "crossed_holdout")
    ]
    maximum_shift = rank_shifts.iloc[
        rank_shifts["rank_change_comparison_minus_crossed"].abs().argmax()
    ]
    return {
        "protocol_leaders": leaders,
        "measurement_random_minus_crossed_effect_range": {
            "minimum": float(random_effects["effect_comparison_minus_reference"].min()),
            "maximum": float(random_effects["effect_comparison_minus_reference"].max()),
            "all_interval_lower_bounds": {
                str(row.method): float(row.bootstrap_lower_95)
                for row in random_effects.itertuples(index=False)
            },
        },
        "pooled_rank_agreement_with_crossed": {
            str(row.left_protocol): float(row.kendall_tau)
            for row in crossed_tau.itertuples(index=False)
        },
        "largest_absolute_rank_shift": {
            "protocol": str(maximum_shift["comparison_protocol"]),
            "method": str(maximum_shift["method"]),
            "endpoint": str(maximum_shift["rank_endpoint"]),
            "comparison_rank": float(maximum_shift["comparison_rank"]),
            "crossed_rank": float(maximum_shift["crossed_rank"]),
        },
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--features", type=Path, required=True)
    parser.add_argument("--crossed-predictions", type=Path, required=True)
    parser.add_argument("--prospective-seal", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--device", default="cuda:0")
    parser.add_argument("--bootstrap-draws", type=int, default=BOOTSTRAP_DRAWS)
    return parser


def main() -> int:
    arguments = build_parser().parse_args()
    input_hashes = {
        "features": _verify_file(
            arguments.features,
            EXPECTED_FEATURE_SHA256,
            "EXP-406 primary features",
        ),
        "crossed_predictions": _verify_file(
            arguments.crossed_predictions,
            EXPECTED_CROSSED_SHA256,
            "EXP-417 crossed predictions",
        ),
        "prospective_seal": _verify_file(
            arguments.prospective_seal,
            EXPECTED_PROSPECTIVE_SEAL_SHA256,
            "D2 prospective seal",
        ),
    }
    arguments.output_dir.mkdir(parents=True, exist_ok=True)
    if any(arguments.output_dir.iterdir()):
        raise ValueError("output directory must be empty")
    if arguments.device.startswith("cuda") and not torch.cuda.is_available():
        raise RuntimeError("the frozen neural contrast requires CUDA")
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
    protocol_folds = build_protocol_model_folds(frame, random_seed=RANDOM_SEED)
    _validate_crossed_fold_parity(frame, protocol_folds)
    crossed = _load_crossed_predictions(arguments.crossed_predictions, frame)
    configuration_record = {
        "run_version": RUN_VERSION,
        "methods": list(METHODS),
        "seeds": [int(seed) for seed in AUDIT_SEEDS],
        "candidate_ids": candidate_ids,
        "configurations": {method: asdict(configurations[method]) for method in METHODS},
        "development_hashes": development_hashes,
    }
    _write_json(arguments.output_dir / "frozen_configurations.json", configuration_record)

    new_predictions, fit_log, traces = _train_new_protocols(
        frame,
        protocol_folds,
        configurations,
        candidate_ids,
        device=arguments.device,
        output_directory=arguments.output_dir,
    )
    predictions = _attach_metadata(
        pd.concat((new_predictions, crossed), ignore_index=True),
        frame,
    )
    topology = _validate_complete_predictions(predictions)
    predictions = predictions.sort_values(
        ["protocol", "method", "seed", "row_index"], kind="stable"
    ).reset_index(drop=True)
    ensemble = ensemble_seed_predictions(
        predictions,
        expected_seeds=tuple(int(seed) for seed in AUDIT_SEEDS),
    )
    aggregate, cell_metrics = score_oof_predictions(ensemble)
    effects = protocol_effect_table(aggregate)
    concordance = protocol_rank_concordance(aggregate)
    bootstrap, bootstrap_draws, draw_plan = paired_bearing_bootstrap(
        ensemble,
        draws=arguments.bootstrap_draws,
        random_seed=RANDOM_SEED,
    )
    method_minus_erm = _method_minus_erm(aggregate)
    rank_shifts = _rank_shifts(aggregate)

    table_outputs = {
        "fit_log.csv": fit_log,
        "aggregate_metrics.csv": aggregate,
        "cell_metrics.csv": cell_metrics,
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
    _write_json(arguments.output_dir / "training_traces.json", traces)
    for filename, table in table_outputs.items():
        _write_csv(arguments.output_dir / filename, table)
    output_files = [
        "frozen_configurations.json",
        "predictions.parquet",
        "ensemble_predictions.parquet",
        "training_traces.json",
        *table_outputs,
    ]
    output_hashes = {
        filename: _sha256(arguments.output_dir / filename)
        for filename in sorted(output_files)
    }
    summary = {
        "run_version": RUN_VERSION,
        "status": "retrospective_development_not_confirmatory",
        "inputs_sha256": input_hashes,
        "design": {
            "row_count": len(frame),
            "feature_count": 72,
            "protocols": list(PROTOCOLS),
            "trained_protocols": list(TRAINED_PROTOCOLS),
            "imported_protocol": "crossed_holdout",
            "methods": list(METHODS),
            "seeds": [int(seed) for seed in AUDIT_SEEDS],
            "new_fit_count": len(fit_log),
            "bootstrap_draws": arguments.bootstrap_draws,
            "bootstrap_unit": "bearing_code_stratified_by_truth",
            "configuration_search": "none",
        },
        "integrity": topology,
        "findings": _summary_findings(aggregate, bootstrap, concordance, rank_shifts),
        "output_sha256": output_hashes,
    }
    _write_json(arguments.output_dir / "neural_protocol_contrast_summary.json", summary)
    print(json.dumps(summary["findings"], ensure_ascii=False, indent=2, sort_keys=True))
    print(json.dumps(output_hashes, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
