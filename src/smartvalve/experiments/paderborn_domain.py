"""Quarantine-safe model folds for the prospective Paderborn evaluation."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from smartvalve.data.paderborn_features import main_signal_feature_names
from smartvalve.experiments.domain_data import SourceOnlyFold
from smartvalve.experiments.paderborn_partitions import (
    PADERBORN_LABELS,
    build_paderborn_partitions,
    validate_paderborn_measurement_index,
)


@dataclass(frozen=True)
class PaderbornModelFold:
    """A source/target-only training view plus immutable full-index provenance."""

    fold: SourceOnlyFold
    held_bearing_codes: tuple[str, ...]
    held_setting_code: str
    source_global_indices: np.ndarray
    target_global_indices: np.ndarray
    quarantine_global_indices: np.ndarray

    def validate(self, full_frame: pd.DataFrame) -> None:
        self.fold.validate()
        global_partitions = (
            self.source_global_indices,
            self.target_global_indices,
            self.quarantine_global_indices,
        )
        flattened = np.concatenate(global_partitions)
        if (
            len(flattened) != len(full_frame)
            or len(np.unique(flattened)) != len(full_frame)
            or not np.array_equal(np.sort(flattened), np.arange(len(full_frame)))
        ):
            raise ValueError("Paderborn model-fold provenance does not partition the full frame")
        source_count = len(self.source_global_indices)
        target_count = len(self.target_global_indices)
        if not np.array_equal(self.fold.source_indices, np.arange(source_count)):
            raise ValueError("Paderborn model-fold source coordinates are not local")
        if not np.array_equal(
            self.fold.target_indices,
            np.arange(source_count, source_count + target_count),
        ):
            raise ValueError("Paderborn model-fold target coordinates are not local")
        target = full_frame.iloc[self.target_global_indices]
        if set(target["bearing_code"]) != set(self.held_bearing_codes):
            raise ValueError("Paderborn target provenance changes the held identities")
        if set(target["setting_code"]) != {self.held_setting_code}:
            raise ValueError("Paderborn target provenance changes the held setting")


def validate_paderborn_feature_frame(frame: pd.DataFrame) -> tuple[str, ...]:
    validate_paderborn_measurement_index(frame)
    feature_names = main_signal_feature_names()
    missing = set(feature_names) - set(frame.columns)
    if missing:
        raise ValueError(f"Paderborn feature frame is missing features: {sorted(missing)}")
    unexpected = [
        column
        for column in frame.columns
        if "__" in column and column not in feature_names
    ]
    if unexpected:
        raise ValueError(f"Paderborn feature frame has unexpected features: {unexpected}")
    values = frame.loc[:, feature_names].to_numpy(dtype=float)
    if not np.isfinite(values).all():
        raise ValueError("Paderborn feature frame contains non-finite values")
    return feature_names


def build_paderborn_model_folds(
    frame: pd.DataFrame,
) -> tuple[PaderbornModelFold, ...]:
    """Drop each fold's quarantine before exposing any arrays to a trainer."""

    frame = frame.reset_index(drop=True).copy()
    feature_names = validate_paderborn_feature_frame(frame)
    partitions = build_paderborn_partitions(frame)
    label_index = {label: index for index, label in enumerate(PADERBORN_LABELS)}
    model_folds = []
    for fold_number, partition in enumerate(partitions):
        retained_global = np.concatenate(
            (partition.source_indices, partition.target_indices)
        )
        retained = frame.iloc[retained_global].reset_index(drop=True)
        labels = retained["truth"].map(label_index)
        if labels.isna().any():
            raise ValueError("Paderborn model fold contains a non-primary label")
        source_count = len(partition.source_indices)
        target_count = len(partition.target_indices)
        source_only = SourceOnlyFold(
            dataset="paderborn",
            fold_id=partition.fold_id,
            held_factor="identity_fold_and_setting",
            held_level=fold_number,
            features=retained.loc[:, feature_names].to_numpy(dtype=np.float32),
            labels=labels.to_numpy(dtype=np.int64),
            label_names=tuple(PADERBORN_LABELS),
            feature_names=tuple(feature_names),
            environment_ids=retained["setting_code"].to_numpy(dtype=str),
            block_ids=(
                retained.loc[
                    :, ["bearing_code", "setting_code", "measurement_index"]
                ]
                .astype(str)
                .agg("|".join, axis=1)
                .to_numpy(dtype=str)
            ),
            source_indices=np.arange(source_count, dtype=np.int64),
            target_indices=np.arange(
                source_count, source_count + target_count, dtype=np.int64
            ),
            nuisance_pairs=partition.nuisance_pairs.copy(),
            fault_pairs=partition.fault_pairs.copy(),
        )
        model_fold = PaderbornModelFold(
            fold=source_only,
            held_bearing_codes=partition.held_bearing_codes,
            held_setting_code=partition.held_setting_code,
            source_global_indices=partition.source_indices.copy(),
            target_global_indices=partition.target_indices.copy(),
            quarantine_global_indices=partition.quarantine_indices.copy(),
        )
        model_fold.validate(frame)
        model_folds.append(model_fold)
    target_counts = np.zeros(len(frame), dtype=int)
    for model_fold in model_folds:
        target_counts[model_fold.target_global_indices] += 1
    if not np.all(target_counts == 1):
        raise ValueError("Paderborn model folds do not target every pure measurement once")
    return tuple(model_folds)
