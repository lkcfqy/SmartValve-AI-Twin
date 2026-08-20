"""Window-nested, recording-scored protocols for sealed HUST D3."""

from __future__ import annotations

from dataclasses import dataclass
from itertools import combinations

import numpy as np
import pandas as pd
from sklearn.model_selection import StratifiedKFold

from smartvalve.data.hust import (
    HUST_LABELS,
    HUST_LOADS_W,
    HUST_SPECIFICATION_GROUPS,
    HUST_WINDOWS_PER_RECORDING,
    hust_feature_names,
)
from smartvalve.experiments.domain_data import SourceOnlyFold

SCHEMA_VERSION = "smartvalve-hust-d3-factorial-0.1.0"
HUST_RANDOM_SEED = 20260819
HUST_PROTOCOLS = (
    "recording_random",
    "load_holdout",
    "matched_specification_holdout",
    "crossed_holdout",
)


@dataclass(frozen=True)
class HustProtocolSplit:
    protocol: str
    fold_id: str
    source_indices: np.ndarray
    target_indices: np.ndarray
    quarantine_indices: np.ndarray

    def validate(self, frame: pd.DataFrame) -> None:
        arrays = (self.source_indices, self.target_indices, self.quarantine_indices)
        flattened = np.concatenate(arrays)
        if (
            self.protocol not in HUST_PROTOCOLS
            or len(flattened) != len(frame)
            or len(np.unique(flattened)) != len(frame)
            or not np.array_equal(np.sort(flattened), np.arange(len(frame)))
        ):
            raise ValueError("HUST protocol split does not partition all windows once")
        if len(self.source_indices) == 0 or len(self.target_indices) == 0:
            raise ValueError("HUST source and target must be non-empty")
        partitions = []
        for name, indices in zip(("source", "target", "quarantine"), arrays, strict=True):
            rows = frame.iloc[indices]
            counts = rows.groupby("filename", observed=True).size()
            if len(counts) and not counts.eq(HUST_WINDOWS_PER_RECORDING).all():
                raise ValueError(f"HUST {name} splits windows from one recording")
            partitions.append(set(rows["filename"].astype(str)))
        if any(partitions[left] & partitions[right] for left, right in combinations(range(3), 2)):
            raise ValueError("HUST recording appears in more than one access partition")
        if set(frame.iloc[self.source_indices]["truth"].astype(str)) != set(HUST_LABELS):
            raise ValueError("HUST source fold loses a primary class")


@dataclass(frozen=True)
class HustProtocolModelFold:
    protocol: str
    fold: SourceOnlyFold
    target_global_indices: np.ndarray
    quarantine_global_indices: np.ndarray


def validate_hust_feature_frame(frame: pd.DataFrame) -> tuple[str, ...]:
    required = {
        "filename",
        "bearing_code",
        "specification_group",
        "load_w",
        "truth",
        "window_index",
    }
    missing = required - set(frame)
    if missing:
        raise ValueError(f"HUST feature frame is missing columns: {sorted(missing)}")
    features = hust_feature_names()
    if set(features) - set(frame):
        raise ValueError("HUST feature frame is missing sealed vibration features")
    unexpected = [column for column in frame if "__" in column and column not in features]
    if unexpected:
        raise ValueError(f"HUST feature frame has unexpected features: {unexpected}")
    if len(frame) != 450 or frame["filename"].nunique() != 45:
        raise ValueError("HUST feature frame must contain 450 windows from 45 recordings")
    recording_counts = frame.groupby("filename", observed=True).agg(
        windows=("window_index", "nunique"),
        bearings=("bearing_code", "nunique"),
        groups=("specification_group", "nunique"),
        loads=("load_w", "nunique"),
        labels=("truth", "nunique"),
    )
    if (
        not recording_counts["windows"].eq(10).all()
        or not recording_counts.drop(columns="windows").eq(1).all().all()
    ):
        raise ValueError("HUST recording metadata or window nesting changed")
    window_sets = frame.groupby("filename", observed=True)["window_index"].apply(set)
    if not all(values == set(range(10)) for values in window_sets):
        raise ValueError("HUST recording window indices changed")
    records = frame.drop_duplicates("filename")
    if (
        records["bearing_code"].nunique() != 15
        or set(records["specification_group"].astype(int)) != set(HUST_SPECIFICATION_GROUPS)
        or set(records["load_w"].astype(int)) != set(HUST_LOADS_W)
        or set(records["truth"].astype(str)) != set(HUST_LABELS)
    ):
        raise ValueError("HUST physical factorial changed")
    values = frame.loc[:, features].to_numpy(dtype=float)
    if not np.isfinite(values).all():
        raise ValueError("HUST feature frame contains non-finite values")
    return features


