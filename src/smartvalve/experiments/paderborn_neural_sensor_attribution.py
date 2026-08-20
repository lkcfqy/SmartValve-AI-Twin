"""Neural multi-sensor attribution for the frozen Paderborn protocol audit."""

from __future__ import annotations

from itertools import combinations

import numpy as np
import pandas as pd
from scipy.stats import kendalltau
from sklearn.metrics import confusion_matrix

from smartvalve.data.paderborn_features import MAIN_SIGNAL_FEATURE_FAMILIES
from smartvalve.experiments.paderborn_evaluation import METHODS
from smartvalve.experiments.paderborn_partitions import PADERBORN_LABELS
from smartvalve.experiments.paderborn_protocol_contrast import (
    PROTOCOLS,
    _macro_f1_from_confusions,
)
from smartvalve.experiments.paderborn_sensor_audit import SENSOR_GAP_COMPARISONS

SCHEMA_VERSION = "smartvalve-paderborn-neural-sensor-attribution-0.1.0"


def validate_neural_sensor_ensemble(predictions: pd.DataFrame) -> None:
    required = {
        "feature_family",
        "protocol",
        "method",
        "row_index",
        "bearing_code",
        "truth",
        "prediction",
    }
    missing = required - set(predictions)
    if missing:
        raise ValueError(f"neural sensor ensemble is missing columns: {sorted(missing)}")
    if (
        set(predictions["feature_family"].astype(str)) != set(MAIN_SIGNAL_FEATURE_FAMILIES)
        or set(predictions["protocol"].astype(str)) != set(PROTOCOLS)
        or set(predictions["method"].astype(str)) != set(METHODS)
    ):
        raise ValueError("neural sensor ensemble changes a frozen design axis")
    key = ["feature_family", "protocol", "method", "row_index"]
    if predictions.duplicated(key).any():
        raise ValueError("neural sensor ensemble contains duplicate keys")
    counts = predictions.groupby(["feature_family", "protocol", "method"], observed=True).size()
    expected_groups = len(MAIN_SIGNAL_FEATURE_FAMILIES) * len(PROTOCOLS) * len(METHODS)
    if len(counts) != expected_groups or not counts.eq(2_319).all():
        raise ValueError("a neural sensor family/protocol/method loses an OOF row")


def bootstrap_neural_sensor_score_differences(
    predictions: pd.DataFrame,
    draw_plan: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Pair absolute protocol scores across sensor families on one bearing draw plan."""

    validate_neural_sensor_ensemble(predictions)
    bearing_codes = tuple(str(column) for column in draw_plan.columns)
    if set(bearing_codes) != set(predictions["bearing_code"].astype(str)):
        raise ValueError("neural sensor score contrast uses another bearing draw plan")
    weights = draw_plan.loc[:, bearing_codes].to_numpy(dtype=float)
    if len(weights) < 1 or not np.all(weights.sum(axis=1) == len(bearing_codes)):
        raise ValueError("neural sensor bearing draw plan is invalid")
    bearing_index = {code: index for index, code in enumerate(bearing_codes)}
    confusions: dict[tuple[str, str, str], np.ndarray] = {}
    for (family, protocol, method), rows in predictions.groupby(
        ["feature_family", "protocol", "method"], sort=True, observed=True
    ):
        matrices = np.zeros((len(bearing_codes), 3, 3), dtype=np.int64)
        for bearing, bearing_rows in rows.groupby("bearing_code", sort=True, observed=True):
            matrices[bearing_index[str(bearing)]] = confusion_matrix(
                bearing_rows["truth"],
                bearing_rows["prediction"],
                labels=PADERBORN_LABELS,
            )
        confusions[(str(family), str(protocol), str(method))] = matrices

    summaries = []
    draws = []
    for left_family, right_family in SENSOR_GAP_COMPARISONS:
        for protocol in PROTOCOLS:
            for method in METHODS:
                left_confusions = confusions[(left_family, protocol, method)]
                right_confusions = confusions[(right_family, protocol, method)]
                left_values = _macro_f1_from_confusions(
                    np.einsum("db,bij->dij", weights, left_confusions, optimize=True)
                )
                right_values = _macro_f1_from_confusions(
                    np.einsum("db,bij->dij", weights, right_confusions, optimize=True)
                )
                differences = left_values - right_values
                observed = float(
                    _macro_f1_from_confusions(left_confusions.sum(axis=0)[None])[0]
                    - _macro_f1_from_confusions(right_confusions.sum(axis=0)[None])[0]
                )
                lower, upper = np.quantile(differences, (0.025, 0.975))
                summaries.append(
                    {
                        "left_feature_family": left_family,
                        "right_feature_family": right_family,
                        "protocol": protocol,
                        "method": method,
                        "metric": "pooled_macro_f1",
                        "effect_left_minus_right": observed,
                        "bootstrap_lower_95": float(lower),
                        "bootstrap_upper_95": float(upper),
                        "bootstrap_draws": len(differences),
                        "resampling_unit": ("bearing_code_stratified_by_truth_shared_plan"),
                    }
                )
                draws.extend(
                    {
                        "draw": draw,
                        "left_feature_family": left_family,
                        "right_feature_family": right_family,
                        "protocol": protocol,
                        "method": method,
                        "effect_left_minus_right": float(value),
                    }
                    for draw, value in enumerate(differences)
                )
    return pd.DataFrame(summaries), pd.DataFrame(draws)


def neural_sensor_rank_concordance(aggregate: pd.DataFrame) -> pd.DataFrame:
    """Compare method rankings induced by different frozen sensor views."""

    records = []
    for protocol in PROTOCOLS:
        rows = aggregate.loc[aggregate["protocol"] == protocol]
        for metric in ("pooled_macro_f1", "mean_cell_macro_f1"):
            ranks = rows.pivot(index="method", columns="feature_family", values=metric).rank(
                ascending=False, method="average"
            )
            if set(ranks.columns) != set(MAIN_SIGNAL_FEATURE_FAMILIES):
                raise ValueError("neural sensor rank table loses a feature family")
            for left, right in combinations(MAIN_SIGNAL_FEATURE_FAMILIES, 2):
                result = kendalltau(ranks[left], ranks[right])
                records.append(
                    {
                        "protocol": protocol,
                        "metric": metric,
                        "left_feature_family": left,
                        "right_feature_family": right,
                        "kendall_tau": float(result.statistic),
                        "method_count": len(ranks),
                    }
                )
    return pd.DataFrame(records)
