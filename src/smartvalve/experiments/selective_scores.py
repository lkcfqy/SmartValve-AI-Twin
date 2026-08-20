"""Target-blind uncertainty scores for selective-classification comparisons."""

from __future__ import annotations

import numpy as np


def _probability_matrix(probabilities: np.ndarray) -> np.ndarray:
    values = np.asarray(probabilities, dtype=np.float64)
    if (
        values.ndim != 2
        or values.shape[0] == 0
        or values.shape[1] < 2
        or not np.isfinite(values).all()
        or np.any(values < 0)
        or not np.allclose(values.sum(axis=1), 1.0, atol=1e-6)
    ):
        raise ValueError("probabilities must be a finite normalized N x C matrix")
    return values


def _logit_matrix(logits: np.ndarray) -> np.ndarray:
    values = np.asarray(logits, dtype=np.float64)
    if (
        values.ndim != 2
        or values.shape[0] == 0
        or values.shape[1] < 2
        or not np.isfinite(values).all()
    ):
        raise ValueError("logits must be a finite non-empty N x C matrix")
    return values


def maximum_softmax_uncertainty(probabilities: np.ndarray) -> np.ndarray:
    """Return ``1 - max(p)``; larger values mean stronger rejection evidence."""

    values = _probability_matrix(probabilities)
    return 1.0 - values.max(axis=1)


def normalized_predictive_entropy(probabilities: np.ndarray) -> np.ndarray:
    """Return entropy divided by log(class count), in the interval [0, 1]."""

    values = _probability_matrix(probabilities)
    terms = np.where(values > 0, values * np.log(np.maximum(values, 1e-300)), 0.0)
    return -terms.sum(axis=1) / np.log(values.shape[1])


def energy_uncertainty(logits: np.ndarray, *, temperature: float = 1.0) -> np.ndarray:
    """Return negative log-sum-exp energy; larger values are more rejectable."""

    values = _logit_matrix(logits)
    if temperature <= 0:
        raise ValueError("energy temperature must be positive")
    scaled = values / temperature
    maximum = scaled.max(axis=1)
    logsumexp = maximum + np.log(
        np.exp(scaled - maximum[:, None]).sum(axis=1)
    )
    return -temperature * logsumexp


def negative_max_logit(logits: np.ndarray) -> np.ndarray:
    """Return the negative maximum logit so all score directions agree."""

    return -_logit_matrix(logits).max(axis=1)


def pnorm_normalized_max_logit(
    logits: np.ndarray,
    *,
    order: float = 2.0,
    epsilon: float = 1e-12,
) -> np.ndarray:
    """Return negative centered max-logit after row-wise p-norm normalization.

    Row centering removes the additive degree of freedom that leaves softmax
    probabilities unchanged.  This is an explicit SmartValve baseline adaptation,
    not a claim that raw logit energy is shift invariant.
    """

    values = _logit_matrix(logits)
    if order < 1 or epsilon <= 0:
        raise ValueError("p-norm order and epsilon must be valid")
    centered = values - values.mean(axis=1, keepdims=True)
    norms = np.linalg.norm(centered, ord=order, axis=1, keepdims=True)
    normalized = centered / np.maximum(norms, epsilon)
    return -normalized.max(axis=1)


def ensemble_jensen_shannon(probabilities: np.ndarray) -> np.ndarray:
    """Return normalized ensemble Jensen-Shannon disagreement per prediction row."""

    values = np.asarray(probabilities, dtype=np.float64)
    if values.ndim != 3 or values.shape[0] < 2:
        raise ValueError("ensemble probabilities must have shape M x N x C with M >= 2")
    for member in values:
        _probability_matrix(member)
    mean = values.mean(axis=0)
    mean_entropy = normalized_predictive_entropy(mean)
    member_entropy = np.stack(
        [normalized_predictive_entropy(member) for member in values]
    ).mean(axis=0)
    disagreement = mean_entropy - member_entropy
    return np.maximum(disagreement, 0.0)
