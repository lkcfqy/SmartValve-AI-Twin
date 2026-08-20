from __future__ import annotations

import numpy as np
import pandas as pd

from smartvalve.data.hust import HUST_LABELS
from smartvalve.experiments.hust_evaluation import (
    aggregate_hust_record_predictions,
    bootstrap_hust_record_predictions,
    ensemble_hust_seed_windows,
    hust_confusion_counts,
    hust_protocol_effect_table,
    hust_rank_concordance,
    hust_replication_gate,
    score_hust_record_predictions,
)
from smartvalve.experiments.hust_protocol import HUST_PROTOCOLS


def _seed_predictions() -> pd.DataFrame:
    records = []
    label_to_index = {label: index for index, label in enumerate(HUST_LABELS)}
    row_index = 0
    for group in range(4, 9):
        for truth in HUST_LABELS:
            bearing_code = f"{truth[0]}{group}"
            for load in (0, 200, 400):
                filename = f"{bearing_code}-{load}.mat"
                for window in range(10):
                    for protocol in HUST_PROTOCOLS:
                        for method in ("a", "b"):
                            predicted = truth
                            if protocol == "crossed_holdout" and method == "b":
                                predicted = HUST_LABELS[(label_to_index[truth] + 1) % 3]
                            probabilities = np.full(3, 0.05)
                            probabilities[label_to_index[predicted]] = 0.90
                            for seed in (11, 23):
                                records.append(
                                    {
                                        "protocol": protocol,
                                        "method": method,
                                        "seed": seed,
                                        "fold_id": f"{protocol}-{group}-{load}",
                                        "row_index": row_index,
                                        "filename": filename,
                                        "bearing_code": bearing_code,
                                        "specification_group": group,
                                        "load_w": load,
                                        "truth": truth,
                                        "window_index": window,
                                        "evaluation_cell": f"specification={group}|load_w={load}",
                                        "probability_healthy": probabilities[0],
                                        "probability_outer": probabilities[1],
                                        "probability_inner": probabilities[2],
                                    }
                                )
                    row_index += 1
    return pd.DataFrame(records)


def test_hust_seed_window_record_and_metric_hierarchy() -> None:
    windows = ensemble_hust_seed_windows(_seed_predictions(), expected_seeds=(11, 23))
    recordings = aggregate_hust_record_predictions(windows)
    aggregate, cells = score_hust_record_predictions(recordings)
    effects = hust_protocol_effect_table(aggregate)
    concordance = hust_rank_concordance(aggregate)
    confusion = hust_confusion_counts(recordings)
    gate = hust_replication_gate(aggregate, concordance)

    assert len(windows) == 450 * 4 * 2
    assert len(recordings) == 45 * 4 * 2
    assert len(aggregate) == 4 * 2
    assert len(cells) == 15 * 4 * 2
    assert len(effects) == 3 * 2 * 5
    assert len(concordance) == 12
    assert len(confusion) == 4 * 2 * 9
    assert recordings["window_disagreement_rate"].eq(0.0).all()
    assert gate["positive_method_count"] == 1
    assert not gate["protocol_gap_rule_passed"]
    assert not gate["rank_instability_rule_passed"]


def test_hust_bootstrap_is_physical_bearing_paired_and_deterministic() -> None:
    windows = ensemble_hust_seed_windows(_seed_predictions(), expected_seeds=(11, 23))
    recordings = aggregate_hust_record_predictions(windows)
    first = bootstrap_hust_record_predictions(recordings, draws=23)
    second = bootstrap_hust_record_predictions(recordings, draws=23)

    for left, right in zip(first, second, strict=True):
        pd.testing.assert_frame_equal(left, right)
    summary, draws, plan = first
    assert len(summary) == 3 * 2
    assert len(draws) == 3 * 2 * 23
    assert plan.shape == (23, 15)
    assert plan.sum(axis=1).eq(15).all()
