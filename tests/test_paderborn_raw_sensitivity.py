from __future__ import annotations

import importlib.util
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
import torch

from smartvalve.experiments.paderborn_partitions import PADERBORN_LABELS
from smartvalve.experiments.paderborn_protocol_contrast import PROBABILITY_COLUMNS
from smartvalve.experiments.paderborn_raw_sensitivity import (
    RAW_MODELS,
    aggregate_raw_window_predictions,
    build_raw_sensitivity_model,
    deterministic_window_offsets,
    paired_raw_protocol_bootstrap,
    raw_sensitivity_gate,
    standardize_raw_windows,
)


def _training_script_module():
    path = Path(__file__).parents[1] / "scripts" / "paderborn_raw_architecture_sensitivity.py"
    spec = importlib.util.spec_from_file_location("raw_architecture_training_script", path)
    if spec is None or spec.loader is None:
        raise RuntimeError("could not load raw architecture training script")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_deterministic_raw_windows_cover_first_and_last_valid_sample() -> None:
    offsets = deterministic_window_offsets(256_000, window_size=8_192, window_count=4)

    assert offsets == (0, 82_603, 165_205, 247_808)
    assert offsets[-1] + 8_192 == 256_000
    with pytest.raises(ValueError, match="shorter"):
        deterministic_window_offsets(10, window_size=20)


def test_raw_models_emit_three_logits_and_window_normalization_is_finite() -> None:
    values = torch.linspace(-1.0, 1.0, 2 * 2_048).reshape(2, 1, 2_048)
    normalized = standardize_raw_windows(values)

    assert torch.isfinite(normalized).all()
    assert normalized.mean(dim=-1).abs().max().item() < 1e-6
    for model_name in RAW_MODELS:
        model = build_raw_sensitivity_model(model_name, n_fft=128)
        model.eval()
        with torch.no_grad():
            logits = model(normalized)
        assert logits.shape == (2, 3)


def test_raw_training_core_produces_ordered_probabilities_without_target_selection(
    tmp_path,
) -> None:
    module = _training_script_module()
    window_path = tmp_path / "windows.npy"
    generator = np.random.default_rng(11)
    np.save(window_path, generator.normal(size=(12, 8_192)).astype(np.float32))
    rows = pd.DataFrame({"window_row_index": np.arange(12)})
    train_rows = rows.iloc[:9].reset_index(drop=True)
    target_rows = rows.iloc[9:].reset_index(drop=True)
    train_dataset = module.RawWindowDataset(
        window_path,
        train_rows,
        np.asarray([0, 1, 2] * 3),
    )
    target_dataset = module.RawWindowDataset(
        window_path,
        target_rows,
        np.asarray([0, 1, 2]),
    )

    probabilities, window_rows, diagnostics, trace = module._fit_predict(
        model_name="cnn1d",
        seed=41,
        train_dataset=train_dataset,
        target_dataset=target_dataset,
        device=torch.device("cpu"),
        epochs=1,
        batch_size=3,
    )

    assert probabilities.shape == (3, 3)
    assert np.allclose(probabilities.sum(axis=1), 1.0)
    assert window_rows.tolist() == [9, 10, 11]
    assert len(diagnostics["model_state_sha256"]) == 64
    assert trace["epochs"][0]["epoch"] == 1


def _window_predictions() -> pd.DataFrame:
    rows = []
    for seed in (41, 42, 43):
        for window_index in range(4):
            rows.append(
                {
                    "protocol": "measurement_random",
                    "method": "cnn1d",
                    "seed": seed,
                    "row_index": 7,
                    "window_index": window_index,
                    "fold_id": "random=0",
                    "filename": "fixture.mat",
                    "bearing_code": "K001",
                    "setting_code": "N09_M07_F10",
                    "measurement_index": 1,
                    "truth": "healthy",
                    "identity_fold_id": "identity=0",
                    "evaluation_cell": "identity=0|setting=N09_M07_F10",
                    PROBABILITY_COLUMNS[0]: 0.6 + window_index / 100,
                    PROBABILITY_COLUMNS[1]: 0.3 - window_index / 100,
                    PROBABILITY_COLUMNS[2]: 0.1,
                }
            )
    return pd.DataFrame(rows)


def test_raw_window_aggregation_preserves_one_record_per_seed() -> None:
    result = aggregate_raw_window_predictions(_window_predictions())

    assert len(result) == 3
    assert result["prediction"].eq("healthy").all()
    assert result[PROBABILITY_COLUMNS[0]].eq(0.615).all()

    incomplete = _window_predictions().iloc[:-1]
    with pytest.raises(ValueError, match="every deterministic window"):
        aggregate_raw_window_predictions(incomplete)


def test_raw_physical_bootstrap_and_gate_use_all_three_architectures() -> None:
    records = []
    for method in RAW_MODELS:
        for protocol in ("measurement_random", "crossed_holdout"):
            for label_index, label in enumerate(PADERBORN_LABELS):
                for bearing_index in range(2):
                    truth = label
                    prediction = truth
                    if protocol == "crossed_holdout" and bearing_index == 0:
                        prediction = PADERBORN_LABELS[(label_index + 1) % 3]
                    records.append(
                        {
                            "protocol": protocol,
                            "method": method,
                            "bearing_code": f"{label}-{bearing_index}",
                            "truth": truth,
                            "prediction": prediction,
                        }
                    )
    summary, draws, plan = paired_raw_protocol_bootstrap(
        pd.DataFrame(records),
        draws=200,
        random_seed=123,
    )
    gate = raw_sensitivity_gate(summary)

    assert len(summary) == 3
    assert len(draws) == 600
    assert plan.shape == (200, 6)
    assert np.allclose(summary["effect_comparison_minus_reference"], 0.5)
    assert gate["positive_model_count"] == 3
    assert gate["median_random_minus_crossed_macro_f1"] == pytest.approx(0.5)
