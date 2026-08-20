from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from smartvalve.experiments.selective_bootstrap import (
    AUDIT_SEEDS,
    BOOTSTRAP_REPLICATES,
    BOOTSTRAP_SEED,
    _interval,
    _run_bootstrap_core,
    dataset_metrics,
    holm_adjust,
    run_bootstrap,
    stratified_block_choices,
    tensorize_dataset,
    validate_execution_authorization,
)


def _fixture() -> tuple[pd.DataFrame, pd.DataFrame]:
    predictions = []
    decisions = []
    for method in ("erm", "pirl_ratio"):
        for seed in AUDIT_SEEDS:
            for fold_index, fold_id in enumerate(("held=0", "held=1")):
                for environment_index, environment in enumerate(("a", "b")):
                    for repetition in (1, 2):
                        block = f"{environment}|{repetition}"
                        for truth_index, truth in enumerate(("fault", "healthy")):
                            prediction = truth
                            if (
                                method == "erm"
                                and fold_index == 1
                                and environment_index == 1
                                and repetition == 2
                                and truth_index == 0
                            ):
                                prediction = "healthy"
                            row_index = (
                                fold_index * 100
                                + environment_index * 20
                                + repetition * 2
                                + truth_index
                            )
                            row = {
                                "dataset": "fixture",
                                "method": method,
                                "seed": seed,
                                "fold_id": fold_id,
                                "row_index": row_index,
                                "environment_id": environment,
                                "block_id": block,
                                "truth": truth,
                                "prediction": prediction,
                                "correct": prediction == truth,
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


def test_point_metrics_keep_model_seeds_paired_and_favor_perfect_pirl() -> None:
    predictions, decisions = _fixture()
    arrays = tensorize_dataset(predictions, decisions, "fixture")

    metrics = dataset_metrics(arrays, np.ones(len(arrays.blocks)))

    assert metrics.shape == (2, 2)
    assert metrics[1, 0] == pytest.approx(1.0)
    assert metrics[1, 1] == pytest.approx(0.0)
    assert metrics[1, 0] > metrics[0, 0]
    assert metrics[1, 1] < metrics[0, 1]


def test_zero_accepted_draw_receives_conservative_risk_one() -> None:
    predictions, decisions = _fixture()
    decisions["accepted"] = False
    arrays = tensorize_dataset(predictions, decisions, "fixture")

    metrics = dataset_metrics(arrays, np.ones(len(arrays.blocks)))

    assert metrics[:, 1] == pytest.approx(1.0)


def test_stratified_choices_never_cross_environment_block_sets() -> None:
    blocks = pd.DataFrame(
        {
            "environment_id": ["a", "a", "b", "b"],
            "block_id": ["a1", "a2", "b1", "b2"],
        }
    )

    choices, slots = stratified_block_choices(blocks, replicates=20, seed=17)

    assert choices.shape == (20, 4)
    for slot, environment in enumerate(slots["environment_id"]):
        selected_environments = blocks.loc[choices[:, slot], "environment_id"]
        assert selected_environments.eq(environment).all()


def test_interval_and_holm_are_finite_monotone_and_bounded() -> None:
    interval = _interval(0.2, np.asarray([-0.1, 0.1, 0.2, 0.3, 0.4]))
    adjusted = holm_adjust({"a": 0.01, "b": 0.04, "c": 0.03})

    assert interval["ci95_low"] == pytest.approx(-0.08)
    assert interval["ci95_high"] == pytest.approx(0.39)
    assert adjusted == pytest.approx({"a": 0.03, "b": 0.06, "c": 0.06})
    with pytest.raises(ValueError, match="Holm"):
        holm_adjust({"bad": 1.1})


def test_small_recorded_bootstrap_writes_complete_draw_and_metric_tensors(
    tmp_path,
) -> None:
    predictions, decisions = _fixture()
    prediction_path = tmp_path / "predictions.parquet"
    decision_path = tmp_path / "decisions.parquet"
    output = tmp_path / "output"
    predictions.to_parquet(prediction_path, index=False)
    decisions.to_parquet(decision_path, index=False)

    metrics = _run_bootstrap_core(
        prediction_path,
        decision_path,
        output,
        replicates=10,
        seed=101,
    )

    assert metrics["artifacts"]["bootstrap_metric_tensor"]["rows"] == 20
    assert metrics["artifacts"]["bootstrap_draw_plan"]["rows"] == 40
    comparison = metrics["paired_comparisons"]["fixture"]
    assert comparison["pirl_minus_erm_worst_fold_macro_f1"]["point_estimate"] > 0
    assert (
        comparison["erm_minus_pirl_selective_risk_at_source_50pct"][
            "point_estimate"
        ]
        > 0
    )


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _authorization_fixture(tmp_path: Path) -> dict[str, object]:
    tmp_path.mkdir(parents=True, exist_ok=True)
    predictions, decisions = _fixture()
    prediction_path = tmp_path / "predictions.parquet"
    decision_path = tmp_path / "decisions.parquet"
    predictions.to_parquet(prediction_path, index=False)
    decisions.to_parquet(decision_path, index=False)
    metrics = tmp_path / "metrics.json"
    manifest = tmp_path / "expected_manifest.json"
    metrics.write_text('{"status":"complete"}\n', encoding="utf-8")
    manifest.write_text('{"status":"frozen"}\n', encoding="utf-8")
    prediction_hash = _sha256(prediction_path)
    decision_hash = _sha256(decision_path)
    validation = tmp_path / "validation.json"
    validation.write_text(
        json.dumps(
            {
                "status": "passed_against_outcome_blind_selective_manifest",
                "artifact_hashes": {
                    "target_predictions": prediction_hash,
                    "selection_decisions": decision_hash,
                },
                "selective_metrics": {
                    "path": str(metrics.resolve()),
                    "sha256": _sha256(metrics),
                },
                "expected_manifest": {
                    "path": str(manifest.resolve()),
                    "sha256": _sha256(manifest),
                },
                "paderborn_archive_contents_opened": False,
            }
        ),
        encoding="utf-8",
    )
    validation_hash = _sha256(validation)
    protocol = tmp_path / "protocol.md"
    protocol.write_text(
        "\n".join(
            (
                "# bootstrap frozen v0.1",
                "Use 2,000 replicates and root seed 20260818.",
                prediction_hash,
                decision_hash,
                validation_hash,
                _sha256(metrics),
                _sha256(manifest),
            )
        ),
        encoding="utf-8",
    )
    return {
        "target_predictions_path": prediction_path,
        "target_predictions_sha256": prediction_hash,
        "selection_decisions_path": decision_path,
        "selection_decisions_sha256": decision_hash,
        "protocol_document": protocol,
        "protocol_sha256": _sha256(protocol),
        "selective_validation": validation,
        "selective_validation_sha256": validation_hash,
    }


def test_formal_bootstrap_requires_frozen_validated_inputs(tmp_path: Path) -> None:
    arguments = _authorization_fixture(tmp_path)

    authorization = validate_execution_authorization(**arguments)  # type: ignore[arg-type]

    assert authorization["target_predictions"] == arguments[
        "target_predictions_sha256"
    ]
    assert authorization["selective_validation"] == arguments[
        "selective_validation_sha256"
    ]


def test_formal_bootstrap_rejects_input_drift_and_nonfrozen_design(
    tmp_path: Path,
) -> None:
    arguments = _authorization_fixture(tmp_path)
    prediction_path = arguments["target_predictions_path"]
    assert isinstance(prediction_path, Path)
    prediction_path.write_bytes(b"changed")
    with pytest.raises(ValueError, match="target_predictions SHA-256 mismatch"):
        validate_execution_authorization(**arguments)  # type: ignore[arg-type]

    arguments = _authorization_fixture(tmp_path / "fresh")
    with pytest.raises(ValueError, match="exactly 2000 replicates"):
        run_bootstrap(
            output_directory=tmp_path / "output",
            replicates=BOOTSTRAP_REPLICATES - 1,
            seed=BOOTSTRAP_SEED,
            **arguments,  # type: ignore[arg-type]
        )
