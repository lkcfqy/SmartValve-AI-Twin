from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest

from smartvalve.experiments.selective_input_preflight import (
    validate_reference_prediction_topology,
)


def _fixture() -> tuple[SimpleNamespace, dict[str, list[SimpleNamespace]]]:
    fold = SimpleNamespace(
        fold_id="context=held",
        target_indices=np.array([1, 3]),
        labels=np.array([0, 0, 1, 1]),
        label_names=("healthy", "fault"),
        environment_ids=np.array(["source", "held", "source", "held"]),
        block_ids=np.array(["b0", "b1", "b2", "b3"]),
    )
    rows = []
    hashes = {}
    for method in ("erm", "pirl_ratio"):
        for seed in (11, 23):
            hashes[("synthetic", method, seed, fold.fold_id)] = f"hash-{method}-{seed}"
            for row_index, truth, prediction, p_healthy in (
                (1, "healthy", "healthy", 0.8),
                (3, "fault", "healthy", 0.6),
            ):
                rows.append(
                    {
                        "dataset": "synthetic",
                        "method": method,
                        "seed": seed,
                        "fold_id": fold.fold_id,
                        "row_index": row_index,
                        "environment_id": "held",
                        "block_id": f"b{row_index}",
                        "truth": truth,
                        "prediction": prediction,
                        "correct": truth == prediction,
                        "probability_healthy": p_healthy,
                        "probability_fault": 1.0 - p_healthy,
                    }
                )
    references = SimpleNamespace(
        predictions=pd.DataFrame(rows), model_state_sha256=hashes
    )
    return references, {"synthetic": [fold]}


def test_reference_prediction_preflight_validates_exact_fold_topology() -> None:
    references, datasets = _fixture()

    result = validate_reference_prediction_topology(
        references,
        datasets,
        methods=("erm", "pirl_ratio"),
        seeds=(11, 23),
    )

    assert result["groups"] == 4
    assert result["model_states"] == 4
    assert result["prediction_rows"] == 8
    assert len(result["prediction_key_sha256"]) == 64
    assert result["maximum_probability_sum_error"] == pytest.approx(0.0)


@pytest.mark.parametrize(
    ("column", "value", "message"),
    [
        ("row_index", 0, "row indices"),
        ("environment_id", "wrong", "environment"),
        ("block_id", "wrong", "physical block"),
        ("truth", "fault", "truth"),
        ("correct", False, "correctness"),
        ("probability_healthy", 1.2, "probabilities"),
    ],
)
def test_reference_prediction_preflight_rejects_drift(
    column: str, value: object, message: str
) -> None:
    references, datasets = _fixture()
    references.predictions.loc[0, column] = value

    with pytest.raises(ValueError, match=message):
        validate_reference_prediction_topology(
            references,
            datasets,
            methods=("erm", "pirl_ratio"),
            seeds=(11, 23),
        )


def test_reference_prediction_preflight_rejects_state_key_drift() -> None:
    references, datasets = _fixture()
    references.model_state_sha256.pop(next(iter(references.model_state_sha256)))

    with pytest.raises(ValueError, match="model-state keys"):
        validate_reference_prediction_topology(
            references,
            datasets,
            methods=("erm", "pirl_ratio"),
            seeds=(11, 23),
        )


def test_reference_prediction_preflight_has_no_filesystem_side_effect(tmp_path: Path) -> None:
    references, datasets = _fixture()
    validate_reference_prediction_topology(
        references,
        datasets,
        methods=("erm", "pirl_ratio"),
        seeds=(11, 23),
    )
    assert list(tmp_path.iterdir()) == []
