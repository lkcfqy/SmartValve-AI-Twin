"""Source-only selection and evaluation of a support-aware abstention threshold."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

import numpy as np


@dataclass(frozen=True)
class SelectivePolicy:
    beta: float
    threshold: float
    source_coverage: float
    source_selective_risk: float
    source_worst_environment_risk: float
    source_minimum_environment_coverage: float
    source_accepted: int

    def to_record(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class SourceCoveragePolicy:
    """A score threshold fixed exclusively from source OOF predictions."""

    score_name: str
    nominal_source_coverage: float
    minimum_source_environment_coverage: float
    threshold: float
    source_coverage: float
    source_selective_risk: float
    source_worst_environment_risk: float
    source_minimum_environment_coverage: float
    source_accepted: int

    def to_record(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class RiskEnvelopeBetaSelection:
    """Source-OOF choice of the support-distance coefficient."""

    beta: float
    source_aurc: float
    source_worst_environment_aurc: float
    candidates: tuple[dict[str, Any], ...]

    def to_record(self) -> dict[str, Any]:
        return asdict(self)


def _validated_inputs(
    uncertainty: np.ndarray,
    distance: np.ndarray,
    errors: np.ndarray,
    environments: np.ndarray,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    uncertainty = np.asarray(uncertainty, dtype=float)
    distance = np.asarray(distance, dtype=float)
    errors = np.asarray(errors, dtype=bool)
    environments = np.asarray(environments)
    lengths = {len(uncertainty), len(distance), len(errors), len(environments)}
    if len(lengths) != 1 or not lengths or next(iter(lengths)) == 0:
        raise ValueError("selective inputs must be aligned and non-empty")
    if (
        uncertainty.ndim != 1
        or distance.ndim != 1
        or errors.ndim != 1
        or environments.ndim != 1
    ):
        raise ValueError("selective inputs must be one-dimensional")
    if not np.isfinite(uncertainty).all() or not np.isfinite(distance).all():
        raise ValueError("selective scores must be finite")
    if np.any(uncertainty < 0) or np.any(distance < 0):
        raise ValueError("uncertainty and distance must be nonnegative")
    if len(np.unique(environments)) < 2:
        raise ValueError("source-only selection requires multiple environments")
    return uncertainty, distance, errors, environments


def _policy_metrics(
    accepted: np.ndarray,
    errors: np.ndarray,
    environments: np.ndarray,
) -> tuple[float, float, float, float, int]:
    accepted_count = int(accepted.sum())
    if accepted_count == 0:
        raise ValueError("a selective policy must accept at least one row")
    coverage = float(accepted.mean())
    selective_risk = float(errors[accepted].mean())
    environment_risks = []
    environment_coverages = []
    for environment in np.unique(environments):
        rows = environments == environment
        environment_accepted = accepted & rows
        environment_coverages.append(float(environment_accepted.sum() / rows.sum()))
        environment_risks.append(
            float(errors[environment_accepted].mean())
            if environment_accepted.any()
            else 1.0
        )
    return (
        coverage,
        selective_risk,
        float(max(environment_risks)),
        float(min(environment_coverages)),
        accepted_count,
    )


def select_source_policy(
    uncertainty: np.ndarray,
    distance: np.ndarray,
    errors: np.ndarray,
    environments: np.ndarray,
    *,
    beta_candidates: tuple[float, ...] = (0.0, 0.1, 0.25, 0.5, 1.0),
    minimum_coverage: float = 0.5,
    minimum_environment_coverage: float = 0.25,
) -> SelectivePolicy:
    """Choose beta and a global threshold from out-of-fold source predictions only."""

    uncertainty, distance, errors, environments = _validated_inputs(
        uncertainty, distance, errors, environments
    )
    if not 0 < minimum_coverage <= 1 or not 0 < minimum_environment_coverage <= 1:
        raise ValueError("coverage requirements must lie in (0, 1]")
    if not beta_candidates or any(beta < 0 for beta in beta_candidates):
        raise ValueError("beta candidates must be a non-empty nonnegative tuple")
    candidates: list[tuple[tuple[float, ...], SelectivePolicy]] = []
    for beta in beta_candidates:
        scores = uncertainty + beta * distance
        for threshold in np.unique(scores):
            accepted = scores <= threshold
            (
                coverage,
                selective_risk,
                worst_environment_risk,
                minimum_observed_environment_coverage,
                accepted_count,
            ) = _policy_metrics(accepted, errors, environments)
            if (
                coverage + 1e-12 < minimum_coverage
                or minimum_observed_environment_coverage + 1e-12
                < minimum_environment_coverage
            ):
                continue
            policy = SelectivePolicy(
                beta=float(beta),
                threshold=float(threshold),
                source_coverage=coverage,
                source_selective_risk=selective_risk,
                source_worst_environment_risk=worst_environment_risk,
                source_minimum_environment_coverage=(
                    minimum_observed_environment_coverage
                ),
                source_accepted=accepted_count,
            )
            objective = (
                worst_environment_risk,
                selective_risk,
                -coverage,
                float(beta),
                float(threshold),
            )
            candidates.append((objective, policy))
    if not candidates:
        raise ValueError("no source-only threshold satisfies the frozen coverage constraints")
    return min(candidates, key=lambda item: item[0])[1]


def apply_policy(
    policy: SelectivePolicy,
    uncertainty: np.ndarray,
    distance: np.ndarray,
) -> np.ndarray:
    uncertainty = np.asarray(uncertainty, dtype=float)
    distance = np.asarray(distance, dtype=float)
    if (
        uncertainty.ndim != 1
        or distance.ndim != 1
        or len(uncertainty) != len(distance)
        or not np.isfinite(uncertainty).all()
        or not np.isfinite(distance).all()
    ):
        raise ValueError("policy inputs must be aligned finite vectors")
    return uncertainty + policy.beta * distance <= policy.threshold


def evaluate_policy(
    policy: SelectivePolicy,
    uncertainty: np.ndarray,
    distance: np.ndarray,
    errors: np.ndarray,
    environments: np.ndarray,
) -> dict[str, Any]:
    uncertainty, distance, errors, environments = _validated_inputs(
        uncertainty, distance, errors, environments
    )
    accepted = apply_policy(policy, uncertainty, distance)
    coverage, risk, worst_risk, minimum_environment_coverage, count = _policy_metrics(
        accepted, errors, environments
    )
    per_environment = {}
    for environment in np.unique(environments):
        rows = environments == environment
        selected = accepted & rows
        per_environment[str(environment)] = {
            "rows": int(rows.sum()),
            "accepted": int(selected.sum()),
            "coverage": float(selected.sum() / rows.sum()),
            "selective_risk": float(errors[selected].mean()) if selected.any() else None,
        }
    return {
        "coverage": coverage,
        "selective_risk": risk,
        "worst_environment_risk": worst_risk,
        "minimum_environment_coverage": minimum_environment_coverage,
        "accepted": count,
        "errors_accepted": int((errors & accepted).sum()),
        "per_environment": per_environment,
    }


def _validated_score_inputs(
    scores: np.ndarray,
    errors: np.ndarray,
    environments: np.ndarray,
    *,
    require_multiple_environments: bool,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    score_values = np.asarray(scores, dtype=float)
    error_values = np.asarray(errors, dtype=bool)
    environment_values = np.asarray(environments)
    lengths = {len(score_values), len(error_values), len(environment_values)}
    if len(lengths) != 1 or not lengths or next(iter(lengths)) == 0:
        raise ValueError("score-policy inputs must be aligned and non-empty")
    if (
        score_values.ndim != 1
        or error_values.ndim != 1
        or environment_values.ndim != 1
    ):
        raise ValueError("score-policy inputs must be one-dimensional")
    if not np.isfinite(score_values).all():
        raise ValueError("selective scores must be finite")
    if require_multiple_environments and len(np.unique(environment_values)) < 2:
        raise ValueError("source-only selection requires multiple environments")
    return score_values, error_values, environment_values


def _coverage_threshold(scores: np.ndarray, coverage: float) -> float:
    if not 0 < coverage <= 1:
        raise ValueError("coverage must lie in (0, 1]")
    accepted_count = min(len(scores), max(1, int(np.ceil(coverage * len(scores)))))
    return float(np.sort(scores, kind="stable")[accepted_count - 1])


def select_source_coverage_policy(
    scores: np.ndarray,
    errors: np.ndarray,
    environments: np.ndarray,
    *,
    score_name: str,
    nominal_source_coverage: float,
    minimum_source_environment_coverage: float = 0.25,
) -> SourceCoveragePolicy:
    """Fix a threshold by source coverage, with a source-environment floor.

    Lower scores are accepted.  The threshold is the larger of the pooled
    source-coverage quantile and every environment's minimum-coverage quantile.
    Source errors are reported but cannot change this threshold.
    """

    score_values, error_values, environment_values = _validated_score_inputs(
        scores,
        errors,
        environments,
        require_multiple_environments=True,
    )
    if not score_name.strip():
        raise ValueError("score name must be non-empty")
    if not 0 < nominal_source_coverage <= 1:
        raise ValueError("nominal source coverage must lie in (0, 1]")
    if not 0 < minimum_source_environment_coverage <= 1:
        raise ValueError("minimum source environment coverage must lie in (0, 1]")
    threshold = max(
        _coverage_threshold(score_values, nominal_source_coverage),
        *(
            _coverage_threshold(
                score_values[environment_values == environment],
                minimum_source_environment_coverage,
            )
            for environment in np.unique(environment_values)
        ),
    )
    accepted = score_values <= threshold
    (
        coverage,
        selective_risk,
        worst_environment_risk,
        minimum_observed_environment_coverage,
        accepted_count,
    ) = _policy_metrics(accepted, error_values, environment_values)
    return SourceCoveragePolicy(
        score_name=score_name,
        nominal_source_coverage=float(nominal_source_coverage),
        minimum_source_environment_coverage=float(
            minimum_source_environment_coverage
        ),
        threshold=threshold,
        source_coverage=coverage,
        source_selective_risk=selective_risk,
        source_worst_environment_risk=worst_environment_risk,
        source_minimum_environment_coverage=(
            minimum_observed_environment_coverage
        ),
        source_accepted=accepted_count,
    )


def apply_score_policy(
    policy: SourceCoveragePolicy,
    scores: np.ndarray,
) -> np.ndarray:
    score_values = np.asarray(scores, dtype=float)
    if score_values.ndim != 1 or not np.isfinite(score_values).all():
        raise ValueError("policy scores must be a finite vector")
    return score_values <= policy.threshold


def evaluate_score_policy(
    policy: SourceCoveragePolicy,
    scores: np.ndarray,
    errors: np.ndarray,
    environments: np.ndarray,
) -> dict[str, Any]:
    """Evaluate a frozen source policy without failing on target zero coverage."""

    score_values, error_values, environment_values = _validated_score_inputs(
        scores,
        errors,
        environments,
        require_multiple_environments=False,
    )
    accepted = apply_score_policy(policy, score_values)
    accepted_count = int(accepted.sum())
    per_environment: dict[str, dict[str, Any]] = {}
    environment_risks = []
    environment_coverages = []
    for environment in np.unique(environment_values):
        rows = environment_values == environment
        selected = accepted & rows
        selected_count = int(selected.sum())
        risk = (
            float(error_values[selected].mean()) if selected_count else None
        )
        environment_risks.append(1.0 if risk is None else risk)
        environment_coverages.append(float(selected_count / rows.sum()))
        per_environment[str(environment)] = {
            "rows": int(rows.sum()),
            "accepted": selected_count,
            "coverage": float(selected_count / rows.sum()),
            "selective_risk": risk,
        }
    return {
        "score_name": policy.score_name,
        "nominal_source_coverage": policy.nominal_source_coverage,
        "threshold": policy.threshold,
        "rows": len(score_values),
        "accepted": accepted_count,
        "coverage": float(accepted.mean()),
        "selective_risk": (
            float(error_values[accepted].mean()) if accepted_count else None
        ),
        "worst_environment_risk": float(max(environment_risks)),
        "minimum_environment_coverage": float(min(environment_coverages)),
        "accepted_errors": int((accepted & error_values).sum()),
        "per_environment": per_environment,
    }


def _aurc(scores: np.ndarray, errors: np.ndarray) -> float:
    order = np.argsort(scores, kind="stable")
    ordered_errors = errors[order].astype(float)
    cumulative_risk = np.cumsum(ordered_errors) / np.arange(1, len(errors) + 1)
    return float(cumulative_risk.mean())


def _average_tie_ranks(values: np.ndarray) -> np.ndarray:
    order = np.argsort(values, kind="stable")
    ranks = np.empty(len(values), dtype=float)
    ordered = values[order]
    start = 0
    while start < len(values):
        stop = start + 1
        while stop < len(values) and ordered[stop] == ordered[start]:
            stop += 1
        ranks[order[start:stop]] = 0.5 * ((start + 1) + stop)
        start = stop
    return ranks


def _error_detection_auroc(scores: np.ndarray, errors: np.ndarray) -> float | None:
    positive_count = int(errors.sum())
    negative_count = len(errors) - positive_count
    if positive_count == 0 or negative_count == 0:
        return None
    ranks = _average_tie_ranks(scores)
    statistic = ranks[errors].sum() - positive_count * (positive_count + 1) / 2
    return float(statistic / (positive_count * negative_count))


def _error_detection_average_precision(
    scores: np.ndarray,
    errors: np.ndarray,
) -> float | None:
    positive_count = int(errors.sum())
    if positive_count == 0:
        return None
    order = np.argsort(-scores, kind="stable")
    ordered_scores = scores[order]
    ordered_errors = errors[order]
    cumulative_positive = 0
    cumulative_count = 0
    average_precision = 0.0
    start = 0
    while start < len(scores):
        stop = start + 1
        while stop < len(scores) and ordered_scores[stop] == ordered_scores[start]:
            stop += 1
        group_positive = int(ordered_errors[start:stop].sum())
        cumulative_positive += group_positive
        cumulative_count += stop - start
        average_precision += (
            group_positive / positive_count
        ) * (cumulative_positive / cumulative_count)
        start = stop
    return float(average_precision)


def risk_coverage_summary(
    scores: np.ndarray,
    errors: np.ndarray,
    *,
    coverage_levels: tuple[float, ...] = (0.5, 0.7, 0.9),
) -> dict[str, Any]:
    """Return ranking quality without using the evaluated rows for selection."""

    score_values = np.asarray(scores, dtype=float)
    error_values = np.asarray(errors, dtype=bool)
    if (
        score_values.ndim != 1
        or error_values.ndim != 1
        or len(score_values) != len(error_values)
        or len(score_values) == 0
        or not np.isfinite(score_values).all()
    ):
        raise ValueError("risk-coverage inputs must be aligned finite vectors")
    if not coverage_levels or any(not 0 < value <= 1 for value in coverage_levels):
        raise ValueError("coverage levels must be a non-empty tuple in (0, 1]")
    aurc = _aurc(score_values, error_values)
    optimal_scores = error_values.astype(float)
    optimal_aurc = _aurc(optimal_scores, error_values)
    order = np.argsort(score_values, kind="stable")
    ordered_errors = error_values[order].astype(float)
    cumulative_errors = np.cumsum(ordered_errors)
    points = {}
    for coverage in coverage_levels:
        accepted_count = min(
            len(score_values),
            max(1, int(np.ceil(coverage * len(score_values)))),
        )
        points[str(coverage)] = {
            "accepted": accepted_count,
            "coverage": float(accepted_count / len(score_values)),
            "selective_risk": float(
                cumulative_errors[accepted_count - 1] / accepted_count
            ),
            "score_threshold": float(score_values[order[accepted_count - 1]]),
        }
    return {
        "rows": len(score_values),
        "errors": int(error_values.sum()),
        "base_risk": float(error_values.mean()),
        "aurc": aurc,
        "optimal_aurc": optimal_aurc,
        "excess_aurc": float(aurc - optimal_aurc),
        "error_detection_auroc": _error_detection_auroc(
            score_values, error_values
        ),
        "error_detection_average_precision": (
            _error_detection_average_precision(score_values, error_values)
        ),
        "coverage_points": points,
    }


def select_risk_envelope_beta(
    uncertainty: np.ndarray,
    distance: np.ndarray,
    errors: np.ndarray,
    environments: np.ndarray,
    *,
    beta_candidates: tuple[float, ...] = (0.0, 0.1, 0.25, 0.5, 1.0),
) -> RiskEnvelopeBetaSelection:
    """Choose beta by worst-environment then pooled source-OOF AURC."""

    uncertainty_values, distance_values, error_values, environment_values = (
        _validated_inputs(uncertainty, distance, errors, environments)
    )
    if not beta_candidates or any(beta < 0 for beta in beta_candidates):
        raise ValueError("beta candidates must be a non-empty nonnegative tuple")
    diagnostics = []
    for beta in beta_candidates:
        scores = uncertainty_values + beta * distance_values
        environment_aurcs = {
            str(environment): _aurc(
                scores[environment_values == environment],
                error_values[environment_values == environment],
            )
            for environment in np.unique(environment_values)
        }
        diagnostics.append(
            {
                "beta": float(beta),
                "source_aurc": _aurc(scores, error_values),
                "source_worst_environment_aurc": float(
                    max(environment_aurcs.values())
                ),
                "source_environment_aurcs": environment_aurcs,
            }
        )
    selected = min(
        diagnostics,
        key=lambda row: (
            float(row["source_worst_environment_aurc"]),
            float(row["source_aurc"]),
            float(row["beta"]),
        ),
    )
    return RiskEnvelopeBetaSelection(
        beta=float(selected["beta"]),
        source_aurc=float(selected["source_aurc"]),
        source_worst_environment_aurc=float(
            selected["source_worst_environment_aurc"]
        ),
        candidates=tuple(diagnostics),
    )
