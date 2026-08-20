"""Bearing-cluster bootstrap for the sealed Paderborn prospective evaluation."""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from smartvalve.data.paderborn import (
    BEARING_METADATA,
    OPERATING_SETTINGS,
    PRIMARY_BEARING_CODES,
)
from smartvalve.experiments.cranfield_causal_audit import AUDIT_SEEDS
from smartvalve.experiments.paderborn_partitions import MEASUREMENT_INDICES
from smartvalve.experiments.paderborn_splits import PADERBORN_OUTER_FOLDS
from smartvalve.experiments.selective_bootstrap import (
    HEADLINE_SCORE,
    HEADLINE_SOURCE_COVERAGE,
    METHODS,
    DatasetArrays,
    _artifact,
    _interval,
    _sha256,
    _validate_inputs,
    tensorize_dataset,
)

BOOTSTRAP_VERSION = "paderborn-paired-bearing-cluster-bootstrap-0.1.0"
BOOTSTRAP_REPLICATES = 2_000
BOOTSTRAP_SEED = 20_260_818
ENDPOINTS = (
    "minimum_setting_macro_f1",
    "selective_risk_at_source_50pct",
)
PRACTICAL_EFFECTS = {
    "pirl_minus_erm_minimum_setting_macro_f1": 0.01,
    "erm_minus_pirl_selective_risk_at_source_50pct": 0.01,
}
PADERBORN_METADATA_COLUMNS = (
    "bearing_code",
    "setting_code",
    "measurement_index",
)


@dataclass(frozen=True)
class PaderbornBootstrapArrays:
    """Dense arrays plus the physical identity map used by every paired draw."""

    base: DatasetArrays
    settings: tuple[str, ...]
    bearings: pd.DataFrame
    prediction_setting: np.ndarray
    block_bearing: np.ndarray


def _official_label_map() -> dict[str, str]:
    return {
        item.code: item.primary_label
        for item in BEARING_METADATA
        if item.code in PRIMARY_BEARING_CODES
    }


def _official_fold_map() -> dict[tuple[str, str], str]:
    mapping: dict[tuple[str, str], str] = {}
    for fold in PADERBORN_OUTER_FOLDS:
        for bearing_code in fold.held_bearing_codes:
            key = (bearing_code, fold.held_setting_code)
            if key in mapping:
                raise ValueError("Paderborn fold manifest maps a target twice")
            mapping[key] = fold.fold_id
    return mapping


def _validate_metadata_parity(
    predictions: pd.DataFrame,
    decisions: pd.DataFrame,
) -> None:
    required = set(PADERBORN_METADATA_COLUMNS)
    missing_predictions = required - set(predictions.columns)
    missing_decisions = required - set(decisions.columns)
    if missing_predictions or missing_decisions:
        raise ValueError(
            "Paderborn bootstrap inputs are missing physical metadata: "
            f"predictions={sorted(missing_predictions)}, "
            f"decisions={sorted(missing_decisions)}"
        )
    key = ["dataset", "method", "seed", "fold_id", "row_index"]
    parity = decisions.loc[:, [*key, *PADERBORN_METADATA_COLUMNS]].merge(
        predictions.loc[:, [*key, *PADERBORN_METADATA_COLUMNS]],
        on=key,
        how="outer",
        suffixes=("_decision", "_prediction"),
        validate="one_to_one",
        indicator=True,
    )
    if not parity["_merge"].eq("both").all():
        raise ValueError("Paderborn decision and prediction metadata keys differ")
    for column in PADERBORN_METADATA_COLUMNS:
        if not np.array_equal(
            parity[f"{column}_decision"].to_numpy(),
            parity[f"{column}_prediction"].to_numpy(),
        ):
            raise ValueError(f"Paderborn decision {column} differs from predictions")


