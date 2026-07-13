"""Grouped simulation benchmark for ValveDNA rules and explicit rejection."""

# ruff: noqa: E501 -- generated Markdown templates are intentionally kept readable.

from __future__ import annotations

import argparse
import json
import time
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from scipy.stats import spearmanr

from smartvalve import MODEL_VERSION
from smartvalve.config import project_root
from smartvalve.diagnosis.rules import DiagnosisResult, diagnose
from smartvalve.signature.analysis import analyze_signature
from smartvalve.simulation.model import FAULT_TYPES, FaultConfig, ValveSimulator

CLASS_NAMES = tuple(FAULT_TYPES)


@dataclass(frozen=True)
class BenchmarkProfile:
    name: str
    severities: tuple[float, ...]
    load_factors: tuple[float, ...]
    seeds: tuple[int, ...]
    split_policy: str
    all_holdout: bool = False

    @property
    def expected_runs(self) -> int:
        return len(CLASS_NAMES) * len(self.severities) * len(self.load_factors) * len(self.seeds)


PROFILES = {
    "smoke": BenchmarkProfile(
        name="smoke",
        severities=(0.0, 0.5, 1.0),
        load_factors=(0.8, 1.0, 1.2),
        seeds=(0, 1, 2),
        split_policy=(
            "First 67% of ordered load-factor groups are development; the remaining group is "
            "a smoke-test holdout."
        ),
    ),
    "full": BenchmarkProfile(
        name="full",
        severities=(0.0, 0.25, 0.5, 0.75, 1.0),
        load_factors=tuple(float(value) for value in np.linspace(0.75, 1.4, 10)),
        seeds=tuple(range(10)),
        split_policy=(
            "First 70% of ordered load-factor groups are development and the remaining groups "
            "form a grouped regression holdout. Version 0.3 was improved after reviewing the "
            "version 0.2 regression result, so this is not a pristine final test."
        ),
    ),
    "challenge": BenchmarkProfile(
        name="challenge",
        severities=(0.0, 0.25, 0.5, 0.75, 1.0),
        load_factors=(0.72, 0.86, 1.03, 1.21, 1.43),
        seeds=tuple(range(100, 110)),
        split_policy=(
            "Locked challenge created after version 0.3 rules were frozen. All exact load and "
            "seed groups differ from the 3000-run development/regression matrix."
        ),
        all_holdout=True,
    ),
}


def prediction_from_diagnosis(diagnosis: DiagnosisResult) -> str:
    """Map transparent findings to benchmark classes without accessing the true label."""

    if diagnosis.decision_state == "needs_review":
        return "rejected"
    finding = diagnosis.primary_finding.lower()
    if finding == "no actionable deviation":
        return "normal"
    if "sensor" in finding:
        return "sensor_drift"
    if "actuator performance" in finding:
        return "actuator_degradation"
    if finding.startswith("travel obstruction"):
        return "obstruction"
    if "stiction" in finding:
        return "stiction"
    if "friction" in finding:
        return "friction"
    return "rejected"


def _class_metrics(frame: pd.DataFrame) -> dict[str, dict[str, float | int]]:
    result: dict[str, dict[str, float | int]] = {}
    for label in CLASS_NAMES:
        true_positive = int(((frame["truth"] == label) & (frame["prediction"] == label)).sum())
        false_positive = int(((frame["truth"] != label) & (frame["prediction"] == label)).sum())
        false_negative = int(((frame["truth"] == label) & (frame["prediction"] != label)).sum())
        support = int((frame["truth"] == label).sum())
        precision = true_positive / max(1, true_positive + false_positive)
        recall = true_positive / max(1, true_positive + false_negative)
        f1 = 2.0 * precision * recall / max(1e-12, precision + recall)
        result[label] = {
            "precision": round(precision, 4),
            "recall": round(recall, 4),
            "f1": round(f1, 4),
            "support": support,
        }
    return result


def _confusion_matrix(frame: pd.DataFrame) -> dict[str, dict[str, int]]:
    columns = (*CLASS_NAMES, "rejected")
    return {
        truth: {
            predicted: int(
                ((frame["truth"] == truth) & (frame["prediction"] == predicted)).sum()
            )
            for predicted in columns
        }
        for truth in CLASS_NAMES
    }


