"""Outcome-blind HUST control that matches crossed source size while sharing both factors."""

from __future__ import annotations

from dataclasses import dataclass
from itertools import combinations

import numpy as np
import pandas as pd
from scipy.stats import kendalltau
from sklearn.metrics import confusion_matrix

from smartvalve.data.hust import (
    HUST_LABELS,
    HUST_LOADS_W,
    HUST_SPECIFICATION_GROUPS,
    HUST_WINDOWS_PER_RECORDING,
)
from smartvalve.experiments.domain_data import SourceOnlyFold
from smartvalve.experiments.hust_evaluation import score_hust_record_predictions
from smartvalve.experiments.hust_protocol import (
    HustProtocolModelFold,
    build_hust_source_pairs,
    validate_hust_feature_frame,
)

SCHEMA_VERSION = "smartvalve-hust-d3-size-matched-control-0.1.0"
SIZE_MATCHED_PROTOCOL = "size_matched_shared_access"
REFERENCE_PROTOCOL = "crossed_holdout"
SIZE_MATCHED_PROTOCOLS = (SIZE_MATCHED_PROTOCOL, REFERENCE_PROTOCOL)


@dataclass(frozen=True)
class HustSizeMatchedSplit:
    """One target cell with a crossed-sized source that exposes both held factors."""

    fold_id: str
    held_specification_group: int
    held_load_w: int
    anchor_specification_group: int
    source_indices: np.ndarray
    target_indices: np.ndarray
    inaccessible_indices: np.ndarray

    def validate(self, frame: pd.DataFrame) -> None:
        arrays = (self.source_indices, self.target_indices, self.inaccessible_indices)
        flattened = np.concatenate(arrays)
        if (
            len(flattened) != len(frame)
            or len(np.unique(flattened)) != len(frame)
            or not np.array_equal(np.sort(flattened), np.arange(len(frame)))
        ):
            raise ValueError("size-matched split does not partition every HUST window once")
        observed = tuple(len(values) for values in arrays)
        if observed != (240, 30, 180):
            raise ValueError(f"size-matched window counts changed: {observed}")
        partitions = []
        for name, indices in zip(("source", "target", "inaccessible"), arrays, strict=True):
            rows = frame.iloc[indices]
            counts = rows.groupby("filename", observed=True).size()
            if not counts.eq(HUST_WINDOWS_PER_RECORDING).all():
                raise ValueError(f"size-matched {name} splits a recording")
            partitions.append(set(rows["filename"].astype(str)))
        if any(partitions[left] & partitions[right] for left, right in combinations(range(3), 2)):
            raise ValueError("a recording appears in multiple size-matched partitions")

        source = frame.iloc[self.source_indices]
        target = frame.iloc[self.target_indices]
        if (
            set(source["truth"].astype(str)) != set(HUST_LABELS)
            or set(target["truth"].astype(str)) != set(HUST_LABELS)
            or source.groupby("truth", observed=True).size().to_dict()
            != {label: 80 for label in HUST_LABELS}
        ):
            raise ValueError("size-matched source or target class balance changed")
        if set(target["specification_group"].astype(int)) != {self.held_specification_group} or set(
            target["load_w"].astype(int)
        ) != {self.held_load_w}:
            raise ValueError("size-matched target cell changed")
        source_groups = set(source["specification_group"].astype(int))
        source_loads = set(source["load_w"].astype(int))
        if (
            self.held_specification_group not in source_groups
            or self.held_load_w not in source_loads
            or source_groups != set(HUST_SPECIFICATION_GROUPS)
            or source_loads != set(HUST_LOADS_W)
        ):
            raise ValueError("size-matched source does not expose both target factors")
        held_bearings = set(target["bearing_code"].astype(str))
        exposed_bearings = set(source["bearing_code"].astype(str))
        if held_bearings - exposed_bearings:
            raise ValueError("size-matched source must expose each target bearing at another load")


def _cyclic_successor(group: int) -> int:
    groups = tuple(int(value) for value in HUST_SPECIFICATION_GROUPS)
    position = groups.index(int(group))
    return groups[(position + 1) % len(groups)]


