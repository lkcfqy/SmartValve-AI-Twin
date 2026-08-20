from __future__ import annotations

from dataclasses import asdict

import pytest

from smartvalve.experiments.pirl_ratio_ablation import (
    ablation_configurations,
)
from smartvalve.experiments.pirl_sore import TrainingConfig


def _selected() -> TrainingConfig:
    return TrainingConfig(
        method="pirl_ratio",
        representation_dim=64,
        hidden_dim=128,
        intervention_weight=1.0,
        worst_environment_weight=0.0,
        fault_margin=0.5,
        ratio_term_weight=1.0,
        fault_margin_weight=1.0,
        epochs=300,
    )


def test_ablation_arms_change_only_the_declared_training_components() -> None:
    selected = _selected()
    arms = ablation_configurations(selected)

    assert arms["same_arch_erm"].method == "erm"
    assert arms["ratio_only"].ratio_term_weight == pytest.approx(1.0)
    assert arms["ratio_only"].fault_margin_weight == pytest.approx(0.0)
    assert arms["margin_only"].ratio_term_weight == pytest.approx(0.0)
    assert arms["margin_only"].fault_margin_weight == pytest.approx(1.0)

    ignored = {"method", "ratio_term_weight", "fault_margin_weight"}
    selected_record = asdict(selected)
    for arm in arms.values():
        arm_record = asdict(arm)
        assert {
            key: value for key, value in arm_record.items() if key not in ignored
        } == {
            key: value for key, value in selected_record.items() if key not in ignored
        }


def test_ablation_rejects_a_non_ratio_reference() -> None:
    with pytest.raises(ValueError, match="pirl_ratio"):
        ablation_configurations(TrainingConfig(method="erm"))
