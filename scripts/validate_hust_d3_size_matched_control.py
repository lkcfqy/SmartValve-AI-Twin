#!/usr/bin/env python3
"""Independently recompute the HUST equal-volume control without fitting models."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import pandas as pd

from smartvalve.experiments.cranfield_causal_audit import AUDIT_SEEDS
from smartvalve.experiments.hust_artifact_validation import (
    _assert_frame_equal,
    _record_diagnostics,
)
from smartvalve.experiments.hust_evaluation import (
    ensemble_hust_seed_windows,
    hust_confusion_counts,
)
from smartvalve.experiments.hust_size_matched_control import (
    REFERENCE_PROTOCOL,
    aggregate_hust_size_matched_records,
    bootstrap_hust_size_matched_comparison,
    hust_size_matched_gate,
    hust_size_matched_rank_concordance,
    score_hust_size_matched_comparison,
)
from smartvalve.experiments.hust_validation_utils import assert_findings_equal
from smartvalve.experiments.paderborn_evaluation import METHODS

VALIDATION_VERSION = "smartvalve-hust-d3-size-matched-validation-0.1.1"
EXPECTED_COUNTS = {
    "fit_count": 675,
    "dann_auxiliary_states": 75,
    "seed_window_predictions": 20_250,
    "ensemble_window_predictions": 4_050,
    "size_matched_recording_predictions": 405,
    "combined_recording_predictions": 810,
    "aggregate_metrics": 18,
    "cell_metrics": 270,
    "ranking_concordance": 2,
    "bootstrap_summary": 9,
    "bootstrap_draws": 45_000,
    "bootstrap_draw_plan": 5_000,
    "rank_shifts": 18,
    "confusion_counts": 162,
    "recording_diagnostics": 18,
}


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _verify(path: Path, expected: str, role: str) -> str:
    if not path.is_file():
        raise FileNotFoundError(path)
    observed = _sha256(path)
    if observed != expected:
        raise ValueError(f"{role} SHA-256 changed: expected {expected}, observed {observed}")
    return observed


def _rank_shifts(aggregate: pd.DataFrame) -> pd.DataFrame:
    values = aggregate.set_index(["protocol", "method"])
    records = []
    for method in METHODS:
        for metric in ("pooled_macro_f1", "mean_cell_macro_f1"):
            column = f"rank_{metric}"
            comparison = float(values.loc[("size_matched_shared_access", method), column])
            reference = float(values.loc[(REFERENCE_PROTOCOL, method), column])
            records.append(
                {
                    "comparison_protocol": "size_matched_shared_access",
                    "reference_protocol": REFERENCE_PROTOCOL,
                    "method": method,
                    "rank_endpoint": metric,
                    "comparison_rank": comparison,
                    "crossed_rank": reference,
                    "rank_change_comparison_minus_crossed": comparison - reference,
                }
            )
    return pd.DataFrame(records)


def _load_primary_crossed(directory: Path) -> tuple[str, pd.DataFrame]:
    summary_path = directory / "hust_d3_summary.json"
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    for filename, expected_hash in summary.get("output_sha256", {}).items():
        _verify(directory / filename, str(expected_hash), f"primary HUST output {filename}")
    records = pd.read_parquet(directory / "recording_predictions.parquet")
    crossed = records.loc[records["protocol"] == REFERENCE_PROTOCOL].reset_index(drop=True)
    if len(crossed) != 405:
        raise ValueError("primary crossed recording count changed")
    return _sha256(summary_path), crossed


def validate(
    *,
    result_directory: Path,
    summary_sha256: str,
    primary_result_directory: Path,
    control_seal_path: Path,
    control_seal_sha256: str,
    output_path: Path,
) -> dict[str, object]:
    summary_path = result_directory / "hust_d3_size_matched_summary.json"
    _verify(summary_path, summary_sha256, "HUST size-matched outcome summary")
    _verify(control_seal_path, control_seal_sha256, "HUST size-matched control seal")
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    if (
        summary.get("run_version") != "smartvalve-hust-d3-size-matched-control-0.1.0"
        or summary.get("status") != "outcome_blind_equal_source_volume_control"
        or summary.get("control_seal_sha256") != control_seal_sha256
    ):
        raise ValueError("HUST size-matched summary identity changed")
    for filename, expected_hash in summary.get("output_sha256", {}).items():
        _verify(result_directory / filename, str(expected_hash), f"control output {filename}")

    predictions = pd.read_parquet(result_directory / "seed_window_predictions.parquet")
    fit_log = pd.read_csv(result_directory / "fit_log.csv")
    traces = json.loads((result_directory / "training_traces.json").read_text(encoding="utf-8"))
    ensemble = ensemble_hust_seed_windows(
        predictions,
        expected_seeds=tuple(int(seed) for seed in AUDIT_SEEDS),
    )
    size_records = aggregate_hust_size_matched_records(ensemble)
    primary_summary_sha256, crossed = _load_primary_crossed(primary_result_directory)
    if primary_summary_sha256 != summary.get("primary_hust_summary_sha256"):
        raise ValueError("control result is linked to a different primary HUST summary")
    combined = pd.concat((size_records, crossed), ignore_index=True)
    aggregate, cells = score_hust_size_matched_comparison(size_records, crossed)
    concordance = hust_size_matched_rank_concordance(aggregate)
    bootstrap, bootstrap_draws, plan = bootstrap_hust_size_matched_comparison(
        combined,
        draws=5_000,
    )
    rank_shifts = _rank_shifts(aggregate)
    confusion = hust_confusion_counts(combined)
    diagnostics = _record_diagnostics(combined)
    observed_counts = {
        "fit_count": len(fit_log),
        "dann_auxiliary_states": int(
            fit_log.loc[fit_log["method"] == "dann", "auxiliary_state_sha256"].notna().sum()
        ),
        "seed_window_predictions": len(predictions),
        "ensemble_window_predictions": len(ensemble),
        "size_matched_recording_predictions": len(size_records),
        "combined_recording_predictions": len(combined),
        "aggregate_metrics": len(aggregate),
        "cell_metrics": len(cells),
        "ranking_concordance": len(concordance),
        "bootstrap_summary": len(bootstrap),
        "bootstrap_draws": len(bootstrap_draws),
        "bootstrap_draw_plan": len(plan),
        "rank_shifts": len(rank_shifts),
        "confusion_counts": len(confusion),
        "recording_diagnostics": len(diagnostics),
    }
    if observed_counts != EXPECTED_COUNTS or len(traces) != EXPECTED_COUNTS["fit_count"]:
        raise ValueError("HUST size-matched artifact counts changed")

    comparisons = {
        "ensemble_window_predictions": (ensemble, "ensemble_window_predictions.parquet"),
        "size_matched_recording_predictions": (
            size_records,
            "size_matched_recording_predictions.parquet",
        ),
        "combined_recording_predictions": (
            combined,
            "combined_recording_predictions.parquet",
        ),
        "aggregate_metrics": (aggregate, "aggregate_metrics.csv"),
        "cell_metrics": (cells, "cell_metrics.csv"),
        "ranking_concordance": (concordance, "ranking_concordance.csv"),
        "bootstrap_summary": (bootstrap, "bootstrap_summary.csv"),
        "bootstrap_draws": (bootstrap_draws, "bootstrap_draws.csv"),
        "bootstrap_draw_plan": (plan, "bootstrap_draw_plan.csv"),
        "rank_shifts": (rank_shifts, "rank_shifts.csv"),
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
            name=f"HUST size-matched {name}",
        )
    findings = hust_size_matched_gate(aggregate, concordance)
    saved_findings = summary.get("findings")
    if not isinstance(saved_findings, dict):
        raise ValueError("HUST size-matched saved findings are not a JSON object")
    findings_maximum_difference = assert_findings_equal(findings, saved_findings)
    validation: dict[str, object] = {
        "schema_version": VALIDATION_VERSION,
        "status": "passed_independent_no_refit_recomputation",
        "input_sha256": {
            "outcome_summary": summary_sha256,
            "primary_hust_summary": primary_summary_sha256,
            "control_seal": control_seal_sha256,
            "seed_window_predictions": _sha256(
                result_directory / "seed_window_predictions.parquet"
            ),
        },
        "validated_counts": observed_counts,
        "maximum_absolute_numeric_difference": maximum_differences,
        "findings_maximum_absolute_numeric_difference": findings_maximum_difference,
        "findings": findings,
        "refit_performed": False,
    }
    if output_path.exists():
        raise ValueError("HUST size-matched validation output already exists")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(validation, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return validation


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--result-dir", type=Path, required=True)
    parser.add_argument("--summary-sha256", required=True)
    parser.add_argument("--primary-result-dir", type=Path, required=True)
    parser.add_argument("--control-seal", type=Path, required=True)
    parser.add_argument("--control-seal-sha256", required=True)
    parser.add_argument("--output", type=Path, required=True)
    return parser


def main() -> int:
    arguments = build_parser().parse_args()
    result = validate(
        result_directory=arguments.result_dir,
        summary_sha256=arguments.summary_sha256,
        primary_result_directory=arguments.primary_result_dir,
        control_seal_path=arguments.control_seal,
        control_seal_sha256=arguments.control_seal_sha256,
        output_path=arguments.output,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
