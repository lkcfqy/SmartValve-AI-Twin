"""Metadata-only Paderborn source/target/quarantine partitions and pair topology."""

from __future__ import annotations

from dataclasses import dataclass
from itertools import combinations

import numpy as np
import pandas as pd

from smartvalve.data.paderborn import (
    BEARING_METADATA,
    OPERATING_SETTINGS,
    PRIMARY_BEARING_CODES,
)
from smartvalve.data.paderborn_features import (
    STRUCTURALLY_EXCLUDED_FILENAMES,
    parse_measurement_filename,
)
from smartvalve.experiments.paderborn_splits import PADERBORN_OUTER_FOLDS

PADERBORN_LABELS = ("healthy", "outer", "inner")
MEASUREMENT_INDICES = tuple(range(1, 21))
PARTITION_COLUMNS = (
    "bearing_code",
    "setting_code",
    "measurement_index",
    "truth",
)


@dataclass(frozen=True)
class PaderbornPartition:
    """One strict double-unseen split with source-local intervention pairs."""

    fold_id: str
    held_bearing_codes: tuple[str, ...]
    held_setting_code: str
    source_indices: np.ndarray
    target_indices: np.ndarray
    quarantine_indices: np.ndarray
    nuisance_pairs: np.ndarray
    fault_pairs: np.ndarray

    def validate(self, frame: pd.DataFrame) -> None:
        row_count = len(frame)
        partitions = (
            self.source_indices,
            self.target_indices,
            self.quarantine_indices,
        )
        flattened = np.concatenate(partitions)
        if (
            len(flattened) != row_count
            or len(np.unique(flattened)) != row_count
            or not np.array_equal(np.sort(flattened), np.arange(row_count))
        ):
            raise ValueError("source, target and quarantine must partition every row once")
        held_identity = frame["bearing_code"].isin(self.held_bearing_codes).to_numpy()
        held_setting = frame["setting_code"].to_numpy(dtype=str) == self.held_setting_code
        expected_source = np.flatnonzero(~held_identity & ~held_setting)
        expected_target = np.flatnonzero(held_identity & held_setting)
        expected_quarantine = np.flatnonzero(held_identity ^ held_setting)
        if not np.array_equal(self.source_indices, expected_source):
            raise ValueError("source rows do not exclude both held axes")
        if not np.array_equal(self.target_indices, expected_target):
            raise ValueError("target rows are not the held-axis intersection")
        if not np.array_equal(self.quarantine_indices, expected_quarantine):
            raise ValueError("quarantine rows are not the two unused cross arms")

        source = frame.iloc[self.source_indices].reset_index(drop=True)
        for pairs, name in (
            (self.nuisance_pairs, "nuisance"),
            (self.fault_pairs, "fault"),
        ):
            if pairs.ndim != 2 or pairs.shape[1] != 2 or len(pairs) == 0:
                raise ValueError(f"{name} pairs must be a non-empty two-column array")
            if pairs.min() < 0 or pairs.max() >= len(source):
                raise ValueError(f"{name} pairs point outside source-local coordinates")

        nuisance_left = source.iloc[self.nuisance_pairs[:, 0]].reset_index(drop=True)
        nuisance_right = source.iloc[self.nuisance_pairs[:, 1]].reset_index(drop=True)
        for column in ("bearing_code", "measurement_index", "truth"):
            if not np.array_equal(nuisance_left[column], nuisance_right[column]):
                raise ValueError(f"nuisance pairs change {column}")
        if np.any(nuisance_left["setting_code"] == nuisance_right["setting_code"]):
            raise ValueError("nuisance pairs do not change the operating setting")

        fault_left = source.iloc[self.fault_pairs[:, 0]].reset_index(drop=True)
        fault_right = source.iloc[self.fault_pairs[:, 1]].reset_index(drop=True)
        for column in ("setting_code", "measurement_index"):
            if not np.array_equal(fault_left[column], fault_right[column]):
                raise ValueError(f"fault pairs change {column}")
        if np.any(fault_left["truth"] == fault_right["truth"]):
            raise ValueError("fault pairs do not change the pure-class label")

        class_pairs = [
            tuple(sorted((left, right)))
            for left, right in zip(fault_left["truth"], fault_right["truth"], strict=True)
        ]
        counts = pd.Series(class_pairs).value_counts().to_dict()
        expected_class_pairs = {tuple(sorted(pair)) for pair in combinations(PADERBORN_LABELS, 2)}
        if set(counts) != expected_class_pairs or len(set(counts.values())) != 1:
            raise ValueError("fault pair label strata are not equally weighted")


