from __future__ import annotations

from dataclasses import replace

import pytest

from smartvalve.data.paderborn import (
    BEARING_METADATA,
    COMPOUND_BEARING_CODES,
    OPERATING_SETTINGS,
    PRIMARY_BEARING_CODES,
)
from smartvalve.experiments.paderborn_splits import (
    PADERBORN_IDENTITY_FOLDS,
    PADERBORN_OUTER_FOLDS,
    validate_paderborn_identity_folds,
    validate_paderborn_outer_folds,
)


def test_identity_manifest_is_complete_disjoint_and_class_balanced() -> None:
    metadata = {bearing.code: bearing for bearing in BEARING_METADATA}
    flattened = [
        code for fold in PADERBORN_IDENTITY_FOLDS for code in fold.bearing_codes
    ]

    validate_paderborn_identity_folds(PADERBORN_IDENTITY_FOLDS)
    assert len(PADERBORN_IDENTITY_FOLDS) == 6
    assert set(flattened) == set(PRIMARY_BEARING_CODES)
    assert len(flattened) == len(set(flattened)) == 29
    assert set(flattened).isdisjoint(COMPOUND_BEARING_CODES)
    assert sorted(len(fold.bearing_codes) for fold in PADERBORN_IDENTITY_FOLDS) == [
        4,
        5,
        5,
        5,
        5,
        5,
    ]

    for fold in PADERBORN_IDENTITY_FOLDS:
        labels = [metadata[code].primary_label for code in fold.bearing_codes]
        assert labels.count("healthy") == 1
        assert labels.count("outer") == 2
        assert labels.count("inner") in {1, 2}
        origins = {
            metadata[code].damage_origin
            for code in fold.bearing_codes
            if metadata[code].primary_label != "healthy"
        }
        assert origins == {"artificial", "real"}


def test_outer_manifest_is_exact_six_by_four_cross_product() -> None:
    validate_paderborn_outer_folds(PADERBORN_OUTER_FOLDS)

    assert len(PADERBORN_OUTER_FOLDS) == 24
    expected_settings = {setting.code for setting in OPERATING_SETTINGS}
    for identity_fold in PADERBORN_IDENTITY_FOLDS:
        matching = [
            fold
            for fold in PADERBORN_OUTER_FOLDS
            if fold.identity_fold_id == identity_fold.fold_id
        ]
        assert {fold.held_setting_code for fold in matching} == expected_settings
        assert all(
            fold.held_bearing_codes == identity_fold.bearing_codes for fold in matching
        )


def test_identity_validator_rejects_leakage_or_omission() -> None:
    changed = list(PADERBORN_IDENTITY_FOLDS)
    changed[0] = replace(
        changed[0], bearing_codes=(*changed[0].bearing_codes[:-1], "K002")
    )

    with pytest.raises(ValueError, match="more than one fold"):
        validate_paderborn_identity_folds(tuple(changed))


def test_outer_validator_rejects_membership_drift() -> None:
    changed = list(PADERBORN_OUTER_FOLDS)
    changed[0] = replace(changed[0], held_bearing_codes=("K001",))

    with pytest.raises(ValueError, match="membership changed"):
        validate_paderborn_outer_folds(tuple(changed))
