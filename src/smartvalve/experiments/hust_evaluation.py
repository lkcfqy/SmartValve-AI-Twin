"""Recording-level evaluation and physical-bearing inference for sealed HUST D3."""

from __future__ import annotations

from itertools import combinations

import numpy as np
import pandas as pd
from scipy.stats import kendalltau
from sklearn.metrics import accuracy_score, balanced_accuracy_score, confusion_matrix, f1_score

from smartvalve.data.hust import HUST_LABELS, HUST_WINDOWS_PER_RECORDING
from smartvalve.experiments.hust_protocol import HUST_PROTOCOLS, HUST_RANDOM_SEED
from smartvalve.experiments.paderborn_protocol_contrast import PROBABILITY_COLUMNS

HUST_BOOTSTRAP_DRAWS = 5_000


def ensemble_hust_seed_windows(
    predictions: pd.DataFrame,
    *,
    expected_seeds: tuple[int, ...],
) -> pd.DataFrame:
    """Average seed probabilities for each target window without pooling recordings."""

    metadata = [
        "fold_id",
        "filename",
        "bearing_code",
        "specification_group",
        "load_w",
        "truth",
        "window_index",
        "evaluation_cell",
    ]
    required = {
        "protocol",
        "method",
        "seed",
        "row_index",
        *metadata,
        *PROBABILITY_COLUMNS,
    }
    missing = required - set(predictions)
    if missing:
        raise ValueError(f"HUST seed predictions are missing columns: {sorted(missing)}")
    if set(predictions["seed"].astype(int)) != set(expected_seeds):
        raise ValueError("HUST seed prediction set changed")
    key = ["protocol", "method", "row_index"]
    if predictions.duplicated([*key, "seed"]).any():
        raise ValueError("HUST seed predictions contain duplicate keys")
    counts = predictions.groupby(key, observed=True)["seed"].nunique()
    if not counts.eq(len(expected_seeds)).all():
        raise ValueError("a HUST window lacks one or more seeds")
    metadata_counts = predictions.groupby(key, observed=True)[metadata].nunique(dropna=False)
    if (metadata_counts > 1).any().any():
        raise ValueError("HUST physical metadata changes across seeds")
    probabilities = predictions.loc[:, PROBABILITY_COLUMNS].to_numpy(dtype=float)
    if (
        not np.isfinite(probabilities).all()
        or float(np.max(np.abs(probabilities.sum(axis=1) - 1.0))) > 2e-6
    ):
        raise ValueError("HUST seed probabilities are invalid")
    aggregation = {column: "first" for column in metadata}
    aggregation.update({column: "mean" for column in PROBABILITY_COLUMNS})
    ensemble = predictions.groupby(key, sort=True, observed=True).agg(aggregation).reset_index()
    values = ensemble.loc[:, PROBABILITY_COLUMNS].to_numpy(dtype=float)
    ensemble["prediction"] = np.asarray(HUST_LABELS)[values.argmax(axis=1)]
    return ensemble


def aggregate_hust_record_predictions(window_predictions: pd.DataFrame) -> pd.DataFrame:
    """Average the ten seed-ensemble window probabilities into one recording decision."""

    required = {
        "protocol",
        "method",
        "filename",
        "bearing_code",
        "specification_group",
        "load_w",
        "truth",
        "window_index",
        "evaluation_cell",
        "prediction",
        *PROBABILITY_COLUMNS,
    }
    missing = required - set(window_predictions)
    if missing:
        raise ValueError(f"HUST window ensemble is missing columns: {sorted(missing)}")
    records = []
    metadata = (
        "bearing_code",
        "specification_group",
        "load_w",
        "truth",
        "evaluation_cell",
    )
    for (protocol, method, filename), rows in window_predictions.groupby(
        ["protocol", "method", "filename"], sort=True, observed=True
    ):
        if (
            len(rows) != HUST_WINDOWS_PER_RECORDING
            or set(rows["window_index"].astype(int)) != set(range(HUST_WINDOWS_PER_RECORDING))
            or any(rows[column].nunique(dropna=False) != 1 for column in metadata)
        ):
            raise ValueError("HUST window-to-record hierarchy changed")
        probabilities = rows.loc[:, PROBABILITY_COLUMNS].to_numpy(dtype=float).mean(axis=0)
        predicted_index = int(probabilities.argmax())
        predicted = HUST_LABELS[predicted_index]
        entropy = float(-np.sum(probabilities * np.log(np.maximum(probabilities, 1e-300))))
        record = {
            "protocol": protocol,
            "method": method,
            "filename": filename,
            **{column: rows.iloc[0][column] for column in metadata},
            **{
                column: float(probabilities[index])
                for index, column in enumerate(PROBABILITY_COLUMNS)
            },
            "prediction": predicted,
            "predictive_entropy": entropy,
            "window_disagreement_rate": float(
                np.mean(rows["prediction"].to_numpy(dtype=str) != predicted)
            ),
        }
        records.append(record)
    result = pd.DataFrame(records)
    expected_rows = 45 * len(HUST_PROTOCOLS) * window_predictions["method"].nunique()
    if len(result) != expected_rows:
        raise ValueError("HUST recording prediction count changed")
    counts = result.groupby(["protocol", "method"], observed=True).size()
    if not counts.eq(45).all():
        raise ValueError("a HUST protocol/method does not predict all 45 recordings")
    return result.sort_values(["protocol", "method", "filename"], kind="stable").reset_index(
        drop=True
    )


