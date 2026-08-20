"""Deterministic source-environment splits for target-blind model selection."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from smartvalve.experiments.domain_data import SourceOnlyFold


@dataclass(frozen=True)
class InnerSplit:
    split_id: str
    training_indices: np.ndarray
    validation_indices: np.ndarray
    training_nuisance_pairs: np.ndarray
    training_fault_pairs: np.ndarray


def _training_pairs(pairs: np.ndarray, training_indices: np.ndarray) -> np.ndarray:
    training_set = set(int(value) for value in training_indices)
    mapping = {
        int(outer_source_index): inner_source_index
        for inner_source_index, outer_source_index in enumerate(training_indices)
    }
    selected = [
        (mapping[int(left)], mapping[int(right)])
        for left, right in pairs
        if int(left) in training_set and int(right) in training_set
    ]
    if not selected:
        raise ValueError("inner training partition removes every audited pair")
    return np.asarray(selected, dtype=np.int64)


def build_inner_splits(
    fold: SourceOnlyFold,
    *,
    maximum_partitions: int = 4,
) -> list[InnerSplit]:
    """Partition only outer-source environments; target rows are structurally unavailable."""

    fold.validate()
    if maximum_partitions < 2:
        raise ValueError("inner selection requires at least two partitions")
    source_environments = fold.source_environments
    unique_environments = np.unique(source_environments)
    partition_count = min(maximum_partitions, len(unique_environments))
    if partition_count < 2:
        raise ValueError("inner selection requires multiple source environments")
    if len(unique_environments) <= maximum_partitions:
        validation_environment_sets = [
            {environment} for environment in unique_environments
        ]
    else:
        validation_environment_sets = [
            set(unique_environments[index::partition_count])
            for index in range(partition_count)
        ]
    splits = []
    seen_validation = np.zeros(len(source_environments), dtype=int)
    for split_index, validation_environments in enumerate(
        validation_environment_sets
    ):
        validation_mask = np.isin(
            source_environments, list(validation_environments)
        )
        training_indices = np.flatnonzero(~validation_mask)
        validation_indices = np.flatnonzero(validation_mask)
        if len(training_indices) == 0 or len(validation_indices) == 0:
            raise ValueError("inner source partition is empty")
        if set(fold.source_labels[training_indices]) != set(
            range(len(fold.label_names))
        ):
            raise ValueError("inner training partition loses a fault class")
        if set(fold.source_labels[validation_indices]) != set(
            range(len(fold.label_names))
        ):
            raise ValueError("inner validation partition loses a fault class")
        seen_validation[validation_indices] += 1
        splits.append(
            InnerSplit(
                split_id=f"inner={split_index}",
                training_indices=training_indices,
                validation_indices=validation_indices,
                training_nuisance_pairs=_training_pairs(
                    fold.nuisance_pairs, training_indices
                ),
                training_fault_pairs=_training_pairs(
                    fold.fault_pairs, training_indices
                ),
            )
        )
    if not np.all(seen_validation == 1):
        raise ValueError("inner validation partitions do not cover source rows exactly once")
    return splits


def materialize_inner_fold(
    outer_fold: SourceOnlyFold,
    split: InnerSplit,
) -> SourceOnlyFold:
    """Expose an inner split through the same training contract as an outer fold."""

    outer_source = outer_fold.source_indices
    fold = SourceOnlyFold(
        dataset=outer_fold.dataset,
        fold_id=f"{outer_fold.fold_id}/{split.split_id}",
        held_factor="inner_source_environment_partition",
        held_level=int(split.split_id.split("=")[1]),
        features=outer_fold.source_features,
        labels=outer_fold.source_labels,
        label_names=outer_fold.label_names,
        feature_names=outer_fold.feature_names,
        environment_ids=outer_fold.source_environments,
        block_ids=outer_fold.block_ids[outer_source],
        source_indices=split.training_indices,
        target_indices=split.validation_indices,
        nuisance_pairs=split.training_nuisance_pairs,
        fault_pairs=split.training_fault_pairs,
    )
    fold.validate()
    return fold
