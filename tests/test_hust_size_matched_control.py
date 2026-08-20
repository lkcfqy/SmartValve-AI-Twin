from __future__ import annotations

import numpy as np
import pandas as pd

from smartvalve.data.hust import HUST_LABELS, HUST_WINDOWS_PER_RECORDING, hust_feature_names
from smartvalve.experiments.hust_size_matched_control import (
    REFERENCE_PROTOCOL,
    SIZE_MATCHED_PROTOCOL,
    aggregate_hust_size_matched_records,
    bootstrap_hust_size_matched_comparison,
    build_hust_size_matched_model_folds,
    build_hust_size_matched_splits,
    hust_size_matched_gate,
    hust_size_matched_rank_concordance,
    score_hust_size_matched_comparison,
)


def _feature_frame() -> pd.DataFrame:
    records = []
    for label, prefix in zip(HUST_LABELS, ("N", "O", "I"), strict=True):
        for group in range(4, 9):
            for load in (0, 200, 400):
                filename = f"{prefix}{group}-{load}.mat"
                for window in range(HUST_WINDOWS_PER_RECORDING):
                    record: dict[str, object] = {
                        "filename": filename,
                        "bearing_code": f"{prefix}{group}",
                        "specification_group": group,
                        "load_w": load,
                        "truth": label,
                        "window_index": window,
                        "evaluation_cell": f"specification={group}|load_w={load}",
                    }
                    for number, feature in enumerate(hust_feature_names(), start=1):
                        record[feature] = float(group + load / 1000 + window / 100 + number / 10000)
                    records.append(record)
    return pd.DataFrame(records)


def test_size_matched_topology_exposes_both_factors_at_equal_volume() -> None:
    frame = _feature_frame()
    splits = build_hust_size_matched_splits(frame)

    assert len(splits) == 15
    target_counts = np.zeros(len(frame), dtype=int)
    for split in splits:
        split.validate(frame)
        target_counts[split.target_indices] += 1
        source = frame.iloc[split.source_indices]
        target = frame.iloc[split.target_indices]
        inaccessible = frame.iloc[split.inaccessible_indices]
        assert source["filename"].nunique() == 24
        assert target["filename"].nunique() == 3
        assert inaccessible["filename"].nunique() == 18
        assert set(target["bearing_code"]) <= set(source["bearing_code"])
        assert set(target["filename"]).isdisjoint(set(source["filename"]))
        assert set(source["load_w"]) == {0, 200, 400}
        assert set(source["specification_group"]) == set(range(4, 9))
    np.testing.assert_array_equal(target_counts, np.ones(len(frame), dtype=int))


def test_size_matched_model_folds_preserve_crossed_pair_budget() -> None:
    folds = build_hust_size_matched_model_folds(_feature_frame())

    assert len(folds) == 15
    for model_fold in folds:
        model_fold.fold.validate()
        assert model_fold.protocol == SIZE_MATCHED_PROTOCOL
        assert len(model_fold.fold.source_indices) == 240
        assert len(model_fold.fold.target_indices) == 30
        assert len(model_fold.quarantine_global_indices) == 180
        assert len(model_fold.fold.nuisance_pairs) == 120
        assert len(model_fold.fold.fault_pairs) == 240


def _size_matched_window_predictions(frame: pd.DataFrame) -> pd.DataFrame:
    methods = ("alpha", "beta", "gamma")
    records = []
    for method in methods:
        for row_index, row in frame.iterrows():
            probabilities = {label: 0.05 for label in HUST_LABELS}
            probabilities[str(row["truth"])] = 0.90
            records.append(
                {
                    "protocol": SIZE_MATCHED_PROTOCOL,
                    "method": method,
                    "row_index": row_index,
                    "fold_id": str(row["evaluation_cell"]),
                    **row.loc[
                        [
                            "filename",
                            "bearing_code",
                            "specification_group",
                            "load_w",
                            "truth",
                            "window_index",
                            "evaluation_cell",
                        ]
                    ].to_dict(),
                    **{f"probability_{label}": probabilities[label] for label in HUST_LABELS},
                    "prediction": str(row["truth"]),
                }
            )
    return pd.DataFrame(records)


def test_size_matched_evaluation_pairs_the_same_recordings() -> None:
    frame = _feature_frame()
    size_records = aggregate_hust_size_matched_records(_size_matched_window_predictions(frame))
    crossed = size_records.copy()
    crossed["protocol"] = REFERENCE_PROTOCOL
    label_cycle = {
        HUST_LABELS[0]: HUST_LABELS[1],
        HUST_LABELS[1]: HUST_LABELS[2],
        HUST_LABELS[2]: HUST_LABELS[0],
    }
    crossed.loc[crossed["method"] == "alpha", "prediction"] = crossed.loc[
        crossed["method"] == "alpha", "truth"
    ].map(label_cycle)
    beta_rows = crossed["method"] == "beta"
    crossed.loc[beta_rows & (crossed["load_w"] == 0), "prediction"] = crossed.loc[
        beta_rows & (crossed["load_w"] == 0), "truth"
    ].map(label_cycle)
    size_records.loc[size_records["method"] == "gamma", "prediction"] = size_records.loc[
        size_records["method"] == "gamma", "truth"
    ].map(label_cycle)

    aggregate, cells = score_hust_size_matched_comparison(size_records, crossed)
    concordance = hust_size_matched_rank_concordance(aggregate)
    combined = pd.concat((size_records, crossed), ignore_index=True)
    summary, draws, plan = bootstrap_hust_size_matched_comparison(combined, draws=25)
    gate = hust_size_matched_gate(aggregate, concordance)

    assert len(aggregate) == 6
    assert len(cells) == 90
    assert len(concordance) == 2
    assert concordance.loc[concordance["metric"] == "pooled_macro_f1", "kendall_tau"].item() < -0.8
    assert len(summary) == 3
    assert len(draws) == 75
    assert plan.shape == (25, 15)
    assert gate["positive_method_count"] == 2
    assert not gate["access_effect_rule_passed"]
