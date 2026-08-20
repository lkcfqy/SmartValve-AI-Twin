"""Assemble and Holm-correct the frozen six-test confirmatory family."""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from smartvalve.experiments.cranfield_causal_audit import AUDIT_SEEDS
from smartvalve.experiments.paderborn_bootstrap import (
    BOOTSTRAP_VERSION as PADERBORN_BOOTSTRAP_VERSION,
)
from smartvalve.experiments.selective_bootstrap import (
    BOOTSTRAP_REPLICATES,
    BOOTSTRAP_SEED,
    HEADLINE_SCORE,
    HEADLINE_SOURCE_COVERAGE,
    METHODS,
    _artifact,
    _sha256,
    holm_adjust,
)
from smartvalve.experiments.selective_bootstrap import (
    BOOTSTRAP_VERSION as DEVELOPMENT_BOOTSTRAP_VERSION,
)

FAMILY_VERSION = "smartvalve-six-test-confirmatory-family-0.1.0"
ALPHA = 0.05
MINIMUM_PRACTICAL_EFFECT = 0.01


@dataclass(frozen=True)
class FamilyTest:
    dataset: str
    endpoint_role: str
    source: str
    comparison_name: str

    @property
    def test_id(self) -> str:
        return f"{self.dataset}:{self.endpoint_role}"


FAMILY = (
    FamilyTest(
        "cranfield",
        "minimum_environment_macro_f1",
        "development",
        "pirl_minus_erm_worst_fold_macro_f1",
    ),
    FamilyTest(
        "cranfield",
        "selective_risk_at_source_50pct",
        "development",
        "erm_minus_pirl_selective_risk_at_source_50pct",
    ),
    FamilyTest(
        "uci_hydraulic",
        "minimum_environment_macro_f1",
        "development",
        "pirl_minus_erm_worst_fold_macro_f1",
    ),
    FamilyTest(
        "uci_hydraulic",
        "selective_risk_at_source_50pct",
        "development",
        "erm_minus_pirl_selective_risk_at_source_50pct",
    ),
    FamilyTest(
        "paderborn",
        "minimum_environment_macro_f1",
        "paderborn",
        "pirl_minus_erm_minimum_setting_macro_f1",
    ),
    FamilyTest(
        "paderborn",
        "selective_risk_at_source_50pct",
        "paderborn",
        "erm_minus_pirl_selective_risk_at_source_50pct",
    ),
)


def _validate_configuration(metrics: dict[str, Any], *, paderborn: bool) -> None:
    expected_version = (
        PADERBORN_BOOTSTRAP_VERSION
        if paderborn
        else DEVELOPMENT_BOOTSTRAP_VERSION
    )
    if metrics.get("bootstrap_version") != expected_version:
        raise ValueError("confirmatory input has an unexpected bootstrap version")
    configuration = metrics.get("configuration")
    if not isinstance(configuration, dict):
        raise ValueError("confirmatory input has no bootstrap configuration")
    expected = {
        "replicates": BOOTSTRAP_REPLICATES,
        "seed": BOOTSTRAP_SEED,
        "methods": list(METHODS),
        "model_seeds": list(AUDIT_SEEDS),
        "headline_score": HEADLINE_SCORE,
        "headline_source_coverage": HEADLINE_SOURCE_COVERAGE,
    }
    for key, value in expected.items():
        if configuration.get(key) != value:
            raise ValueError(f"confirmatory input changes frozen configuration {key}")
    if paderborn:
        if configuration.get("resampling_unit") != "bearing_identity":
            raise ValueError("D2 confirmatory input is not a bearing-identity bootstrap")
        if configuration.get("stratification") != "truth":
            raise ValueError("D2 confirmatory input is not class-stratified")
        contract = metrics.get("contract")
        if not isinstance(contract, dict):
            raise ValueError("D2 confirmatory input has no physical contract")
        if contract.get("pure_bearings") != 29:
            raise ValueError("D2 confirmatory input changes the pure-bearing count")
        if contract.get("physical_measurements") != 2_320:
            raise ValueError("D2 confirmatory input changes the measurement count")
    else:
        comparisons = metrics.get("paired_comparisons")
        if not isinstance(comparisons, dict) or set(comparisons) != {
            "cranfield",
            "uci_hydraulic",
        }:
            raise ValueError("development confirmatory input must contain exactly D0 and D1")


