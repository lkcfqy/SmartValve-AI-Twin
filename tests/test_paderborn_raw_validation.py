from __future__ import annotations

import inspect
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from smartvalve.experiments import paderborn_raw_validation as validation


def _seed_predictions() -> pd.DataFrame:
    rows = []
    row_index = 0
    next_label = {
        "healthy": "outer",
        "outer": "inner",
        "inner": "healthy",
    }
    for cell_index in range(24):
        for truth in validation.LABELS:
            for protocol in validation.PROTOCOLS:
                prediction = truth if protocol == "measurement_random" else next_label[truth]
                probabilities = {
                    column: float(label == prediction)
                    for label, column in zip(
                        validation.LABELS, validation.PROBABILITY_COLUMNS, strict=True
                    )
                }
                for method in validation.MODELS:
                    for seed in validation.SEEDS:
                        rows.append(
                            {
                                "protocol": protocol,
                                "method": method,
                                "seed": seed,
                                "fold_id": f"cell={cell_index}",
                                "row_index": row_index,
                                "filename": f"record-{row_index}.mat",
                                "bearing_code": f"bearing-{cell_index}-{truth}",
                                "setting_code": f"setting-{cell_index % 4}",
                                "measurement_index": 0,
                                "truth": truth,
                                "identity_fold_id": f"identity={cell_index // 4}",
                                "evaluation_cell": f"cell={cell_index:02d}",
                                **probabilities,
                            }
                        )
            row_index += 1
    return pd.DataFrame(rows)


def test_independent_calculation_module_has_no_producer_calculation_import() -> None:
    source = inspect.getsource(validation)
    assert "paderborn_raw_sensitivity" not in source
    assert "paderborn_protocol_contrast" not in source

    root = Path(__file__).resolve().parents[1]
    cli = (root / "scripts/validate_paderborn_raw_architecture_sensitivity.py").read_text(
        encoding="utf-8"
    )
    assert "paderborn_raw_sensitivity import" not in cli
    assert "paderborn_protocol_contrast import" not in cli
    assert "aggregate_windows_independently" in cli
    watcher = (
        root / "artifacts/research/launch/run_EXP457_after_EXP456R1.sh"
    ).read_text(encoding="utf-8")
    assert '--features-sha256 "${FEATURES_SHA256}"' in watcher
    assert '--raw-window-summary-sha256 "${RAW_WINDOW_SUMMARY_SHA256}"' in watcher


def test_independent_window_aggregation_rejects_missing_or_duplicate_windows() -> None:
    rows = []
    for window_index in range(validation.WINDOWS_PER_RECORD):
        rows.append(
            {
                "protocol": "measurement_random",
                "method": "cnn1d",
                "seed": 41,
                "fold_id": "random=0",
                "row_index": 0,
                "window_index": window_index,
                "filename": "record.mat",
                "bearing_code": "bearing-0",
                "setting_code": "setting-0",
                "measurement_index": 0,
                "truth": "healthy",
                "identity_fold_id": "identity=0",
                "evaluation_cell": "cell=00",
                "probability_healthy": 0.75,
                "probability_outer": 0.20,
                "probability_inner": 0.05,
            }
        )
    frame = pd.DataFrame(rows)
    aggregated = validation.aggregate_windows_independently(frame)
    assert len(aggregated) == 1
    assert aggregated.loc[0, "prediction"] == "healthy"
    assert aggregated.loc[0, "probability_healthy"] == pytest.approx(0.75)

    with pytest.raises(ValueError, match="every frozen window"):
        validation.aggregate_windows_independently(frame.iloc[:-1])
    duplicate = frame.copy()
    duplicate.loc[3, "window_index"] = 2
    with pytest.raises(ValueError, match="duplicate window"):
        validation.aggregate_windows_independently(duplicate)


def test_independent_score_bootstrap_and_gate_have_hand_checkable_effect() -> None:
    seed_predictions = _seed_predictions()
    ensemble = validation.ensemble_seeds_independently(seed_predictions)
    assert len(ensemble) == 2 * 3 * 24 * 3
    probabilities = ensemble.loc[:, validation.PROBABILITY_COLUMNS].to_numpy(dtype=float)
    assert np.allclose(probabilities.sum(axis=1), 1.0)

    aggregate, cells = validation.score_predictions_independently(ensemble)
    assert len(aggregate) == 6
    assert len(cells) == 144
    random_scores = aggregate.loc[
        aggregate["protocol"] == "measurement_random", "pooled_macro_f1"
    ]
    crossed_scores = aggregate.loc[
        aggregate["protocol"] == "crossed_holdout", "pooled_macro_f1"
    ]
    assert np.array_equal(random_scores.to_numpy(dtype=float), np.ones(3))
    assert np.array_equal(crossed_scores.to_numpy(dtype=float), np.zeros(3))

    summary, draws, plan = validation.bootstrap_protocol_effects_independently(
        ensemble, draws=25
    )
    assert summary["effect_comparison_minus_reference"].tolist() == [1.0, 1.0, 1.0]
    assert summary["bootstrap_lower_95"].tolist() == [1.0, 1.0, 1.0]
    assert len(draws) == 75
    assert plan.shape == (25, 72)
    assert plan.sum(axis=1).eq(72).all()
    assert validation.evaluate_gate_independently(summary) == {
        "positive_model_count": 3,
        "positive_interval_count": 3,
        "median_random_minus_crossed_macro_f1": 1.0,
        "representation_sensitivity_rule_passed": True,
    }
