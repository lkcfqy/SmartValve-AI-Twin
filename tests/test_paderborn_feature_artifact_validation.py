from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pandas as pd
import pytest

from smartvalve.data.paderborn import (
    ARCHIVE_NAMES,
    BEARING_METADATA,
    OPERATING_SETTINGS,
)
from smartvalve.data.paderborn_features import (
    MAIN_SIGNAL_ENDPOINT_POLICY,
    MAXIMUM_STORED_SAMPLES_PER_MAIN_SIGNAL,
    MINIMUM_STORED_SAMPLES_PER_MAIN_SIGNAL,
    SAMPLES_PER_MAIN_SIGNAL,
    STRUCTURALLY_EXCLUDED_FILENAMES,
    expected_measurement_filenames,
    main_signal_feature_names,
    parse_measurement_filename,
    retained_measurement_filenames,
)
from smartvalve.experiments.paderborn_feature_artifact_validation import (
    EXPECTED_EXCLUDED_BYTES,
    EXPECTED_EXCLUDED_SHA256,
    EXPECTED_STATUS,
    validate_paderborn_feature_artifacts,
)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _artifact(path: Path, **counts: int) -> dict[str, object]:
    return {
        "path": path.name,
        **counts,
        "bytes": path.stat().st_size,
        "sha256": _sha256(path),
    }


def _write_fixture(root: Path, amendment_sha256: str) -> Path:
    bearings = {item.code: item for item in BEARING_METADATA}
    settings = {item.code: item for item in OPERATING_SETTINGS}
    rows = []
    for row_index, filename in enumerate(retained_measurement_filenames()):
        key = parse_measurement_filename(filename)
        bearing = bearings[key.bearing_code]
        setting = settings[key.setting_code]
        row = {
            "filename": filename,
            "bearing_code": key.bearing_code,
            "setting_code": key.setting_code,
            "measurement_index": key.measurement_index,
            "truth": bearing.primary_label,
            "damage_origin": bearing.damage_origin,
            "component": bearing.component,
            "damage_extent": bearing.damage_extent,
            "speed_rpm": setting.speed_rpm,
            "torque_nm": setting.torque_nm,
            "radial_force_n": setting.radial_force_n,
        }
        row.update(
            {
                name: float((row_index + feature_index) % 17)
                for feature_index, name in enumerate(main_signal_feature_names())
            }
        )
        rows.append(row)
    full = pd.DataFrame(rows)
    primary = full.loc[full["truth"] != "compound"].reset_index(drop=True)

    inventory_rows = []
    retained = set(retained_measurement_filenames())
    included_number = 0
    for filename in expected_measurement_filenames():
        key = parse_measurement_filename(filename)
        if filename in retained:
            stored = SAMPLES_PER_MAIN_SIGNAL
            if included_number == 0:
                stored = MINIMUM_STORED_SAMPLES_PER_MAIN_SIGNAL
            elif included_number == 1:
                stored = MAXIMUM_STORED_SAMPLES_PER_MAIN_SIGNAL
            inventory_rows.append(
                {
                    "archive_filename": f"{key.bearing_code}.rar",
                    "archive_member_path": f"{key.bearing_code}/{filename}",
                    "filename": filename,
                    "bytes": 10,
                    "sha256": "a" * 64,
                    "stored_samples_per_channel": stored,
                    "retained_samples_per_channel": SAMPLES_PER_MAIN_SIGNAL,
                    "feature_status": "included",
                }
            )
            included_number += 1
        else:
            assert filename in STRUCTURALLY_EXCLUDED_FILENAMES
            inventory_rows.append(
                {
                    "archive_filename": "KA08.rar",
                    "archive_member_path": f"KA08/{filename}",
                    "filename": filename,
                    "bytes": EXPECTED_EXCLUDED_BYTES,
                    "sha256": EXPECTED_EXCLUDED_SHA256,
                    "stored_samples_per_channel": None,
                    "retained_samples_per_channel": None,
                    "feature_status": "structurally_excluded_unreadable_mat",
                }
            )
    inventory = pd.DataFrame(inventory_rows)
    traces = [{"archive_filename": archive, "exit_code": 0} for archive in ARCHIVE_NAMES]
    quarantined = [
        {
            "archive_filename": archive,
            "archive_member_path": f"{archive.removesuffix('.rar')}/meta-{index}.pdf",
            "handling": "quarantined_not_parsed_not_used",
        }
        for archive in ARCHIVE_NAMES
        for index in range(2)
    ]

    feature_path = root / "feature_matrix.parquet"
    primary_path = root / "primary_feature_matrix.parquet"
    inventory_path = root / "mat_inventory.parquet"
    traces_path = root / "extraction_traces.json"
    quarantine_path = root / "quarantined_non_mat.json"
    full.to_parquet(feature_path, index=False)
    primary.to_parquet(primary_path, index=False)
    inventory.to_parquet(inventory_path, index=False)
    traces_path.write_text(json.dumps(traces), encoding="utf-8")
    quarantine_path.write_text(json.dumps(quarantined), encoding="utf-8")
    metrics = {
        "status": EXPECTED_STATUS,
        "input": {"feature_contract_amendment_sha256": amendment_sha256},
        "corpus": {
            "measurement_count": 2_559,
            "locked_mat_count": 2_560,
            "structurally_excluded_mat_count": 1,
            "primary_measurement_count": 2_319,
            "compound_measurement_count": 240,
            "feature_count": 72,
            "model_fold_count": 24,
            "quarantined_non_mat_count": 64,
            "endpoint_policy": MAIN_SIGNAL_ENDPOINT_POLICY,
        },
        "artifacts": {
            "feature_matrix": _artifact(feature_path, rows=len(full)),
            "primary_feature_matrix": _artifact(primary_path, rows=len(primary)),
            "mat_inventory": _artifact(inventory_path, rows=len(inventory)),
            "extraction_traces": _artifact(traces_path, archives=len(traces)),
            "quarantined_non_mat": _artifact(quarantine_path, files=len(quarantined)),
        },
        "access_attestation": {
            "model_fitted": False,
            "model_outcomes_inspected": False,
            "target_guided_reselection_performed": False,
            "quarantined_non_mat_files_used": False,
        },
    }
    metrics_path = root / "metrics.json"
    metrics_path.write_text(json.dumps(metrics), encoding="utf-8")
    return metrics_path


def test_feature_artifact_validator_checks_exact_exclusion_and_topology(
    tmp_path: Path,
) -> None:
    amendment_sha256 = "b" * 64
    metrics_path = _write_fixture(tmp_path, amendment_sha256)

    result = validate_paderborn_feature_artifacts(
        metrics_path=metrics_path,
        expected_metrics_sha256=_sha256(metrics_path),
        expected_feature_amendment_sha256=amendment_sha256,
    )

    assert result["status"] == "passed_before_paderborn_model_outcome_access"
    assert result["counts"]["measurement_count"] == 2_559
    assert result["counts"]["minimum_target_coverage"] == 1
    assert result["structural_exclusion"]["sha256"] == EXPECTED_EXCLUDED_SHA256

    with pytest.raises(ValueError, match="metrics SHA-256"):
        validate_paderborn_feature_artifacts(
            metrics_path=metrics_path,
            expected_metrics_sha256="0" * 64,
            expected_feature_amendment_sha256=amendment_sha256,
        )