def _comparison(metrics: dict[str, Any], spec: FamilyTest) -> dict[str, Any]:
    comparisons = metrics.get("paired_comparisons")
    if not isinstance(comparisons, dict):
        raise ValueError("confirmatory input has no paired comparisons")
    if spec.source == "development":
        dataset_comparisons = comparisons.get(spec.dataset)
        if not isinstance(dataset_comparisons, dict):
            raise ValueError(f"confirmatory input has no dataset {spec.dataset}")
    else:
        dataset_comparisons = comparisons
    result = dataset_comparisons.get(spec.comparison_name)
    if not isinstance(result, dict):
        raise ValueError(f"confirmatory input has no comparison {spec.comparison_name}")
    required = {
        "point_estimate",
        "bootstrap_mean",
        "bootstrap_standard_error",
        "ci95_low",
        "ci95_high",
        "two_sided_bootstrap_tail_p",
        "positive_favors_pirl",
        "minimum_practical_effect",
        "practically_positive_and_ci_excludes_zero",
    }
    if required - set(result):
        raise ValueError("confirmatory comparison is missing frozen fields")
    numeric_fields = required - {
        "positive_favors_pirl",
        "practically_positive_and_ci_excludes_zero",
    }
    values = np.asarray([result[field] for field in numeric_fields], dtype=float)
    if not np.isfinite(values).all():
        raise ValueError("confirmatory comparison contains non-finite values")
    if not 0 <= float(result["two_sided_bootstrap_tail_p"]) <= 1:
        raise ValueError("confirmatory bootstrap tail probability is outside [0, 1]")
    if float(result["ci95_low"]) > float(result["ci95_high"]):
        raise ValueError("confirmatory interval endpoints are reversed")
    if result["positive_favors_pirl"] is not True:
        raise ValueError("confirmatory effect direction must be positive for PIRL")
    if not np.isclose(
        float(result["minimum_practical_effect"]),
        MINIMUM_PRACTICAL_EFFECT,
    ):
        raise ValueError("confirmatory minimum practical effect changed")
    expected_gate = bool(
        float(result["point_estimate"]) >= MINIMUM_PRACTICAL_EFFECT
        and float(result["ci95_low"]) > 0
    )
    if bool(result["practically_positive_and_ci_excludes_zero"]) != expected_gate:
        raise ValueError("confirmatory comparison reports an inconsistent practical gate")
    return result


def assemble_family(
    development_metrics: dict[str, Any],
    paderborn_metrics: dict[str, Any],
) -> tuple[pd.DataFrame, dict[str, Any]]:
    """Return the immutable six rows and an explicit family-level summary."""

    _validate_configuration(development_metrics, paderborn=False)
    _validate_configuration(paderborn_metrics, paderborn=True)
    raw_rows = []
    raw_p_values = {}
    for spec in FAMILY:
        source = (
            development_metrics
            if spec.source == "development"
            else paderborn_metrics
        )
        comparison = _comparison(source, spec)
        raw_p = float(comparison["two_sided_bootstrap_tail_p"])
        raw_p_values[spec.test_id] = raw_p
        raw_rows.append(
            {
                "test_id": spec.test_id,
                "dataset": spec.dataset,
                "endpoint_role": spec.endpoint_role,
                "effect_definition": spec.comparison_name,
                "point_estimate": float(comparison["point_estimate"]),
                "bootstrap_mean": float(comparison["bootstrap_mean"]),
                "bootstrap_standard_error": float(
                    comparison["bootstrap_standard_error"]
                ),
                "ci95_low": float(comparison["ci95_low"]),
                "ci95_high": float(comparison["ci95_high"]),
                "raw_two_sided_tail_p": raw_p,
                "minimum_practical_effect": MINIMUM_PRACTICAL_EFFECT,
                "material_and_ci_positive": bool(
                    comparison["practically_positive_and_ci_excludes_zero"]
                ),
            }
        )
    adjusted = holm_adjust(raw_p_values)
    rows = pd.DataFrame(raw_rows)
    rows["holm_adjusted_p"] = rows["test_id"].map(adjusted).astype(float)
    rows["holm_reject_at_0p05"] = rows["holm_adjusted_p"] <= ALPHA
    rows["confirmatory_positive"] = (
        rows["material_and_ci_positive"] & rows["holm_reject_at_0p05"]
    )
    rows["materially_harmful_and_ci_excludes_zero"] = (
        (rows["point_estimate"] <= -MINIMUM_PRACTICAL_EFFECT)
        & (rows["ci95_high"] < 0)
    )
    dataset_decisions = {
        dataset: {
            "confirmatory_positive_endpoints": sorted(
                group.loc[group["confirmatory_positive"], "endpoint_role"].tolist()
            ),
            "materially_harmful_endpoints": sorted(
                group.loc[
                    group["materially_harmful_and_ci_excludes_zero"],
                    "endpoint_role",
                ].tolist()
            ),
        }
        for dataset, group in rows.groupby("dataset", sort=True, observed=True)
    }
    improved_datasets = sorted(
        dataset
        for dataset, decision in dataset_decisions.items()
        if decision["confirmatory_positive_endpoints"]
    )
    harmful_datasets = sorted(
        dataset
        for dataset, decision in dataset_decisions.items()
        if decision["materially_harmful_endpoints"]
    )
    summary = {
        "family_size": len(FAMILY),
        "alpha": ALPHA,
        "correction": "Holm step-down family-wise error control",
        "positive_test_count": int(rows["confirmatory_positive"].sum()),
        "materially_harmful_test_count": int(
            rows["materially_harmful_and_ci_excludes_zero"].sum()
        ),
        "all_six_confirmatory_positive": bool(rows["confirmatory_positive"].all()),
        "dataset_decisions": dataset_decisions,
        "datasets_with_confirmatory_improvement": improved_datasets,
        "datasets_with_material_harm": harmful_datasets,
        "internal_multi_dataset_evidence_gate_passed": bool(
            len(improved_datasets) >= 2 and not harmful_datasets
        ),
        "internal_multi_dataset_evidence_gate_rule": (
            "At least one confirmatory-positive endpoint on at least two datasets and no "
            "materially harmful endpoint with CI excluding zero on any dataset."
        ),
        "claim_rule": (
            "Each dataset-endpoint claim requires effect >= 0.01, percentile CI low > 0, "
            "and Holm-adjusted p <= 0.05; no subset or pooled replacement is permitted."
        ),
    }
    return rows, summary


