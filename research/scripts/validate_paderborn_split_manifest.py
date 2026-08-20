"""Emit the metadata-only prospective Paderborn split manifest without opening D2."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from datetime import UTC, datetime
from itertools import product
from pathlib import Path

import pandas as pd

from smartvalve.data.paderborn import (
    BEARING_METADATA,
    COMPOUND_BEARING_CODES,
    OPERATING_SETTINGS,
    PRIMARY_BEARING_CODES,
)
from smartvalve.data.paderborn_features import (
    MAIN_SIGNAL_CHANNELS,
    PADERBORN_SAMPLING_HZ,
    SAMPLES_PER_MAIN_SIGNAL,
    STRUCTURALLY_EXCLUDED_FILENAMES,
    expected_measurement_filenames,
    main_signal_feature_names,
    parse_measurement_filename,
    retained_measurement_filenames,
)
from smartvalve.experiments.paderborn_partitions import (
    MEASUREMENT_INDICES,
    build_paderborn_partitions,
)
from smartvalve.experiments.paderborn_splits import (
    PADERBORN_IDENTITY_FOLDS,
    PADERBORN_OUTER_FOLDS,
    validate_paderborn_identity_folds,
    validate_paderborn_outer_folds,
)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-directory", type=Path, required=True)
    args = parser.parse_args()

    validate_paderborn_identity_folds(PADERBORN_IDENTITY_FOLDS)
    validate_paderborn_outer_folds(PADERBORN_OUTER_FOLDS)
    metadata = {bearing.code: bearing for bearing in BEARING_METADATA}
    excluded_keys = {
        (
            parse_measurement_filename(filename).bearing_code,
            parse_measurement_filename(filename).setting_code,
            parse_measurement_filename(filename).measurement_index,
        )
        for filename in STRUCTURALLY_EXCLUDED_FILENAMES
    }
    synthetic_index = pd.DataFrame(
        [
            {
                "bearing_code": bearing,
                "setting_code": setting.code,
                "measurement_index": measurement,
                "truth": metadata[bearing].primary_label,
            }
            for bearing, setting, measurement in product(
                PRIMARY_BEARING_CODES,
                OPERATING_SETTINGS,
                MEASUREMENT_INDICES,
            )
            if (bearing, setting.code, measurement) not in excluded_keys
        ]
    )
    partitions = build_paderborn_partitions(synthetic_index)
    label_counts = Counter(bearing.primary_label for bearing in BEARING_METADATA)
    origin_counts = Counter(
        (bearing.primary_label, bearing.damage_origin)
        for bearing in BEARING_METADATA
        if bearing.primary_label in {"outer", "inner"}
    )
    payload = {
        "schema_version": "smartvalve-paderborn-split-manifest-0.2.0",
        "generated_at": datetime.now(UTC).isoformat(),
        "status": "candidate_manifest_not_execution_authorization",
        "access_tier": "metadata-plus-frozen-structural-exclusion",
        "seal": {
            "archive_contents_opened_before_amendment": True,
            "signal_features_used_to_define_partitions": False,
            "model_outcomes_inspected": False,
            "structurally_excluded_filenames": list(STRUCTURALLY_EXCLUDED_FILENAMES),
        },
        "cohort": {
            "all_bearing_count": len(BEARING_METADATA),
            "primary_pure_bearing_count": len(PRIMARY_BEARING_CODES),
            "compound_stress_bearing_count": len(COMPOUND_BEARING_CODES),
            "label_counts": dict(sorted(label_counts.items())),
            "damage_origin_counts": {
                f"{label}:{origin}": count
                for (label, origin), count in sorted(origin_counts.items())
            },
            "compound_bearing_codes": list(COMPOUND_BEARING_CODES),
        },
        "operating_settings": [
            {
                "code": setting.code,
                "speed_rpm": setting.speed_rpm,
                "torque_nm": setting.torque_nm,
                "radial_force_n": setting.radial_force_n,
            }
            for setting in OPERATING_SETTINGS
        ],
        "identity_folds": [
            {
                "fold_id": fold.fold_id,
                "bearing_codes": list(fold.bearing_codes),
                "bearings": [
                    {
                        "code": code,
                        "label": metadata[code].primary_label,
                        "damage_origin": metadata[code].damage_origin,
                        "damage_extent": metadata[code].damage_extent,
                    }
                    for code in fold.bearing_codes
                ],
            }
            for fold in PADERBORN_IDENTITY_FOLDS
        ],
        "outer_folds": [
            {
                "fold_id": fold.fold_id,
                "identity_fold_id": fold.identity_fold_id,
                "held_bearing_codes": list(fold.held_bearing_codes),
                "held_setting_code": fold.held_setting_code,
                "source_excludes_held_bearings": True,
                "source_excludes_held_setting": True,
                "target_is_held_bearing_setting_intersection": True,
            }
            for fold in PADERBORN_OUTER_FOLDS
        ],
        "partition_contract": {
            "synthetic_metadata_rows": len(synthetic_index),
            "signal_values_accessed": False,
            "folds": [
                {
                    "fold_id": partition.fold_id,
                    "source_rows": len(partition.source_indices),
                    "target_rows": len(partition.target_indices),
                    "quarantine_rows": len(partition.quarantine_indices),
                    "nuisance_pairs": len(partition.nuisance_pairs),
                    "balanced_fault_pairs": len(partition.fault_pairs),
                    "fault_pairs_per_label_stratum": (len(partition.fault_pairs) // 3),
                }
                for partition in partitions
            ],
        },
        "candidate_signal_contract": {
            "all_locked_mat_files": len(expected_measurement_filenames()),
            "all_retained_mat_files": len(retained_measurement_filenames()),
            "retained_pure_class_mat_files": len(
                retained_measurement_filenames(pure_class_only=True)
            ),
            "main_channels": list(MAIN_SIGNAL_CHANNELS),
            "sampling_hz": PADERBORN_SAMPLING_HZ,
            "samples_per_four_second_channel": SAMPLES_PER_MAIN_SIGNAL,
            "whole_measurement_feature_count": len(main_signal_feature_names()),
            "whole_measurement_feature_names": list(main_signal_feature_names()),
            "signal_features_used_to_define_partitions": False,
        },
        "cluster_unit": "bearing_identity",
        "prediction_unit": "four_second_measurement",
    }
    args.output_directory.mkdir(parents=True, exist_ok=True)
    output = args.output_directory / "paderborn_split_manifest.json"
    output.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(payload, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
