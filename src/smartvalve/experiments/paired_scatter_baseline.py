"""Closed-form paired-scatter baseline for retrospective DG diagnosis.

This module deliberately implements a *baseline*, not a novel SmartValve method.
Its generalized-eigenvalue objective is closely related to Fisher discriminant
analysis, DICA, SCA, MDA, and invariant-feature subspace recovery.  The only
project-specific ingredient is the audited nuisance/fault pair topology already
carried by :class:`~smartvalve.experiments.domain_data.SourceOnlyFold`.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from scipy.linalg import eigh
from sklearn.discriminant_analysis import LinearDiscriminantAnalysis


@dataclass(frozen=True)
class PairedScatterProjector:
    """Source-fitted standardization and ordered generalized eigenvectors."""

    mean: np.ndarray
    scale: np.ndarray
    components: np.ndarray
    eigenvalues: np.ndarray
    nuisance_scatter: np.ndarray
    fault_scatter: np.ndarray
    ridge: float

    def transform(
        self,
        features: np.ndarray,
        *,
        n_components: int | None = None,
    ) -> np.ndarray:
        """Standardize and project rows onto the leading ordered components."""

        values = _as_feature_matrix(features)
        if values.shape[1] != self.mean.size:
            raise ValueError("feature dimension differs from the fitted projector")
        count = self.components.shape[1] if n_components is None else n_components
        if not 1 <= count <= self.components.shape[1]:
            raise ValueError("n_components falls outside the fitted component range")
        standardized = (values - self.mean) / self.scale
        return standardized @ self.components[:, :count]


@dataclass
class PairedScatterLDA:
    """A paired-scatter projection followed by shrinkage LDA."""

    projector: PairedScatterProjector
    n_components: int
    classifier: LinearDiscriminantAnalysis
    classes: np.ndarray

    def predict_proba(self, features: np.ndarray) -> np.ndarray:
        projected = self.projector.transform(
            features,
            n_components=self.n_components,
        )
        probabilities = self.classifier.predict_proba(projected)
        if not np.array_equal(self.classifier.classes_, self.classes):
            raise ValueError("fitted LDA class order changed")
        return np.asarray(probabilities, dtype=np.float64)

    def predict(self, features: np.ndarray) -> np.ndarray:
        return self.classes[np.argmax(self.predict_proba(features), axis=1)]


def _as_feature_matrix(features: np.ndarray) -> np.ndarray:
    values = np.asarray(features, dtype=np.float64)
    if values.ndim != 2 or values.shape[0] < 2 or values.shape[1] < 1:
        raise ValueError("features must be a non-trivial two-dimensional matrix")
    if not np.isfinite(values).all():
        raise ValueError("features contain non-finite values")
    return values


def _validated_pairs(pairs: np.ndarray, *, row_count: int, name: str) -> np.ndarray:
    values = np.asarray(pairs)
    if values.ndim != 2 or values.shape[1] != 2 or len(values) == 0:
        raise ValueError(f"{name} pairs must be a non-empty two-column matrix")
    if not np.issubdtype(values.dtype, np.integer) and not np.equal(
        values, np.floor(values)
    ).all():
        raise ValueError(f"{name} pairs must contain integer indices")
    values = values.astype(np.int64, copy=False)
    if values.min() < 0 or values.max() >= row_count:
        raise ValueError(f"{name} pairs point outside the feature matrix")
    if np.any(values[:, 0] == values[:, 1]):
        raise ValueError(f"{name} pairs contain self-pairs")
    return values


def pair_difference_scatter(features: np.ndarray, pairs: np.ndarray) -> np.ndarray:
    """Return the mean outer product of the declared pair differences."""

    values = _as_feature_matrix(features)
    pair_indices = _validated_pairs(pairs, row_count=len(values), name="response")
    differences = values[pair_indices[:, 0]] - values[pair_indices[:, 1]]
    scatter = differences.T @ differences / len(differences)
    return (scatter + scatter.T) * 0.5


def _canonicalize_component_signs(components: np.ndarray) -> np.ndarray:
    canonical = components.copy()
    for index in range(canonical.shape[1]):
        column = canonical[:, index]
        anchor = int(np.argmax(np.abs(column)))
        if column[anchor] < 0:
            canonical[:, index] *= -1.0
    return canonical


def fit_paired_scatter_projector(
    source_features: np.ndarray,
    nuisance_pairs: np.ndarray,
    fault_pairs: np.ndarray,
    *,
    max_components: int,
    ridge: float = 1e-3,
    scale_floor: float = 1e-12,
) -> PairedScatterProjector:
    """Fit a source-only fault-to-nuisance generalized Rayleigh projection.

    The ordered columns solve ``S_fault v = lambda (S_nuisance + ridge I) v``
    after source-only z-standardization.  The scatter matrices use audited pair
    differences rather than unpaired marginal domain means.
    """

    values = _as_feature_matrix(source_features)
    if not 1 <= max_components <= values.shape[1]:
        raise ValueError("max_components must lie within the feature dimension")
    if ridge <= 0 or scale_floor <= 0:
        raise ValueError("ridge and scale_floor must be positive")
    nuisance = _validated_pairs(
        nuisance_pairs,
        row_count=len(values),
        name="nuisance",
    )
    fault = _validated_pairs(
        fault_pairs,
        row_count=len(values),
        name="fault",
    )
    mean = values.mean(axis=0)
    raw_scale = values.std(axis=0, ddof=0)
    scale = np.where(raw_scale > scale_floor, raw_scale, 1.0)
    standardized = (values - mean) / scale
    nuisance_scatter = pair_difference_scatter(standardized, nuisance)
    fault_scatter = pair_difference_scatter(standardized, fault)
    regularized_nuisance = nuisance_scatter + ridge * np.eye(values.shape[1])
    eigenvalues, eigenvectors = eigh(
        fault_scatter,
        regularized_nuisance,
        check_finite=True,
        driver="gvd",
    )
    order = np.argsort(eigenvalues, kind="stable")[::-1][:max_components]
    ordered_values = np.asarray(eigenvalues[order], dtype=np.float64)
    ordered_vectors = _canonicalize_component_signs(
        np.asarray(eigenvectors[:, order], dtype=np.float64)
    )
    if not np.isfinite(ordered_values).all() or not np.isfinite(ordered_vectors).all():
        raise ValueError("generalized eigensolver returned non-finite values")
    return PairedScatterProjector(
        mean=mean,
        scale=scale,
        components=ordered_vectors,
        eigenvalues=ordered_values,
        nuisance_scatter=nuisance_scatter,
        fault_scatter=fault_scatter,
        ridge=float(ridge),
    )


def fit_paired_scatter_lda(
    source_features: np.ndarray,
    source_labels: np.ndarray,
    nuisance_pairs: np.ndarray,
    fault_pairs: np.ndarray,
    *,
    n_components: int = 4,
    ridge: float = 1e-3,
) -> PairedScatterLDA:
    """Fit the paired projection and a deterministic shrinkage-LDA head."""

    values = _as_feature_matrix(source_features)
    labels = np.asarray(source_labels)
    if labels.ndim != 1 or len(labels) != len(values):
        raise ValueError("source labels do not align with source features")
    classes = np.unique(labels)
    if len(classes) < 2:
        raise ValueError("at least two source classes are required")
    projector = fit_paired_scatter_projector(
        values,
        nuisance_pairs,
        fault_pairs,
        max_components=n_components,
        ridge=ridge,
    )
    projected = projector.transform(values, n_components=n_components)
    classifier = LinearDiscriminantAnalysis(solver="lsqr", shrinkage="auto")
    classifier.fit(projected, labels)
    return PairedScatterLDA(
        projector=projector,
        n_components=n_components,
        classifier=classifier,
        classes=classes,
    )
