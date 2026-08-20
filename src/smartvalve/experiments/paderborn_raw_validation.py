"""Independent calculations for validating the sealed raw-sensitivity outputs.

This module intentionally does not import the producer's raw aggregation, protocol scoring,
bootstrap, or gate functions.  The duplicated implementation is small and explicit so a shared
calculation bug cannot make producer and validator agree automatically.
"""

from __future__ import annotations

from collections.abc import Mapping

import numpy as np
import pandas as pd
from sklearn.metrics import accuracy_score, balanced_accuracy_score, confusion_matrix, f1_score

VALIDATION_CALCULATION_VERSION = "smartvalve-paderborn-raw-independent-calculations-0.2.0"
LABELS = ("healthy", "outer", "inner")
PROBABILITY_COLUMNS = tuple(f"probability_{label}" for label in LABELS)
MODELS = ("cnn1d", "fft", "stft")
PROTOCOLS = ("measurement_random", "crossed_holdout")
SEEDS = (41, 42, 43)
WINDOWS_PER_RECORD = 4
BOOTSTRAP_RANDOM_SEED = 20_260_818


def _validate_probabilities(frame: pd.DataFrame, *, role: str) -> None:
    values = frame.loc[:, PROBABILITY_COLUMNS].to_numpy(dtype=float)
    if not np.isfinite(values).all() or (values < -1e-12).any() or (values > 1 + 1e-12).any():
        raise ValueError(f"{role} contain invalid probabilities")
    if float(np.max(np.abs(values.sum(axis=1) - 1.0))) > 2e-6:
        raise ValueError(f"{role} probabilities do not sum to one")


def aggregate_windows_independently(
    predictions: pd.DataFrame,
    *,
    windows_per_record: int = WINDOWS_PER_RECORD,
) -> pd.DataFrame:
    """Independently average four window probabilities to a recording per seed."""

    key = ["protocol", "method", "seed", "row_index"]
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
    required = {*key, "window_index", *metadata, *PROBABILITY_COLUMNS}
    missing = required - set(predictions)
    if missing:
        raise ValueError(f"raw validation window predictions lack columns: {sorted(missing)}")
    counts = predictions.groupby(key, observed=True).size()
    if counts.empty or not counts.eq(windows_per_record).all():
        raise ValueError("raw validation recording does not contain every frozen window")
    if predictions.duplicated([*key, "window_index"]).any():
        raise ValueError("raw validation window predictions contain a duplicate window")
    metadata_counts = predictions.groupby(key, observed=True)[metadata].nunique(dropna=False)
    if (metadata_counts > 1).any().any():
        raise ValueError("raw validation recording metadata change across windows")
    _validate_probabilities(predictions, role="raw validation window predictions")

    aggregation: dict[str, str] = {column: "first" for column in metadata}
    aggregation.update({column: "mean" for column in PROBABILITY_COLUMNS})
    records = predictions.groupby(key, sort=True, observed=True).agg(aggregation).reset_index()
    probabilities = records.loc[:, PROBABILITY_COLUMNS].to_numpy(dtype=float)
    records["prediction"] = np.asarray(LABELS)[probabilities.argmax(axis=1)]
    return records


def ensemble_seeds_independently(
    predictions: pd.DataFrame,
    *,
    expected_seeds: tuple[int, ...] = SEEDS,
) -> pd.DataFrame:
    """Independently average complete seed-level recording probabilities."""

    key = ["protocol", "method", "row_index"]
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
    required = {*key, "seed", *metadata, *PROBABILITY_COLUMNS}
    missing = required - set(predictions)
    if missing:
        raise ValueError(f"raw validation seed predictions lack columns: {sorted(missing)}")
    if set(predictions["seed"].astype(int)) != set(expected_seeds):
        raise ValueError("raw validation seed family changed")
    counts = predictions.groupby(key, sort=False, observed=True)["seed"].nunique()
    if counts.empty or not counts.eq(len(expected_seeds)).all():
        raise ValueError("raw validation recording does not contain every frozen seed")
    if predictions.duplicated([*key, "seed"]).any():
        raise ValueError("raw validation seed predictions contain a duplicate seed")
    metadata_counts = predictions.groupby(key, sort=False, observed=True)[metadata].nunique(
        dropna=False
    )
    if (metadata_counts > 1).any().any():
        raise ValueError("raw validation physical metadata change across seeds")
    _validate_probabilities(predictions, role="raw validation seed predictions")

    aggregation: dict[str, str] = {column: "first" for column in metadata}
    aggregation.update({column: "mean" for column in PROBABILITY_COLUMNS})
    ensemble = predictions.groupby(key, sort=True, observed=True).agg(aggregation).reset_index()
    probabilities = ensemble.loc[:, PROBABILITY_COLUMNS].to_numpy(dtype=float)
    ensemble["prediction"] = np.asarray(LABELS)[probabilities.argmax(axis=1)]
    return ensemble


