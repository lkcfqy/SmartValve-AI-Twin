"""Cross-check EXP-110 table metrics against the bootstrap identity draw."""

from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path

import numpy as np

from smartvalve.experiments.uci_hydraulic_bootstrap import (
    ALL_METRICS,
    AUDIT_SEEDS,
    CONTEXT_COLUMNS,
    CONTEXTS,
    ESTIMATORS,
    PRIMARY_REPETITIONS,
    PROTOCOLS,
    _all_metric_tensor,
    _file_sha256,
    _tensorize_records,
    load_and_validate_records,
)


def validate_identity(
    records_path: Path,
    audit_metrics_path: Path,
    *,
    tolerance: float = 1e-10,
) -> dict[str, object]:
    if tolerance <= 0:
        raise ValueError("identity tolerance must be positive")
    records_path = records_path.resolve()
    audit_metrics_path = audit_metrics_path.resolve()
    records = load_and_validate_records(records_path)
    probabilities, predictions = _tensorize_records(records)
    identity_performance = np.broadcast_to(
        np.arange(len(PRIMARY_REPETITIONS)),
        (len(CONTEXTS), len(PRIMARY_REPETITIONS)),
    )
    identity_control = np.broadcast_to(
        np.arange(len(PRIMARY_REPETITIONS)),
        (len(CONTEXT_COLUMNS), len(CONTEXTS), len(PRIMARY_REPETITIONS)),
    )
    observed = _all_metric_tensor(
        probabilities,
        predictions,
        identity_performance,
        identity_control,
    )
    audit = json.loads(audit_metrics_path.read_text(encoding="utf-8"))
    records_sha256 = _file_sha256(records_path)
    declared_sha256 = audit["artifacts"]["records"]["sha256"]
    if records_sha256 != declared_sha256:
        raise ValueError("EXP-110 metrics do not reference the supplied record bytes")

    differences = []
    for estimator_index, estimator in enumerate(ESTIMATORS):
        for protocol_index, protocol in enumerate(PROTOCOLS):
            rows = {
                int(row["seed"]): row
                for row in audit["results"][estimator][protocol]["per_seed"]
            }
            if set(rows) != set(AUDIT_SEEDS):
                raise ValueError(f"audit seed grid changed for {estimator}/{protocol}")
            for seed_index, seed in enumerate(AUDIT_SEEDS):
                for metric_index, metric in enumerate(ALL_METRICS):
                    expected = float(rows[int(seed)][metric])
                    actual = float(
                        observed[
                            estimator_index,
                            protocol_index,
                            seed_index,
                            metric_index,
                        ]
                    )
                    differences.append(
                        {
                            "estimator": estimator,
                            "protocol": protocol,
                            "seed": int(seed),
                            "metric": metric,
                            "audit_value": expected,
                            "identity_value": actual,
                            "absolute_difference": abs(actual - expected),
                        }
                    )
    maximum = max(float(row["absolute_difference"]) for row in differences)
    if maximum > tolerance:
        worst = max(differences, key=lambda row: row["absolute_difference"])
        raise ValueError(
            f"bootstrap identity differs from EXP-110 by {maximum}: {worst}"
        )
    return {
        "schema_version": "smartvalve-uci-bootstrap-identity-0.1.0",
        "generated_at": datetime.now(UTC).isoformat(),
        "status": "pass",
        "records_path": str(records_path),
        "records_sha256": records_sha256,
        "audit_metrics_path": str(audit_metrics_path),
        "audit_metrics_sha256": _file_sha256(audit_metrics_path),
        "record_rows": len(records),
        "comparison_count": len(differences),
        "tolerance": tolerance,
        "maximum_absolute_difference": maximum,
        "comparisons": differences,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--records", type=Path, required=True)
    parser.add_argument("--audit-metrics", type=Path, required=True)
    parser.add_argument("--output-directory", type=Path, required=True)
    parser.add_argument("--tolerance", type=float, default=1e-10)
    args = parser.parse_args()
    result = validate_identity(
        args.records,
        args.audit_metrics,
        tolerance=args.tolerance,
    )
    args.output_directory.mkdir(parents=True, exist_ok=True)
    output = args.output_directory / "identity_validation.json"
    output.write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                key: result[key]
                for key in (
                    "status",
                    "record_rows",
                    "comparison_count",
                    "maximum_absolute_difference",
                )
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