def attach_hust_common_cells(frame: pd.DataFrame) -> pd.DataFrame:
    validate_hust_feature_frame(frame)
    result = frame.copy()
    result["evaluation_cell"] = (
        "specification="
        + result["specification_group"].astype(str)
        + "|load_w="
        + result["load_w"].astype(str)
    )
    cells = result.groupby("evaluation_cell", observed=True)
    if cells.ngroups != 15:
        raise ValueError("HUST evaluation topology must contain 15 physical cells")
    if not cells["truth"].nunique().eq(3).all() or not cells.size().eq(30).all():
        raise ValueError("a HUST physical cell loses a class or window")
    return result


def _indices_for_recordings(frame: pd.DataFrame, filenames: set[str]) -> np.ndarray:
    return np.flatnonzero(frame["filename"].astype(str).isin(filenames).to_numpy())


def _complement(row_count: int, target: np.ndarray) -> np.ndarray:
    mask = np.ones(row_count, dtype=bool)
    mask[target] = False
    return np.flatnonzero(mask)


def build_hust_protocol_splits(
    frame: pd.DataFrame,
    *,
    random_seed: int = HUST_RANDOM_SEED,
) -> dict[str, tuple[HustProtocolSplit, ...]]:
    indexed = frame.reset_index(drop=True)
    validate_hust_feature_frame(indexed)
    records = indexed.drop_duplicates("filename").reset_index(drop=True)
    result: dict[str, tuple[HustProtocolSplit, ...]] = {}

    random_splits = []
    splitter = StratifiedKFold(n_splits=5, shuffle=True, random_state=random_seed)
    for number, (_, target_records) in enumerate(
        splitter.split(np.zeros(len(records)), records["truth"].astype(str))
    ):
        filenames = set(records.iloc[target_records]["filename"].astype(str))
        target = _indices_for_recordings(indexed, filenames)
        random_splits.append(
            HustProtocolSplit(
                "recording_random",
                f"recording_random={number}",
                _complement(len(indexed), target),
                target,
                np.empty(0, dtype=np.int64),
            )
        )
    result["recording_random"] = tuple(random_splits)

    load_splits = []
    for load in HUST_LOADS_W:
        target = np.flatnonzero(indexed["load_w"].to_numpy(dtype=int) == load)
        load_splits.append(
            HustProtocolSplit(
                "load_holdout",
                f"load_w={load}",
                _complement(len(indexed), target),
                target,
                np.empty(0, dtype=np.int64),
            )
        )
    result["load_holdout"] = tuple(load_splits)

    specification_splits = []
    groups = indexed["specification_group"].to_numpy(dtype=int)
    for group in HUST_SPECIFICATION_GROUPS:
        target = np.flatnonzero(groups == group)
        specification_splits.append(
            HustProtocolSplit(
                "matched_specification_holdout",
                f"specification={group}",
                _complement(len(indexed), target),
                target,
                np.empty(0, dtype=np.int64),
            )
        )
    result["matched_specification_holdout"] = tuple(specification_splits)

    crossed_splits = []
    loads = indexed["load_w"].to_numpy(dtype=int)
    for group in HUST_SPECIFICATION_GROUPS:
        for load in HUST_LOADS_W:
            group_mask = groups == group
            load_mask = loads == load
            source = np.flatnonzero(~group_mask & ~load_mask)
            target = np.flatnonzero(group_mask & load_mask)
            quarantine = np.flatnonzero(group_mask ^ load_mask)
            crossed_splits.append(
                HustProtocolSplit(
                    "crossed_holdout",
                    f"specification={group}|load_w={load}",
                    source,
                    target,
                    quarantine,
                )
            )
    result["crossed_holdout"] = tuple(crossed_splits)

    if tuple(result) != HUST_PROTOCOLS:
        raise ValueError("HUST protocol order changed")
    expected_counts = {
        "recording_random": (360, 90, 0),
        "load_holdout": (300, 150, 0),
        "matched_specification_holdout": (360, 90, 0),
        "crossed_holdout": (240, 30, 180),
    }
    for protocol, splits in result.items():
        target_counts = np.zeros(len(indexed), dtype=int)
        for split in splits:
            split.validate(indexed)
            observed = tuple(
                len(values)
                for values in (
                    split.source_indices,
                    split.target_indices,
                    split.quarantine_indices,
                )
            )
            if observed != expected_counts[protocol]:
                raise ValueError(f"HUST {protocol} split counts changed: {observed}")
            target_counts[split.target_indices] += 1
        if not np.all(target_counts == 1):
            raise ValueError(f"HUST {protocol} does not target every window exactly once")
    return result


