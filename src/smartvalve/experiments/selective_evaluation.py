"""Leakage-proof source-OOF selection and target selective evaluation."""

from __future__ import annotations

from dataclasses import fields
from typing import Any

import numpy as np
import pandas as pd

from smartvalve.experiments.selective_scores import (
    energy_uncertainty,
    ensemble_jensen_shannon,
    maximum_softmax_uncertainty,
    negative_max_logit,
    normalized_predictive_entropy,
    pnorm_normalized_max_logit,
)
from smartvalve.experiments.source_selective import (
    SourceCoveragePolicy,
    apply_score_policy,
    evaluate_score_policy,
    risk_coverage_summary,
    select_risk_envelope_beta,
    select_source_coverage_policy,
)

SELECTIVE_EVALUATION_VERSION = "source-oof-selective-evaluation-0.1.0"
COVERAGE_LEVELS = (0.5, 0.7, 0.9)
MINIMUM_SOURCE_ENVIRONMENT_COVERAGE = 0.25
BETA_CANDIDATES = (0.0, 0.1, 0.25, 0.5, 1.0)
GROUP_COLUMNS = ("dataset", "method", "seed", "fold_id")
INDIVIDUAL_SCORE_COLUMNS = {
    "msp": "score_msp",
    "predictive_entropy": "score_predictive_entropy",
    "energy_t1": "score_energy_t1",
    "negative_max_logit": "score_negative_max_logit",
    "pnorm_max_logit_p2": "score_pnorm_max_logit_p2",
    "robust_class_support": "score_robust_class_support",
}
ENSEMBLE_SCORE_COLUMNS = {
    "ensemble_msp": "score_msp",
    "ensemble_predictive_entropy": "score_predictive_entropy",
    "ensemble_jensen_shannon": "score_ensemble_jensen_shannon",
    "ensemble_mean_robust_support": "score_robust_class_support",
}


def _active_columns(frame: pd.DataFrame, prefix: str) -> list[str]:
    columns = [
        column
        for column in frame.columns
        if column.startswith(prefix) and frame[column].notna().all()
    ]
    if len(columns) < 2:
        raise ValueError(f"prediction group has fewer than two active {prefix} columns")
    return sorted(columns)


def add_individual_scores(records: pd.DataFrame) -> pd.DataFrame:
    """Compute every frozen single-network score within each dataset group."""

    required = {
        *GROUP_COLUMNS,
        "truth",
        "prediction",
        "correct",
        "environment_id",
        "robust_class_support_distance",
    }
    missing = required - set(records.columns)
    if missing:
        raise ValueError(f"prediction records are missing columns: {sorted(missing)}")
    scored_groups = []
    for _, group in records.groupby(list(GROUP_COLUMNS), sort=True, observed=True):
        group = group.copy()
        probability_columns = _active_columns(group, "probability_")
        logit_columns = _active_columns(group, "logit_")
        if [name.removeprefix("probability_") for name in probability_columns] != [
            name.removeprefix("logit_") for name in logit_columns
        ]:
            raise ValueError("probability and logit label columns do not align")
        probabilities = group.loc[:, probability_columns].to_numpy(dtype=float)
        logits = group.loc[:, logit_columns].to_numpy(dtype=float)
        distance = group["robust_class_support_distance"].to_numpy(dtype=float)
        if np.any(distance < 0) or not np.isfinite(distance).all():
            raise ValueError("robust class-support distance must be finite and nonnegative")
        group["score_msp"] = maximum_softmax_uncertainty(probabilities)
        group["score_predictive_entropy"] = normalized_predictive_entropy(
            probabilities
        )
        group["score_energy_t1"] = energy_uncertainty(logits)
        group["score_negative_max_logit"] = negative_max_logit(logits)
        group["score_pnorm_max_logit_p2"] = pnorm_normalized_max_logit(
            logits, order=2.0
        )
        group["score_robust_class_support"] = distance
        scored_groups.append(group)
    return pd.concat(scored_groups, ignore_index=True)


def _single_group_identifiers(frame: pd.DataFrame) -> dict[str, Any]:
    identifiers = {}
    for column in GROUP_COLUMNS:
        values = frame[column].drop_duplicates()
        if len(values) != 1:
            raise ValueError(f"selective fold mixes {column} values")
        value = values.iloc[0]
        identifiers[column] = int(value) if column == "seed" else str(value)
    return identifiers


