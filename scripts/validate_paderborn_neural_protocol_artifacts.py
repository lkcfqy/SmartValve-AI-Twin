#!/usr/bin/env python3
"""Independently validate EXP-434B neural protocol-contrast artifacts."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from scipy.stats import kendalltau
from sklearn.metrics import accuracy_score, balanced_accuracy_score, confusion_matrix, f1_score

VALIDATION_VERSION = "smartvalve-paderborn-neural-protocol-validation-0.1.1"
PROTOCOLS = (
    "measurement_random",
    "setting_holdout",
    "identity_holdout",
    "crossed_holdout",
)
TRAINED_PROTOCOLS = PROTOCOLS[:-1]
METHODS = (
    "pirl_ratio",
    "erm",
    "coral",
    "vrex",
    "groupdro",
    "dann",
    "lisa",
    "matchdg",
    "ccdg",
)
SEEDS = (11, 23, 37, 53, 71)
LABELS = ("healthy", "outer", "inner")
PROBABILITY_COLUMNS = tuple(f"probability_{label}" for label in LABELS)
EXPECTED_HASHES = {
    "aggregate_metrics.csv": "79e6954e7dd8562a29e5221b06fe4251862f8a798de92b5eaa05861832536495",
    "bootstrap_draw_plan.csv": "2c161da87938a9736353c1e9c300dd3a58a78fedd6840553bb7bad7da8933d0f",
    "bootstrap_draws.csv": "e0e8bc0f7606a61ddda61f54c114d9c51ee0affdc32bbcf363460ff7e6b7e473",
    "bootstrap_summary.csv": "b628602a9bce911b76e1f0c5501834ff8f82b987c921832afc5943196a67339e",
    "cell_metrics.csv": "6af3c2df6bf285158844f1fb27c121fa5efb0bf1857b02c48825df9dcd26596e",
    "ensemble_predictions.parquet": (
        "dc04dee764e5152b334e0f6fb262197336ce50f7739910365486523325492ed5"
    ),
    "fit_log.csv": "f17dc9e23c2f26f219081bb67dae4defdc2f806ecbee3ac509b6e53bdd0f1de1",
    "frozen_configurations.json": (
        "061dd69573257ee7078640e15880c6cc13facb0d341b4298ac6b7277a955e2b1"
    ),
    "method_minus_erm.csv": "0ae1e52501556b3f787e63e3cfb75d6fb17fccea025c2d845b77eabbc3ec0cfb",
    "predictions.parquet": "0f3b3767699b3c6205db5546537881bbe7045a70d14a7f0d2b9990c3f1a34c8f",
    "protocol_effects.csv": "a26d368b848ebce4af02dcf53e4c4da9d2c3fed3d11969b0d894fab6312fb72a",
    "rank_shifts.csv": "dcc0e0acd4f546098aeea98fcdbd9aca604617dc684082962c59ad4318638479",
    "ranking_concordance.csv": "055a7a571796049d0a15b4b32713f726fe338086a660fd3bed4994079503e8e7",
    "training_traces.json": "9c84438aa964d214c0473cc0f599362fa3761ac2c95a959c287b9d4578cafbe3",
}
EXPECTED_CROSSED_HASH = "5e3801e9df4636f180e85ccde060fade77422dfbcb65d5699bf7a93a49d9b400"
CHECKPOINT_HASHES = {
    "checkpoint_measurement_random_predictions.parquet": (
        "0a019bfe8c7ef13778375c5faf42b863bfbdb39394acabb3474822ee4ecd5422"
    ),
    "checkpoint_setting_holdout_predictions.parquet": (
        "7e36b451c129277da7a1c13ff88523a687e894d5b30e67d507c50188047b1296"
    ),
    "checkpoint_identity_holdout_predictions.parquet": (
        "ce21ab7cded827173404b7dd03d3d416305d74b0abf0258877d97578fe44b78b"
    ),
}


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, value: Any) -> None:
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _verify_hashes(directory: Path) -> dict[str, str]:
    observed = {}
    for filename, expected in {**EXPECTED_HASHES, **CHECKPOINT_HASHES}.items():
        path = directory / filename
        if not path.is_file():
            raise FileNotFoundError(f"missing neural protocol artifact: {path}")
        digest = _sha256(path)
        if digest != expected:
            raise ValueError(f"artifact hash changed for {filename}: {digest}")
        observed[filename] = digest
    summary = _read_json(directory / "neural_protocol_contrast_summary.json")
    if summary.get("output_sha256") != EXPECTED_HASHES:
        raise ValueError("summary output-hash table differs from the independent lock")
    return observed


def _validate_seed_predictions(predictions: pd.DataFrame) -> dict[str, Any]:
    expected_rows = 2_319 * len(PROTOCOLS) * len(METHODS) * len(SEEDS)
    if len(predictions) != expected_rows:
        raise ValueError("seed prediction row count changed")
    if (
        set(predictions["protocol"].astype(str)) != set(PROTOCOLS)
        or set(predictions["method"].astype(str)) != set(METHODS)
        or set(predictions["seed"].astype(int)) != set(SEEDS)
    ):
        raise ValueError("seed prediction axes changed")
    key = ["protocol", "method", "seed", "row_index"]
    if predictions.duplicated(key).any():
        raise ValueError("seed predictions contain duplicate keys")
    counts = predictions.groupby(["protocol", "method", "seed"], observed=True).size()
    if not (counts == 2_319).all():
        raise ValueError("a seed prediction group does not cover every row")
    probabilities = predictions.loc[:, PROBABILITY_COLUMNS].to_numpy(dtype=np.float64)
    maximum_error = float(np.max(np.abs(probabilities.sum(axis=1) - 1.0)))
    if (
        not np.isfinite(probabilities).all()
        or np.any(probabilities < 0)
        or np.any(probabilities > 1)
        or maximum_error > 2e-6
    ):
        raise ValueError("seed prediction probabilities are invalid")
    expected_prediction = np.asarray(LABELS)[probabilities.argmax(axis=1)]
    if not np.array_equal(expected_prediction, predictions["prediction"].to_numpy(dtype=str)):
        raise ValueError("seed prediction label differs from probability argmax")
    metadata = [
        "fold_id",
        "filename",
        "bearing_code",
        "setting_code",
        "measurement_index",
        "truth",
        "identity_fold_id",
        "evaluation_cell",
    ]
    uniqueness = predictions.groupby(["protocol", "method", "row_index"], observed=True)[
        metadata
    ].nunique(dropna=False)
    if (uniqueness > 1).any().any():
        raise ValueError("physical metadata differ across seeds")
    return {
        "rows": len(predictions),
        "groups": int(counts.size),
        "maximum_probability_sum_error": maximum_error,
    }


def _validate_ensemble(
    predictions: pd.DataFrame,
    ensemble: pd.DataFrame,
) -> dict[str, Any]:
    key = ["protocol", "method", "row_index"]
    independently_averaged = (
        predictions.groupby(key, sort=True, observed=True)[list(PROBABILITY_COLUMNS)]
        .mean()
        .reset_index()
    )
    observed = ensemble.sort_values(key, kind="stable").reset_index(drop=True)
    if len(observed) != 2_319 * len(PROTOCOLS) * len(METHODS):
        raise ValueError("ensemble row count changed")
    if not independently_averaged.loc[:, key].equals(observed.loc[:, key]):
        raise ValueError("ensemble keys differ from independent seed grouping")
    maximum_difference = float(
        np.max(
            np.abs(
                independently_averaged.loc[:, PROBABILITY_COLUMNS].to_numpy(dtype=float)
                - observed.loc[:, PROBABILITY_COLUMNS].to_numpy(dtype=float)
            )
        )
    )
    if maximum_difference > 1e-12:
        raise ValueError("ensemble probabilities differ from independent seed means")
    probabilities = observed.loc[:, PROBABILITY_COLUMNS].to_numpy(dtype=float)
    expected_prediction = np.asarray(LABELS)[probabilities.argmax(axis=1)]
    if not np.array_equal(expected_prediction, observed["prediction"].to_numpy(dtype=str)):
        raise ValueError("ensemble prediction differs from probability argmax")
    return {"rows": len(observed), "maximum_seed_mean_difference": maximum_difference}


def _score(rows: pd.DataFrame) -> dict[str, float | int]:
    truth = rows["truth"].to_numpy(dtype=str)
    predicted = rows["prediction"].to_numpy(dtype=str)
    matrix = confusion_matrix(truth, predicted, labels=LABELS)
    recall = np.divide(
        np.diag(matrix),
        matrix.sum(axis=1),
        out=np.zeros(len(LABELS), dtype=float),
        where=matrix.sum(axis=1) > 0,
    )
    return {
        "row_count": len(rows),
        "macro_f1": float(
            f1_score(truth, predicted, labels=LABELS, average="macro", zero_division=0)
        ),
        "balanced_accuracy": float(balanced_accuracy_score(truth, predicted)),
        "accuracy": float(accuracy_score(truth, predicted)),
        "minimum_class_recall": float(recall.min()),
    }


def _independent_metrics(ensemble: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    aggregate_records = []
    cell_records = []
    for (protocol, method), rows in ensemble.groupby(
        ["protocol", "method"], sort=True, observed=True
    ):
        pooled = _score(rows)
        cell_f1 = []
        for cell, cell_rows in rows.groupby("evaluation_cell", sort=True, observed=True):
            metrics = _score(cell_rows)
            cell_f1.append(float(metrics["macro_f1"]))
            cell_records.append(
                {
                    "protocol": protocol,
                    "method": method,
                    "evaluation_cell": cell,
                    **metrics,
                }
            )
        if len(cell_f1) != 24:
            raise ValueError("independent metric group does not contain 24 cells")
        aggregate_records.append(
            {
                "protocol": protocol,
                "method": method,
                "row_count": pooled["row_count"],
                "pooled_macro_f1": pooled["macro_f1"],
                "pooled_balanced_accuracy": pooled["balanced_accuracy"],
                "pooled_accuracy": pooled["accuracy"],
                "pooled_minimum_class_recall": pooled["minimum_class_recall"],
                "mean_cell_macro_f1": float(np.mean(cell_f1)),
                "median_cell_macro_f1": float(np.median(cell_f1)),
                "minimum_cell_macro_f1": float(np.min(cell_f1)),
                "q25_cell_macro_f1": float(np.quantile(cell_f1, 0.25)),
            }
        )
    aggregate = pd.DataFrame(aggregate_records).sort_values(
        ["protocol", "method"], kind="stable"
    )
    for metric in ("pooled_macro_f1", "mean_cell_macro_f1"):
        aggregate[f"rank_{metric}"] = aggregate.groupby("protocol", observed=True)[
            metric
        ].rank(method="average", ascending=False)
    cells = pd.DataFrame(cell_records).sort_values(
        ["protocol", "method", "evaluation_cell"], kind="stable"
    )
    return aggregate.reset_index(drop=True), cells.reset_index(drop=True)


def _compare_numeric_tables(
    observed: pd.DataFrame,
    expected: pd.DataFrame,
    *,
    keys: list[str],
    role: str,
) -> float:
    observed = observed.sort_values(keys, kind="stable").reset_index(drop=True)
    expected = expected.sort_values(keys, kind="stable").reset_index(drop=True)
    if len(observed) != len(expected) or not observed.loc[:, keys].equals(expected.loc[:, keys]):
        raise ValueError(f"{role} key table changed")
    numeric = [
        column
        for column in expected.columns
        if column not in keys and pd.api.types.is_numeric_dtype(expected[column])
    ]
    maximum = float(
        np.max(
            np.abs(
                observed.loc[:, numeric].to_numpy(dtype=float)
                - expected.loc[:, numeric].to_numpy(dtype=float)
            )
        )
    )
    if maximum > 1e-10:
        raise ValueError(f"{role} values differ from independent recomputation")
    return maximum


def _validate_crossed_import(
    predictions: pd.DataFrame,
    crossed_path: Path,
) -> dict[str, Any]:
    if _sha256(crossed_path) != EXPECTED_CROSSED_HASH:
        raise ValueError("EXP-417 crossed input hash changed")
    original = pd.read_parquet(crossed_path).loc[
        :, ["method", "seed", "fold_id", "row_index", *PROBABILITY_COLUMNS]
    ]
    observed = predictions.loc[
        predictions["protocol"] == "crossed_holdout",
        ["method", "seed", "fold_id", "row_index", *PROBABILITY_COLUMNS],
    ]
    key = ["method", "seed", "fold_id", "row_index"]
    original = original.sort_values(key, kind="stable").reset_index(drop=True)
    observed = observed.sort_values(key, kind="stable").reset_index(drop=True)
    if not original.loc[:, key].equals(observed.loc[:, key]):
        raise ValueError("crossed import keys differ from EXP-417")
    maximum = float(
        np.max(
            np.abs(
                original.loc[:, PROBABILITY_COLUMNS].to_numpy(dtype=float)
                - observed.loc[:, PROBABILITY_COLUMNS].to_numpy(dtype=float)
            )
        )
    )
    if maximum != 0:
        raise ValueError("crossed import probabilities differ from EXP-417")
    return {"rows": len(observed), "maximum_probability_difference": maximum}


def _validate_checkpoints(directory: Path, predictions: pd.DataFrame) -> dict[str, Any]:
    frames = []
    for protocol in TRAINED_PROTOCOLS:
        filename = f"checkpoint_{protocol}_predictions.parquet"
        frame = pd.read_parquet(directory / filename)
        if set(frame["protocol"].astype(str)) != {protocol}:
            raise ValueError(f"checkpoint protocol mismatch: {protocol}")
        frames.append(frame)
    checkpoints = pd.concat(frames, ignore_index=True)
    columns = [
        "protocol",
        "method",
        "seed",
        "fold_id",
        "row_index",
        *PROBABILITY_COLUMNS,
    ]
    key = ["protocol", "method", "seed", "fold_id", "row_index"]
    expected = predictions.loc[predictions["protocol"].isin(TRAINED_PROTOCOLS), columns]
    checkpoints = checkpoints.loc[:, columns].sort_values(key, kind="stable").reset_index(drop=True)
    expected = expected.sort_values(key, kind="stable").reset_index(drop=True)
    if not checkpoints.loc[:, key].equals(expected.loc[:, key]):
        raise ValueError("checkpoint keys differ from final predictions")
    maximum = float(
        np.max(
            np.abs(
                checkpoints.loc[:, PROBABILITY_COLUMNS].to_numpy(dtype=float)
                - expected.loc[:, PROBABILITY_COLUMNS].to_numpy(dtype=float)
            )
        )
    )
    if maximum != 0:
        raise ValueError("checkpoint probabilities differ from final predictions")
    return {"rows": len(checkpoints), "maximum_probability_difference": maximum}


def _validate_fit_and_traces(directory: Path) -> dict[str, Any]:
    fit = pd.read_csv(directory / "fit_log.csv")
    traces = _read_json(directory / "training_traces.json")
    if len(fit) != 720 or len(traces) != 720:
        raise ValueError("fit or trace count differs from 720")
    key = ["protocol", "method", "seed", "fold_id"]
    if fit.duplicated(key).any() or fit.groupby(key, observed=True).ngroups != 720:
        raise ValueError("fit log keys are incomplete or duplicated")
    if set(fit["protocol"].astype(str)) != set(TRAINED_PROTOCOLS):
        raise ValueError("fit log contains an unexpected protocol")
    if fit["model_state_sha256"].nunique() != 720:
        raise ValueError("model state hashes are not unique")
    auxiliary = fit["auxiliary_state_sha256"].notna()
    if auxiliary.sum() != 80 or set(fit.loc[auxiliary, "method"]) != {"dann"}:
        raise ValueError("DANN auxiliary-state topology changed")
    trace_by_key = {
        (trace["protocol"], trace["method"], int(trace["seed"]), trace["fold_id"]): trace
        for trace in traces
    }
    if len(trace_by_key) != 720:
        raise ValueError("training trace keys are incomplete or duplicated")
    maximum_final_epoch_error = 0
    for row in fit.itertuples(index=False):
        trace = trace_by_key[(row.protocol, row.method, int(row.seed), row.fold_id)]
        if trace["model_state_sha256"] != row.model_state_sha256:
            raise ValueError("trace and fit-log model hashes differ")
        history = trace.get("history")
        if not isinstance(history, list) or not history:
            raise ValueError("a training trace has no checkpoint history")
        maximum_final_epoch_error = max(
            maximum_final_epoch_error,
            abs(int(history[-1]["epoch"]) - 300),
        )
        for checkpoint in history:
            numeric = [value for value in checkpoint.values() if isinstance(value, float)]
            if not np.isfinite(numeric).all():
                raise ValueError("training trace contains a non-finite diagnostic")
    if maximum_final_epoch_error:
        raise ValueError("a training trace does not end at epoch 300")
    return {
        "fits": len(fit),
        "unique_model_states": fit["model_state_sha256"].nunique(),
        "dann_auxiliary_states": int(auxiliary.sum()),
        "all_final_epochs": 300,
    }


def _validate_bootstrap(directory: Path, aggregate: pd.DataFrame) -> dict[str, Any]:
    plan = pd.read_csv(directory / "bootstrap_draw_plan.csv")
    draws = pd.read_csv(directory / "bootstrap_draws.csv")
    summary = pd.read_csv(directory / "bootstrap_summary.csv")
    if plan.shape != (2_000, 29) or not plan.sum(axis=1).eq(29).all():
        raise ValueError("bearing bootstrap draw plan changed")
    if len(draws) != 3 * len(METHODS) * 2_000 or len(summary) != 3 * len(METHODS):
        raise ValueError("bootstrap effect family size changed")
    aggregate_indexed = aggregate.set_index(["protocol", "method"])
    maximum_quantile_error = 0.0
    maximum_estimate_error = 0.0
    for record in summary.itertuples(index=False):
        group = draws.loc[
            (draws["comparison_protocol"] == record.comparison_protocol)
            & (draws["method"] == record.method),
            "effect_comparison_minus_reference",
        ].to_numpy(dtype=float)
        if len(group) != 2_000:
            raise ValueError("a bootstrap group does not contain 2,000 draws")
        lower, upper = np.quantile(group, (0.025, 0.975))
        maximum_quantile_error = max(
            maximum_quantile_error,
            abs(float(lower) - float(record.bootstrap_lower_95)),
            abs(float(upper) - float(record.bootstrap_upper_95)),
        )
        expected_effect = float(
            aggregate_indexed.loc[(record.comparison_protocol, record.method), "pooled_macro_f1"]
            - aggregate_indexed.loc[("crossed_holdout", record.method), "pooled_macro_f1"]
        )
        maximum_estimate_error = max(
            maximum_estimate_error,
            abs(expected_effect - float(record.effect_comparison_minus_reference)),
        )
    if maximum_quantile_error > 1e-10 or maximum_estimate_error > 1e-10:
        raise ValueError("bootstrap summary differs from raw draws or aggregate effects")
    return {
        "draws": len(plan),
        "bearing_columns": len(plan.columns),
        "effect_draw_rows": len(draws),
        "maximum_quantile_error": maximum_quantile_error,
        "maximum_estimate_error": maximum_estimate_error,
    }


def _validate_rank_concordance(directory: Path, aggregate: pd.DataFrame) -> float:
    observed = pd.read_csv(directory / "ranking_concordance.csv")
    records = []
    for metric in ("pooled_macro_f1", "mean_cell_macro_f1"):
        ranks = aggregate.pivot(index="method", columns="protocol", values=metric).rank(
            ascending=False,
            method="average",
        )
        for left_index, left in enumerate(PROTOCOLS):
            for right in PROTOCOLS[left_index + 1 :]:
                records.append(
                    {
                        "metric": metric,
                        "left_protocol": left,
                        "right_protocol": right,
                        "kendall_tau": float(kendalltau(ranks[left], ranks[right]).statistic),
                        "method_count": len(METHODS),
                    }
                )
    expected = pd.DataFrame(records)
    return _compare_numeric_tables(
        observed,
        expected,
        keys=["metric", "left_protocol", "right_protocol"],
        role="rank concordance",
    )


def validate(
    *,
    artifact_directory: Path,
    crossed_predictions: Path,
    output: Path,
) -> dict[str, Any]:
    directory = artifact_directory.resolve(strict=True)
    hashes = _verify_hashes(directory)
    predictions = pd.read_parquet(directory / "predictions.parquet")
    ensemble = pd.read_parquet(directory / "ensemble_predictions.parquet")
    seed_integrity = _validate_seed_predictions(predictions)
    ensemble_integrity = _validate_ensemble(predictions, ensemble)
    independent_aggregate, independent_cells = _independent_metrics(ensemble)
    recorded_aggregate = pd.read_csv(directory / "aggregate_metrics.csv")
    recorded_cells = pd.read_csv(directory / "cell_metrics.csv")
    metric_error = _compare_numeric_tables(
        recorded_aggregate,
        independent_aggregate,
        keys=["protocol", "method"],
        role="aggregate metrics",
    )
    cell_error = _compare_numeric_tables(
        recorded_cells,
        independent_cells,
        keys=["protocol", "method", "evaluation_cell"],
        role="cell metrics",
    )
    crossed_integrity = _validate_crossed_import(predictions, crossed_predictions)
    checkpoint_integrity = _validate_checkpoints(directory, predictions)
    training_integrity = _validate_fit_and_traces(directory)
    bootstrap_integrity = _validate_bootstrap(directory, independent_aggregate)
    rank_error = _validate_rank_concordance(directory, independent_aggregate)
    result = {
        "validation_version": VALIDATION_VERSION,
        "status": "passed_independent_neural_protocol_artifact_validation",
        "refit_performed": False,
        "artifact_directory": str(directory),
        "locked_artifact_sha256": hashes,
        "seed_prediction_integrity": seed_integrity,
        "ensemble_integrity": ensemble_integrity,
        "metric_recomputation": {
            "aggregate_maximum_difference": metric_error,
            "cell_maximum_difference": cell_error,
            "rank_concordance_maximum_difference": rank_error,
        },
        "crossed_import_integrity": crossed_integrity,
        "checkpoint_integrity": checkpoint_integrity,
        "training_integrity": training_integrity,
        "bootstrap_integrity": bootstrap_integrity,
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    _write_json(output, result)
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--artifact-directory", type=Path, required=True)
    parser.add_argument("--crossed-predictions", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    arguments = parser.parse_args()
    result = validate(
        artifact_directory=arguments.artifact_directory,
        crossed_predictions=arguments.crossed_predictions,
        output=arguments.output,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