def _physical_measurements(predictions: pd.DataFrame) -> pd.DataFrame:
    physical_columns = [
        "block_id",
        "bearing_code",
        "setting_code",
        "measurement_index",
        "environment_id",
        "truth",
        "fold_id",
        "row_index",
    ]
    grouped = predictions.groupby("block_id", sort=True, observed=True)
    if (grouped[physical_columns[1:]].nunique(dropna=False) != 1).any().any():
        raise ValueError("a Paderborn physical block changes metadata across paired models")
    physical = (
        predictions.loc[:, physical_columns]
        .drop_duplicates("block_id")
        .sort_values("block_id", kind="stable")
        .reset_index(drop=True)
    )
    expected_keys = {
        (bearing, setting.code, measurement)
        for bearing in PRIMARY_BEARING_CODES
        for setting in OPERATING_SETTINGS
        for measurement in MEASUREMENT_INDICES
    }
    actual_keys = set(
        physical.loc[
            :, ["bearing_code", "setting_code", "measurement_index"]
        ].itertuples(index=False, name=None)
    )
    if actual_keys != expected_keys or len(physical) != len(expected_keys):
        raise ValueError("Paderborn predictions do not contain the exact pure measurement set")
    row_indices = physical["row_index"].to_numpy(dtype=np.int64)
    if not np.array_equal(np.sort(row_indices), np.arange(len(expected_keys))):
        raise ValueError("Paderborn row_index must be a unique global 0-based coordinate")
    expected_block_ids = (
        physical.loc[:, ["bearing_code", "setting_code", "measurement_index"]]
        .astype(str)
        .agg("|".join, axis=1)
        .to_numpy(dtype=str)
    )
    if not np.array_equal(
        expected_block_ids, physical["block_id"].to_numpy(dtype=str)
    ):
        raise ValueError("Paderborn block_id differs from its physical measurement key")

    label_map = _official_label_map()
    expected_truth = physical["bearing_code"].map(label_map)
    if expected_truth.isna().any() or not np.array_equal(
        expected_truth.to_numpy(dtype=str), physical["truth"].to_numpy(dtype=str)
    ):
        raise ValueError("Paderborn prediction labels differ from frozen metadata")
    if not np.array_equal(
        physical["environment_id"].to_numpy(dtype=str),
        physical["setting_code"].to_numpy(dtype=str),
    ):
        raise ValueError("Paderborn environment_id must equal the operating setting")

    fold_map = _official_fold_map()
    expected_folds = np.asarray(
        [
            fold_map[(bearing, setting)]
            for bearing, setting in physical.loc[
                :, ["bearing_code", "setting_code"]
            ].itertuples(index=False, name=None)
        ],
        dtype=str,
    )
    if not np.array_equal(expected_folds, physical["fold_id"].to_numpy(dtype=str)):
        raise ValueError("Paderborn target rows do not match the frozen 24-fold manifest")

    paired_counts = predictions.groupby(
        ["method", "seed", "block_id"], sort=False, observed=True
    ).size()
    expected_paired_rows = len(METHODS) * len(AUDIT_SEEDS) * len(expected_keys)
    if len(predictions) != expected_paired_rows or not paired_counts.eq(1).all():
        raise ValueError("each Paderborn block must occur once per paired method and seed")
    return physical


def tensorize_paderborn(
    predictions: pd.DataFrame,
    decisions: pd.DataFrame,
) -> PaderbornBootstrapArrays:
    """Validate the prospective schema and map every measurement to one bearing."""

    if set(predictions["dataset"].astype(str)) != {"paderborn"}:
        raise ValueError("the Paderborn bootstrap accepts only the paderborn dataset")
    if set(decisions["dataset"].astype(str)) != {"paderborn"}:
        raise ValueError("the Paderborn decisions contain an unexpected dataset")
    _validate_metadata_parity(predictions, decisions)
    physical = _physical_measurements(predictions)
    base = tensorize_dataset(predictions, decisions, "paderborn")

    label_map = _official_label_map()
    bearings = pd.DataFrame(
        {
            "bearing_code": PRIMARY_BEARING_CODES,
            "truth": [label_map[code] for code in PRIMARY_BEARING_CODES],
        }
    ).sort_values(["truth", "bearing_code"], kind="stable", ignore_index=True)
    bearing_index = {
        code: index for index, code in enumerate(bearings["bearing_code"])
    }
    physical_by_block = physical.set_index("block_id", verify_integrity=True)
    aligned_bearings = base.blocks["block_id"].map(
        physical_by_block["bearing_code"]
    )
    if aligned_bearings.isna().any():
        raise ValueError("Paderborn tensor blocks lost their bearing provenance")
    block_bearing = aligned_bearings.map(bearing_index)
    if block_bearing.isna().any():
        raise ValueError("Paderborn tensor contains an unknown bearing")

    settings = tuple(setting.code for setting in OPERATING_SETTINGS)
    setting_index = {setting: index for index, setting in enumerate(settings)}
    prediction_setting = predictions["setting_code"].map(setting_index)
    if prediction_setting.isna().any():
        raise ValueError("Paderborn predictions contain an unknown operating setting")
    return PaderbornBootstrapArrays(
        base=base,
        settings=settings,
        bearings=bearings,
        prediction_setting=prediction_setting.to_numpy(dtype=np.int64),
        block_bearing=block_bearing.to_numpy(dtype=np.int64),
    )


