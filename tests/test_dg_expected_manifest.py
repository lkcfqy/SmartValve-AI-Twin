from __future__ import annotations

from dataclasses import replace
from itertools import product

import pandas as pd
import pytest

pytest.importorskip("torch")

from smartvalve.experiments.cranfield_benchmark import (  # noqa: E402
    LABELS,
    LOADS,
    MOTIONS,
    REPETITIONS,
)
from smartvalve.experiments.dg_expected_manifest import (  # noqa: E402
    build_expected_manifest,
    canonical_key_record,
    run_manifest,
)
from smartvalve.experiments.dg_training import BASELINE_METHODS  # noqa: E402
from smartvalve.experiments.domain_data import build_cranfield_folds  # noqa: E402


def _frame() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "motion": motion,
                "load_kg": load,
                "repetition": repetition,
                "truth": label,
                "feature": float(load + LABELS.index(label)),
            }
            for motion, label, load, repetition in product(
                MOTIONS, LABELS, LOADS, REPETITIONS
            )
        ]
    )


def test_canonical_key_hash_is_order_invariant_and_rejects_duplicates() -> None:
    rows = [("b", 2), ("a", 1)]

    forward = canonical_key_record(rows, ("name", "index"))
    reverse = canonical_key_record(reversed(rows), ("name", "index"))

    assert forward == reverse
    assert forward["count"] == 2
    with pytest.raises(ValueError, match="duplicate"):
        canonical_key_record([("a", 1), ("a", 1)], ("name", "index"))


def test_manifest_freezes_all_candidate_tuning_final_and_prediction_keys() -> None:
    cranfield = build_cranfield_folds(_frame())[0]
    uci_like = replace(cranfield, dataset="uci_hydraulic")
    manifest = build_expected_manifest(
        {"cranfield": [cranfield], "uci_hydraulic": [uci_like]},
        uci_feature_matrix="fixture.parquet",
        uci_feature_matrix_sha256="a" * 64,
    )

    keys = manifest["expected_key_sets"]
    target_rows = len(cranfield.target_indices) * 2
    assert manifest["configuration"]["candidate_count"] == 44
    assert keys["candidate_metrics"]["count"] == 44 * 2
    assert keys["tuning_models"]["count"] == 44 * 2 * 4
    assert keys["outer_selections"]["count"] == len(BASELINE_METHODS) * 2
    assert keys["final_models"]["count"] == len(BASELINE_METHODS) * 2 * 5
    assert keys["target_predictions"]["count"] == (
        target_rows * len(BASELINE_METHODS) * 5
    )
    assert keys["target_provenance"]["count"] == target_rows


def test_manifest_checks_uci_hash_before_loading_features(tmp_path) -> None:
    feature_path = tmp_path / "feature.parquet"
    feature_path.write_bytes(b"not a parquet file")

    with pytest.raises(ValueError, match="hash differs"):
        run_manifest(
            feature_path,
            tmp_path / "manifest.json",
            expected_uci_sha256="0" * 64,
        )