def _monotonicity(frame: pd.DataFrame) -> dict[str, float | None]:
    correlations: dict[str, list[float]] = {fault: [] for fault in CLASS_NAMES if fault != "normal"}
    fault_frame = frame.loc[frame["configured_fault"] != "normal"]
    for (fault, _load_factor, _seed), group in fault_frame.groupby(
        ["configured_fault", "load_factor", "seed"]
    ):
        if group["severity"].nunique() < 3:
            continue
        coefficient = spearmanr(group["severity"], 100.0 - group["health_score"]).statistic
        if np.isfinite(coefficient):
            correlations[str(fault)].append(float(coefficient))
    return {
        fault: round(float(np.mean(values)), 4) if values else None
        for fault, values in correlations.items()
    }


def summarize_metrics(
    records: pd.DataFrame,
    *,
    profile: BenchmarkProfile,
    out_of_spec_voltage_rejection_recall: float,
) -> dict[str, Any]:
    holdout = records.loc[records["split"] == "holdout"].copy()
    class_metrics = _class_metrics(holdout)
    accepted = holdout.loc[holdout["prediction"] != "rejected"]
    normal = holdout.loc[holdout["truth"] == "normal"]
    macro_f1 = float(np.mean([values["f1"] for values in class_metrics.values()]))
    result = {
        "model_version": MODEL_VERSION,
        "profile": profile.name,
        "matrix": {
            "fault_states": len(CLASS_NAMES),
            "severity_levels": len(profile.severities),
            "operating_conditions": len(profile.load_factors),
            "seeds": len(profile.seeds),
            "total_runs": len(records),
            "unique_observable_runs": int(records["observable_sha256"].nunique()),
            "redundant_parameterizations": int(
                len(records) - records["observable_sha256"].nunique()
            ),
            "development_runs": int((records["split"] == "development").sum()),
            "holdout_runs": len(holdout),
            "holdout_unique_observable_runs": int(
                holdout["observable_sha256"].nunique()
            ),
        },
        "split_policy": profile.split_policy,
        "holdout": {
            "macro_f1_including_rejection_as_error": round(macro_f1, 4),
            "overall_accuracy": round(float((holdout["truth"] == holdout["prediction"]).mean()), 4),
            "accepted_accuracy": round(
                (
                    float((accepted["truth"] == accepted["prediction"]).mean())
                    if len(accepted)
                    else 0.0
                ),
                4,
            ),
            "false_positive_rate_normal": round(
                float((normal["prediction"] != "normal").mean()) if len(normal) else 0.0,
                4,
            ),
            "rejection_rate": round(float((holdout["prediction"] == "rejected").mean()), 4),
            "out_of_spec_voltage_rejection_recall": round(
                out_of_spec_voltage_rejection_recall, 4
            ),
            "latency_ms": {
                "p50": round(float(holdout["latency_ms"].quantile(0.50)), 3),
                "p95": round(float(holdout["latency_ms"].quantile(0.95)), 3),
                "max": round(float(holdout["latency_ms"].max()), 3),
            },
            "per_class": class_metrics,
            "confusion_matrix": _confusion_matrix(holdout),
        },
        "severity_vs_degradation_spearman": _monotonicity(records),
        "claim_boundary": (
            "Simulation benchmark only. Scores do not estimate accuracy on a Weilong valve or "
            "any unseen physical product."
        ),
    }
    return result


def _evaluate_ood_rejection(
    simulator: ValveSimulator,
    profile: BenchmarkProfile,
) -> float:
    decisions: list[str] = []
    for voltage in (3.8, 6.2):
        for load_factor in profile.load_factors:
            for seed in profile.seeds:
                baseline = simulator.simulate(
                    FaultConfig(
                        fault_type="normal",
                        severity=0.0,
                        supply_voltage_v=voltage,
                        load_factor=load_factor,
                        seed=seed,
                    )
                )
                current = simulator.simulate(
                    FaultConfig(
                        fault_type="actuator_degradation",
                        severity=0.5,
                        supply_voltage_v=voltage,
                        load_factor=load_factor,
                        seed=seed,
                    )
                )
                diagnosis = diagnose(analyze_signature(baseline, current), current)
                decisions.append(diagnosis.decision_state)
    return sum(decision == "needs_review" for decision in decisions) / max(1, len(decisions))