def build_hust_source_pairs(source: pd.DataFrame) -> tuple[np.ndarray, np.ndarray]:
    """Build aligned-window nuisance and fault controls using source rows only."""

    rows = source.reset_index(drop=True)
    nuisance = []
    for _, group in rows.groupby(["bearing_code", "window_index"], observed=True):
        for left, right in combinations(group.index.to_numpy(dtype=int), 2):
            if rows.loc[left, "load_w"] != rows.loc[right, "load_w"]:
                nuisance.append((left, right))
    fault = []
    for _, group in rows.groupby(["specification_group", "load_w", "window_index"], observed=True):
        for left, right in combinations(group.index.to_numpy(dtype=int), 2):
            if rows.loc[left, "truth"] != rows.loc[right, "truth"]:
                fault.append((left, right))
    nuisance_array = np.asarray(nuisance, dtype=np.int64).reshape(-1, 2)
    fault_array = np.asarray(fault, dtype=np.int64).reshape(-1, 2)
    return nuisance_array, fault_array


def build_hust_protocol_model_folds(
    frame: pd.DataFrame,
    *,
    random_seed: int = HUST_RANDOM_SEED,
) -> dict[str, tuple[HustProtocolModelFold, ...]]:
    indexed = frame.reset_index(drop=True)
    features = validate_hust_feature_frame(indexed)
    splits = build_hust_protocol_splits(indexed, random_seed=random_seed)
    label_index = {label: index for index, label in enumerate(HUST_LABELS)}
    result: dict[str, tuple[HustProtocolModelFold, ...]] = {}
    for protocol, protocol_splits in splits.items():
        model_folds = []
        for fold_number, split in enumerate(protocol_splits):
            retained_global = np.concatenate((split.source_indices, split.target_indices))
            retained = indexed.iloc[retained_global].reset_index(drop=True)
            source_count = len(split.source_indices)
            source = retained.iloc[:source_count].reset_index(drop=True)
            nuisance_pairs, fault_pairs = build_hust_source_pairs(source)
            labels = retained["truth"].map(label_index)
            if labels.isna().any():
                raise ValueError("HUST model fold contains an unknown label")
            fold = SourceOnlyFold(
                dataset="hust_bearing_v3",
                fold_id=split.fold_id,
                held_factor=protocol,
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
            model_folds.append(
                HustProtocolModelFold(
                    protocol=protocol,
                    fold=fold,
                    target_global_indices=split.target_indices.copy(),
                    quarantine_global_indices=split.quarantine_indices.copy(),
                )
            )
        result[protocol] = tuple(model_folds)
    return result