def stratified_bearing_choices(
    bearings: pd.DataFrame,
    *,
    replicates: int,
    seed: int,
) -> tuple[np.ndarray, pd.DataFrame]:
    """Resample identities within class; each slot represents a complete bearing."""

    required = {"bearing_code", "truth"}
    if required - set(bearings.columns):
        raise ValueError("bearing bootstrap table requires bearing_code and truth")
    if replicates < 1:
        raise ValueError("bootstrap replicate count must be positive")
    bearings = bearings.loc[:, ["bearing_code", "truth"]].reset_index(drop=True)
    if bearings.empty or bearings["bearing_code"].duplicated().any():
        raise ValueError("bearing bootstrap identities must be non-empty and unique")
    if bearings.groupby("bearing_code", observed=True)["truth"].nunique().max() != 1:
        raise ValueError("a bearing identity maps to multiple classes")
    rng = np.random.default_rng(seed)
    choices = np.empty((replicates, len(bearings)), dtype=np.int64)
    slot_truth: list[str] = []
    slot_number: list[int] = []
    offset = 0
    for truth, group in bearings.groupby("truth", sort=True, observed=True):
        indices = group.index.to_numpy(dtype=np.int64)
        if len(indices) < 2:
            raise ValueError("every bearing bootstrap class needs at least two identities")
        choices[:, offset : offset + len(indices)] = rng.choice(
            indices,
            size=(replicates, len(indices)),
            replace=True,
        )
        slot_truth.extend([str(truth)] * len(indices))
        slot_number.extend(range(len(indices)))
        offset += len(indices)
    slots = pd.DataFrame(
        {
            "slot": np.arange(len(bearings), dtype=np.int64),
            "truth": slot_truth,
            "draw_slot": slot_number,
        }
    )
    return choices, slots


def bearing_weights_to_block_weights(
    arrays: PaderbornBootstrapArrays,
    bearing_weights: np.ndarray,
) -> np.ndarray:
    bearing_weights = np.asarray(bearing_weights, dtype=float)
    if (
        bearing_weights.ndim != 1
        or len(bearing_weights) != len(arrays.bearings)
        or np.any(bearing_weights < 0)
        or not np.isfinite(bearing_weights).all()
    ):
        raise ValueError("bearing weights must be an aligned nonnegative vector")
    if bearing_weights.sum() <= 0:
        raise ValueError("at least one bearing must have positive weight")
    return bearing_weights[arrays.block_bearing]


def _macro_f1(
    truth: np.ndarray,
    prediction: np.ndarray,
    weights: np.ndarray,
    class_count: int,
) -> float:
    confusion = np.bincount(
        truth * class_count + prediction,
        weights=weights,
        minlength=class_count**2,
    ).reshape(class_count, class_count)
    true_positive = np.diag(confusion)
    denominator = confusion.sum(axis=0) + confusion.sum(axis=1)
    class_f1 = np.divide(
        2 * true_positive,
        denominator,
        out=np.zeros_like(true_positive),
        where=denominator > 0,
    )
    return float(class_f1.mean())


