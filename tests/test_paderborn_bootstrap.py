from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from smartvalve.data.paderborn import (
    BEARING_METADATA,
    OPERATING_SETTINGS,
    PRIMARY_BEARING_CODES,
)
from smartvalve.experiments.cranfield_causal_audit import AUDIT_SEEDS
from smartvalve.experiments.paderborn_bootstrap import (
    bearing_weights_to_block_weights,
    paderborn_metrics,
    run_paderborn_bootstrap,
    stratified_bearing_choices,
    tensorize_paderborn,
)
from smartvalve.experiments.paderborn_partitions import MEASUREMENT_INDICES
from smartvalve.experiments.paderborn_splits import PADERBORN_OUTER_FOLDS
from smartvalve.experiments.selective_bootstrap import _validate_inputs


@pytest.fixture(scope="module")
def paderborn_frames() -> tuple[pd.DataFrame, pd.DataFrame]:
    labels = {
        item.code: item.primary_label
        for item in BEARING_METADATA
        if item.code in PRIMARY_BEARING_CODES
    }
    fold_ids = {
        (bearing, fold.held_setting_code): fold.fold_id
        for fold in PADERBORN_OUTER_FOLDS
        for bearing in fold.held_bearing_codes
    }
    physical_rows = []
    for row_index, (bearing, setting, measurement) in enumerate(
        (bearing, setting.code, measurement)
        for bearing in PRIMARY_BEARING_CODES
        for setting in OPERATING_SETTINGS
        for measurement in MEASUREMENT_INDICES
    ):
        physical_rows.append(
            {
                "fold_id": fold_ids[(bearing, setting)],
                "row_index": row_index,
                "environment_id": setting,
                "block_id": f"{bearing}|{setting}|{measurement}",
                "bearing_code": bearing,
                "setting_code": setting,
                "measurement_index": measurement,
                "truth": labels[bearing],
            }
        )

    predictions = []
    decisions = []
    first_setting = OPERATING_SETTINGS[0].code
    for method in ("erm", "pirl_ratio"):
        for seed in AUDIT_SEEDS:
            for physical in physical_rows:
                prediction = physical["truth"]
                if (
                    method == "erm"
                    and physical["bearing_code"] == "K001"
                    and physical["setting_code"] == first_setting
                ):
                    prediction = "outer"
                row = {
                    "dataset": "paderborn",
                    "method": method,
                    "seed": seed,
                    **physical,
                    "prediction": prediction,
                    "correct": prediction == physical["truth"],
                }
                predictions.append(row)
                decisions.append(
                    {
                        **row,
                        "score_name": "risk_envelope",
                        "nominal_source_coverage": 0.5,
                        "accepted": True,
                    }
                )
    return pd.DataFrame(predictions), pd.DataFrame(decisions)


def test_tensor_and_point_metrics_use_minimum_setting_and_paired_seeds(
    paderborn_frames,
) -> None:
    predictions, decisions = _validate_inputs(*paderborn_frames)
    arrays = tensorize_paderborn(predictions, decisions)

    metrics = paderborn_metrics(
        arrays, np.ones(len(arrays.bearings), dtype=float)
    )

    assert metrics.shape == (2, 2)
    assert len(arrays.bearings) == 29
    assert len(arrays.base.blocks) == 2_320
    assert metrics[1] == pytest.approx((1.0, 0.0))
    assert metrics[1, 0] > metrics[0, 0]
    assert metrics[1, 1] < metrics[0, 1]


def test_bearing_draws_stay_in_class_and_carry_all_measurements(
    paderborn_frames,
) -> None:
    predictions, decisions = _validate_inputs(*paderborn_frames)
    arrays = tensorize_paderborn(predictions, decisions)
    choices, slots = stratified_bearing_choices(
        arrays.bearings, replicates=20, seed=17
    )

    assert choices.shape == (20, 29)
    for slot, truth in enumerate(slots["truth"]):
        selected_truth = arrays.bearings.loc[choices[:, slot], "truth"]
        assert selected_truth.eq(truth).all()
    identity_weights = np.bincount(
        choices[0], minlength=len(arrays.bearings)
    ).astype(float)
    block_weights = bearing_weights_to_block_weights(arrays, identity_weights)
    for bearing_index in range(len(arrays.bearings)):
        carried = block_weights[arrays.block_bearing == bearing_index]
        assert len(carried) == 80
        assert np.unique(carried) == pytest.approx([identity_weights[bearing_index]])


def test_contract_rejects_a_bearing_label_change(paderborn_frames) -> None:
    predictions, decisions = paderborn_frames
    predictions = predictions.copy()
    decisions = decisions.copy()
    changed = predictions["bearing_code"].eq("K001")
    predictions.loc[changed, "truth"] = "inner"
    predictions.loc[changed, "prediction"] = "inner"
    predictions.loc[changed, "correct"] = True
    decisions.loc[changed, "truth"] = "inner"
    decisions.loc[changed, "prediction"] = "inner"
    decisions.loc[changed, "correct"] = True
    filtered_predictions, filtered_decisions = _validate_inputs(
        predictions, decisions
    )

    with pytest.raises(ValueError, match="frozen metadata"):
        tensorize_paderborn(filtered_predictions, filtered_decisions)


def test_contract_rejects_fold_local_instead_of_global_row_indices(
    paderborn_frames,
) -> None:
    predictions, decisions = paderborn_frames
    predictions = predictions.copy()
    decisions = decisions.copy()
    changed_block = predictions["block_id"].eq(
        f"K002|{OPERATING_SETTINGS[0].code}|1"
    )
    predictions.loc[changed_block, "row_index"] = 0
    decisions.loc[changed_block, "row_index"] = 0
    filtered_predictions, filtered_decisions = _validate_inputs(
        predictions, decisions
    )

    with pytest.raises(ValueError, match="unique global"):
        tensorize_paderborn(filtered_predictions, filtered_decisions)


def test_small_paderborn_bootstrap_retains_identity_draw_and_metric_tensors(
    tmp_path,
    paderborn_frames,
) -> None:
    predictions, decisions = paderborn_frames
    prediction_path = tmp_path / "predictions.parquet"
    decision_path = tmp_path / "decisions.parquet"
    output = tmp_path / "output"
    predictions.to_parquet(prediction_path, index=False)
    decisions.to_parquet(decision_path, index=False)

    metrics = run_paderborn_bootstrap(
        prediction_path,
        decision_path,
        output,
        replicates=8,
        seed=101,
    )

    assert metrics["configuration"]["resampling_unit"] == "bearing_identity"
    assert metrics["configuration"]["stratification"] == "truth"
    assert metrics["artifacts"]["bootstrap_metric_tensor"]["rows"] == 16
    assert metrics["artifacts"]["bootstrap_draw_plan"]["rows"] == 8 * 29
    comparison = metrics["paired_comparisons"]
    assert comparison["pirl_minus_erm_minimum_setting_macro_f1"][
        "point_estimate"
    ] > 0
    assert comparison["erm_minus_pirl_selective_risk_at_source_50pct"][
        "point_estimate"
    ] > 0