def _minimum_class_recall(truth: np.ndarray, predicted: np.ndarray) -> float:
    matrix = confusion_matrix(truth, predicted, labels=HUST_LABELS)
    denominators = matrix.sum(axis=1)
    recalls = np.divide(
        np.diag(matrix),
        denominators,
        out=np.zeros(len(HUST_LABELS), dtype=float),
        where=denominators > 0,
    )
    return float(recalls.min())


def _score(rows: pd.DataFrame) -> dict[str, float | int]:
    truth = rows["truth"].to_numpy(dtype=str)
    predicted = rows["prediction"].to_numpy(dtype=str)
    return {
        "recording_count": len(rows),
        "macro_f1": float(
            f1_score(
                truth,
                predicted,
                labels=HUST_LABELS,
                average="macro",
                zero_division=0,
            )
        ),
        "balanced_accuracy": float(balanced_accuracy_score(truth, predicted)),
        "accuracy": float(accuracy_score(truth, predicted)),
        "minimum_class_recall": _minimum_class_recall(truth, predicted),
    }


def score_hust_record_predictions(
    predictions: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Score pooled recordings and the same 15 specification/load cells."""

    aggregate_records = []
    cell_records = []
    for (protocol, method), rows in predictions.groupby(
        ["protocol", "method"], sort=True, observed=True
    ):
        pooled = _score(rows)
        cell_values = []
        for cell_id, cell in rows.groupby("evaluation_cell", sort=True, observed=True):
            metrics = _score(cell)
            cell_values.append(float(metrics["macro_f1"]))
            cell_records.append(
                {
                    "protocol": protocol,
                    "method": method,
                    "evaluation_cell": cell_id,
                    **metrics,
                }
            )
        if len(cell_values) != 15:
            raise ValueError("a HUST protocol/method does not contain 15 cells")
        aggregate_records.append(
            {
                "protocol": protocol,
                "method": method,
                "recording_count": pooled["recording_count"],
                "pooled_macro_f1": pooled["macro_f1"],
                "pooled_balanced_accuracy": pooled["balanced_accuracy"],
                "pooled_accuracy": pooled["accuracy"],
                "pooled_minimum_class_recall": pooled["minimum_class_recall"],
                "mean_cell_macro_f1": float(np.mean(cell_values)),
                "median_cell_macro_f1": float(np.median(cell_values)),
                "minimum_cell_macro_f1": float(np.min(cell_values)),
                "q25_cell_macro_f1": float(np.quantile(cell_values, 0.25)),
            }
        )
    aggregate = pd.DataFrame(aggregate_records)
    for metric in ("pooled_macro_f1", "mean_cell_macro_f1"):
        aggregate[f"rank_{metric}"] = aggregate.groupby("protocol", observed=True)[metric].rank(
            method="average", ascending=False
        )
    cells = pd.DataFrame(cell_records)
    return (
        aggregate.sort_values(["protocol", "method"], kind="stable").reset_index(drop=True),
        cells.sort_values(["protocol", "method", "evaluation_cell"], kind="stable").reset_index(
            drop=True
        ),
    )


def hust_protocol_effect_table(aggregate: pd.DataFrame) -> pd.DataFrame:
    metrics = (
        "pooled_macro_f1",
        "mean_cell_macro_f1",
        "median_cell_macro_f1",
        "minimum_cell_macro_f1",
        "q25_cell_macro_f1",
    )
    reference = aggregate.loc[aggregate["protocol"] == "crossed_holdout"].set_index("method")
    records = []
    for protocol in HUST_PROTOCOLS[:-1]:
        comparison = aggregate.loc[aggregate["protocol"] == protocol].set_index("method")
        if set(comparison.index) != set(reference.index):
            raise ValueError("HUST method set changes across protocols")
        for method in sorted(reference.index.astype(str)):
            for metric in metrics:
                records.append(
                    {
                        "comparison_protocol": protocol,
                        "reference_protocol": "crossed_holdout",
                        "method": method,
                        "metric": metric,
                        "effect_comparison_minus_reference": float(
                            comparison.loc[method, metric] - reference.loc[method, metric]
                        ),
                    }
                )
    return pd.DataFrame(records)


def hust_rank_concordance(aggregate: pd.DataFrame) -> pd.DataFrame:
    records = []
    for metric in ("pooled_macro_f1", "mean_cell_macro_f1"):
        ranks = aggregate.pivot(index="method", columns="protocol", values=metric).rank(
            ascending=False,
            method="average",
        )
        if set(ranks.columns) != set(HUST_PROTOCOLS):
            raise ValueError("HUST rank table loses a protocol")
        for left, right in combinations(HUST_PROTOCOLS, 2):
            result = kendalltau(ranks[left], ranks[right])
            records.append(
                {
                    "metric": metric,
                    "left_protocol": left,
                    "right_protocol": right,
                    "kendall_tau": float(result.statistic),
                    "method_count": len(ranks),
                }
            )
    return pd.DataFrame(records)


def _macro_f1_from_confusions(matrices: np.ndarray) -> np.ndarray:
    values = np.asarray(matrices, dtype=float)
    true_positive = np.diagonal(values, axis1=-2, axis2=-1)
    false_positive = values.sum(axis=-2) - true_positive
    false_negative = values.sum(axis=-1) - true_positive
    denominator = 2 * true_positive + false_positive + false_negative
    per_class = np.divide(
        2 * true_positive,
        denominator,
        out=np.zeros_like(true_positive),
        where=denominator > 0,
    )
    return per_class.mean(axis=-1)


def bootstrap_hust_record_predictions(
    predictions: pd.DataFrame,
    *,
    draws: int = HUST_BOOTSTRAP_DRAWS,
    random_seed: int = HUST_RANDOM_SEED,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Bootstrap paired protocol effects over 15 physical bearings, stratified by class."""

    if draws < 1:
        raise ValueError("HUST bootstrap draw count must be positive")
    bearing_truth = (
        predictions.loc[:, ["bearing_code", "truth"]]
        .drop_duplicates()
        .sort_values("bearing_code", kind="stable")
        .reset_index(drop=True)
    )
    if len(bearing_truth) != 15 or not bearing_truth.groupby("truth").size().eq(5).all():
        raise ValueError("HUST bootstrap requires five bearings per class")
    bearing_codes = bearing_truth["bearing_code"].astype(str).to_numpy()
    bearing_index = {code: index for index, code in enumerate(bearing_codes)}
    weights = np.zeros((draws, len(bearing_codes)), dtype=np.int16)
    generator = np.random.default_rng(random_seed)
    for label in HUST_LABELS:
        candidates = np.flatnonzero(bearing_truth["truth"].to_numpy(dtype=str) == label)
        sampled = generator.choice(candidates, size=(draws, len(candidates)), replace=True)
        for draw_index, row in enumerate(sampled):
            weights[draw_index] += np.bincount(row, minlength=len(bearing_codes)).astype(np.int16)
    if not np.all(weights.sum(axis=1) == 15):
        raise ValueError("HUST bootstrap physical draw size changed")

    confusion_by_key: dict[tuple[str, str], np.ndarray] = {}
    for (protocol, method), rows in predictions.groupby(
        ["protocol", "method"], sort=True, observed=True
    ):
        matrices = np.zeros((15, 3, 3), dtype=np.int64)
        for bearing_code, bearing_rows in rows.groupby("bearing_code", sort=True, observed=True):
            matrices[bearing_index[str(bearing_code)]] = confusion_matrix(
                bearing_rows["truth"],
                bearing_rows["prediction"],
                labels=HUST_LABELS,
            )
        confusion_by_key[(str(protocol), str(method))] = matrices

    summary_records = []
    draw_records = []
    methods = sorted(predictions["method"].astype(str).unique())
    for protocol in HUST_PROTOCOLS[:-1]:
        for method in methods:
            comparison = np.einsum(
                "db,bij->dij",
                weights,
                confusion_by_key[(protocol, method)],
                optimize=True,
            )
            reference = np.einsum(
                "db,bij->dij",
                weights,
                confusion_by_key[("crossed_holdout", method)],
                optimize=True,
            )
            values = _macro_f1_from_confusions(comparison) - _macro_f1_from_confusions(reference)
            observed = float(
                _macro_f1_from_confusions(confusion_by_key[(protocol, method)].sum(axis=0)[None])[0]
                - _macro_f1_from_confusions(
                    confusion_by_key[("crossed_holdout", method)].sum(axis=0)[None]
                )[0]
            )
            lower, upper = np.quantile(values, (0.025, 0.975))
            summary_records.append(
                {
                    "comparison_protocol": protocol,
                    "reference_protocol": "crossed_holdout",
                    "method": method,
                    "metric": "pooled_recording_macro_f1",
                    "effect_comparison_minus_reference": observed,
                    "bootstrap_lower_95": float(lower),
                    "bootstrap_upper_95": float(upper),
                    "bootstrap_draws": draws,
                    "resampling_unit": "bearing_code_stratified_by_truth",
                }
            )
            draw_records.extend(
                {
                    "draw": draw,
                    "comparison_protocol": protocol,
                    "reference_protocol": "crossed_holdout",
                    "method": method,
                    "effect_comparison_minus_reference": float(value),
                }
                for draw, value in enumerate(values)
            )
    plan = pd.DataFrame(weights, columns=bearing_codes)
    return pd.DataFrame(summary_records), pd.DataFrame(draw_records), plan


def hust_confusion_counts(predictions: pd.DataFrame) -> pd.DataFrame:
    records = []
    for (protocol, method), rows in predictions.groupby(
        ["protocol", "method"], sort=True, observed=True
    ):
        matrix = confusion_matrix(rows["truth"], rows["prediction"], labels=HUST_LABELS)
        for truth_index, truth in enumerate(HUST_LABELS):
            for prediction_index, prediction in enumerate(HUST_LABELS):
                records.append(
                    {
                        "protocol": protocol,
                        "method": method,
                        "truth": truth,
                        "prediction": prediction,
                        "recording_count": int(matrix[truth_index, prediction_index]),
                    }
                )
    return pd.DataFrame(records)


def hust_replication_gate(
    aggregate: pd.DataFrame,
    concordance: pd.DataFrame,
) -> dict[str, float | int | bool]:
    """Apply the predeclared descriptive protocol-gap and rank-instability rules."""

    pivot = aggregate.pivot(index="method", columns="protocol", values="pooled_macro_f1")
    gaps = pivot["recording_random"] - pivot["crossed_holdout"]
    random_ranks = pivot["recording_random"].rank(ascending=False, method="average")
    crossed_ranks = pivot["crossed_holdout"].rank(ascending=False, method="average")
    tau_rows = concordance.loc[
        (concordance["metric"] == "pooled_macro_f1")
        & (concordance["left_protocol"] == "recording_random")
        & (concordance["right_protocol"] == "crossed_holdout")
    ]
    if len(tau_rows) != 1:
        raise ValueError("HUST primary rank concordance row changed")
    tau = float(tau_rows.iloc[0]["kendall_tau"])
    positive = int((gaps > 0).sum())
    median_gap = float(gaps.median())
    maximum_shift = float((random_ranks - crossed_ranks).abs().max())
    return {
        "positive_method_count": positive,
        "median_random_minus_crossed_macro_f1": median_gap,
        "protocol_gap_rule_passed": positive >= 7 and median_gap >= 0.15,
        "random_crossed_kendall_tau": tau,
        "maximum_absolute_rank_shift": maximum_shift,
        "rank_instability_rule_passed": tau < 0.50 or maximum_shift >= 3,
    }
