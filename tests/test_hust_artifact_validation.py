from __future__ import annotations

import pandas as pd
import pytest

from smartvalve.experiments.hust_artifact_validation import (
    _assert_frame_equal,
    _key_record,
    _validate_counts,
)
from smartvalve.experiments.hust_expected_manifest import EXPECTED_COUNTS


def test_hust_validation_helpers_check_keys_counts_and_numeric_drift() -> None:
    fits = pd.DataFrame(
        {
            "protocol": ["recording_random"],
            "method": ["erm"],
            "seed": [11],
            "fold_id": ["recording_random=0"],
        }
    )
    key = _key_record(fits, "training_fits")

    assert key["count"] == 1
    assert _assert_frame_equal(
        pd.DataFrame({"key": ["a"], "value": [1.0]}),
        pd.DataFrame({"key": ["a"], "value": [1.0 + 1e-13]}),
        name="fixture",
    ) == pytest.approx(1e-13)
    _validate_counts({"fit_count": EXPECTED_COUNTS["fit_count"]})
    with pytest.raises(ValueError, match="fit_count"):
        _validate_counts({"fit_count": 1})
    with pytest.raises(ValueError, match="numeric column"):
        _assert_frame_equal(
            pd.DataFrame({"value": [1.0]}),
            pd.DataFrame({"value": [2.0]}),
            name="fixture",
        )