def _minimum_class_recall(truth: np.ndarray, predicted: np.ndarray) -> float:
    matrix = confusion_matrix(truth, predicted, labels=LABELS)
    denominators = matrix.sum(axis=1)
    recalls = np.divide(
        np.diag(matrix),
        denominators,
        out=np.zeros(len(LABELS), dtype=float),
        where=denominators > 0,
    )
    return float(recalls.min())


def _score_rows(rows: pd.DataFrame) -> dict[str, float | int]:
    truth = rows["truth"].to_numpy(dtype=str)
    predicted = rows["prediction"].to_numpy(dtype=str)
    return {
        "row_count": len(rows),
        "macro_f1": float(
            f1_score(truth, predicted, labels=LABELS, average="macro", zero_division=0)
        ),
        "balanced_accuracy": float(balanced_accuracy_score(truth, predicted)),
        "accuracy": float(accuracy_score(truth, predicted)),
        "minimum_class_recall": _minimum_class_recall(truth, predicted),
    }


def score_predictions_independently(
    predictions: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Independently score pooled records and the common 24 physical cells."""

    required = {
        "protocol",
        "method",
        "row_index",
        "truth",
        "prediction",
        "evaluation_cell",
    }
    missing = required - set(predictions)
    if missing:
        raise ValueError(f"raw validation ensemble lacks columns: {sorted(missing)}")
    aggregate_records: list[dict[str, object]] = []
    cell_records: list[dict[str, object]] = []
    for (protocol, method), group in predictions.groupby(
        ["protocol", "method"], sort=True, observed=True
    ):
        pooled = _score_rows(group)
        cell_values = []
        for cell_id, cell in group.groupby("evaluation_cell", sort=True, observed=True):
            metrics = _score_rows(cell)
            cell_values.append(float(metrics["macro_f1"]))
            cell_records.append(
                {
                    "protocol": protocol,
                    "method": method,
                    "evaluation_cell": cell_id,
                    **metrics,
                }
            )
        if len(cell_values) != 24:
            raise ValueError("raw validation protocol/method lacks the common 24 cells")
        aggregate_records.append(
            {
                "protocol": protocol,
                "method": method,
                "row_count": pooled["row_count"],
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
    aggregate = pd.DataFrame(aggregate_records).sort_values(
        ["protocol", "method"], kind="stable"
    )
    for metric in ("pooled_macro_f1", "mean_cell_macro_f1"):
        aggregate[f"rank_{metric}"] = aggregate.groupby("protocol", observed=True)[metric].rank(
            method="average", ascending=False
        )
    cells = pd.DataFrame(cell_records).sort_values(
        ["protocol", "method", "evaluation_cell"], kind="stable"
    )
    return aggregate.reset_index(drop=True), cells.reset_index(drop=True)


def _macro_f1_from_confusions(matrices: np.ndarray) -> np.ndarray:
    values = np.asarray(matrices, dtype=np.float64)
    true_positive = np.diagonal(values, axis1=-2, axis2=-1)
    false_positive = values.sum(axis=-2) - true_positive
    false_negative = values.sum(axis=-1) - true_positive
    denominator = 2.0 * true_positive + false_positive + false_negative
    per_class = np.divide(
        2.0 * true_positive,
        denominator,
        out=np.zeros_like(true_positive),
        where=denominator > 0,
    )
    return per_class.mean(axis=-1)


def bootstrap_protocol_effects_independently(
    predictions: pd.DataFrame,
    *,
    draws: int = 2_000,
    random_seed: int = BOOTSTRAP_RANDOM_SEED,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Independently bootstrap paired protocol effects by physical bearing."""

    if draws < 1:
        raise ValueError("raw validation bootstrap draws must be positive")
    if set(predictions["protocol"].astype(str)) != set(PROTOCOLS):
        raise ValueError("raw validation protocol family changed")
    if set(predictions["method"].astype(str)) != set(MODELS):
        raise ValueError("raw validation architecture family changed")
    bearing_truth = (
        predictions.loc[:, ["bearing_code", "truth"]]
        .drop_duplicates()
        .sort_values("bearing_code", kind="stable")
        .reset_index(drop=True)
    )
    if not bearing_truth.groupby("bearing_code", observed=True)["truth"].nunique().eq(1).all():
        raise ValueError("raw validation bearing is associated with multiple labels")
    bearing_codes = bearing_truth["bearing_code"].astype(str).to_numpy()
    bearing_lookup = {bearing: index for index, bearing in enumerate(bearing_codes)}
    weights = np.zeros((draws, len(bearing_codes)), dtype=np.int16)
    generator = np.random.default_rng(random_seed)
    truth_values = bearing_truth["truth"].to_numpy(dtype=str)
    for label in LABELS:
        candidates = np.flatnonzero(truth_values == label)
        if len(candidates) == 0:
            raise ValueError(f"raw validation bootstrap lacks label: {label}")
        sampled = generator.choice(candidates, size=(draws, len(candidates)), replace=True)
        for draw_index, values in enumerate(sampled):
            weights[draw_index] += np.bincount(
                values, minlength=len(bearing_codes)
            ).astype(np.int16)
    if not np.all(weights.sum(axis=1) == len(bearing_codes)):
        raise ValueError("raw validation bootstrap draw size changed")

    confusions: dict[tuple[str, str], np.ndarray] = {}
    expected_bearings = set(bearing_codes)
    for (protocol, method), rows in predictions.groupby(
        ["protocol", "method"], sort=True, observed=True
    ):
        if set(rows["bearing_code"].astype(str)) != expected_bearings:
            raise ValueError("raw validation protocol/method does not cover every bearing")
        matrices = np.zeros((len(bearing_codes), len(LABELS), len(LABELS)), dtype=np.int64)
        for bearing, bearing_rows in rows.groupby("bearing_code", sort=True, observed=True):
            matrices[bearing_lookup[str(bearing)]] = confusion_matrix(
                bearing_rows["truth"], bearing_rows["prediction"], labels=LABELS
            )
        confusions[(str(protocol), str(method))] = matrices
    expected_keys = {(protocol, method) for protocol in PROTOCOLS for method in MODELS}
    if set(confusions) != expected_keys:
        raise ValueError("raw validation protocol/method confusion topology changed")

    summaries: list[dict[str, object]] = []
    draw_rows: list[dict[str, object]] = []
    for method in MODELS:
        comparison_confusions = confusions[("measurement_random", method)]
        reference_confusions = confusions[("crossed_holdout", method)]
        comparison = _macro_f1_from_confusions(
            np.einsum("db,bij->dij", weights, comparison_confusions, optimize=True)
        )
        reference = _macro_f1_from_confusions(
            np.einsum("db,bij->dij", weights, reference_confusions, optimize=True)
        )
        differences = comparison - reference
        observed = float(
            _macro_f1_from_confusions(comparison_confusions.sum(axis=0)[None])[0]
            - _macro_f1_from_confusions(reference_confusions.sum(axis=0)[None])[0]
        )
        lower, upper = np.quantile(differences, (0.025, 0.975))
        summaries.append(
            {
                "comparison_protocol": "measurement_random",
                "reference_protocol": "crossed_holdout",
                "method": method,
                "metric": "pooled_macro_f1",
                "effect_comparison_minus_reference": observed,
                "bootstrap_lower_95": float(lower),
                "bootstrap_upper_95": float(upper),
                "bootstrap_draws": draws,
                "resampling_unit": "bearing_code_stratified_by_truth",
            }
        )
        draw_rows.extend(
            {
                "draw": draw,
                "method": method,
                "effect_comparison_minus_reference": float(value),
            }
            for draw, value in enumerate(differences)
        )
    return (
        pd.DataFrame(summaries),
        pd.DataFrame(draw_rows),
        pd.DataFrame(weights, columns=bearing_codes),
    )


def evaluate_gate_independently(bootstrap: pd.DataFrame) -> Mapping[str, object]:
    """Independently apply the four frozen representation-sensitivity conditions."""

    if set(bootstrap["method"].astype(str)) != set(MODELS):
        raise ValueError("raw validation gate received another architecture family")
    effects = bootstrap["effect_comparison_minus_reference"].to_numpy(dtype=float)
    lower = bootstrap["bootstrap_lower_95"].to_numpy(dtype=float)
    median = float(np.median(effects))
    return {
        "positive_model_count": int((effects > 0).sum()),
        "positive_interval_count": int((lower > 0).sum()),
        "median_random_minus_crossed_macro_f1": median,
        "representation_sensitivity_rule_passed": bool(
            (effects > 0).all() and (lower > 0).all() and median >= 0.15
        ),
    }
