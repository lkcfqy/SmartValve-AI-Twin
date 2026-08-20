from __future__ import annotations

import hashlib
import json
from dataclasses import asdict

import numpy as np
import pandas as pd
import pytest

pytest.importorskip("torch")

from smartvalve.experiments.cranfield_causal_audit import (  # noqa: E402
    AUDIT_SEEDS,
)
from smartvalve.experiments.dg_artifact_validation import (  # noqa: E402
    validate_artifacts,
    validate_candidate_values,
    validate_prediction_values,
)
from smartvalve.experiments.dg_expected_manifest import (  # noqa: E402
    KEY_SCHEMAS,
    MANIFEST_VERSION,
    canonical_key_record,
)
from smartvalve.experiments.dg_selection import (  # noqa: E402
    SELECTION_SEED,
    SELECTION_TOLERANCE,
    SELECTION_VERSION,
    candidate_grid,
    candidate_id,
    select_common_candidate,
    select_outer_candidate,
)
from smartvalve.experiments.dg_training import (  # noqa: E402
    BASELINE_METHODS,
)


def _candidate_frame() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "source_oof_macro_f1": [0.8, 0.7],
            "source_oof_worst_environment_macro_f1": [0.7, 0.6],
            "source_oof_multiclass_brier": [0.2, 0.3],
            "source_oof_nuisance_probability_response": [0.1, 0.2],
            "source_oof_fault_probability_response": [0.5, 0.4],
            "source_oof_probability_response_ratio": [0.2, 0.5],
        }
    )


def _prediction_frame() -> pd.DataFrame:
    probability_a = np.asarray([0.8, 0.25])
    probability_b = 1.0 - probability_a
    return pd.DataFrame(
        {
            "dataset": ["fixture", "fixture"],
            "method": ["erm", "erm"],
            "seed": [11, 11],
            "fold_id": ["held=0", "held=0"],
            "row_index": [0, 1],
            "truth": ["a", "b"],
            "prediction": ["a", "b"],
            "correct": [True, True],
            "confidence": [0.8, 0.75],
            "robust_class_support_distance": [0.1, 0.2],
            "risk_envelope_score_beta_0_25": [0.2, 0.3],
            "probability_a": probability_a,
            "probability_b": probability_b,
            "logit_a": np.log(probability_a),
            "logit_b": np.log(probability_b),
            "representation_00": [1.0, 0.0],
            "representation_01": [0.0, 1.0],
        }
    )


def _common_selection() -> dict:
    return {
        "erm": {
            "configuration": {
                "representation_dim": 2,
            }
        }
    }


def test_candidate_numeric_contract_checks_response_ratio() -> None:
    diagnostics = validate_candidate_values(_candidate_frame())

    assert diagnostics["maximum_probability_response_ratio_error"] == pytest.approx(
        0.0
    )
    broken = _candidate_frame()
    broken.loc[0, "source_oof_probability_response_ratio"] = 0.9
    with pytest.raises(ValueError, match="internally inconsistent"):
        validate_candidate_values(broken)


def test_prediction_numeric_contract_reconstructs_softmax_and_unit_norm() -> None:
    diagnostics = validate_prediction_values(
        _prediction_frame(), _common_selection()
    )

    assert diagnostics["maximum_probability_sum_error"] == pytest.approx(0.0)
    assert diagnostics["maximum_softmax_probability_error"] < 1e-12
    assert diagnostics["maximum_representation_norm_error"] == pytest.approx(0.0)


def test_prediction_numeric_contract_rejects_probability_tampering() -> None:
    broken = _prediction_frame()
    broken.loc[0, "probability_a"] = 0.7

    with pytest.raises(ValueError, match="not normalized"):
        validate_prediction_values(broken, _common_selection())