def validate_paderborn_measurement_index(frame: pd.DataFrame) -> None:
    missing = set(PARTITION_COLUMNS) - set(frame.columns)
    if missing:
        raise ValueError(f"Paderborn index is missing columns: {sorted(missing)}")
    excluded_keys = {
        (
            parse_measurement_filename(filename).bearing_code,
            parse_measurement_filename(filename).setting_code,
            parse_measurement_filename(filename).measurement_index,
        )
        for filename in STRUCTURALLY_EXCLUDED_FILENAMES
    }
    expected_rows = len(PRIMARY_BEARING_CODES) * len(OPERATING_SETTINGS) * len(
        MEASUREMENT_INDICES
    ) - len(excluded_keys)
    if len(frame) != expected_rows:
        raise ValueError(f"expected {expected_rows} pure-class measurements")
    key = ["bearing_code", "setting_code", "measurement_index"]
    if frame.duplicated(key).any():
        raise ValueError("Paderborn measurement index contains a duplicate key")
    expected_keys = {
        (bearing, setting.code, measurement)
        for bearing in PRIMARY_BEARING_CODES
        for setting in OPERATING_SETTINGS
        for measurement in MEASUREMENT_INDICES
    } - excluded_keys
    actual_keys = set(frame.loc[:, key].itertuples(index=False, name=None))
    if actual_keys != expected_keys:
        raise ValueError("Paderborn measurement index is incomplete or contains extra keys")
    labels = {bearing.code: bearing.primary_label for bearing in BEARING_METADATA}
    expected_truth = frame["bearing_code"].map(labels)
    if expected_truth.isna().any() or not np.array_equal(expected_truth, frame["truth"]):
        raise ValueError("Paderborn labels differ from the official pure-class metadata")


def _nuisance_pairs(source: pd.DataFrame) -> np.ndarray:
    pairs = []
    for _, group in source.groupby(["bearing_code", "measurement_index"], sort=True, observed=True):
        rows = group.sort_values("setting_code").index.to_numpy(dtype=int)
        pairs.extend(combinations(rows, 2))
    return np.asarray(pairs, dtype=np.int64)


def _fault_pairs(source: pd.DataFrame) -> np.ndarray:
    """Build equal class-pair strata with deterministic rotation across blocks."""

    pairs: list[tuple[int, int]] = []
    setting_order = {setting.code: index for index, setting in enumerate(OPERATING_SETTINGS)}
    class_pairs = tuple(combinations(PADERBORN_LABELS, 2))
    for (setting, measurement), group in source.groupby(
        ["setting_code", "measurement_index"], sort=True, observed=True
    ):
        rows_by_class = {
            label: group.loc[group["truth"] == label]
            .sort_values("bearing_code")
            .index.to_numpy(dtype=int)
            for label in PADERBORN_LABELS
        }
        pair_count = min(len(rows) for rows in rows_by_class.values())
        if pair_count == 0:
            raise ValueError("source block loses a Paderborn pure class")
        block_offset = setting_order[str(setting)] * len(MEASUREMENT_INDICES) + int(measurement) - 1
        for pair_index, (left_label, right_label) in enumerate(class_pairs):
            left_rows = rows_by_class[left_label]
            right_rows = rows_by_class[right_label]
            for offset in range(pair_count):
                left = left_rows[(block_offset + offset) % len(left_rows)]
                right = right_rows[(block_offset + pair_index + offset) % len(right_rows)]
                pairs.append((int(left), int(right)))
    return np.asarray(pairs, dtype=np.int64)


def build_paderborn_source_pairs(
    source: pd.DataFrame,
) -> tuple[np.ndarray, np.ndarray]:
    """Build the frozen source-local nuisance and fault pair topology.

    This public wrapper is used by retrospective protocol contrasts whose source
    rows differ from the original crossed holdout.  It never reads target rows
    and preserves the exact pair construction used by the prospective D2 folds.
    """

    required = {"bearing_code", "setting_code", "measurement_index", "truth"}
    missing = required - set(source.columns)
    if missing:
        raise ValueError(f"Paderborn source pair frame is missing: {sorted(missing)}")
    local = source.reset_index(drop=True)
    nuisance_pairs = _nuisance_pairs(local)
    fault_pairs = _fault_pairs(local)
    for pairs, name in ((nuisance_pairs, "nuisance"), (fault_pairs, "fault")):
        if pairs.ndim != 2 or pairs.shape[1] != 2 or len(pairs) == 0:
            raise ValueError(f"Paderborn {name} pair topology is empty or malformed")
        if pairs.min() < 0 or pairs.max() >= len(local):
            raise ValueError(f"Paderborn {name} pairs leave source-local coordinates")
    return nuisance_pairs, fault_pairs


def build_paderborn_partitions(frame: pd.DataFrame) -> tuple[PaderbornPartition, ...]:
    """Build all 24 metadata-only prospective partitions without reading signal values."""

    frame = frame.reset_index(drop=True).copy()
    validate_paderborn_measurement_index(frame)
    partitions = []
    for spec in PADERBORN_OUTER_FOLDS:
        held_identity = frame["bearing_code"].isin(spec.held_bearing_codes).to_numpy()
        held_setting = frame["setting_code"].to_numpy(dtype=str) == spec.held_setting_code
        source_indices = np.flatnonzero(~held_identity & ~held_setting)
        target_indices = np.flatnonzero(held_identity & held_setting)
        quarantine_indices = np.flatnonzero(held_identity ^ held_setting)
        source = frame.iloc[source_indices].reset_index(drop=True)
        nuisance_pairs, fault_pairs = build_paderborn_source_pairs(source)
        partition = PaderbornPartition(
            fold_id=spec.fold_id,
            held_bearing_codes=spec.held_bearing_codes,
            held_setting_code=spec.held_setting_code,
            source_indices=source_indices,
            target_indices=target_indices,
            quarantine_indices=quarantine_indices,
            nuisance_pairs=nuisance_pairs,
            fault_pairs=fault_pairs,
        )
        partition.validate(frame)
        partitions.append(partition)
    return tuple(partitions)
