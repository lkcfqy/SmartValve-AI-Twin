#!/usr/bin/env python3
"""Run the sealed retrospective Paderborn split-protocol contrast."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

import pandas as pd

from smartvalve.experiments.paderborn_protocol_contrast import (
    BOOTSTRAP_DRAWS,
    MODEL_NAMES,
    PROTOCOLS,
    RANDOM_SEED,
    SCHEMA_VERSION,
    build_protocol_splits,
    generate_oof_predictions,
    paired_bearing_bootstrap,
    protocol_effect_table,
    protocol_rank_concordance,
    score_oof_predictions,
)

EXPECTED_FEATURE_SHA256 = "c5caf0cfc408057ae4bfaebef37abdf597135620105ec62e17f3aece6800aff4"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _write_csv(path: Path, frame: pd.DataFrame) -> None:
    frame.to_csv(path, index=False, float_format="%.12g", lineterminator="\n")


def _write_json(path: Path, value: Any) -> None:
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _split_topology(frame: pd.DataFrame) -> pd.DataFrame:
    records = []
    for protocol, splits in build_protocol_splits(frame, random_seed=RANDOM_SEED).items():
        for split in splits:
            source = frame.iloc[split.source_indices]
            target = frame.iloc[split.target_indices]
            records.append(
                {
                    "protocol": protocol,
                    "fold_id": split.fold_id,
                    "source_count": len(source),
                    "target_count": len(target),
                    "quarantine_count": len(split.quarantine_indices),
                    "source_bearing_count": source["bearing_code"].nunique(),
                    "target_bearing_count": target["bearing_code"].nunique(),
                    "shared_bearing_count": len(
                        set(source["bearing_code"]) & set(target["bearing_code"])
                    ),
                    "source_setting_count": source["setting_code"].nunique(),
                    "target_setting_count": target["setting_code"].nunique(),
                    "shared_setting_count": len(
                        set(source["setting_code"]) & set(target["setting_code"])
                    ),
                }
            )
    return pd.DataFrame(records)


def _findings(
    aggregate: pd.DataFrame,
    bootstrap: pd.DataFrame,
    concordance: pd.DataFrame,
) -> dict[str, Any]:
    protocol_leaders = {}
    for protocol, rows in aggregate.groupby("protocol", sort=True, observed=True):
        pooled = rows.sort_values(
            ["pooled_macro_f1", "method"], ascending=[False, True], kind="stable"
        ).iloc[0]
        tail = rows.sort_values(
            ["minimum_cell_macro_f1", "method"],
            ascending=[False, True],
            kind="stable",
        ).iloc[0]
        protocol_leaders[str(protocol)] = {
            "best_pooled_method": str(pooled["method"]),
            "best_pooled_macro_f1": float(pooled["pooled_macro_f1"]),
            "best_minimum_cell_method": str(tail["method"]),
            "best_minimum_cell_macro_f1": float(tail["minimum_cell_macro_f1"]),
        }

    random_effects = bootstrap.loc[
        bootstrap["comparison_protocol"] == "measurement_random"
    ].sort_values("effect_comparison_minus_reference", ascending=False, kind="stable")
    largest = random_effects.iloc[0]
    smallest = random_effects.iloc[-1]
    crossed_tau = concordance.loc[
        (concordance["metric"] == "pooled_macro_f1")
        & (concordance["right_protocol"] == "crossed_holdout")
    ].sort_values("left_protocol", kind="stable")
    return {
        "protocol_leaders": protocol_leaders,
        "measurement_random_minus_crossed_pooled_macro_f1": {
            "largest_method": str(largest["method"]),
            "largest_effect": float(largest["effect_comparison_minus_reference"]),
            "largest_interval": [
                float(largest["bootstrap_lower_95"]),
                float(largest["bootstrap_upper_95"]),
            ],
            "smallest_method": str(smallest["method"]),
            "smallest_effect": float(smallest["effect_comparison_minus_reference"]),
            "smallest_interval": [
                float(smallest["bootstrap_lower_95"]),
                float(smallest["bootstrap_upper_95"]),
            ],
        },
        "pooled_rank_agreement_with_crossed": {
            str(row.left_protocol): float(row.kendall_tau)
            for row in crossed_tau.itertuples(index=False)
        },
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--features", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--bootstrap-draws", type=int, default=BOOTSTRAP_DRAWS)
    return parser


def main() -> int:
    arguments = build_parser().parse_args()
    if not arguments.features.is_file():
        raise FileNotFoundError(f"missing frozen feature input: {arguments.features}")
    observed_hash = _sha256(arguments.features)
    if observed_hash != EXPECTED_FEATURE_SHA256:
        raise ValueError(
            "Paderborn feature SHA-256 changed: "
            f"expected {EXPECTED_FEATURE_SHA256}, observed {observed_hash}"
        )
    arguments.output_dir.mkdir(parents=True, exist_ok=True)
    if any(arguments.output_dir.iterdir()):
        raise ValueError("output directory must be empty")

    frame = pd.read_parquet(arguments.features)
    topology = _split_topology(frame)
    predictions, fit_log = generate_oof_predictions(frame, random_seed=RANDOM_SEED)
    aggregate, cell_metrics = score_oof_predictions(predictions)
    concordance = protocol_rank_concordance(aggregate)
    effects = protocol_effect_table(aggregate)
    bootstrap, bootstrap_draws, draw_plan = paired_bearing_bootstrap(
        predictions,
        draws=arguments.bootstrap_draws,
        random_seed=RANDOM_SEED,
    )

    outputs = {
        "split_topology.csv": topology,
        "predictions.parquet": predictions,
        "fit_log.csv": fit_log,
        "aggregate_metrics.csv": aggregate,
        "cell_metrics.csv": cell_metrics,
        "protocol_effects.csv": effects,
        "ranking_concordance.csv": concordance,
        "bootstrap_summary.csv": bootstrap,
        "bootstrap_draws.csv": bootstrap_draws,
        "bootstrap_draw_plan.csv": draw_plan,
    }
    for name, value in outputs.items():
        path = arguments.output_dir / name
        if name.endswith(".parquet"):
            value.to_parquet(path, index=False)
        else:
            _write_csv(path, value)

    file_hashes = {
        name: _sha256(arguments.output_dir / name)
        for name in sorted(outputs)
    }
    summary = {
        "schema_version": SCHEMA_VERSION,
        "status": "retrospective_development_not_confirmatory",
        "input": {
            "path": str(arguments.features),
            "sha256": observed_hash,
            "rows": len(frame),
        },
        "design": {
            "protocols": list(PROTOCOLS),
            "models": list(MODEL_NAMES),
            "feature_count": sum("__" in column for column in frame.columns),
            "common_evaluation_cells": 24,
            "random_seed": RANDOM_SEED,
            "bootstrap_draws": arguments.bootstrap_draws,
            "bootstrap_unit": "bearing_code_stratified_by_truth",
            "configuration_search": "none",
            "target_use": "scoring_only_after_source_fit",
        },
        "findings": _findings(aggregate, bootstrap, concordance),
        "output_sha256": file_hashes,
    }
    _write_json(arguments.output_dir / "protocol_contrast_summary.json", summary)

    print(json.dumps(summary["findings"], ensure_ascii=False, indent=2, sort_keys=True))
    print("output_sha256")
    print(json.dumps(file_hashes, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