def _observable_digest(frame: pd.DataFrame) -> str:
    """Hash only signals available to diagnosis, excluding hidden benchmark labels."""

    hidden_columns = {"fault_type", "fault_severity", "operating_condition_id", "seed"}
    observable = frame.drop(
        columns=[column for column in hidden_columns if column in frame], errors="ignore"
    )
    observable = observable.reindex(sorted(observable.columns), axis=1)
    values = pd.util.hash_pandas_object(observable, index=True).to_numpy().tobytes()
    return sha256(values).hexdigest()


def run_benchmark(profile: BenchmarkProfile) -> tuple[pd.DataFrame, dict[str, Any]]:
    simulator = ValveSimulator()
    records: list[dict[str, object]] = []
    development_count = (
        0
        if profile.all_holdout
        else min(
            len(profile.load_factors) - 1,
            max(1, int(np.floor(len(profile.load_factors) * 0.7))),
        )
    )
    baseline_cache: dict[tuple[float, int], pd.DataFrame] = {}

    for operating_index, load_factor in enumerate(profile.load_factors):
        split = (
            "holdout"
            if profile.all_holdout
            else ("development" if operating_index < development_count else "holdout")
        )
        for seed in profile.seeds:
            baseline_cache[(load_factor, seed)] = simulator.simulate(
                FaultConfig(
                    fault_type="normal",
                    severity=0.0,
                    load_factor=load_factor,
                    seed=seed,
                )
            )
            for fault in CLASS_NAMES:
                for severity in profile.severities:
                    current = simulator.simulate(
                        FaultConfig(
                            fault_type=fault,
                            severity=severity,
                            load_factor=load_factor,
                            seed=seed,
                        )
                    )
                    started = time.perf_counter()
                    analysis = analyze_signature(baseline_cache[(load_factor, seed)], current)
                    diagnosis = diagnose(analysis, current)
                    latency_ms = (time.perf_counter() - started) * 1000.0
                    truth = "normal" if severity == 0.0 else fault
                    records.append(
                        {
                            "split": split,
                            "operating_condition": operating_index,
                            "load_factor": round(load_factor, 5),
                            "seed": seed,
                            "configured_fault": fault,
                            "severity": severity,
                            "truth": truth,
                            "prediction": prediction_from_diagnosis(diagnosis),
                            "decision_state": diagnosis.decision_state,
                            "finding": diagnosis.primary_finding,
                            "health_score": diagnosis.health_score,
                            "evidence_strength": diagnosis.confidence,
                            "observable_sha256": _observable_digest(current),
                            "latency_ms": round(latency_ms, 4),
                        }
                    )
    frame = pd.DataFrame.from_records(records)
    ood_recall = _evaluate_ood_rejection(simulator, profile)
    return frame, summarize_metrics(
        frame,
        profile=profile,
        out_of_spec_voltage_rejection_recall=ood_recall,
    )


def _report_markdown(metrics: dict[str, Any]) -> str:
    holdout = metrics["holdout"]
    matrix = metrics["matrix"]
    per_class = holdout["per_class"]
    rows = "\n".join(
        f"| {name} | {values['precision']:.3f} | {values['recall']:.3f} | "
        f"{values['f1']:.3f} | {values['support']} |"
        for name, values in per_class.items()
    )
    monotonicity = "\n".join(
        f"- `{fault}`: {value if value is not None else 'not available'}"
        for fault, value in metrics["severity_vs_degradation_spearman"].items()
    )
    return f"""# ValveDNA grouped benchmark report

Model: `{metrics['model_version']}`
Profile: `{metrics['profile']}`

## Protocol

- {matrix['fault_states']} configured states × {matrix['severity_levels']} severity levels × {matrix['operating_conditions']} load groups × {matrix['seeds']} seeds = **{matrix['total_runs']} parameterized runs**.
- Unique observable traces: **{matrix['unique_observable_runs']}**; redundant zero-effect parameterizations: **{matrix['redundant_parameterizations']}**.
- Development runs: {matrix['development_runs']}.
- Grouped holdout/challenge runs: {matrix['holdout_runs']}.
- {metrics['split_policy']}
- Ground-truth fault names are used only by this scorer, never by `diagnose()`.

## Holdout results

- Macro F1, counting rejection as error: **{holdout['macro_f1_including_rejection_as_error']:.3f}**
- Overall accuracy: **{holdout['overall_accuracy']:.3f}**
- Accepted-only accuracy: **{holdout['accepted_accuracy']:.3f}**
- Normal false-positive rate: **{holdout['false_positive_rate_normal']:.3f}**
- In-distribution rejection rate: **{holdout['rejection_rate']:.3f}**
- Out-of-spec voltage rejection recall: **{holdout['out_of_spec_voltage_rejection_recall']:.3f}**
- Diagnostic latency p50 / p95 / max: **{holdout['latency_ms']['p50']:.2f} / {holdout['latency_ms']['p95']:.2f} / {holdout['latency_ms']['max']:.2f} ms**

| Class | Precision | Recall | F1 | Support |
|---|---:|---:|---:|---:|
{rows}

## Severity monotonicity

Spearman correlation between severity and degradation score (`100 - health`), averaged across load/seed groups:

{monotonicity}

## Claim boundary

{metrics['claim_boundary']}
"""


