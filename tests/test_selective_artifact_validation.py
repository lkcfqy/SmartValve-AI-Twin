from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import pandas as pd
import pytest

from smartvalve.experiments.dg_expected_manifest import canonical_key_record
from smartvalve.experiments.selective_artifact_validation import (
    _validate_probabilities,
    validate_expected_key_set,
    validate_selective_artifacts,
)
from smartvalve.experiments.selective_expected_manifest import (
    KEY_SCHEMAS,
    MANIFEST_VERSION,
)


def _frame() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "dataset": ["d0", "d0"],
            "method": ["erm", "erm"],
            "seed": [11, 11],
            "fold_id": ["f0", "f0"],
            "row_index": [1, 2],
            "probability_a": [0.8, 0.3],
            "probability_b": [0.2, 0.7],
        }
    )


def _expected(frame: pd.DataFrame, name: str) -> dict[str, Any]:
    columns = KEY_SCHEMAS[name]
    return canonical_key_record(
        frame[list(columns)].itertuples(index=False, name=None), columns
    )


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _json_write(path: Path, value: Any) -> None:
    path.write_text(json.dumps(value) + "\n", encoding="utf-8")


def test_selective_validator_accepts_exact_key_hash_and_probabilities() -> None:
    frame = _frame()

    observed = validate_expected_key_set(
        frame,
        key_set_name="target_predictions",
        expected=_expected(frame, "target_predictions"),
    )

    assert observed["count"] == 2
    assert _validate_probabilities([frame]) == pytest.approx(0.0)


def test_selective_validator_rejects_key_drift() -> None:
    frame = _frame()
    expected = _expected(frame, "target_predictions")
    frame.loc[0, "row_index"] = 9

    with pytest.raises(ValueError, match="key set differs"):
        validate_expected_key_set(
            frame,
            key_set_name="target_predictions",
            expected=expected,
        )


@pytest.mark.parametrize(
    ("column", "value", "message"),
    [
        ("probability_a", float("nan"), "lacks active probabilities"),
        ("probability_a", -0.1, "probabilities are invalid"),
        ("probability_a", 0.9, "not normalized"),
    ],
)
def test_selective_validator_rejects_probability_drift(
    column: str, value: float, message: str
) -> None:
    frame = _frame()
    frame.loc[0, column] = value

    with pytest.raises(ValueError, match=message):
        _validate_probabilities([frame])