def run_confirmatory_family(
    development_metrics_path: Path,
    paderborn_metrics_path: Path,
    output_directory: Path,
    *,
    expected_development_sha256: str,
    expected_paderborn_sha256: str,
) -> dict[str, Any]:
    development_hash = _sha256(development_metrics_path)
    paderborn_hash = _sha256(paderborn_metrics_path)
    if development_hash != expected_development_sha256:
        raise ValueError("development bootstrap metrics hash does not match the final seal")
    if paderborn_hash != expected_paderborn_sha256:
        raise ValueError("Paderborn bootstrap metrics hash does not match the final seal")
    development_metrics = json.loads(
        development_metrics_path.read_text(encoding="utf-8")
    )
    paderborn_metrics = json.loads(paderborn_metrics_path.read_text(encoding="utf-8"))
    tests, summary = assemble_family(development_metrics, paderborn_metrics)

    output_directory.mkdir(parents=True, exist_ok=True)
    tests_path = output_directory / "confirmatory_tests.parquet"
    tests.to_parquet(tests_path, index=False)
    metrics = {
        "family_version": FAMILY_VERSION,
        "generated_at": datetime.now(UTC).isoformat(),
        "protocol_document": (
            "research/protocols/paderborn_prospective_evaluation_v0.1.md"
        ),
        "inputs": {
            "development_metrics": str(development_metrics_path.resolve()),
            "development_metrics_sha256": development_hash,
            "paderborn_metrics": str(paderborn_metrics_path.resolve()),
            "paderborn_metrics_sha256": paderborn_hash,
        },
        "summary": summary,
        "tests": tests.to_dict(orient="records"),
        "artifacts": {
            "confirmatory_tests": _artifact(tests_path, rows=len(tests)),
        },
    }
    metrics_path = output_directory / "metrics.json"
    metrics_path.write_text(
        json.dumps(metrics, ensure_ascii=False, indent=2, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    return metrics


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--development-metrics", type=Path, required=True)
    parser.add_argument("--paderborn-metrics", type=Path, required=True)
    parser.add_argument("--expected-development-sha256", required=True)
    parser.add_argument("--expected-paderborn-sha256", required=True)
    parser.add_argument("--output-directory", type=Path, required=True)
    args = parser.parse_args()
    result = run_confirmatory_family(
        args.development_metrics,
        args.paderborn_metrics,
        args.output_directory,
        expected_development_sha256=args.expected_development_sha256,
        expected_paderborn_sha256=args.expected_paderborn_sha256,
    )
    print(json.dumps(result["summary"], ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
