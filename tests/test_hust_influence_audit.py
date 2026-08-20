from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import pytest

from smartvalve.experiments.hust_influence_audit import (
    METHODS,
    compute_influence_tables,
    run_hust_influence_audit,
    sha256_file,
)
from smartvalve.experiments.hust_influence_validation import (
    validate_hust_influence_audit,
)

CLASSES = ("healthy", "inner", "outer")


def _prediction_rows() -> tuple[pd.DataFrame, pd.DataFrame]:
    base: list[dict[str, object]] = []
    for method_index, method in enumerate(METHODS):
        for group in range(4, 9):
            for truth_index, truth in enumerate(CLASSES):
                bearing_code = f"{truth[0].upper()}{group}"
                for load_w in (0, 200, 400):
                    filename = f"{bearing_code}_{load_w}.mat"
                    error_groups = {4 + method_index % 5, 4 + (method_index + 1) % 5}
                    crossed_error = group in error_groups and load_w == 0
                    crossed_prediction = (
                        CLASSES[(truth_index + 1) % len(CLASSES)] if crossed_error else truth
                    )
                    for protocol in (
                        "recording_random",
                        "load_holdout",
                        "matched_specification_holdout",
                        "crossed_holdout",
                    ):
                        prediction = crossed_prediction if protocol == "crossed_holdout" else truth
                        probabilities = {name: 0.0 for name in CLASSES}
                        probabilities[prediction] = 1.0
                        base.append(
                            {
                                "protocol": protocol,
                                "method": method,
                                "filename": filename,
                                "bearing_code": bearing_code,
                                "specification_group": group,
                                "load_w": load_w,
                                "truth": truth,
                                "evaluation_cell": f"specification={group}|load_w={load_w}",
                                "probability_healthy": probabilities["healthy"],
                                "probability_outer": probabilities["outer"],
                                "probability_inner": probabilities["inner"],
                                "prediction": prediction,
                                "predictive_entropy": 0.0,
                                "window_disagreement_rate": 0.0,
                            }
                        )
    primary = pd.DataFrame(base)
    crossed = primary.loc[primary["protocol"] == "crossed_holdout"].copy()
    shared = crossed.copy()
    shared["protocol"] = "size_matched_shared_access"
    shared["prediction"] = shared["truth"]
    for truth in CLASSES:
        shared[f"probability_{truth}"] = (shared["truth"] == truth).astype(float)
    control = pd.concat([shared, crossed], ignore_index=True)
    return primary, control


def _write_json(path: Path, value: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, sort_keys=True) + "\n", encoding="utf-8")


def _inputs(root: Path) -> dict[str, object]:
    primary, control = _prediction_rows()
    primary_dir = root / "primary"
    control_dir = root / "control"
    primary_dir.mkdir(parents=True)
    control_dir.mkdir(parents=True)
    primary_predictions = primary_dir / "recording_predictions.parquet"
    control_predictions = control_dir / "combined_recording_predictions.parquet"
    primary.to_parquet(primary_predictions, index=False)
    control.to_parquet(control_predictions, index=False)
    primary_summary = primary_dir / "hust_d3_summary.json"
    control_summary = control_dir / "hust_d3_size_matched_summary.json"
    _write_json(
        primary_summary,
        {
            "status": "one_shot_protocol_prospective_signal_unopened_before_seal",
            "output_sha256": {
                "recording_predictions.parquet": sha256_file(primary_predictions)
            },
        },
    )
    _write_json(
        control_summary,
        {
            "status": "outcome_blind_equal_source_volume_control",
            "output_sha256": {
                "combined_recording_predictions.parquet": sha256_file(control_predictions)
            },
        },
    )
    primary_validation = root / "primary-validation.json"
    control_validation = root / "control-validation.json"
    _write_json(
        primary_validation,
        {
            "status": "passed_independent_no_refit_recomputation",
            "refit_performed": False,
            "input_sha256": {"outcome_summary": sha256_file(primary_summary)},
        },
    )
    _write_json(
        control_validation,
        {
            "status": "passed_independent_no_refit_recomputation",
            "refit_performed": False,
            "input_sha256": {"outcome_summary": sha256_file(control_summary)},
        },
    )
    plan = root / "plan.md"
    plan.write_text("# Frozen synthetic plan\n", encoding="utf-8")
    return {
        "primary": primary,
        "control": control,
        "primary_summary": primary_summary,
        "primary_summary_sha256": sha256_file(primary_summary),
        "primary_validation": primary_validation,
        "primary_validation_sha256": sha256_file(primary_validation),
        "control_summary": control_summary,
        "control_summary_sha256": sha256_file(control_summary),
        "control_validation": control_validation,
        "control_validation_sha256": sha256_file(control_validation),
        "analysis_plan": plan,
        "analysis_plan_sha256": sha256_file(plan),
    }


