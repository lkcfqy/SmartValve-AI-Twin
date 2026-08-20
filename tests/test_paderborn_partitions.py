from __future__ import annotations

from collections import Counter
from itertools import product

import numpy as np
import pandas as pd
import pytest

from smartvalve.data.paderborn import (
    BEARING_METADATA,
    OPERATING_SETTINGS,
    PRIMARY_BEARING_CODES,
)
from smartvalve.data.paderborn_features import (
    STRUCTURALLY_EXCLUDED_FILENAMES,
    parse_measurement_filename,
)
from smartvalve.experiments.domain_data import _pair_indices
from smartvalve.experiments.paderborn_partitions import (
    MEASUREMENT_INDICES,
    PADERBORN_LABELS,
    _fault_pairs,
    _nuisance_pairs,
    build_paderborn_partitions,
    validate_paderborn_measurement_index,
)


def _measurement_index() -> pd.DataFrame:
    labels = {bearing.code: bearing.primary_label for bearing in BEARING_METADATA}
    excluded = {
        (
            parse_measurement_filename(filename).bearing_code,
            parse_measurement_filename(filename).setting_code,
            parse_measurement_filename(filename).measurement_index,
        )
        for filename in STRUCTURALLY_EXCLUDED_FILENAMES
    }
    return pd.DataFrame(
        [
            {
                "bearing_code": bearing,
                "setting_code": setting.code,
                "measurement_index": measurement,
                "truth": labels[bearing],
            }
            for bearing, setting, measurement in product(
                PRIMARY_BEARING_CODES,
                OPERATING_SETTINGS,
                MEASUREMENT_INDICES,
            )
            if (bearing, setting.code, measurement) not in excluded
        ]
    )


def test_partitions_cover_each_target_once_and_quarantine_cross_arms() -> None:
    frame = _measurement_index()
    partitions = build_paderborn_partitions(frame)

    assert len(partitions) == 24
    target_counts = np.zeros(len(frame), dtype=int)
    for partition in partitions:
        target_counts[partition.target_indices] += 1
        held_count = len(partition.held_bearing_codes)
        expected_source = 1440 if held_count == 5 else 1500
        expected_target = 100 if held_count == 5 else 80
        expected_quarantine = 780 if held_count == 5 else 740
        excluded_key = parse_measurement_filename(STRUCTURALLY_EXCLUDED_FILENAMES[0])
        exclusion_is_held_identity = excluded_key.bearing_code in (partition.held_bearing_codes)
        exclusion_is_held_setting = excluded_key.setting_code == partition.held_setting_code
        if exclusion_is_held_identity and exclusion_is_held_setting:
            expected_target -= 1
        elif exclusion_is_held_identity ^ exclusion_is_held_setting:
            expected_quarantine -= 1
        else:
            expected_source -= 1
        assert len(partition.source_indices) == expected_source
        assert len(partition.target_indices) == expected_target
        assert len(partition.quarantine_indices) == expected_quarantine
        assert len(partition.nuisance_pairs) in (expected_source - 1, expected_source)
        assert len(partition.fault_pairs) == 900
    assert np.all(target_counts == 1)


def test_fault_pairs_are_source_local_and_equal_across_label_strata() -> None:
    frame = _measurement_index()
    partition = build_paderborn_partitions(frame)[0]
    source = frame.iloc[partition.source_indices].reset_index(drop=True)
    left = source.iloc[partition.fault_pairs[:, 0]].reset_index(drop=True)
    right = source.iloc[partition.fault_pairs[:, 1]].reset_index(drop=True)
    label_pairs = Counter(
        tuple(sorted(pair)) for pair in zip(left["truth"], right["truth"], strict=True)
    )

    assert set(label_pairs) == {
        ("healthy", "inner"),
        ("healthy", "outer"),
        ("inner", "outer"),
    }
    assert set(label_pairs.values()) == {300}
    assert np.array_equal(left["setting_code"], right["setting_code"])
    assert np.array_equal(left["measurement_index"], right["measurement_index"])
    assert all(label in PADERBORN_LABELS for label in left["truth"])


def test_pair_rules_reduce_to_development_topology_when_blocks_are_balanced() -> None:
    """The D2 rules must equal the D0/D1 all-pairs rule at one row per class."""

    bearings = tuple(zip(("K001", "KA01", "KI01"), PADERBORN_LABELS, strict=True))
    settings = tuple(setting.code for setting in OPERATING_SETTINGS[:3])
    balanced = pd.DataFrame(
        [
            {
                "bearing_code": bearing,
                "setting_code": setting,
                "measurement_index": measurement,
                "truth": label,
            }
            for setting, measurement, (bearing, label) in product(
                settings,
                (1, 2),
                bearings,
            )
        ]
    )
    source_indices = np.arange(len(balanced), dtype=np.int64)

    expected_fault = _pair_indices(
        balanced,
        source_indices,
        group_columns=("setting_code", "measurement_index"),
        distinct_column="truth",
    )
    expected_nuisance = _pair_indices(
        balanced,
        source_indices,
        group_columns=("bearing_code", "measurement_index", "truth"),
        distinct_column="setting_code",
    )

    def undirected_multiset(pairs: np.ndarray) -> list[tuple[int, int]]:
        return sorted(tuple(sorted(pair)) for pair in pairs.tolist())

    assert undirected_multiset(_fault_pairs(balanced)) == undirected_multiset(expected_fault)
    assert undirected_multiset(_nuisance_pairs(balanced)) == undirected_multiset(expected_nuisance)


def test_measurement_index_rejects_missing_or_changed_official_rows() -> None:
    frame = _measurement_index()

    with pytest.raises(ValueError, match="expected 2319"):
        validate_paderborn_measurement_index(frame.iloc[:-1])
    changed = frame.copy()
    changed.loc[0, "truth"] = "outer"
    with pytest.raises(ValueError, match="official"):
        validate_paderborn_measurement_index(changed)