def test_selective_validator_checks_a_complete_artifact_package(tmp_path: Path) -> None:
    output_directory = tmp_path / "selective"
    output_directory.mkdir()
    source = _frame()
    target = _frame()
    source_ensemble = source.assign(seed=-1)
    target_ensemble = target.assign(seed=-1)
    decisions = pd.DataFrame(
        {
            "dataset": ["d0"],
            "method": ["erm"],
            "seed": [11],
            "fold_id": ["f0"],
            "score_name": ["risk_envelope"],
            "nominal_source_coverage": [0.5],
            "row_index": [1],
            "score": [0.2],
            "threshold": [0.3],
            "accepted": [True],
        }
    )
    policies = [
        {
            "dataset": "d0",
            "method": "erm",
            "seed": 11,
            "fold_id": "f0",
            "score_name": "risk_envelope",
            "nominal_source_coverage": 0.5,
        }
    ]
    beta_selections = [
        {"dataset": "d0", "method": "erm", "seed": 11, "fold_id": "f0"}
    ]
    policy_metrics = [dict(policies[0])]
    ranking_metrics = [
        {
            "dataset": "d0",
            "method": "erm",
            "seed": 11,
            "fold_id": "f0",
            "score_name": "risk_envelope",
        }
    ]
    training_traces = [
        {
            "dataset": "d0",
            "method": "erm",
            "seed": 11,
            "fold_id": "f0",
            "inner_split_id": None,
        }
    ]
    crosschecks = [
        {"dataset": "d0", "method": "erm", "seed": 11, "fold_id": "f0"}
    ]
    values: dict[str, pd.DataFrame | list[dict[str, Any]]] = {
        "source_oof_predictions": source,
        "target_predictions": target,
        "source_oof_ensemble_predictions": source_ensemble,
        "target_ensemble_predictions": target_ensemble,
        "selection_decisions": decisions,
        "policies": policies,
        "beta_selections": beta_selections,
        "policy_metrics": policy_metrics,
        "ranking_metrics": ranking_metrics,
        "training_traces": training_traces,
        "reference_crosschecks": crosschecks,
    }
    artifact_paths = {}
    for name, value in values.items():
        suffix = ".parquet" if isinstance(value, pd.DataFrame) else ".json"
        path = output_directory / f"{name}{suffix}"
        if isinstance(value, pd.DataFrame):
            value.to_parquet(path, index=False)
        else:
            _json_write(path, value)
        artifact_paths[name] = path

    key_name_by_artifact = {
        "source_oof_predictions": "source_oof_predictions",
        "target_predictions": "target_predictions",
        "source_oof_ensemble_predictions": "source_oof_ensemble_predictions",
        "target_ensemble_predictions": "target_ensemble_predictions",
        "selection_decisions": "selection_decisions",
        "policies": "policies",
        "beta_selections": "beta_selections",
        "policy_metrics": "policy_metrics",
        "ranking_metrics": "ranking_metrics",
        "training_traces": "training_models",
        "reference_crosschecks": "reference_crosschecks",
    }
    expected_key_sets = {}
    for artifact_name, key_name in key_name_by_artifact.items():
        value = values[artifact_name]
        columns = KEY_SCHEMAS[key_name]
        if isinstance(value, pd.DataFrame):
            rows = value[list(columns)].itertuples(index=False, name=None)
        else:
            rows = (tuple(record[column] for column in columns) for record in value)
        expected_key_sets[key_name] = canonical_key_record(rows, columns)

    frozen_input = {
        "uci_feature_matrix_sha256": "a" * 64,
        "pirl_metrics_sha256": "b" * 64,
        "dg_metrics_sha256": "c" * 64,
        "paderborn_archive_contents_opened": False,
    }
    manifest_path = tmp_path / "expected_manifest.json"
    _json_write(
        manifest_path,
        {
            "manifest_version": MANIFEST_VERSION,
            "input": frozen_input,
            "expected_key_sets": expected_key_sets,
        },
    )
    count_field = {
        "source_oof_predictions": "rows",
        "target_predictions": "rows",
        "source_oof_ensemble_predictions": "rows",
        "target_ensemble_predictions": "rows",
        "selection_decisions": "rows",
        "policies": "policies",
        "beta_selections": "selections",
        "policy_metrics": "evaluations",
        "ranking_metrics": "evaluations",
        "training_traces": "models",
        "reference_crosschecks": "groups",
    }
    artifacts = {}
    for name, path in artifact_paths.items():
        artifacts[name] = {
            "path": path.name,
            count_field[name]: len(values[name]),
            "bytes": path.stat().st_size,
            "sha256": _sha256(path),
        }
    _json_write(
        output_directory / "metrics.json",
        {
            "input": frozen_input,
            "integrity": {
                "reference_crosschecks": 1,
                "maximum_absolute_probability_difference": 0.0,
                "all_final_model_state_hashes_exact": True,
                "prediction_topology": {
                    "groups": 1,
                    "source_oof_rows": 2,
                    "target_rows": 2,
                },
            },
            "artifacts": artifacts,
        },
    )

    validation = validate_selective_artifacts(
        selective_output_directory=output_directory,
        expected_manifest_path=manifest_path,
        expected_manifest_sha256=_sha256(manifest_path),
        output=tmp_path / "validation.json",
    )

    assert validation["status"] == "passed_against_outcome_blind_selective_manifest"
    assert validation["reference_crosschecks"] == 1
    assert validation["maximum_probability_sum_error"] == pytest.approx(0.0)
    assert validation["paderborn_archive_contents_opened"] is False