def paderborn_metrics(
    arrays: PaderbornBootstrapArrays,
    bearing_weights: np.ndarray,
) -> np.ndarray:
    """Return paired method endpoints after carrying each sampled identity intact."""

    base = arrays.base
    block_weights = bearing_weights_to_block_weights(arrays, bearing_weights)
    result = np.empty((len(base.methods), len(ENDPOINTS)), dtype=float)
    for method_index in range(len(base.methods)):
        seed_minimum_f1 = []
        seed_selective_risk = []
        for seed_index in range(len(base.seeds)):
            setting_f1 = []
            for setting_index in range(len(arrays.settings)):
                rows = (
                    (base.prediction_method == method_index)
                    & (base.prediction_seed == seed_index)
                    & (arrays.prediction_setting == setting_index)
                )
                weights = block_weights[base.prediction_block[rows]]
                setting_f1.append(
                    _macro_f1(
                        base.prediction_truth[rows],
                        base.prediction_value[rows],
                        weights,
                        len(base.labels),
                    )
                )
            seed_minimum_f1.append(min(setting_f1))
            rows = (
                (base.selective_method == method_index)
                & (base.selective_seed == seed_index)
            )
            weights = block_weights[base.selective_block[rows]]
            accepted_weights = weights * base.selective_accepted[rows]
            accepted_total = float(accepted_weights.sum())
            seed_selective_risk.append(
                float(
                    (
                        accepted_weights
                        * base.selective_error[rows].astype(float)
                    ).sum()
                    / accepted_total
                )
                if accepted_total > 0
                else 1.0
            )
        result[method_index] = (
            float(np.mean(seed_minimum_f1)),
            float(np.mean(seed_selective_risk)),
        )
    return result


def _draw_plan(
    arrays: PaderbornBootstrapArrays,
    choices: np.ndarray,
    slots: pd.DataFrame,
) -> pd.DataFrame:
    replicate_count, slot_count = choices.shape
    return pd.DataFrame(
        {
            "dataset": "paderborn",
            "replicate": np.repeat(np.arange(replicate_count), slot_count),
            "truth": np.tile(slots["truth"].to_numpy(), replicate_count),
            "draw_slot": np.tile(slots["draw_slot"].to_numpy(), replicate_count),
            "selected_bearing_code": arrays.bearings.loc[
                choices.ravel(), "bearing_code"
            ].to_numpy(),
        }
    )