def build_hust_size_matched_splits(
    frame: pd.DataFrame,
) -> tuple[HustSizeMatchedSplit, ...]:
    """Build 15 deterministic, class-balanced controls for the crossed target cells.

    Each source contains all 18 original XOR-arm recordings plus the six recordings from the
    cyclic-successor specification group at the two non-target loads. It therefore has the same
    24-recording size, class balance, environment support, nuisance-pair count, and fault-pair
    count as the strict crossed source while exposing the target bearing identities at other loads
    and the target load on other bearings.
    """

    indexed = frame.reset_index(drop=True)
    validate_hust_feature_frame(indexed)
    groups = indexed["specification_group"].to_numpy(dtype=int)
    loads = indexed["load_w"].to_numpy(dtype=int)
    splits = []
    target_counts = np.zeros(len(indexed), dtype=np.int64)
    for group in HUST_SPECIFICATION_GROUPS:
        for load in HUST_LOADS_W:
            anchor = _cyclic_successor(int(group))
            group_mask = groups == int(group)
            load_mask = loads == int(load)
            xor_mask = group_mask ^ load_mask
            anchor_strict_mask = (groups == anchor) & ~load_mask
            source = np.flatnonzero(xor_mask | anchor_strict_mask)
            target = np.flatnonzero(group_mask & load_mask)
            inaccessible = np.flatnonzero(
                ~(xor_mask | anchor_strict_mask | (group_mask & load_mask))
            )
            split = HustSizeMatchedSplit(
                fold_id=f"specification={group}|load_w={load}",
                held_specification_group=int(group),
                held_load_w=int(load),
                anchor_specification_group=anchor,
                source_indices=source,
                target_indices=target,
                inaccessible_indices=inaccessible,
            )
            split.validate(indexed)
            source_frame = indexed.iloc[source].reset_index(drop=True)
            nuisance_pairs, fault_pairs = build_hust_source_pairs(source_frame)
            if len(nuisance_pairs) != 120 or len(fault_pairs) != 240:
                raise ValueError("size-matched paired-control topology changed")
            target_counts[target] += 1
            splits.append(split)
    if len(splits) != 15 or not np.all(target_counts == 1):
        raise ValueError("size-matched protocol does not target every HUST window exactly once")
    return tuple(splits)


def build_hust_size_matched_model_folds(
    frame: pd.DataFrame,
) -> tuple[HustProtocolModelFold, ...]:
    """Materialize trainer-facing folds for the size-matched shared-access control."""

    indexed = frame.reset_index(drop=True)
    features = validate_hust_feature_frame(indexed)
    label_index = {label: index for index, label in enumerate(HUST_LABELS)}
    result = []
    for fold_number, split in enumerate(build_hust_size_matched_splits(indexed)):
        retained_global = np.concatenate((split.source_indices, split.target_indices))
        retained = indexed.iloc[retained_global].reset_index(drop=True)
        source_count = len(split.source_indices)
        source = retained.iloc[:source_count].reset_index(drop=True)
        nuisance_pairs, fault_pairs = build_hust_source_pairs(source)
        labels = retained["truth"].map(label_index)
        if labels.isna().any():
            raise ValueError("size-matched fold contains an unknown label")
        fold = SourceOnlyFold(
            dataset="hust_bearing_v3",
            fold_id=split.fold_id,
            held_factor=SIZE_MATCHED_PROTOCOL,
            held_level=fold_number,
            features=retained.loc[:, features].to_numpy(dtype=np.float32),
            labels=labels.to_numpy(dtype=np.int64),
            label_names=HUST_LABELS,
            feature_names=features,
            environment_ids=retained["load_w"].astype(str).to_numpy(),
            block_ids=(
                retained.loc[:, ["filename", "window_index"]]
                .astype(str)
                .agg("|".join, axis=1)
                .to_numpy()
            ),
            source_indices=np.arange(source_count, dtype=np.int64),
            target_indices=np.arange(source_count, len(retained), dtype=np.int64),
            nuisance_pairs=nuisance_pairs,
            fault_pairs=fault_pairs,
        )
        fold.validate()
        result.append(
            HustProtocolModelFold(
                protocol=SIZE_MATCHED_PROTOCOL,
                fold=fold,
                target_global_indices=split.target_indices.copy(),
                quarantine_global_indices=split.inaccessible_indices.copy(),
            )
        )
    return tuple(result)