def _state_hash(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _history() -> list[dict[str, float | int]]:
    checkpoints = sorted({0, 299, *range(24, 300, 25)})
    return [
        {
            "epoch": checkpoint + 1,
            "objective": 0.5,
            "empirical_risk": 0.4,
            "method_penalty": 0.1,
            "gradient_norm_before_clip": 1.0,
        }
        for checkpoint in checkpoints
    ]


def _artifact_record(path, count_name: str, count: int) -> dict:
    return {
        "path": path.name,
        "bytes": path.stat().st_size,
        "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        count_name: count,
    }


def _write_synthetic_artifacts(tmp_path) -> tuple:
    output = tmp_path / "dg"
    output.mkdir()
    datasets = ("cranfield", "uci_hydraulic")
    grids = {method: candidate_grid(method) for method in BASELINE_METHODS}
    grid_records = {
        method: [
            {
                "candidate_id": candidate_id(config),
                "configuration": asdict(config),
            }
            for config in grid
        ]
        for method, grid in grids.items()
    }
    candidate_rows = []
    outer_selections = []
    for method in BASELINE_METHODS:
        for dataset in datasets:
            fold_rows = []
            for index, config in enumerate(grids[method]):
                row = {
                    "method": method,
                    "dataset": dataset,
                    "outer_fold_id": f"{dataset}=0",
                    "candidate_id": candidate_id(config),
                    "source_oof_macro_f1": 0.9 - index * 0.001,
                    "source_oof_worst_environment_macro_f1": 0.8 - index * 0.001,
                    "source_oof_multiclass_brier": 0.2 + index * 0.001,
                    "source_oof_nuisance_probability_response": 0.1,
                    "source_oof_fault_probability_response": 0.5,
                    "source_oof_probability_response_ratio": 0.2,
                }
                fold_rows.append(row)
                candidate_rows.append(row)
            outer_selections.append(select_outer_candidate(fold_rows))
    candidate_frame = pd.DataFrame(candidate_rows)

    common_selections = {}
    for method in BASELINE_METHODS:
        method_metrics = [row for row in candidate_rows if row["method"] == method]
        method_outer = [row for row in outer_selections if row["method"] == method]
        common = select_common_candidate(method_outer, method_metrics)
        selected_config = next(
            config
            for config in grids[method]
            if candidate_id(config) == common["selected_candidate_id"]
        )
        common_selections[method] = {
            **common,
            "configuration": asdict(selected_config),
        }

    tuning_traces = []
    configuration_lookup = {
        (method, row["candidate_id"]): row["configuration"]
        for method, rows in grid_records.items()
        for row in rows
    }
    for row in candidate_rows:
        configuration = configuration_lookup[(row["method"], row["candidate_id"])]
        for inner_index in range(4):
            key = (
                f"{row['method']}|{row['dataset']}|{row['outer_fold_id']}|"
                f"{row['candidate_id']}|{inner_index}"
            )
            tuning_traces.append(
                {
                    "dataset": row["dataset"],
                    "outer_fold_id": row["outer_fold_id"],
                    "inner_split_id": f"inner={inner_index}",
                    "candidate_id": row["candidate_id"],
                    "configuration": configuration,
                    "fit_seconds": 1.0,
                    "model_state_sha256": _state_hash(key),
                    "auxiliary_state_sha256": (
                        _state_hash(f"aux|{key}")
                        if row["method"] == "dann"
                        else None
                    ),
                    "history": _history(),
                }
            )

    final_traces = []
    prediction_rows = []
    for dataset in datasets:
        fold_id = f"{dataset}=0"
        for method in BASELINE_METHODS:
            selected = common_selections[method]
            for seed in AUDIT_SEEDS:
                configuration = {
                    **selected["configuration"],
                    "seed": int(seed),
                }
                key = f"{dataset}|{method}|{seed}|{fold_id}"
                final_traces.append(
                    {
                        "dataset": dataset,
                        "method": method,
                        "seed": int(seed),
                        "fold_id": fold_id,
                        "candidate_id": selected["selected_candidate_id"],
                        "configuration": configuration,
                        "model_state_sha256": _state_hash(key),
                        "auxiliary_state_sha256": (
                            _state_hash(f"aux|{key}") if method == "dann" else None
                        ),
                        "history": _history(),
                    }
                )
                dimension = int(configuration["representation_dim"])
                for row_index, truth in enumerate(("a", "b")):
                    probability_a = 0.8 if truth == "a" else 0.2
                    probability_b = 1.0 - probability_a
                    record = {
                        "dataset": dataset,
                        "method": method,
                        "seed": int(seed),
                        "fold_id": fold_id,
                        "row_index": row_index,
                        "environment_id": f"environment={row_index}",
                        "block_id": f"{dataset}|block={row_index}",
                        "truth": truth,
                        "prediction": truth,
                        "correct": True,
                        "confidence": 0.8,
                        "robust_class_support_distance": 0.1,
                        "risk_envelope_score_beta_0_25": 0.2,
                        "probability_a": probability_a,
                        "probability_b": probability_b,
                        "logit_a": float(np.log(probability_a)),
                        "logit_b": float(np.log(probability_b)),
                    }
                    record.update(
                        {
                            f"representation_{index:02d}": 1.0 if index == 0 else 0.0
                            for index in range(dimension)
                        }
                    )
                    prediction_rows.append(record)
    predictions = pd.DataFrame(prediction_rows)

    candidate_path = output / "candidate_metrics.parquet"
    tuning_path = output / "tuning_traces.json"
    final_path = output / "final_training_traces.json"
    predictions_path = output / "predictions.parquet"
    candidate_frame.to_parquet(candidate_path, index=False)
    tuning_path.write_text(json.dumps(tuning_traces), encoding="utf-8")
    final_path.write_text(json.dumps(final_traces), encoding="utf-8")
    predictions.to_parquet(predictions_path, index=False)

    key_sets = {
        "candidate_metrics": canonical_key_record(
            candidate_frame.loc[:, KEY_SCHEMAS["candidate_metrics"]].itertuples(
                index=False, name=None
            ),
            KEY_SCHEMAS["candidate_metrics"],
        ),
        "tuning_models": canonical_key_record(
            (
                (
                    trace["configuration"]["method"],
                    trace["dataset"],
                    trace["outer_fold_id"],
                    trace["candidate_id"],
                    trace["inner_split_id"],
                )
                for trace in tuning_traces
            ),
            KEY_SCHEMAS["tuning_models"],
        ),
        "outer_selections": canonical_key_record(
            (
                (row["method"], row["dataset"], row["outer_fold_id"])
                for row in outer_selections
            ),
            KEY_SCHEMAS["outer_selections"],
        ),
        "final_models": canonical_key_record(
            (
                (trace["dataset"], trace["method"], trace["seed"], trace["fold_id"])
                for trace in final_traces
            ),
            KEY_SCHEMAS["final_models"],
        ),
        "target_predictions": canonical_key_record(
            predictions.loc[:, KEY_SCHEMAS["target_predictions"]].itertuples(
                index=False, name=None
            ),
            KEY_SCHEMAS["target_predictions"],
        ),
        "target_provenance": canonical_key_record(
            predictions.loc[:, KEY_SCHEMAS["target_provenance"]]
            .drop_duplicates(["dataset", "fold_id", "row_index"])
            .itertuples(index=False, name=None),
            KEY_SCHEMAS["target_provenance"],
        ),
    }
    manifest = {
        "manifest_version": MANIFEST_VERSION,
        "input": {"uci_feature_matrix_sha256": "a" * 64},
        "configuration": {
            "methods": list(BASELINE_METHODS),
            "seeds": list(AUDIT_SEEDS),
            "candidate_count": 44,
            "candidate_grids": grid_records,
        },
        "expected_key_sets": key_sets,
    }
    manifest_path = tmp_path / "expected_manifest.json"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    manifest_hash = hashlib.sha256(manifest_path.read_bytes()).hexdigest()
    metrics = {
        "selection_version": SELECTION_VERSION,
        "input": {
            "uci_feature_matrix_sha256": "a" * 64,
            "paderborn_archive_contents_opened": False,
        },
        "configuration": {
            "methods": list(BASELINE_METHODS),
            "candidate_count": 44,
            "candidate_grids": grid_records,
            "selection_seed": SELECTION_SEED,
            "selection_tolerance": SELECTION_TOLERANCE,
            "final_seeds": list(AUDIT_SEEDS),
            "epochs": 300,
            "device": "cuda:0",
        },
        "outer_selections": outer_selections,
        "common_selections": common_selections,
        "artifacts": {
            "candidate_metrics": _artifact_record(
                candidate_path, "rows", len(candidate_frame)
            ),
            "tuning_traces": _artifact_record(
                tuning_path, "models", len(tuning_traces)
            ),
            "final_training_traces": _artifact_record(
                final_path, "models", len(final_traces)
            ),
            "predictions": _artifact_record(
                predictions_path, "rows", len(predictions)
            ),
        },
    }
    (output / "metrics.json").write_text(json.dumps(metrics), encoding="utf-8")
    return output, manifest_path, manifest_hash


def test_end_to_end_validator_recomputes_frozen_topology_and_selection(tmp_path) -> None:
    output, manifest_path, manifest_hash = _write_synthetic_artifacts(tmp_path)

    result = validate_artifacts(
        output,
        manifest_path,
        expected_manifest_sha256=manifest_hash,
    )

    assert result["passed"] is True
    assert result["counts"] == {
        "candidate_metrics": 88,
        "tuning_models": 352,
        "outer_selections": 16,
        "final_models": 80,
        "target_predictions": 160,
        "physical_target_rows": 4,
    }
    assert set(result["selected_candidates"]) == set(BASELINE_METHODS)
    assert result["numeric_diagnostics"]["maximum_probability_sum_error"] == 0