def run_paderborn_bootstrap(
    target_predictions_path: Path,
    selection_decisions_path: Path,
    output_directory: Path,
    *,
    replicates: int = BOOTSTRAP_REPLICATES,
    seed: int = BOOTSTRAP_SEED,
) -> dict[str, Any]:
    predictions, decisions = _validate_inputs(
        pd.read_parquet(target_predictions_path),
        pd.read_parquet(selection_decisions_path),
    )
    arrays = tensorize_paderborn(predictions, decisions)
    point = paderborn_metrics(
        arrays, np.ones(len(arrays.bearings), dtype=float)
    )
    choices, slots = stratified_bearing_choices(
        arrays.bearings,
        replicates=replicates,
        seed=seed,
    )
    replicate_metrics = np.empty(
        (replicates, len(METHODS), len(ENDPOINTS)), dtype=float
    )
    for replicate in range(replicates):
        weights = np.bincount(
            choices[replicate], minlength=len(arrays.bearings)
        ).astype(float)
        replicate_metrics[replicate] = paderborn_metrics(arrays, weights)

    point_results = {
        method: {
            endpoint: float(point[method_index, endpoint_index])
            for endpoint_index, endpoint in enumerate(ENDPOINTS)
        }
        for method_index, method in enumerate(METHODS)
    }
    comparisons = {
        "pirl_minus_erm_minimum_setting_macro_f1": (
            point[1, 0] - point[0, 0],
            replicate_metrics[:, 1, 0] - replicate_metrics[:, 0, 0],
        ),
        "erm_minus_pirl_selective_risk_at_source_50pct": (
            point[0, 1] - point[1, 1],
            replicate_metrics[:, 0, 1] - replicate_metrics[:, 1, 1],
        ),
    }
    comparison_summaries = {}
    for name, (point_difference, distribution) in comparisons.items():
        summary = _interval(float(point_difference), distribution)
        summary["positive_favors_pirl"] = True
        summary["minimum_practical_effect"] = PRACTICAL_EFFECTS[name]
        summary["practically_positive_and_ci_excludes_zero"] = bool(
            point_difference >= PRACTICAL_EFFECTS[name]
            and summary["ci95_low"] > 0
        )
        comparison_summaries[name] = summary

    replicate_rows = []
    for replicate in range(replicates):
        for method_index, method in enumerate(METHODS):
            replicate_rows.append(
                {
                    "dataset": "paderborn",
                    "replicate": replicate,
                    "method": method,
                    **{
                        endpoint: float(
                            replicate_metrics[
                                replicate, method_index, endpoint_index
                            ]
                        )
                        for endpoint_index, endpoint in enumerate(ENDPOINTS)
                    },
                }
            )
    replicate_frame = pd.DataFrame(replicate_rows)
    draw_plan = _draw_plan(arrays, choices, slots)
    output_directory.mkdir(parents=True, exist_ok=True)
    replicate_path = output_directory / "bootstrap_metric_tensor.parquet"
    draw_path = output_directory / "bootstrap_draw_plan.parquet"
    replicate_frame.to_parquet(replicate_path, index=False)
    draw_plan.to_parquet(draw_path, index=False)
    metrics = {
        "bootstrap_version": BOOTSTRAP_VERSION,
        "generated_at": datetime.now(UTC).isoformat(),
        "protocol_document": (
            "research/protocols/paderborn_prospective_evaluation_v0.1.md"
        ),
        "input": {
            "target_predictions": str(target_predictions_path.resolve()),
            "target_predictions_sha256": _sha256(target_predictions_path),
            "selection_decisions": str(selection_decisions_path.resolve()),
            "selection_decisions_sha256": _sha256(selection_decisions_path),
            "archive_access": "not performed by this bootstrap stage",
        },
        "configuration": {
            "replicates": replicates,
            "seed": seed,
            "methods": list(METHODS),
            "model_seeds": list(AUDIT_SEEDS),
            "headline_score": HEADLINE_SCORE,
            "headline_source_coverage": HEADLINE_SOURCE_COVERAGE,
            "endpoints": list(ENDPOINTS),
            "resampling_unit": "bearing_identity",
            "stratification": "truth",
            "identity_payload": "all four settings and all 20 repetitions",
            "zero_accepted_bootstrap_draw_risk": 1.0,
            "practical_effects": PRACTICAL_EFFECTS,
        },
        "contract": {
            "pure_bearings": len(arrays.bearings),
            "physical_measurements": len(arrays.base.blocks),
            "settings": list(arrays.settings),
            "measurements_per_bearing_setting": len(MEASUREMENT_INDICES),
        },
        "point_results": point_results,
        "paired_comparisons": comparison_summaries,
        "multiplicity": {
            "status": "not applied until the frozen D0/D1/D2 six-test family is complete",
            "planned_family_size": 6,
        },
        "artifacts": {
            "bootstrap_metric_tensor": _artifact(
                replicate_path, rows=len(replicate_frame)
            ),
            "bootstrap_draw_plan": _artifact(draw_path, rows=len(draw_plan)),
        },
    }
    metrics_path = output_directory / "metrics.json"
    metrics_path.write_text(
        json.dumps(metrics, ensure_ascii=False, indent=2, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    return metrics


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--target-predictions", type=Path, required=True)
    parser.add_argument("--selection-decisions", type=Path, required=True)
    parser.add_argument("--output-directory", type=Path, required=True)
    parser.add_argument("--replicates", type=int, default=BOOTSTRAP_REPLICATES)
    parser.add_argument("--seed", type=int, default=BOOTSTRAP_SEED)
    args = parser.parse_args()
    result = run_paderborn_bootstrap(
        args.target_predictions,
        args.selection_decisions,
        args.output_directory,
        replicates=args.replicates,
        seed=args.seed,
    )
    print(json.dumps(result["paired_comparisons"], ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