def _run_fixture(root: Path) -> tuple[dict[str, object], Path]:
    arguments = _inputs(root)
    output = root / "output"
    run_hust_influence_audit(
        **{key: value for key, value in arguments.items() if key not in {"primary", "control"}},
        output_directory=output,
    )
    return arguments, output


def _validation_arguments(arguments: dict[str, object], output: Path) -> dict[str, object]:
    selected = {
        key: value for key, value in arguments.items() if key not in {"primary", "control"}
    }
    summary = output / "hust_influence_audit_summary.json"
    selected.update(
        {
            "audit_summary": summary,
            "audit_summary_sha256": sha256_file(summary),
        }
    )
    return selected


def test_influence_tables_have_frozen_physical_unit_topology() -> None:
    primary, control = _prediction_rows()

    tables = compute_influence_tables(primary, control)

    assert len(tables["hust_influence_full_effects.csv"]) == 18
    assert len(tables["hust_influence_leave_one_bearing.csv"]) == 270
    assert len(tables["hust_influence_leave_one_group.csv"]) == 90
    summary = tables["hust_influence_summary.csv"]
    assert len(summary) == 18
    assert summary["bearing_loo_positive_count"].eq(15).all()
    assert summary["group_loo_positive_count"].eq(5).all()


def test_audit_writes_hash_locked_nonconfirmatory_outputs(tmp_path: Path) -> None:
    arguments = _inputs(tmp_path)
    output = tmp_path / "output"

    result = run_hust_influence_audit(
        **{key: value for key, value in arguments.items() if key not in {"primary", "control"}},
        output_directory=output,
    )

    assert result["status"] == "posthoc_no_refit_physical_unit_influence_audit"
    assert result["refit_performed"] is False
    assert result["p_values_computed"] is False
    assert result["primary_endpoints_replaced"] is False
    assert result["design"]["leave_one_bearing_rows"] == 270
    assert result["design"]["leave_one_group_rows"] == 90
    for filename, expected in result["output_sha256"].items():
        assert sha256_file(output / filename) == expected


def test_audit_rejects_control_crossed_prediction_drift(tmp_path: Path) -> None:
    arguments = _inputs(tmp_path)
    control = arguments["control"].copy()
    index = control.index[control["protocol"] == "crossed_holdout"][0]
    control.loc[index, "prediction"] = "outer"

    with pytest.raises(ValueError, match="control crossed predictions differ"):
        compute_influence_tables(arguments["primary"], control)


def test_audit_rejects_validation_that_does_not_lock_summary(tmp_path: Path) -> None:
    arguments = _inputs(tmp_path)
    validation = arguments["primary_validation"]
    _write_json(
        validation,
        {
            "status": "passed_independent_no_refit_recomputation",
            "refit_performed": False,
            "input_sha256": {"outcome_summary": "0" * 64},
        },
    )
    arguments["primary_validation_sha256"] = sha256_file(validation)

    with pytest.raises(ValueError, match="does not lock the supplied outcome summary"):
        run_hust_influence_audit(
            **{
                key: value
                for key, value in arguments.items()
                if key not in {"primary", "control"}
            },
            output_directory=tmp_path / "output",
        )


def test_independent_validator_recomputes_every_deletion_effect(tmp_path: Path) -> None:
    arguments, output = _run_fixture(tmp_path)

    result = validate_hust_influence_audit(
        **_validation_arguments(arguments, output),
    )

    assert (
        result["status"]
        == "passed_independent_no_refit_hust_physical_unit_influence_validation"
    )
    assert result["refit_performed"] is False
    assert result["confirmatory_analysis"] is False
    assert result["p_values_computed"] is False
    assert result["validated_counts"]["leave_one_bearing_rows"] == 270
    assert result["validated_counts"]["leave_one_group_rows"] == 90


def test_independent_validator_rejects_hash_consistent_numeric_tamper(tmp_path: Path) -> None:
    arguments, output = _run_fixture(tmp_path)
    table_path = output / "hust_influence_summary.csv"
    table = pd.read_csv(table_path)
    table.loc[0, "bearing_loo_minimum"] += 0.01
    table.to_csv(table_path, index=False, lineterminator="\n", float_format="%.12g")
    summary_path = output / "hust_influence_audit_summary.json"
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    summary["output_sha256"][table_path.name] = sha256_file(table_path)
    summary_path.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="numeric content changed"):
        validate_hust_influence_audit(
            **_validation_arguments(arguments, output),
        )
