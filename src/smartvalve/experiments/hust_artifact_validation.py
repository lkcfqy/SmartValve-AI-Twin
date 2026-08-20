"""Independent no-refit recomputation for sealed HUST D3 artifacts."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from smartvalve.experiments.cranfield_causal_audit import AUDIT_SEEDS
from smartvalve.experiments.dg_expected_manifest import canonical_key_record
from smartvalve.experiments.hust_evaluation import (
    aggregate_hust_record_predictions,
    bootstrap_hust_record_predictions,
    ensemble_hust_seed_windows,
    hust_confusion_counts,
    hust_protocol_effect_table,
    hust_rank_concordance,
    score_hust_record_predictions,
)
from smartvalve.experiments.hust_expected_manifest import (
    EXPECTED_COUNTS,
    KEY_SCHEMAS,
    file_sha256,
    verify_sha256,
)
from smartvalve.experiments.hust_expected_manifest import (
    SCHEMA_VERSION as EXPECTED_MANIFEST_SCHEMA,
)
from smartvalve.experiments.hust_protocol import HUST_PROTOCOLS, HUST_RANDOM_SEED
from smartvalve.experiments.paderborn_evaluation import METHODS
from smartvalve.experiments.paderborn_protocol_contrast import PROBABILITY_COLUMNS

VALIDATION_VERSION = "smartvalve-hust-d3-artifact-validation-0.1.0"


def _assert_frame_equal(
    observed: pd.DataFrame,
    expected: pd.DataFrame,
    *,
    name: str,
) -> float:
    if list(observed.columns) != list(expected.columns) or len(observed) != len(expected):
        raise ValueError(f"HUST {name} table shape/columns changed")
    maximum = 0.0
    for column in observed:
        if pd.api.types.is_numeric_dtype(observed[column]) and pd.api.types.is_numeric_dtype(
            expected[column]
        ):
            left = observed[column].to_numpy(dtype=float)
            right = expected[column].to_numpy(dtype=float)
            if not np.allclose(left, right, rtol=1e-10, atol=1e-12, equal_nan=True):
                raise ValueError(f"HUST {name} numeric column differs: {column}")
            finite = np.isfinite(left) & np.isfinite(right)
            if finite.any():
                maximum = max(maximum, float(np.max(np.abs(left[finite] - right[finite]))))
        elif (
            not observed[column]
            .fillna("<NA>")
            .astype(str)
            .equals(expected[column].fillna("<NA>").astype(str))
        ):
            raise ValueError(f"HUST {name} identity column differs: {column}")
    return maximum


def _rank_shifts(aggregate: pd.DataFrame) -> pd.DataFrame:
    records = []
    reference = aggregate.loc[aggregate["protocol"] == "crossed_holdout"].set_index("method")
    for protocol in HUST_PROTOCOLS[:-1]:
        comparison = aggregate.loc[aggregate["protocol"] == protocol].set_index("method")
        for method in METHODS:
            for endpoint in ("pooled_macro_f1", "mean_cell_macro_f1"):
                column = f"rank_{endpoint}"
                records.append(
                    {
                        "comparison_protocol": protocol,
                        "reference_protocol": "crossed_holdout",
                        "method": method,
                        "rank_endpoint": endpoint,
                        "comparison_rank": float(comparison.loc[method, column]),
                        "crossed_rank": float(reference.loc[method, column]),
                        "rank_change_comparison_minus_crossed": float(
                            comparison.loc[method, column] - reference.loc[method, column]
                        ),
                    }
                )
    return pd.DataFrame(records)


def _method_minus_erm(aggregate: pd.DataFrame) -> pd.DataFrame:
    records = []
    metrics = ("pooled_macro_f1", "mean_cell_macro_f1", "minimum_cell_macro_f1")
    for protocol, rows in aggregate.groupby("protocol", sort=True, observed=True):
        indexed = rows.set_index("method")
        for method in METHODS:
            for metric in metrics:
                records.append(
                    {
                        "protocol": protocol,
                        "method": method,
                        "reference_method": "erm",
                        "metric": metric,
                        "effect_method_minus_erm": float(
                            indexed.loc[method, metric] - indexed.loc["erm", metric]
                        ),
                    }
                )
    return pd.DataFrame(records)


def _record_diagnostics(records: pd.DataFrame) -> pd.DataFrame:
    return (
        records.groupby(["protocol", "method"], sort=True, observed=True)
        .agg(
            mean_predictive_entropy=("predictive_entropy", "mean"),
            median_predictive_entropy=("predictive_entropy", "median"),
            mean_window_disagreement_rate=("window_disagreement_rate", "mean"),
            maximum_window_disagreement_rate=("window_disagreement_rate", "max"),
        )
        .reset_index()
    )


def _key_record(frame: pd.DataFrame, name: str) -> dict[str, Any]:
    columns = KEY_SCHEMAS[name]
    if set(columns) - set(frame):
        raise ValueError(f"HUST {name} artifact is missing expected-key columns")
    return canonical_key_record(
        frame.loc[:, columns].itertuples(index=False, name=None),
        columns,
    )


def _validate_counts(values: dict[str, int]) -> None:
    for name, observed in values.items():
        expected = EXPECTED_COUNTS[name]
        if observed != expected:
            raise ValueError(f"HUST {name} count changed: {observed} != {expected}")


def validate_hust_d3_artifacts(
    *,
    result_directory: Path,
    expected_manifest_path: Path,
    expected_manifest_sha256: str,
    execution_seal_path: Path,
    execution_seal_sha256: str,
    output_path: Path,
) -> dict[str, Any]:
    verify_sha256(
        expected_manifest_path,
        expected_manifest_sha256,
        "HUST expected manifest",
    )
    verify_sha256(execution_seal_path, execution_seal_sha256, "HUST execution seal")
    manifest = json.loads(expected_manifest_path.read_text(encoding="utf-8"))
    seal = json.loads(execution_seal_path.read_text(encoding="utf-8"))
    summary_path = result_directory / "hust_d3_summary.json"
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    if (
        manifest.get("schema_version") != EXPECTED_MANIFEST_SCHEMA
        or manifest.get("expected_counts") != EXPECTED_COUNTS
        or seal.get("status") != "sealed_after_features_before_model_outcomes"
        or summary.get("status") != "one_shot_protocol_prospective_signal_unopened_before_seal"
    ):
        raise ValueError("HUST validation input identity changed")
    if (
        seal.get("expected_manifest", {}).get("sha256") != expected_manifest_sha256
        or summary.get("execution_seal", {}).get("expected_manifest", {}).get("sha256")
        != expected_manifest_sha256
    ):
        raise ValueError("HUST outcome bundle is linked to another manifest")

    predictions = pd.read_parquet(result_directory / "seed_window_predictions.parquet")
    fit_log = pd.read_csv(result_directory / "fit_log.csv")
    traces = json.loads((result_directory / "training_traces.json").read_text(encoding="utf-8"))
    probabilities = predictions.loc[:, PROBABILITY_COLUMNS].to_numpy(dtype=float)
    probability_error = float(np.max(np.abs(probabilities.sum(axis=1) - 1.0)))
    if not np.isfinite(probabilities).all() or probability_error > 2e-6:
        raise ValueError("HUST seed prediction probabilities are invalid")
    expected_keys = manifest["expected_key_sets"]
    actual_keys = {
        "training_fits": _key_record(fit_log, "training_fits"),
        "seed_window_predictions": _key_record(predictions, "seed_window_predictions"),
    }
    for name, actual in actual_keys.items():
        if actual != expected_keys[name]:
            raise ValueError(f"HUST {name} keys differ from the pre-access manifest")

    ensemble = ensemble_hust_seed_windows(
        predictions,
        expected_seeds=tuple(int(seed) for seed in AUDIT_SEEDS),
    )
    records = aggregate_hust_record_predictions(ensemble)
    aggregate, cells = score_hust_record_predictions(records)
    effects = hust_protocol_effect_table(aggregate)
    concordance = hust_rank_concordance(aggregate)
    bootstrap, bootstrap_draws, bootstrap_plan = bootstrap_hust_record_predictions(
        records,
        draws=int(manifest["configuration"]["bootstrap_draws"]),
        random_seed=HUST_RANDOM_SEED,
    )
    rank_shifts = _rank_shifts(aggregate)
    method_minus_erm = _method_minus_erm(aggregate)
    confusion = hust_confusion_counts(records)
    diagnostics = _record_diagnostics(records)
    actual_keys.update(
        {
            "ensemble_window_predictions": _key_record(ensemble, "ensemble_window_predictions"),
            "recording_predictions": _key_record(records, "recording_predictions"),
        }
    )
    for name in ("ensemble_window_predictions", "recording_predictions"):
        if actual_keys[name] != expected_keys[name]:
            raise ValueError(f"HUST {name} keys differ from the pre-access manifest")
    _validate_counts(
        {
            "fit_count": len(fit_log),
            "dann_auxiliary_states": int(
                fit_log.loc[fit_log["method"] == "dann", "auxiliary_state_sha256"].notna().sum()
            ),
            "seed_window_predictions": len(predictions),
            "ensemble_window_predictions": len(ensemble),
            "recording_predictions": len(records),
            "aggregate_metrics": len(aggregate),
            "cell_metrics": len(cells),
            "protocol_effects": len(effects),
            "ranking_concordance": len(concordance),
            "bootstrap_summary": len(bootstrap),
            "bootstrap_draws": len(bootstrap_draws),
            "bootstrap_draw_plan": len(bootstrap_plan),
            "rank_shifts": len(rank_shifts),
            "method_minus_erm": len(method_minus_erm),
            "confusion_counts": len(confusion),
            "recording_diagnostics": len(diagnostics),
        }
    )
    if len(traces) != EXPECTED_COUNTS["fit_count"]:
        raise ValueError("HUST training trace count changed")

    comparisons: dict[str, tuple[pd.DataFrame, str]] = {
        "ensemble_window_predictions": (
            ensemble,
            "ensemble_window_predictions.parquet",
        ),
        "recording_predictions": (records, "recording_predictions.parquet"),
        "aggregate_metrics": (aggregate, "aggregate_metrics.csv"),
        "cell_metrics": (cells, "cell_metrics.csv"),
        "protocol_effects": (effects, "protocol_effects.csv"),
        "ranking_concordance": (concordance, "ranking_concordance.csv"),
        "bootstrap_summary": (bootstrap, "bootstrap_summary.csv"),
        "bootstrap_draws": (bootstrap_draws, "bootstrap_draws.csv"),
        "bootstrap_draw_plan": (bootstrap_plan, "bootstrap_draw_plan.csv"),
        "rank_shifts": (rank_shifts, "rank_shifts.csv"),
        "method_minus_erm": (method_minus_erm, "method_minus_erm.csv"),
        "confusion_counts": (confusion, "confusion_counts.csv"),
        "recording_diagnostics": (diagnostics, "recording_diagnostics.csv"),
    }
    maximum_differences = {}
    for name, (recomputed, filename) in comparisons.items():
        path = result_directory / filename
        saved = pd.read_parquet(path) if path.suffix == ".parquet" else pd.read_csv(path)
        maximum_differences[name] = _assert_frame_equal(
            recomputed.reset_index(drop=True),
            saved.reset_index(drop=True),
            name=name,
        )
    for filename, expected_hash in summary.get("output_sha256", {}).items():
        verify_sha256(
            result_directory / filename,
            str(expected_hash),
            f"HUST result {filename}",
        )
    validation = {
        "schema_version": VALIDATION_VERSION,
        "status": "passed_independent_no_refit_recomputation",
        "input_sha256": {
            "expected_manifest": expected_manifest_sha256,
            "execution_seal": execution_seal_sha256,
            "outcome_summary": file_sha256(summary_path),
            "seed_window_predictions": file_sha256(
                result_directory / "seed_window_predictions.parquet"
            ),
        },
        "validated_counts": EXPECTED_COUNTS,
        "expected_key_sets": actual_keys,
        "maximum_absolute_numeric_difference": maximum_differences,
        "maximum_probability_sum_error": probability_error,
        "refit_performed": False,
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    if output_path.exists():
        raise ValueError("HUST validation output already exists")
    output_path.write_text(
        json.dumps(validation, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return validation