def aggregate_hust_size_matched_records(
    window_predictions: pd.DataFrame,
) -> pd.DataFrame:
    """Aggregate ten window probabilities into one decision for all 45 target recordings."""

    probability_columns = tuple(f"probability_{label}" for label in HUST_LABELS)
    metadata = (
        "bearing_code",
        "specification_group",
        "load_w",
        "truth",
        "evaluation_cell",
    )
    records = []
    for (protocol, method, filename), rows in window_predictions.groupby(
        ["protocol", "method", "filename"], sort=True, observed=True
    ):
        if (
            protocol != SIZE_MATCHED_PROTOCOL
            or len(rows) != HUST_WINDOWS_PER_RECORDING
            or set(rows["window_index"].astype(int)) != set(range(HUST_WINDOWS_PER_RECORDING))
            or any(rows[column].nunique(dropna=False) != 1 for column in metadata)
        ):
            raise ValueError("size-matched window-to-record hierarchy changed")
        probabilities = rows.loc[:, probability_columns].to_numpy(dtype=float).mean(axis=0)
        predicted = HUST_LABELS[int(probabilities.argmax())]
        records.append(
            {
                "protocol": protocol,
                "method": method,
                "filename": filename,
                **{column: rows.iloc[0][column] for column in metadata},
                **{
                    column: float(probabilities[index])
                    for index, column in enumerate(probability_columns)
                },
                "prediction": predicted,
                "predictive_entropy": float(
                    -np.sum(probabilities * np.log(np.maximum(probabilities, 1e-300)))
                ),
                "window_disagreement_rate": float(
                    np.mean(rows["prediction"].to_numpy(dtype=str) != predicted)
                ),
            }
        )
    result = pd.DataFrame(records)
    methods = result["method"].nunique()
    if len(result) != 45 * methods:
        raise ValueError("size-matched recording prediction count changed")
    counts = result.groupby(["protocol", "method"], observed=True).size()
    if not counts.eq(45).all():
        raise ValueError("a size-matched method does not predict all 45 recordings")
    return result.sort_values(["protocol", "method", "filename"], kind="stable").reset_index(
        drop=True
    )


