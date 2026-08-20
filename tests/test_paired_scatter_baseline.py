from __future__ import annotations

import numpy as np
import pytest

from smartvalve.experiments.paired_scatter_baseline import (
    fit_paired_scatter_lda,
    fit_paired_scatter_projector,
    pair_difference_scatter,
)


def _factorial_fixture() -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    features = np.asarray(
        [
            [-2.0, -3.0],
            [-2.0, 3.0],
            [2.0, -3.0],
            [2.0, 3.0],
            [-1.8, -2.5],
            [-1.8, 2.5],
            [1.8, -2.5],
            [1.8, 2.5],
        ]
    )
    labels = np.asarray([0, 0, 1, 1, 0, 0, 1, 1])
    nuisance_pairs = np.asarray([[0, 1], [2, 3], [4, 5], [6, 7]])
    fault_pairs = np.asarray([[0, 2], [1, 3], [4, 6], [5, 7]])
    return features, labels, nuisance_pairs, fault_pairs


def test_pair_difference_scatter_is_orientation_invariant() -> None:
    features = np.asarray([[0.0, 0.0], [2.0, 1.0], [1.0, 4.0]])
    pairs = np.asarray([[0, 1], [0, 2]])

    observed = pair_difference_scatter(features, pairs)
    reversed_pairs = pair_difference_scatter(features, pairs[:, ::-1])

    expected = np.asarray([[2.5, 3.0], [3.0, 8.5]])
    np.testing.assert_allclose(observed, expected)
    np.testing.assert_allclose(reversed_pairs, expected)


def test_projector_prefers_fault_axis_over_nuisance_axis() -> None:
    features, _, nuisance_pairs, fault_pairs = _factorial_fixture()

    projector = fit_paired_scatter_projector(
        features,
        nuisance_pairs,
        fault_pairs,
        max_components=2,
    )

    assert projector.components[0, 0] > 0
    assert abs(projector.components[0, 0]) > 100 * abs(projector.components[1, 0])
    assert projector.eigenvalues[0] > projector.eigenvalues[1]


def test_paired_scatter_lda_is_deterministic_and_predictive() -> None:
    features, labels, nuisance_pairs, fault_pairs = _factorial_fixture()

    first = fit_paired_scatter_lda(
        features,
        labels,
        nuisance_pairs,
        fault_pairs,
        n_components=1,
    )
    second = fit_paired_scatter_lda(
        features,
        labels,
        nuisance_pairs,
        fault_pairs,
        n_components=1,
    )

    np.testing.assert_allclose(first.projector.components, second.projector.components)
    np.testing.assert_allclose(first.predict_proba(features), second.predict_proba(features))
    np.testing.assert_array_equal(first.predict(features), labels)
    np.testing.assert_allclose(first.predict_proba(features).sum(axis=1), 1.0)


@pytest.mark.parametrize(
    ("pairs", "message"),
    [
        (np.empty((0, 2), dtype=int), "non-empty"),
        (np.asarray([[0, 0]]), "self-pairs"),
        (np.asarray([[0, 99]]), "outside"),
    ],
)
def test_projector_rejects_invalid_pairs(pairs: np.ndarray, message: str) -> None:
    features, _, _, fault_pairs = _factorial_fixture()

    with pytest.raises(ValueError, match=message):
        fit_paired_scatter_projector(
            features,
            pairs,
            fault_pairs,
            max_components=1,
        )