def select_fold_policies(
    source_oof: pd.DataFrame,
    *,
    score_columns: dict[str, str] | None = None,
    coverage_levels: tuple[float, ...] = COVERAGE_LEVELS,
    minimum_environment_coverage: float = MINIMUM_SOURCE_ENVIRONMENT_COVERAGE,
    envelope_score_name: str = "risk_envelope",
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Select all policies from one method/fold/seed source-OOF group."""

    identifiers = _single_group_identifiers(source_oof)
    selected_score_columns = score_columns or INDIVIDUAL_SCORE_COLUMNS
    missing = {
        "correct",
        "environment_id",
        "score_msp",
        "score_robust_class_support",
        *selected_score_columns.values(),
    } - set(source_oof.columns)
    if missing:
        raise ValueError(f"source OOF records are missing scores: {sorted(missing)}")
    errors = ~source_oof["correct"].to_numpy(dtype=bool)
    environments = source_oof["environment_id"].to_numpy()
    beta_selection = select_risk_envelope_beta(
        source_oof["score_msp"].to_numpy(dtype=float),
        source_oof["score_robust_class_support"].to_numpy(dtype=float),
        errors,
        environments,
        beta_candidates=BETA_CANDIDATES,
    )
    score_values = {
        name: source_oof[column].to_numpy(dtype=float)
        for name, column in selected_score_columns.items()
    }
    score_values[envelope_score_name] = (
        source_oof["score_msp"].to_numpy(dtype=float)
        + beta_selection.beta
        * source_oof["score_robust_class_support"].to_numpy(dtype=float)
    )
    policy_records = []
    for score_name, scores in score_values.items():
        for coverage in coverage_levels:
            policy = select_source_coverage_policy(
                scores,
                errors,
                environments,
                score_name=score_name,
                nominal_source_coverage=coverage,
                minimum_source_environment_coverage=minimum_environment_coverage,
            )
            policy_records.append(
                {
                    **identifiers,
                    **policy.to_record(),
                    "risk_envelope_beta": (
                        beta_selection.beta
                        if score_name == envelope_score_name
                        else None
                    ),
                }
            )
    beta_record = {
        **identifiers,
        **beta_selection.to_record(),
    }
    return policy_records, beta_record


def _policy_from_record(record: dict[str, Any]) -> SourceCoveragePolicy:
    names = {field.name for field in fields(SourceCoveragePolicy)}
    return SourceCoveragePolicy(**{name: record[name] for name in names})


def _macro_f1_abstention_as_error(
    truth: np.ndarray,
    prediction: np.ndarray,
    accepted: np.ndarray,
) -> float:
    labels = sorted({str(value) for value in truth})
    class_f1 = []
    for label in labels:
        truth_is_label = truth == label
        prediction_is_label = accepted & (prediction == label)
        true_positive = int((truth_is_label & prediction_is_label).sum())
        false_positive = int((~truth_is_label & prediction_is_label).sum())
        false_negative = int((truth_is_label & ~prediction_is_label).sum())
        denominator = 2 * true_positive + false_positive + false_negative
        class_f1.append(2 * true_positive / denominator if denominator else 0.0)
    return float(np.mean(class_f1))


def _classification_diagnostics(
    target: pd.DataFrame,
    accepted: np.ndarray,
) -> dict[str, Any]:
    truth = target["truth"].to_numpy(dtype=str)
    prediction = target["prediction"].to_numpy(dtype=str)
    correct = target["correct"].to_numpy(dtype=bool)
    errors = ~correct
    per_class = {}
    for label in sorted(np.unique(truth)):
        rows = truth == label
        selected = accepted & rows
        per_class[str(label)] = {
            "rows": int(rows.sum()),
            "accepted": int(selected.sum()),
            "coverage": float(selected.sum() / rows.sum()),
            "selective_risk": (
                float(errors[selected].mean()) if selected.any() else None
            ),
        }
    return {
        "effective_accuracy": float((accepted & correct).mean()),
        "macro_f1_abstention_as_error": _macro_f1_abstention_as_error(
            truth, prediction, accepted
        ),
        "error_detection_recall": (
            float(((~accepted) & errors).sum() / errors.sum())
            if errors.any()
            else 0.0
        ),
        "correct_rejection_rate": (
            float(((~accepted) & correct).sum() / correct.sum())
            if correct.any()
            else 0.0
        ),
        "per_class": per_class,
    }


def evaluate_fold_policies(
    target: pd.DataFrame,
    policies: list[dict[str, Any]],
    beta_record: dict[str, Any],
    *,
    score_columns: dict[str, str] | None = None,
    envelope_score_name: str = "risk_envelope",
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], pd.DataFrame]:
    """Evaluate already selected policies; target rows cannot alter any policy."""

    identifiers = _single_group_identifiers(target)
    for column, value in identifiers.items():
        if beta_record[column] != value:
            raise ValueError("target group does not match its source beta selection")
    selected_score_columns = score_columns or INDIVIDUAL_SCORE_COLUMNS
    score_values = {
        name: target[column].to_numpy(dtype=float)
        for name, column in selected_score_columns.items()
    }
    score_values[envelope_score_name] = (
        target["score_msp"].to_numpy(dtype=float)
        + float(beta_record["beta"])
        * target["score_robust_class_support"].to_numpy(dtype=float)
    )
    errors = ~target["correct"].to_numpy(dtype=bool)
    environments = target["environment_id"].to_numpy()
    ranking_records = []
    for score_name, scores in score_values.items():
        ranking_records.append(
            {
                **identifiers,
                "score_name": score_name,
                "risk_envelope_beta": (
                    float(beta_record["beta"])
                    if score_name == envelope_score_name
                    else None
                ),
                **risk_coverage_summary(scores, errors),
            }
        )
    metric_records = []
    decision_frames = []
    for record in policies:
        if any(record[column] != value for column, value in identifiers.items()):
            raise ValueError("target group does not match a source policy")
        policy = _policy_from_record(record)
        scores = score_values[policy.score_name]
        accepted = apply_score_policy(policy, scores)
        metrics = evaluate_score_policy(
            policy,
            scores,
            errors,
            environments,
        )
        metric_records.append(
            {
                **identifiers,
                **metrics,
                **_classification_diagnostics(target, accepted),
                "source_coverage": policy.source_coverage,
                "source_selective_risk": policy.source_selective_risk,
                "source_worst_environment_risk": (
                    policy.source_worst_environment_risk
                ),
                "source_minimum_environment_coverage": (
                    policy.source_minimum_environment_coverage
                ),
                "risk_envelope_beta": record["risk_envelope_beta"],
            }
        )
        decisions = target.loc[
            :,
            [
                *GROUP_COLUMNS,
                "row_index",
                "environment_id",
                "block_id",
                "truth",
                "prediction",
                "correct",
            ],
        ].copy()
        decisions["score_name"] = policy.score_name
        decisions["nominal_source_coverage"] = policy.nominal_source_coverage
        decisions["score"] = scores
        decisions["threshold"] = policy.threshold
        decisions["accepted"] = accepted
        decisions["risk_envelope_beta"] = float(beta_record["beta"])
        decision_frames.append(decisions)
    return metric_records, ranking_records, pd.concat(decision_frames, ignore_index=True)


def analyze_individual_predictions(
    source_oof: pd.DataFrame,
    target: pd.DataFrame,
) -> dict[str, Any]:
    """Run the full individual-network analysis with a structural source/target split."""

    source_scored = add_individual_scores(source_oof)
    target_scored = add_individual_scores(target)
    policy_records = []
    beta_records = []
    metric_records = []
    ranking_records = []
    decision_frames = []
    grouped_target = {
        key: group
        for key, group in target_scored.groupby(
            list(GROUP_COLUMNS), sort=True, observed=True
        )
    }
    for key, source_group in source_scored.groupby(
        list(GROUP_COLUMNS), sort=True, observed=True
    ):
        if key not in grouped_target:
            raise ValueError(f"source OOF group has no target counterpart: {key}")
        policies, beta = select_fold_policies(source_group)
        metrics, rankings, decisions = evaluate_fold_policies(
            grouped_target.pop(key), policies, beta
        )
        policy_records.extend(policies)
        beta_records.append(beta)
        metric_records.extend(metrics)
        ranking_records.extend(rankings)
        decision_frames.append(decisions)
    if grouped_target:
        raise ValueError("target predictions contain groups without source OOF counterparts")
    return {
        "source_scored": source_scored,
        "target_scored": target_scored,
        "policies": policy_records,
        "beta_selections": beta_records,
        "policy_metrics": metric_records,
        "ranking_metrics": ranking_records,
        "decisions": pd.concat(decision_frames, ignore_index=True),
    }


def build_ensemble_predictions(
    records: pd.DataFrame,
    *,
    expected_seeds: tuple[int, ...],
) -> pd.DataFrame:
    """Average locked members and retain Jensen-Shannon disagreement."""

    if len(expected_seeds) < 2 or len(set(expected_seeds)) != len(expected_seeds):
        raise ValueError("ensemble seeds must be unique and contain at least two members")
    required = {
        *GROUP_COLUMNS,
        "row_index",
        "environment_id",
        "block_id",
        "truth",
        "robust_class_support_distance",
    }
    missing = required - set(records.columns)
    if missing:
        raise ValueError(f"ensemble records are missing columns: {sorted(missing)}")
    output = []
    ensemble_group_columns = ["dataset", "method", "fold_id"]
    identity_columns = ["row_index", "environment_id", "block_id", "truth"]
    for (dataset, method, fold_id), group in records.groupby(
        ensemble_group_columns, sort=True, observed=True
    ):
        seeds = tuple(sorted(int(value) for value in group["seed"].unique()))
        if seeds != tuple(sorted(expected_seeds)):
            raise ValueError(
                f"ensemble seed mismatch for {(dataset, method, fold_id)}: {seeds}"
            )
        probability_columns = _active_columns(group, "probability_")
        members = []
        member_distances = []
        reference_rows: pd.DataFrame | None = None
        for seed in sorted(expected_seeds):
            member = group.loc[group["seed"] == seed].sort_values(
                "row_index", kind="stable"
            )
            if member["row_index"].duplicated().any():
                raise ValueError("ensemble member contains duplicate row indices")
            if reference_rows is None:
                reference_rows = member
            elif not member[identity_columns].reset_index(drop=True).equals(
                reference_rows[identity_columns].reset_index(drop=True)
            ):
                raise ValueError("ensemble member row identities do not align")
            members.append(member[probability_columns].to_numpy(dtype=float))
            member_distances.append(
                member["robust_class_support_distance"].to_numpy(dtype=float)
            )
        if reference_rows is None:
            raise AssertionError("ensemble group unexpectedly has no rows")
        member_probabilities = np.stack(members)
        mean_probabilities = member_probabilities.mean(axis=0)
        mean_distance = np.stack(member_distances).mean(axis=0)
        labels = [column.removeprefix("probability_") for column in probability_columns]
        prediction_indices = mean_probabilities.argmax(axis=1)
        truth = reference_rows["truth"].to_numpy(dtype=str)
        prediction = np.asarray(
            [labels[index] for index in prediction_indices], dtype=str
        )
        ensemble = reference_rows.loc[
            :,
            [
                column
                for column in reference_rows.columns
                if not column.startswith(("probability_", "logit_", "representation_"))
                and column
                not in {
                    "seed",
                    "prediction",
                    "correct",
                    "confidence",
                    "robust_class_support_distance",
                    *INDIVIDUAL_SCORE_COLUMNS.values(),
                }
            ],
        ].copy()
        ensemble.insert(2, "seed", -1)
        ensemble["ensemble_size"] = len(expected_seeds)
        ensemble["prediction"] = prediction
        ensemble["correct"] = prediction == truth
        ensemble["confidence"] = mean_probabilities.max(axis=1)
        ensemble["robust_class_support_distance"] = mean_distance
        for index, column in enumerate(probability_columns):
            ensemble[column] = mean_probabilities[:, index]
        ensemble["score_msp"] = maximum_softmax_uncertainty(mean_probabilities)
        ensemble["score_predictive_entropy"] = normalized_predictive_entropy(
            mean_probabilities
        )
        ensemble["score_ensemble_jensen_shannon"] = ensemble_jensen_shannon(
            member_probabilities
        )
        ensemble["score_robust_class_support"] = mean_distance
        output.append(ensemble)
    return pd.concat(output, ignore_index=True, sort=False)


def analyze_ensemble_predictions(
    source_oof: pd.DataFrame,
    target: pd.DataFrame,
    *,
    expected_seeds: tuple[int, ...],
) -> dict[str, Any]:
    """Run source-selected analysis of a fixed deep ensemble without more fits."""

    source_ensemble = build_ensemble_predictions(
        source_oof, expected_seeds=expected_seeds
    )
    target_ensemble = build_ensemble_predictions(
        target, expected_seeds=expected_seeds
    )
    policy_records = []
    beta_records = []
    metric_records = []
    ranking_records = []
    decision_frames = []
    grouped_target = {
        key: group
        for key, group in target_ensemble.groupby(
            list(GROUP_COLUMNS), sort=True, observed=True
        )
    }
    for key, source_group in source_ensemble.groupby(
        list(GROUP_COLUMNS), sort=True, observed=True
    ):
        if key not in grouped_target:
            raise ValueError(f"source ensemble has no target counterpart: {key}")
        policies, beta = select_fold_policies(
            source_group,
            score_columns=ENSEMBLE_SCORE_COLUMNS,
            envelope_score_name="ensemble_risk_envelope",
        )
        metrics, rankings, decisions = evaluate_fold_policies(
            grouped_target.pop(key),
            policies,
            beta,
            score_columns=ENSEMBLE_SCORE_COLUMNS,
            envelope_score_name="ensemble_risk_envelope",
        )
        policy_records.extend(policies)
        beta_records.append(beta)
        metric_records.extend(metrics)
        ranking_records.extend(rankings)
        decision_frames.append(decisions)
    if grouped_target:
        raise ValueError("target ensemble contains groups without source counterparts")
    return {
        "source_ensemble": source_ensemble,
        "target_ensemble": target_ensemble,
        "policies": policy_records,
        "beta_selections": beta_records,
        "policy_metrics": metric_records,
        "ranking_metrics": ranking_records,
        "decisions": pd.concat(decision_frames, ignore_index=True),
    }
