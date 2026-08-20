from __future__ import annotations

import pandas as pd
import pytest

import smartvalve.experiments.paderborn_neural_sensor_attribution as attribution
from smartvalve.data.paderborn_features import MAIN_SIGNAL_FEATURE_FAMILIES
from smartvalve.experiments.paderborn_evaluation import METHODS
from smartvalve.experiments.paderborn_partitions import PADERBORN_LABELS
from smartvalve.experiments.paderborn_protocol_contrast import PROTOCOLS


def _small_predictions() -> pd.DataFrame:
    records = []
    for family in MAIN_SIGNAL_FEATURE_FAMILIES:
        for protocol in PROTOCOLS:
            for method in METHODS:
                for label in PADERBORN_LABELS:
                    records.append(
                        {
                            "feature_family": family,
                            "protocol": protocol,
                            "method": method,
                            "row_index": len(records),
                            "bearing_code": f"bearing-{label}",
                            "truth": label,
                            "prediction": label,
                        }
                    )
    return pd.DataFrame(records)


def test_neural_sensor_score_bootstrap_uses_shared_physical_draws(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    predictions = _small_predictions()
    monkeypatch.setattr(attribution, "validate_neural_sensor_ensemble", lambda _: None)
    draw_plan = pd.DataFrame(
        {
            "bearing-healthy": [1, 2, 1],
            "bearing-outer": [1, 1, 0],
            "bearing-inner": [1, 0, 2],
        }
    )

    summary, draws = attribution.bootstrap_neural_sensor_score_differences(
        predictions,
        draw_plan,
    )

    assert len(summary) == 3 * 4 * 9
    assert len(draws) == len(summary) * len(draw_plan)
    assert summary["effect_left_minus_right"].eq(0.0).all()
    assert draws["effect_left_minus_right"].eq(0.0).all()


def test_neural_sensor_rank_concordance_covers_all_family_pairs() -> None:
    records = []
    for family in MAIN_SIGNAL_FEATURE_FAMILIES:
        for protocol in PROTOCOLS:
            for rank, method in enumerate(METHODS):
                records.append(
                    {
                        "feature_family": family,
                        "protocol": protocol,
                        "method": method,
                        "pooled_macro_f1": 1.0 - rank / 20,
                        "mean_cell_macro_f1": 1.0 - rank / 25,
                    }
                )

    result = attribution.neural_sensor_rank_concordance(pd.DataFrame(records))

    assert len(result) == 4 * 2 * 3
    assert result["kendall_tau"].eq(1.0).all()


def test_neural_sensor_ensemble_rejects_incomplete_axes() -> None:
    with pytest.raises(ValueError, match="missing columns"):
        attribution.validate_neural_sensor_ensemble(pd.DataFrame({"method": ["erm"]}))
