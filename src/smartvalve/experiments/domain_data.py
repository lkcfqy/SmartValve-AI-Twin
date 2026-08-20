"""Unified source-only feature folds and audited intervention-pair topology."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from itertools import combinations
from pathlib import Path

import numpy as np
import pandas as pd

from smartvalve.data.uci_hydraulic import CONTEXT_COLUMNS, CONTEXT_LEVELS
from smartvalve.experiments.cranfield_benchmark import (
    LABELS as CRANFIELD_LABELS,
)
from smartvalve.experiments.cranfield_benchmark import (
    LOADS,
    MOTIONS,
    REPETITIONS,
)
from smartvalve.experiments.cranfield_causal_audit import (
    build_raw_matrix,
    raw_feature_columns,
)
from smartvalve.experiments.uci_hydraulic_access import (
    LABELS as UCI_LABELS,
)
from smartvalve.experiments.uci_hydraulic_access import (
    validate_feature_matrix,
)


@dataclass(frozen=True)
class SourceOnlyFold:
    """One outer fold with pair indices expressed in source-array coordinates."""

    dataset: str
    fold_id: str
    held_factor: str
    held_level: int
    features: np.ndarray
    labels: np.ndarray
    label_names: tuple[str, ...]
    feature_names: tuple[str, ...]
    environment_ids: np.ndarray
    block_ids: np.ndarray
    source_indices: np.ndarray
    target_indices: np.ndarray
    nuisance_pairs: np.ndarray
    fault_pairs: np.ndarray

    @property
    def source_features(self) -> np.ndarray:
        return self.features[self.source_indices]

    @property
    def source_labels(self) -> np.ndarray:
        return self.labels[self.source_indices]

    @property
    def source_environments(self) -> np.ndarray:
        return self.environment_ids[self.source_indices]

    @property
    def target_features(self) -> np.ndarray:
        return self.features[self.target_indices]

    @property
    def target_labels(self) -> np.ndarray:
        return self.labels[self.target_indices]

    @property
    def target_environments(self) -> np.ndarray:
        return self.environment_ids[self.target_indices]

    def validate(self) -> None:
        row_count = len(self.features)
        if self.features.ndim != 2 or self.features.shape[1] != len(self.feature_names):
            raise ValueError("features do not match their declared two-dimensional schema")
        if not np.isfinite(self.features).all():
            raise ValueError("features contain non-finite values")
        for values, name in (
            (self.labels, "labels"),
            (self.environment_ids, "environment IDs"),
            (self.block_ids, "block IDs"),
        ):
            if len(values) != row_count:
                raise ValueError(f"{name} do not align with feature rows")
        if not np.array_equal(
            np.sort(np.concatenate((self.source_indices, self.target_indices))),
            np.arange(row_count),
        ):
            raise ValueError("source and target indices must partition all rows exactly once")
        if np.intersect1d(self.source_indices, self.target_indices).size:
            raise ValueError("source and target rows overlap")
        if set(self.labels) != set(range(len(self.label_names))):
            raise ValueError("encoded labels do not match declared label names")
        for pairs, name in (
            (self.nuisance_pairs, "nuisance"),
            (self.fault_pairs, "fault"),
        ):
            if pairs.ndim != 2 or pairs.shape[1] != 2 or len(pairs) == 0:
                raise ValueError(f"{name} pairs must be a non-empty two-column array")
            if pairs.min() < 0 or pairs.max() >= len(self.source_indices):
                raise ValueError(f"{name} pairs point outside the source partition")
            if np.any(pairs[:, 0] == pairs[:, 1]):
                raise ValueError(f"{name} pairs contain self-pairs")
        source_labels = self.source_labels
        nuisance_labels_match = (
            source_labels[self.nuisance_pairs[:, 0]]
            == source_labels[self.nuisance_pairs[:, 1]]
        )
        if not np.all(nuisance_labels_match):
            raise ValueError("nuisance pairs change the fault label")
        fault_labels_differ = (
            source_labels[self.fault_pairs[:, 0]]
            != source_labels[self.fault_pairs[:, 1]]
        )
        if not np.all(fault_labels_differ):
            raise ValueError("fault pairs do not change the fault label")


def _encoded_labels(values: pd.Series, names: Sequence[str]) -> np.ndarray:
    mapping = {name: index for index, name in enumerate(names)}
    encoded = values.map(mapping)
    if encoded.isna().any():
        raise ValueError("data contain a label outside the frozen label set")
    return encoded.to_numpy(dtype=np.int64)


def _pair_indices(
    metadata: pd.DataFrame,
    source_indices: np.ndarray,
    *,
    group_columns: Sequence[str],
    distinct_column: str,
) -> np.ndarray:
    """Return every within-group pair whose declared intervention value differs."""

    local_by_global = {
        int(global_index): local_index
        for local_index, global_index in enumerate(source_indices)
    }
    source = metadata.iloc[source_indices].copy()
    source["_global_index"] = source_indices
    pairs: list[tuple[int, int]] = []
    for _, group in source.groupby(list(group_columns), sort=True, observed=True):
        records = group.loc[:, ["_global_index", distinct_column]].to_records(index=False)
        for left, right in combinations(records, 2):
            if left[1] == right[1]:
                continue
            pairs.append(
                (
                    local_by_global[int(left[0])],
                    local_by_global[int(right[0])],
                )
            )
    if not pairs:
        raise ValueError(
            f"no pairs vary {distinct_column} within groups {tuple(group_columns)}"
        )
    return np.asarray(pairs, dtype=np.int64)


def _string_ids(frame: pd.DataFrame, columns: Sequence[str]) -> np.ndarray:
    return frame.loc[:, list(columns)].astype(str).agg("|".join, axis=1).to_numpy(dtype=str)


def build_cranfield_folds(frame: pd.DataFrame | None = None) -> list[SourceOnlyFold]:
    """Build three global leave-one-load-out P0 development folds."""

    frame = build_raw_matrix() if frame is None else frame.copy()
    required = {"motion", "load_kg", "repetition", "truth"}
    missing = required - set(frame.columns)
    if missing:
        raise ValueError(f"Cranfield frame is missing columns: {sorted(missing)}")
    columns = raw_feature_columns(frame)
    if len(frame) != len(MOTIONS) * len(LOADS) * len(REPETITIONS) * len(CRANFIELD_LABELS):
        raise ValueError("Cranfield frame does not contain the frozen 180-trial factorial")
    features = frame.loc[:, columns].to_numpy(dtype=np.float32)
    labels = _encoded_labels(frame["truth"], CRANFIELD_LABELS)
    environments = _string_ids(frame, ("motion", "load_kg"))
    blocks = _string_ids(frame, ("motion", "load_kg", "repetition"))
    folds = []
    for held_load in LOADS:
        source_indices = np.flatnonzero(
            frame["load_kg"].to_numpy(dtype=int) != held_load
        )
        target_indices = np.flatnonzero(
            frame["load_kg"].to_numpy(dtype=int) == held_load
        )
        fold = SourceOnlyFold(
            dataset="cranfield",
            fold_id=f"load={held_load}",
            held_factor="load_kg",
            held_level=int(held_load),
            features=features,
            labels=labels,
            label_names=tuple(CRANFIELD_LABELS),
            feature_names=tuple(columns),
            environment_ids=environments,
            block_ids=blocks,
            source_indices=source_indices,
            target_indices=target_indices,
            nuisance_pairs=_pair_indices(
                frame,
                source_indices,
                group_columns=("motion", "truth", "repetition"),
                distinct_column="load_kg",
            ),
            fault_pairs=_pair_indices(
                frame,
                source_indices,
                group_columns=("motion", "load_kg", "repetition"),
                distinct_column="truth",
            ),
        )
        fold.validate()
        folds.append(fold)
    return folds


def build_uci_folds(
    feature_matrix: pd.DataFrame | Path,
) -> list[SourceOnlyFold]:
    """Build ten leave-one-context-level-out UCI hydraulic P0 folds."""

    frame = (
        pd.read_parquet(feature_matrix)
        if isinstance(feature_matrix, Path)
        else feature_matrix.copy()
    )
    columns = validate_feature_matrix(frame)
    features = frame.loc[:, columns].to_numpy(dtype=np.float32)
    labels = _encoded_labels(frame["truth"], UCI_LABELS)
    environments = _string_ids(frame, CONTEXT_COLUMNS)
    blocks = _string_ids(frame, (*CONTEXT_COLUMNS, "repetition"))
    folds = []
    for held_factor in CONTEXT_COLUMNS:
        other_context = tuple(
            column for column in CONTEXT_COLUMNS if column != held_factor
        )
        for held_level in CONTEXT_LEVELS[held_factor]:
            source_indices = np.flatnonzero(
                frame[held_factor].to_numpy(dtype=int) != held_level
            )
            target_indices = np.flatnonzero(
                frame[held_factor].to_numpy(dtype=int) == held_level
            )
            fold = SourceOnlyFold(
                dataset="uci_hydraulic",
                fold_id=f"{held_factor}={held_level}",
                held_factor=held_factor,
                held_level=int(held_level),
                features=features,
                labels=labels,
                label_names=tuple(UCI_LABELS),
                feature_names=tuple(columns),
                environment_ids=environments,
                block_ids=blocks,
                source_indices=source_indices,
                target_indices=target_indices,
                nuisance_pairs=_pair_indices(
                    frame,
                    source_indices,
                    group_columns=(*other_context, "truth", "repetition"),
                    distinct_column=held_factor,
                ),
                fault_pairs=_pair_indices(
                    frame,
                    source_indices,
                    group_columns=(*CONTEXT_COLUMNS, "repetition"),
                    distinct_column="truth",
                ),
            )
            fold.validate()
            folds.append(fold)
    return folds
