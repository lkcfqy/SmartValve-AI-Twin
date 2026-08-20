from __future__ import annotations

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
    main_signal_feature_names,
    parse_measurement_filename,
)
from smartvalve.experiments.paderborn_domain import (
    build_paderborn_model_folds,
    validate_paderborn_feature_frame,
)
from smartvalve.experiments.paderborn_partitions import MEASUREMENT_INDICES


def _feature_frame() -> pd.DataFrame:
    labels = {bearing.code: bearing.primary_label for bearing in BEARING_METADATA}
    excluded = {
        (
            parse_measurement_filename(filename).bearing_code,
            parse_measurement_filename(filename).setting_code,
            parse_measurement_filename(filename).measurement_index,
        )
        for filename in STRUCTURALLY_EXCLUDED_FILENAMES
    }
    frame = pd.DataFrame(
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
    row = np.arange(len(frame), dtype=float)
    for index, feature in enumerate(main_signal_feature_names(), start=1):
        frame[feature] = np.sin(row / index)
    return frame


def test_model_folds_drop_quarantine_and_preserve_global_provenance() -> None:
    frame = _feature_frame()
    folds = build_paderborn_model_folds(frame)

    assert len(folds) == 24
    target_counts = np.zeros(len(frame), dtype=int)
    for model_fold in folds:
        model_fold.validate(frame)
        target_counts[model_fold.target_global_indices] += 1
        assert len(model_fold.fold.features) == (
            len(model_fold.source_global_indices) + len(model_fold.target_global_indices)
        )
        assert len(model_fold.fold.features) in (1539, 1540, 1579, 1580)
        assert len(np.unique(model_fold.fold.source_environments)) == 3
        assert set(model_fold.fold.target_environments) == {model_fold.held_setting_code}
        assert not np.intersect1d(
            model_fold.source_global_indices,
            model_fold.quarantine_global_indices,
        ).size
    assert np.all(target_counts == 1)


def test_quarantine_feature_mutation_cannot_change_a_fold_training_view() -> None:
    frame = _feature_frame()
    original = build_paderborn_model_folds(frame)[0]
    changed = frame.copy()
    changed.loc[
        original.quarantine_global_indices,
        list(main_signal_feature_names()),
    ] += 1_000_000.0

    rebuilt = build_paderborn_model_folds(changed)[0]

    assert rebuilt.fold.features == pytest.approx(original.fold.features)


def test_feature_frame_rejects_missing_unexpected_or_nonfinite_features() -> None:
    frame = _feature_frame()
    feature = main_signal_feature_names()[0]
    with pytest.raises(ValueError, match="missing"):
        validate_paderborn_feature_frame(frame.drop(columns=feature))
    with pytest.raises(ValueError, match="unexpected"):
        validate_paderborn_feature_frame(frame.assign(extra__feature=0.0))
    changed = frame.copy()
    changed.loc[0, feature] = np.nan
    with pytest.raises(ValueError, match="non-finite"):
        validate_paderborn_feature_frame(changed)
