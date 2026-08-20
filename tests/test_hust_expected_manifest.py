from __future__ import annotations

import pandas as pd

from smartvalve.data.hust import HUST_LABELS
from smartvalve.experiments.hust_expected_manifest import (
    EXPECTED_COUNTS,
    _expected_keys,
    _split_manifest,
    metadata_window_frame,
)


def _primary_inventory() -> pd.DataFrame:
    records = []
    for condition, truth in (("N", "healthy"), ("I", "inner"), ("O", "outer")):
        for group in range(4, 9):
            for load in (0, 200, 400):
                records.append(
                    {
                        "filename": f"{condition}{group}0{load // 100}.mat",
                        "file_id": f"id-{condition}-{group}-{load}",
                        "condition": condition,
                        "specification_group": group,
                        "load_w": load,
                        "bearing_code": f"{condition}{group}",
                        "truth": truth,
                        "bytes": 10,
                        "sha256": "a" * 64,
                    }
                )
    return pd.DataFrame(records).sort_values(
        ["condition", "specification_group", "load_w"], kind="stable"
    )


def test_metadata_only_hust_manifest_freezes_all_prediction_keys() -> None:
    frame = metadata_window_frame(_primary_inventory())
    keys = _expected_keys(frame)
    splits = _split_manifest(frame)

    assert len(frame) == EXPECTED_COUNTS["window_rows"]
    assert set(frame["truth"]) == set(HUST_LABELS)
    assert len(splits) == EXPECTED_COUNTS["folds"]
    assert keys["training_fits"]["count"] == EXPECTED_COUNTS["fit_count"]
    assert keys["seed_window_predictions"]["count"] == EXPECTED_COUNTS["seed_window_predictions"]
    assert (
        keys["ensemble_window_predictions"]["count"]
        == EXPECTED_COUNTS["ensemble_window_predictions"]
    )
    assert keys["recording_predictions"]["count"] == EXPECTED_COUNTS["recording_predictions"]
    crossed = splits.loc[splits["protocol"] == "crossed_holdout"]
    assert len(crossed) == 15
    assert crossed["source_nuisance_pairs"].eq(120).all()
    assert crossed["source_fault_pairs"].eq(240).all()


def test_metadata_expected_keys_are_deterministic() -> None:
    frame = metadata_window_frame(_primary_inventory())

    assert _expected_keys(frame) == _expected_keys(frame.copy())