def _model_card(metrics: dict[str, Any]) -> str:
    holdout = metrics["holdout"]
    return f"""# Model card: {metrics['model_version']}

## Intended use

Transparent full-stroke valve/actuator signature screening for an industrial engineering PoC. The model compares current-versus-position signatures, motion time, stagnation, reported travel and process consistency.

## Decision outputs

- `normal`: no actionable deviation under the current evidence.
- `diagnosed`: one transparent rule matched with an evidence trail.
- `needs_review`: out-of-spec supply or an unclassified signature; do not auto-dispatch maintenance.

## Evaluation

- Profile: `{metrics['profile']}`.
- Operating-condition holdout macro F1: {holdout['macro_f1_including_rejection_as_error']:.3f}.
- Normal false-positive rate: {holdout['false_positive_rate_normal']:.3f}.
- Out-of-spec voltage rejection recall: {holdout['out_of_spec_voltage_rejection_recall']:.3f}.
- p95 diagnostic latency: {holdout['latency_ms']['p95']:.2f} ms.

## Known limitations

- Evaluation is deterministic simulation plus separately reported public-rig evidence; it is not Weilong product accuracy.
- Low-severity faults can be indistinguishable from normal measurement variation.
- Travel-to-hydraulic-loss mapping is illustrative until a Kv/Cv curve is fitted.
- Leakage and remaining useful life are not validated.
- The current rejection test covers supply-voltage scope and unclassified signatures, not every distribution shift.

## Required human oversight

Maintenance decisions require an engineer to review the source grade, operating condition, data quality, evidence variables and previous baseline. `needs_review` must never be converted to a root cause automatically.
"""


def write_artifacts(
    records: pd.DataFrame,
    metrics: dict[str, Any],
    output_dir: Path,
) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    records.to_csv(output_dir / "records.csv", index=False)
    (output_dir / "metrics.json").write_text(
        json.dumps(metrics, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (output_dir / "report.md").write_text(_report_markdown(metrics), encoding="utf-8")
    (output_dir / "model_card.md").write_text(_model_card(metrics), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profile", choices=tuple(PROFILES), default="smoke")
    parser.add_argument("--output-dir", type=Path)
    args = parser.parse_args()
    profile = PROFILES[args.profile]
    output_dir = args.output_dir or project_root() / "artifacts" / "benchmark" / profile.name
    started = time.perf_counter()
    records, metrics = run_benchmark(profile)
    write_artifacts(records, metrics, output_dir)
    elapsed = time.perf_counter() - started
    print(
        json.dumps(
            {
                "output_dir": str(output_dir),
                "runs": len(records),
                "holdout_macro_f1": metrics["holdout"][
                    "macro_f1_including_rejection_as_error"
                ],
                "normal_false_positive_rate": metrics["holdout"][
                    "false_positive_rate_normal"
                ],
                "out_of_spec_voltage_rejection_recall": metrics["holdout"][
                    "out_of_spec_voltage_rejection_recall"
                ],
                "elapsed_s": round(elapsed, 2),
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
