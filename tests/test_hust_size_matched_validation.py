from __future__ import annotations

import math

import pytest

from smartvalve.experiments.hust_validation_utils import assert_findings_equal


def test_findings_comparison_accepts_csv_rounding_and_two_nans() -> None:
    recomputed = {
        "access_effect_rule_passed": True,
        "median_gap": 0.22603046594999998,
        "rank_tau": math.nan,
        "positive_method_count": 9,
    }
    saved = {
        "access_effect_rule_passed": True,
        "median_gap": 0.2260304659498208,
        "rank_tau": math.nan,
        "positive_method_count": 9,
    }

    difference = assert_findings_equal(recomputed, saved)

    assert difference == pytest.approx(1.7919e-13, abs=1e-16)


@pytest.mark.parametrize(
    ("recomputed", "saved", "message"),
    [
        ({"gate": True}, {"gate": False}, "boolean finding changed"),
        ({"score": 0.2}, {"score": 0.21}, "numeric finding changed"),
        ({"tau": math.nan}, {"tau": 0.0}, "NaN finding changed"),
        ({"count": 9}, {"other": 9}, "finding keys do not reproduce"),
    ],
)
def test_findings_comparison_rejects_material_or_structural_changes(
    recomputed: dict[str, object],
    saved: dict[str, object],
    message: str,
) -> None:
    with pytest.raises(ValueError, match=message):
        assert_findings_equal(recomputed, saved)
