"""Emit the synthetic, quarantine-safe Paderborn model-fold manifest."""

from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from itertools import product
from pathlib import Path

import numpy as np
import pandas as pd

from smartvalve.data.paderborn import (
    BEARING_METADATA,
    OPERATING_SETTINGS,
    PRIMARY_BEARING_CODES,
)
from smartvalve.data.paderborn_features import (
    STRUCTURALLY_EXCLUDED_FILENAMES,
    main_signal_feature_names,
    parse_measurement_filename,
)
from smartvalve.experiments.paderborn_domain import build_paderborn_model_folds
from smartvalve.experiments.paderborn_partitions import MEASUREMENT_INDICES


def _synthetic_feature_frame() -> pd.DataFrame:
    labels = {bearing.code: bearing.primary_label for bearing in BEARING_METADATA}
    excluded_keys = {
        (
            parse_measurement_filename(filename).bearing_code,
            parse_measurement_filename(filename).setting_code,
            parse_measurement_filename(filename).measurement_index,
        )
        for filename in STRUCTURALLY_EXCLUDED_FILENAMES
    }
    metadata = pd.DataFrame(
        [
            {
                "bearing_code": bearing,
                "setting_code": setting.code,
                "measurement_index": measurement,
                "truth": labels[bearing],
            }
            for bearing, setting, measurement in product(
                PRIMARY_BEARING_CODES,
                OPERATING_SETTINGS,
                MEASUREMENT_INDICES,
            )
            if (bearing, setting.code, measurement) not in excluded_keys
        ]
    )
    rows = np.arange(len(metadata), dtype=float)[:, None]
    columns = np.arange(1, len(main_signal_feature_names()) + 1, dtype=float)[None, :]
    features = pd.DataFrame(
        np.sin(rows / columns),
        columns=main_signal_feature_names(),
    )
    return pd.concat((metadata, features), axis=1)


def run(output_directory: Path) -> dict[str, object]:
    frame = _synthetic_feature_frame()
    folds = build_paderborn_model_folds(frame)
    target_counts = np.zeros(len(frame), dtype=int)
    fold_records = []
    for model_fold in folds:
        target_counts[model_fold.target_global_indices] += 1
        fold_records.append(
            {
                "fold_id": model_fold.fold.fold_id,
                "held_bearing_codes": list(model_fold.held_bearing_codes),
                "held_setting_code": model_fold.held_setting_code,
                "source_rows": len(model_fold.source_global_indices),
                "target_rows": len(model_fold.target_global_indices),
                "quarantine_rows": len(model_fold.quarantine_global_indices),
                "trainer_visible_rows": len(model_fold.fold.features),
                "source_environment_count": int(
                    len(np.unique(model_fold.fold.source_environments))
                ),
                "target_environment_count": int(
                    len(np.unique(model_fold.fold.target_environments))
                ),
                "nuisance_pairs": len(model_fold.fold.nuisance_pairs),
                "fault_pairs": len(model_fold.fold.fault_pairs),
                "source_coordinates_local": bool(
                    np.array_equal(
                        model_fold.fold.source_indices,
                        np.arange(len(model_fold.source_global_indices)),
                    )
                ),
                "quarantine_exposed_to_trainer": False,
            }
        )
    manifest: dict[str, object] = {
        "manifest_version": "paderborn-model-fold-schema-0.2.0",
        "generated_at": datetime.now(UTC).isoformat(),
        "status": "amended synthetic schema validation before D2 model outcomes",
        "synthetic_feature_fixture": True,
        "feature_count": len(main_signal_feature_names()),
        "pure_measurements": len(frame),
        "outer_folds": len(folds),
        "all_measurements_target_exactly_once": bool(np.all(target_counts == 1)),
        "minimum_target_count": int(target_counts.min()),
        "maximum_target_count": int(target_counts.max()),
        "archive_contents_opened_before_amendment": True,
        "signal_features_used_to_define_folds": False,
        "structurally_excluded_filenames": list(STRUCTURALLY_EXCLUDED_FILENAMES),
        "model_outcomes_inspected": False,
        "folds": fold_records,
    }
    output_directory.mkdir(parents=True, exist_ok=True)
    (output_directory / "model_fold_manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-directory", type=Path, required=True)
    args = parser.parse_args()
    result = run(args.output_directory)
    print(
        json.dumps(
            {
                "outer_folds": result["outer_folds"],
                "pure_measurements": result["pure_measurements"],
                "all_measurements_target_exactly_once": result[
                    "all_measurements_target_exactly_once"
                ],
                "model_outcomes_inspected": result["model_outcomes_inspected"],
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