def score_hust_size_matched_comparison(
    size_matched: pd.DataFrame,
    crossed: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Validate a common target and score the two access protocols together."""

    reference = crossed.loc[crossed["protocol"] == REFERENCE_PROTOCOL].copy()
    if set(size_matched["method"].astype(str)) != set(reference["method"].astype(str)):
        raise ValueError("size-matched and crossed method sets differ")
    key = ["method", "filename", "bearing_code", "specification_group", "load_w", "truth"]
    left = size_matched.loc[:, key].sort_values(key, kind="stable").reset_index(drop=True)
    right = reference.loc[:, key].sort_values(key, kind="stable").reset_index(drop=True)
    if not left.equals(right):
        raise ValueError("size-matched and crossed target recording sets differ")
    combined = pd.concat((size_matched, reference), ignore_index=True)
    return score_hust_record_predictions(combined)


def hust_size_matched_rank_concordance(aggregate: pd.DataFrame) -> pd.DataFrame:
    """Compare nine-method ranks under equal source volume and different access."""

    records = []
    for metric in ("pooled_macro_f1", "mean_cell_macro_f1"):
        values = aggregate.pivot(index="method", columns="protocol", values=metric)
        if set(values) != set(SIZE_MATCHED_PROTOCOLS):
            raise ValueError("size-matched rank comparison loses a protocol")
        ranks = values.rank(ascending=False, method="average")
        statistic = kendalltau(ranks[SIZE_MATCHED_PROTOCOL], ranks[REFERENCE_PROTOCOL]).statistic
        records.append(
            {
                "metric": metric,
                "left_protocol": SIZE_MATCHED_PROTOCOL,
                "right_protocol": REFERENCE_PROTOCOL,
                "kendall_tau": float(statistic),
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


def bootstrap_hust_size_matched_comparison(
    predictions: pd.DataFrame,
    *,
    draws: int = 5_000,
    random_seed: int = 20260819,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Bootstrap shared-access minus crossed effects over class-stratified bearings."""

    if set(predictions["protocol"].astype(str)) != set(SIZE_MATCHED_PROTOCOLS):
        raise ValueError("size-matched bootstrap requires exactly two access protocols")
    bearing_truth = (
        predictions.loc[:, ["bearing_code", "truth"]]
        .drop_duplicates()
        .sort_values("bearing_code", kind="stable")
        .reset_index(drop=True)
    )
    if len(bearing_truth) != 15 or not bearing_truth.groupby("truth").size().eq(5).all():
        raise ValueError("size-matched bootstrap requires five bearings per class")
    bearing_codes = bearing_truth["bearing_code"].astype(str).to_numpy()
    bearing_index = {code: index for index, code in enumerate(bearing_codes)}
    weights = np.zeros((draws, len(bearing_codes)), dtype=np.int16)
    generator = np.random.default_rng(random_seed)
    for label in HUST_LABELS:
        candidates = np.flatnonzero(bearing_truth["truth"].to_numpy(dtype=str) == label)
        sampled = generator.choice(candidates, size=(draws, len(candidates)), replace=True)
        for draw_index, row in enumerate(sampled):
            weights[draw_index] += np.bincount(row, minlength=len(bearing_codes)).astype(np.int16)

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

    summaries = []
    draw_records = []
    for method in sorted(predictions["method"].astype(str).unique()):
        comparison = np.einsum(
            "db,bij->dij",
            weights,
            confusion_by_key[(SIZE_MATCHED_PROTOCOL, method)],
            optimize=True,
        )
        reference = np.einsum(
            "db,bij->dij",
            weights,
            confusion_by_key[(REFERENCE_PROTOCOL, method)],
            optimize=True,
        )
        values = _macro_f1_from_confusions(comparison) - _macro_f1_from_confusions(reference)
        observed = float(
            _macro_f1_from_confusions(
                confusion_by_key[(SIZE_MATCHED_PROTOCOL, method)].sum(axis=0)[None]
            )[0]
            - _macro_f1_from_confusions(
                confusion_by_key[(REFERENCE_PROTOCOL, method)].sum(axis=0)[None]
            )[0]
        )
        lower, upper = np.quantile(values, (0.025, 0.975))
        summaries.append(
            {
                "comparison_protocol": SIZE_MATCHED_PROTOCOL,
                "reference_protocol": REFERENCE_PROTOCOL,
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
                "comparison_protocol": SIZE_MATCHED_PROTOCOL,
                "reference_protocol": REFERENCE_PROTOCOL,
                "method": method,
                "effect_comparison_minus_reference": float(value),
            }
            for draw, value in enumerate(values)
        )
    return (
        pd.DataFrame(summaries),
        pd.DataFrame(draw_records),
        pd.DataFrame(weights, columns=bearing_codes),
    )


def hust_size_matched_gate(
    aggregate: pd.DataFrame,
    concordance: pd.DataFrame,
) -> dict[str, float | int | bool]:
    """Apply the outcome-blind descriptive access and rank thresholds."""

    values = aggregate.pivot(index="method", columns="protocol", values="pooled_macro_f1")
    gaps = values[SIZE_MATCHED_PROTOCOL] - values[REFERENCE_PROTOCOL]
    shared_ranks = values[SIZE_MATCHED_PROTOCOL].rank(ascending=False, method="average")
    crossed_ranks = values[REFERENCE_PROTOCOL].rank(ascending=False, method="average")
    row = concordance.loc[concordance["metric"] == "pooled_macro_f1"]
    if len(row) != 1:
        raise ValueError("size-matched primary rank row changed")
    tau = float(row.iloc[0]["kendall_tau"])
    positive = int((gaps > 0).sum())
    median_gap = float(gaps.median())
    maximum_shift = float((shared_ranks - crossed_ranks).abs().max())
    return {
        "positive_method_count": positive,
        "median_shared_minus_crossed_macro_f1": median_gap,
        "access_effect_rule_passed": positive >= 7 and median_gap >= 0.10,
        "shared_crossed_kendall_tau": tau,
        "maximum_absolute_rank_shift": maximum_shift,
        "rank_instability_rule_passed": tau < 0.50 or maximum_shift >= 3,
    }
