"""Frozen multi-sensor sensitivity utilities for the Paderborn protocol audit."""

from __future__ import annotations

from time import monotonic

import numpy as np
import pandas as pd
from sklearn.metrics import accuracy_score, balanced_accuracy_score, confusion_matrix, f1_score

from smartvalve.data.paderborn_features import (
    MAIN_SIGNAL_FEATURE_FAMILIES,
    main_signal_feature_family_names,
)
from smartvalve.experiments.paderborn_protocol_contrast import (
    BOOTSTRAP_DRAWS,
    MODEL_NAMES,
    RANDOM_SEED,
    attach_common_cells,
    build_classifier,
    build_protocol_splits,
    generate_oof_predictions,
    paired_bearing_bootstrap,
    protocol_effect_table,
    protocol_rank_concordance,
    score_oof_predictions,
)

SCHEMA_VERSION = "smartvalve-paderborn-sensor-protocol-audit-0.1.0"
SENSOR_GAP_COMPARISONS = (
    ("vibration", "motor_current"),
    ("fusion", "vibration"),
    ("fusion", "motor_current"),
)


def generate_sensor_family_fault_predictions(
    frame: pd.DataFrame,
    *,
    random_seed: int = RANDOM_SEED,
    model_names: tuple[str, ...] = MODEL_NAMES,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Generate complete fault OOF predictions for all frozen sensor families."""

    prediction_frames = []
    fit_frames = []
    for family in MAIN_SIGNAL_FEATURE_FAMILIES:
        predictions, fits = generate_oof_predictions(
            frame,
            random_seed=random_seed,
            model_names=model_names,
            feature_names=main_signal_feature_family_names(family),
        )
        predictions.insert(0, "feature_family", family)
        fits.insert(0, "feature_family", family)
        prediction_frames.append(predictions)
        fit_frames.append(fits)
    return (
        pd.concat(prediction_frames, ignore_index=True),
        pd.concat(fit_frames, ignore_index=True),
    )


def score_sensor_family_fault_predictions(
    predictions: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Score each family without pooling predictions across sensor views."""

    if "feature_family" not in predictions:
        raise ValueError("sensor predictions are missing feature_family")
    aggregates = []
    cells = []
    effects = []
    concordances = []
    for family in MAIN_SIGNAL_FEATURE_FAMILIES:
        rows = predictions.loc[predictions["feature_family"] == family].copy()
        if rows.empty:
            raise ValueError(f"sensor predictions are missing family: {family}")
        aggregate, cell = score_oof_predictions(rows)
        effect = protocol_effect_table(aggregate)
        concordance = protocol_rank_concordance(aggregate)
        for table in (aggregate, cell, effect, concordance):
            table.insert(0, "feature_family", family)
        aggregates.append(aggregate)
        cells.append(cell)
        effects.append(effect)
        concordances.append(concordance)
    return tuple(
        pd.concat(tables, ignore_index=True)
        for tables in (aggregates, cells, effects, concordances)
    )


def bootstrap_sensor_family_fault_predictions(
    predictions: pd.DataFrame,
    *,
    draws: int = BOOTSTRAP_DRAWS,
    random_seed: int = RANDOM_SEED,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Use one deterministic physical-bearing draw plan for every sensor family."""

    summaries = []
    draw_frames = []
    shared_plan: pd.DataFrame | None = None
    for family in MAIN_SIGNAL_FEATURE_FAMILIES:
        rows = predictions.loc[predictions["feature_family"] == family].copy()
        if rows.empty:
            raise ValueError(f"sensor predictions are missing family: {family}")
        summary, family_draws, plan = paired_bearing_bootstrap(
            rows,
            draws=draws,
            random_seed=random_seed,
        )
        if shared_plan is None:
            shared_plan = plan
        else:
            pd.testing.assert_frame_equal(shared_plan, plan)
        summary.insert(0, "feature_family", family)
        family_draws.insert(0, "feature_family", family)
        summaries.append(summary)
        draw_frames.append(family_draws)
    if shared_plan is None:
        raise ValueError("no sensor family produced a bootstrap plan")
    return (
        pd.concat(summaries, ignore_index=True),
        pd.concat(draw_frames, ignore_index=True),
        shared_plan,
    )


def sensor_gap_differences(
    bootstrap_summary: pd.DataFrame,
    bootstrap_draws: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Contrast random-minus-crossed gaps between predeclared sensor families."""

    key_columns = (
        "comparison_protocol",
        "reference_protocol",
        "method",
    )
    summary = bootstrap_summary.loc[
        (bootstrap_summary["comparison_protocol"] == "measurement_random")
        & (bootstrap_summary["reference_protocol"] == "crossed_holdout")
    ].copy()
    draws = bootstrap_draws.loc[
        (bootstrap_draws["comparison_protocol"] == "measurement_random")
        & (bootstrap_draws["reference_protocol"] == "crossed_holdout")
    ].copy()
    summary_index = summary.set_index(["feature_family", *key_columns])
    draw_index = draws.set_index(["feature_family", *key_columns, "draw"])
    records = []
    draw_records = []
    for left_family, right_family in SENSOR_GAP_COMPARISONS:
        left_summary = summary_index.xs(left_family, level="feature_family")
        right_summary = summary_index.xs(right_family, level="feature_family")
        if not left_summary.index.equals(right_summary.index):
            raise ValueError("sensor bootstrap summaries have different method keys")
        left_draws = draw_index.xs(left_family, level="feature_family")
        right_draws = draw_index.xs(right_family, level="feature_family")
        if not left_draws.index.equals(right_draws.index):
            raise ValueError("sensor bootstrap draws do not share exact keys")
        values = (
            left_draws["effect_comparison_minus_reference"]
            - right_draws["effect_comparison_minus_reference"]
        )
        for key, value in values.items():
            comparison_protocol, reference_protocol, method, draw = key
            draw_records.append(
                {
                    "left_feature_family": left_family,
                    "right_feature_family": right_family,
                    "comparison_protocol": comparison_protocol,
                    "reference_protocol": reference_protocol,
                    "method": method,
                    "draw": int(draw),
                    "gap_difference_left_minus_right": float(value),
                }
            )
        for key in left_summary.index:
            comparison_protocol, reference_protocol, method = key
            observed = float(
                left_summary.loc[key, "effect_comparison_minus_reference"]
                - right_summary.loc[key, "effect_comparison_minus_reference"]
            )
            method_values = values.xs(key, level=key_columns).to_numpy(dtype=float)
            lower, upper = np.quantile(method_values, (0.025, 0.975))
            records.append(
                {
                    "left_feature_family": left_family,
                    "right_feature_family": right_family,
                    "comparison_protocol": comparison_protocol,
                    "reference_protocol": reference_protocol,
                    "method": method,
                    "gap_difference_left_minus_right": observed,
                    "bootstrap_lower_95": float(lower),
                    "bootstrap_upper_95": float(upper),
                    "bootstrap_draws": len(method_values),
                    "resampling_unit": "bearing_code_stratified_by_truth_shared_plan",
                }
            )
    return pd.DataFrame(records), pd.DataFrame(draw_records)


def generate_bearing_reidentification_predictions(
    frame: pd.DataFrame,
    *,
    random_seed: int = RANDOM_SEED,
    model_names: tuple[str, ...] = MODEL_NAMES,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Predict exact bearing identity across held operating settings."""

    indexed = attach_common_cells(frame.reset_index(drop=True))
    setting_splits = build_protocol_splits(indexed, random_seed=random_seed)[
        "setting_holdout"
    ]
    prediction_records = []
    fit_records = []
    for family in MAIN_SIGNAL_FEATURE_FAMILIES:
        feature_names = main_signal_feature_family_names(family)
        features = indexed.loc[:, feature_names].to_numpy(dtype=float)
        labels = indexed["bearing_code"].to_numpy(dtype=str)
        for split in setting_splits:
            for model_name in model_names:
                started = monotonic()
                classifier = build_classifier(model_name, random_seed=random_seed)
                classifier.fit(features[split.source_indices], labels[split.source_indices])
                predicted = np.asarray(
                    classifier.predict(features[split.target_indices]),
                    dtype=str,
                )
                duration = monotonic() - started
                target = indexed.iloc[split.target_indices].loc[
                    :,
                    [
                        "filename",
                        "bearing_code",
                        "setting_code",
                        "measurement_index",
                        "truth",
                    ],
                ].copy()
                target.insert(0, "row_index", split.target_indices)
                target.insert(0, "fold_id", split.fold_id)
                target.insert(0, "method", model_name)
                target.insert(0, "feature_family", family)
                target.rename(columns={"bearing_code": "bearing_truth"}, inplace=True)
                target["bearing_prediction"] = predicted
                prediction_records.append(target)
                fit_records.append(
                    {
                        "feature_family": family,
                        "fold_id": split.fold_id,
                        "method": model_name,
                        "source_count": len(split.source_indices),
                        "target_count": len(split.target_indices),
                        "feature_count": len(feature_names),
                        "fit_predict_duration_s": duration,
                    }
                )
    predictions = pd.concat(prediction_records, ignore_index=True)
    fits = pd.DataFrame(fit_records)
    expected_rows = len(indexed) * len(MAIN_SIGNAL_FEATURE_FAMILIES) * len(model_names)
    if len(predictions) != expected_rows:
        raise ValueError("bearing re-identification prediction count changed")
    key = ["feature_family", "method", "row_index"]
    if predictions.duplicated(key).any():
        raise ValueError("bearing re-identification contains duplicate OOF rows")
    return predictions.sort_values(key, kind="stable").reset_index(drop=True), fits


def score_bearing_reidentification_predictions(
    predictions: pd.DataFrame,
) -> pd.DataFrame:
    """Score pooled exact-bearing predictions with every physical ID weighted equally."""

    required = {
        "feature_family",
        "method",
        "row_index",
        "bearing_truth",
        "bearing_prediction",
    }
    missing = required - set(predictions)
    if missing:
        raise ValueError(f"bearing re-identification is missing columns: {sorted(missing)}")
    labels = tuple(sorted(predictions["bearing_truth"].astype(str).unique()))
    records = []
    for (family, method), rows in predictions.groupby(
        ["feature_family", "method"], sort=True, observed=True
    ):
        truth = rows["bearing_truth"].to_numpy(dtype=str)
        predicted = rows["bearing_prediction"].to_numpy(dtype=str)
        matrix = confusion_matrix(truth, predicted, labels=labels)
        denominators = matrix.sum(axis=1)
        recalls = np.divide(
            np.diag(matrix),
            denominators,
            out=np.zeros(len(labels), dtype=float),
            where=denominators > 0,
        )
        records.append(
            {
                "feature_family": family,
                "method": method,
                "row_count": len(rows),
                "bearing_class_count": len(labels),
                "macro_f1": float(
                    f1_score(
                        truth,
                        predicted,
                        labels=labels,
                        average="macro",
                        zero_division=0,
                    )
                ),
                "balanced_accuracy": float(balanced_accuracy_score(truth, predicted)),
                "accuracy": float(accuracy_score(truth, predicted)),
                "minimum_bearing_recall": float(recalls.min()),
            }
        )
    result = pd.DataFrame(records)
    result["rank_macro_f1"] = result.groupby("feature_family", observed=True)[
        "macro_f1"
    ].rank(method="average", ascending=False)
    return result.sort_values(
        ["feature_family", "rank_macro_f1", "method"], kind="stable"
    ).reset_index(drop=True)
