"""Paired stratified physical-block bootstrap for locked selective predictions."""

from __future__ import annotations

import argparse
import hashlib
import json
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from smartvalve.experiments.cranfield_causal_audit import AUDIT_SEEDS

BOOTSTRAP_VERSION = "selective-paired-physical-block-bootstrap-0.1.0"
BOOTSTRAP_REPLICATES = 2_000
BOOTSTRAP_SEED = 20_260_818
METHODS = ("erm", "pirl_ratio")
HEADLINE_SCORE = "risk_envelope"
HEADLINE_SOURCE_COVERAGE = 0.5
ENDPOINTS = (
    "worst_fold_macro_f1",
    "selective_risk_at_source_50pct",
)
PRACTICAL_EFFECTS = {
    "pirl_minus_erm_worst_fold_macro_f1": 0.01,
    "erm_minus_pirl_selective_risk_at_source_50pct": 0.01,
}
VALIDATION_STATUS = "passed_against_outcome_blind_selective_manifest"


@dataclass(frozen=True)
class DatasetArrays:
    dataset: str
    methods: tuple[str, ...]
    seeds: tuple[int, ...]
    fold_ids: tuple[str, ...]
    labels: tuple[str, ...]
    blocks: pd.DataFrame
    prediction_method: np.ndarray
    prediction_seed: np.ndarray
    prediction_fold: np.ndarray
    prediction_block: np.ndarray
    prediction_truth: np.ndarray
    prediction_value: np.ndarray
    selective_method: np.ndarray
    selective_seed: np.ndarray
    selective_block: np.ndarray
    selective_accepted: np.ndarray
    selective_error: np.ndarray


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _validate_hash(path: Path, expected: str, label: str) -> str:
    observed = _sha256(path)
    if observed != expected:
        raise ValueError(
            f"{label} SHA-256 mismatch: expected {expected}, observed {observed}"
        )
    return observed


def validate_execution_authorization(
    *,
    target_predictions_path: Path,
    target_predictions_sha256: str,
    selection_decisions_path: Path,
    selection_decisions_sha256: str,
    protocol_document: Path,
    protocol_sha256: str,
    selective_validation: Path,
    selective_validation_sha256: str,
) -> dict[str, str]:
    """Require the frozen protocol and independent EXP-342 validation."""

    paths = {
        "target_predictions": target_predictions_path.resolve(strict=True),
        "selection_decisions": selection_decisions_path.resolve(strict=True),
        "protocol_document": protocol_document.resolve(strict=True),
        "selective_validation": selective_validation.resolve(strict=True),
    }
    expected_hashes = {
        "target_predictions": target_predictions_sha256,
        "selection_decisions": selection_decisions_sha256,
        "protocol_document": protocol_sha256,
        "selective_validation": selective_validation_sha256,
    }
    observed = {
        name: _validate_hash(path, expected_hashes[name], name)
        for name, path in paths.items()
    }
    validation = _read_json(paths["selective_validation"])
    if validation.get("status") != VALIDATION_STATUS:
        raise ValueError("selective artifact validation did not pass")
    artifact_hashes = validation.get("artifact_hashes", {})
    for name in ("target_predictions", "selection_decisions"):
        if artifact_hashes.get(name) != observed[name]:
            raise ValueError(f"selective validation does not authorize {name}")
    if validation.get("paderborn_archive_contents_opened") is not False:
        raise ValueError("selective validation violates the Paderborn access boundary")

    linked_artifacts = {
        "selective_metrics": validation.get("selective_metrics", {}),
        "expected_manifest": validation.get("expected_manifest", {}),
    }
    for name, record in linked_artifacts.items():
        if not isinstance(record, dict) or not record.get("path") or not record.get(
            "sha256"
        ):
            raise ValueError(f"selective validation is missing {name} provenance")
        linked_path = Path(str(record["path"])).resolve(strict=True)
        observed[name] = _validate_hash(linked_path, str(record["sha256"]), name)

    protocol_text = paths["protocol_document"].read_text(encoding="utf-8")
    frozen_values = (
        "frozen v0.1",
        target_predictions_sha256,
        selection_decisions_sha256,
        selective_validation_sha256,
        observed["selective_metrics"],
        observed["expected_manifest"],
        "2,000 replicates",
        "20260818",
    )
    for value in frozen_values:
        if value not in protocol_text:
            raise ValueError(f"bootstrap protocol does not freeze {value}")
    return {
        **observed,
        "target_predictions_path": str(paths["target_predictions"]),
        "selection_decisions_path": str(paths["selection_decisions"]),
        "protocol_document_path": str(paths["protocol_document"]),
        "selective_validation_path": str(paths["selective_validation"]),
    }


def _validate_inputs(
    predictions: pd.DataFrame,
    decisions: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    prediction_required = {
        "dataset",
        "method",
        "seed",
        "fold_id",
        "row_index",
        "environment_id",
        "block_id",
        "truth",
        "prediction",
        "correct",
    }
    decision_required = {
        *prediction_required,
        "score_name",
        "nominal_source_coverage",
        "accepted",
    }
    prediction_missing = prediction_required - set(predictions.columns)
    decision_missing = decision_required - set(decisions.columns)
    if prediction_missing or decision_missing:
        raise ValueError(
            "bootstrap inputs are missing columns: "
            f"predictions={sorted(prediction_missing)}, "
            f"decisions={sorted(decision_missing)}"
        )
    predictions = predictions.loc[
        predictions["method"].isin(METHODS)
        & predictions["seed"].isin(AUDIT_SEEDS)
    ].copy()
    decisions = decisions.loc[
        decisions["method"].isin(METHODS)
        & decisions["seed"].isin(AUDIT_SEEDS)
        & (decisions["score_name"] == HEADLINE_SCORE)
        & np.isclose(
            decisions["nominal_source_coverage"].to_numpy(dtype=float),
            HEADLINE_SOURCE_COVERAGE,
        )
    ].copy()
    if predictions.empty or decisions.empty:
        raise ValueError("headline PIRL/ERM bootstrap inputs are empty")
    key = ["dataset", "method", "seed", "fold_id", "row_index"]
    if predictions.duplicated(key).any() or decisions.duplicated(key).any():
        raise ValueError("bootstrap inputs contain duplicate prediction keys")
    merged = decisions.merge(
        predictions.loc[:, [*key, "environment_id", "block_id", "truth", "prediction", "correct"]],
        on=key,
        suffixes=("_decision", "_prediction"),
        how="outer",
        validate="one_to_one",
        indicator=True,
    )
    if not (merged["_merge"] == "both").all():
        raise ValueError("headline decisions and predictions do not have identical keys")
    for column in ("environment_id", "block_id", "truth", "prediction", "correct"):
        if not np.array_equal(
            merged[f"{column}_decision"].to_numpy(),
            merged[f"{column}_prediction"].to_numpy(),
        ):
            raise ValueError(f"headline decision {column} differs from prediction artifact")
    expected_methods = set(METHODS)
    expected_seeds = set(AUDIT_SEEDS)
    if (
        set(predictions["method"]) != expected_methods
        or set(decisions["method"]) != expected_methods
    ):
        raise ValueError("bootstrap inputs do not contain exactly PIRL and tuned ERM")
    if set(predictions["seed"].astype(int)) != expected_seeds or set(
        decisions["seed"].astype(int)
    ) != expected_seeds:
        raise ValueError("bootstrap inputs do not contain the five paired seeds")
    return predictions, decisions


def _encode(values: pd.Series, ordered: Sequence[Any]) -> np.ndarray:
    mapping = {value: index for index, value in enumerate(ordered)}
    encoded = values.map(mapping)
    if encoded.isna().any():
        raise ValueError("bootstrap value is outside its frozen encoding")
    return encoded.to_numpy(dtype=np.int64)


def tensorize_dataset(
    predictions: pd.DataFrame,
    decisions: pd.DataFrame,
    dataset: str,
) -> DatasetArrays:
    prediction_rows = predictions.loc[predictions["dataset"] == dataset].copy()
    selective_rows = decisions.loc[decisions["dataset"] == dataset].copy()
    if prediction_rows.empty or selective_rows.empty:
        raise ValueError(f"dataset {dataset} is missing bootstrap rows")
    methods = tuple(METHODS)
    seeds = tuple(int(value) for value in AUDIT_SEEDS)
    fold_ids = tuple(sorted(str(value) for value in prediction_rows["fold_id"].unique()))
    labels = tuple(sorted(str(value) for value in prediction_rows["truth"].unique()))
    if not set(prediction_rows["prediction"]).issubset(labels):
        raise ValueError("prediction labels differ from the dataset truth labels")
    blocks = (
        prediction_rows.loc[:, ["environment_id", "block_id"]]
        .drop_duplicates()
        .sort_values(["environment_id", "block_id"], kind="stable")
        .reset_index(drop=True)
    )
    if blocks["block_id"].duplicated().any():
        raise ValueError("a physical block maps to multiple environments")
    block_ids = tuple(str(value) for value in blocks["block_id"])
    return DatasetArrays(
        dataset=dataset,
        methods=methods,
        seeds=seeds,
        fold_ids=fold_ids,
        labels=labels,
        blocks=blocks,
        prediction_method=_encode(prediction_rows["method"], methods),
        prediction_seed=_encode(prediction_rows["seed"].astype(int), seeds),
        prediction_fold=_encode(prediction_rows["fold_id"].astype(str), fold_ids),
        prediction_block=_encode(prediction_rows["block_id"].astype(str), block_ids),
        prediction_truth=_encode(prediction_rows["truth"].astype(str), labels),
        prediction_value=_encode(prediction_rows["prediction"].astype(str), labels),
        selective_method=_encode(selective_rows["method"], methods),
        selective_seed=_encode(selective_rows["seed"].astype(int), seeds),
        selective_block=_encode(selective_rows["block_id"].astype(str), block_ids),
        selective_accepted=selective_rows["accepted"].to_numpy(dtype=bool),
        selective_error=~selective_rows["correct"].to_numpy(dtype=bool),
    )


def stratified_block_choices(
    blocks: pd.DataFrame,
    *,
    replicates: int,
    seed: int,
) -> tuple[np.ndarray, pd.DataFrame]:
    """Draw each environment's physical blocks with replacement and retain the plan."""

    if replicates < 1:
        raise ValueError("bootstrap replicate count must be positive")
    if blocks.empty or blocks["block_id"].duplicated().any():
        raise ValueError("bootstrap blocks must be non-empty and unique")
    rng = np.random.default_rng(seed)
    strata = [
        group.index.to_numpy(dtype=np.int64)
        for _, group in blocks.groupby("environment_id", sort=True, observed=True)
    ]
    if any(len(indices) < 2 for indices in strata):
        raise ValueError("every physical bootstrap stratum needs at least two blocks")
    slot_indices = np.concatenate(strata)
    choices = np.empty((replicates, len(slot_indices)), dtype=np.int64)
    slot_environment = []
    slot_number = []
    offset = 0
    for environment, group in blocks.groupby(
        "environment_id", sort=True, observed=True
    ):
        indices = group.index.to_numpy(dtype=np.int64)
        choices[:, offset : offset + len(indices)] = rng.choice(
            indices,
            size=(replicates, len(indices)),
            replace=True,
        )
        slot_environment.extend([str(environment)] * len(indices))
        slot_number.extend(range(len(indices)))
        offset += len(indices)
    slots = pd.DataFrame(
        {
            "slot": np.arange(len(slot_indices), dtype=np.int64),
            "environment_id": slot_environment,
            "draw_slot": slot_number,
        }
    )
    return choices, slots


def _macro_f1(
    truth: np.ndarray,
    prediction: np.ndarray,
    weights: np.ndarray,
    class_count: int,
) -> float:
    confusion = np.bincount(
        truth * class_count + prediction,
        weights=weights,
        minlength=class_count**2,
    ).reshape(class_count, class_count)
    true_positive = np.diag(confusion)
    denominator = confusion.sum(axis=0) + confusion.sum(axis=1)
    class_f1 = np.divide(
        2 * true_positive,
        denominator,
        out=np.zeros_like(true_positive),
        where=denominator > 0,
    )
    return float(class_f1.mean())


def dataset_metrics(arrays: DatasetArrays, block_weights: np.ndarray) -> np.ndarray:
    """Return method x endpoint values, averaging paired model seeds."""

    block_weights = np.asarray(block_weights, dtype=float)
    if (
        block_weights.ndim != 1
        or len(block_weights) != len(arrays.blocks)
        or np.any(block_weights < 0)
        or not np.isfinite(block_weights).all()
    ):
        raise ValueError("block weights must be an aligned nonnegative vector")
    if block_weights.sum() <= 0:
        raise ValueError("at least one physical block must have positive weight")
    result = np.empty((len(arrays.methods), len(ENDPOINTS)), dtype=float)
    for method_index in range(len(arrays.methods)):
        seed_worst_f1 = []
        seed_selective_risk = []
        for seed_index in range(len(arrays.seeds)):
            fold_f1 = []
            for fold_index in range(len(arrays.fold_ids)):
                rows = (
                    (arrays.prediction_method == method_index)
                    & (arrays.prediction_seed == seed_index)
                    & (arrays.prediction_fold == fold_index)
                )
                weights = block_weights[arrays.prediction_block[rows]]
                fold_f1.append(
                    _macro_f1(
                        arrays.prediction_truth[rows],
                        arrays.prediction_value[rows],
                        weights,
                        len(arrays.labels),
                    )
                )
            seed_worst_f1.append(min(fold_f1))
            rows = (
                (arrays.selective_method == method_index)
                & (arrays.selective_seed == seed_index)
            )
            weights = block_weights[arrays.selective_block[rows]]
            accepted_weights = weights * arrays.selective_accepted[rows]
            accepted_total = float(accepted_weights.sum())
            seed_selective_risk.append(
                float(
                    (
                        accepted_weights
                        * arrays.selective_error[rows].astype(float)
                    ).sum()
                    / accepted_total
                )
                if accepted_total > 0
                else 1.0
            )
        result[method_index] = (
            float(np.mean(seed_worst_f1)),
            float(np.mean(seed_selective_risk)),
        )
    return result


def _interval(point: float, values: np.ndarray) -> dict[str, Any]:
    values = np.asarray(values, dtype=float)
    if values.ndim != 1 or len(values) == 0 or not np.isfinite(values).all():
        raise ValueError("bootstrap interval values must be a finite vector")
    lower_tail = (int((values <= 0).sum()) + 1) / (len(values) + 1)
    upper_tail = (int((values >= 0).sum()) + 1) / (len(values) + 1)
    return {
        "point_estimate": float(point),
        "bootstrap_mean": float(values.mean()),
        "bootstrap_standard_error": (
            float(values.std(ddof=1)) if len(values) > 1 else 0.0
        ),
        "ci95_low": float(np.quantile(values, 0.025)),
        "ci95_high": float(np.quantile(values, 0.975)),
        "two_sided_bootstrap_tail_p": float(min(1.0, 2 * min(lower_tail, upper_tail))),
    }


def holm_adjust(p_values: dict[str, float]) -> dict[str, float]:
    """Return monotone Holm-adjusted p-values under stable name tie-breaking."""

    if not p_values or any(not 0 <= value <= 1 for value in p_values.values()):
        raise ValueError("Holm correction requires named p-values in [0, 1]")
    ordered = sorted(p_values, key=lambda name: (p_values[name], name))
    adjusted = {}
    running = 0.0
    count = len(ordered)
    for rank, name in enumerate(ordered):
        running = max(running, min(1.0, (count - rank) * p_values[name]))
        adjusted[name] = running
    return {name: float(adjusted[name]) for name in p_values}


def _draw_plan(
    dataset: str,
    arrays: DatasetArrays,
    choices: np.ndarray,
    slots: pd.DataFrame,
) -> pd.DataFrame:
    replicate_count, slot_count = choices.shape
    return pd.DataFrame(
        {
            "dataset": dataset,
            "replicate": np.repeat(np.arange(replicate_count), slot_count),
            "environment_id": np.tile(
                slots["environment_id"].to_numpy(), replicate_count
            ),
            "draw_slot": np.tile(slots["draw_slot"].to_numpy(), replicate_count),
            "selected_block_id": arrays.blocks.loc[
                choices.ravel(), "block_id"
            ].to_numpy(),
        }
    )


def _artifact(path: Path, **counts: int) -> dict[str, Any]:
    return {
        "path": path.name,
        **counts,
        "bytes": path.stat().st_size,
        "sha256": _sha256(path),
    }


def _run_bootstrap_core(
    target_predictions_path: Path,
    selection_decisions_path: Path,
    output_directory: Path,
    *,
    replicates: int,
    seed: int,
    authorization: dict[str, str] | None = None,
) -> dict[str, Any]:
    predictions, decisions = _validate_inputs(
        pd.read_parquet(target_predictions_path),
        pd.read_parquet(selection_decisions_path),
    )
    datasets = tuple(sorted(str(value) for value in predictions["dataset"].unique()))
    if set(datasets) != set(decisions["dataset"]):
        raise ValueError("prediction and decision datasets differ")
    seed_sequence = np.random.SeedSequence(seed)
    child_seeds = seed_sequence.spawn(len(datasets))
    point_results = {}
    comparison_summaries = {}
    replicate_rows = []
    draw_plans = []
    for dataset, child_seed in zip(datasets, child_seeds, strict=True):
        arrays = tensorize_dataset(predictions, decisions, dataset)
        point = dataset_metrics(arrays, np.ones(len(arrays.blocks), dtype=float))
        child_value = int(child_seed.generate_state(1, dtype=np.uint64)[0])
        choices, slots = stratified_block_choices(
            arrays.blocks,
            replicates=replicates,
            seed=child_value,
        )
        replicate_metrics = np.empty(
            (replicates, len(METHODS), len(ENDPOINTS)), dtype=float
        )
        for replicate in range(replicates):
            weights = np.bincount(
                choices[replicate], minlength=len(arrays.blocks)
            ).astype(float)
            replicate_metrics[replicate] = dataset_metrics(arrays, weights)
        point_results[dataset] = {
            method: {
                endpoint: float(point[method_index, endpoint_index])
                for endpoint_index, endpoint in enumerate(ENDPOINTS)
            }
            for method_index, method in enumerate(METHODS)
        }
        comparisons = {
            "pirl_minus_erm_worst_fold_macro_f1": (
                point[1, 0] - point[0, 0],
                replicate_metrics[:, 1, 0] - replicate_metrics[:, 0, 0],
            ),
            "erm_minus_pirl_selective_risk_at_source_50pct": (
                point[0, 1] - point[1, 1],
                replicate_metrics[:, 0, 1] - replicate_metrics[:, 1, 1],
            ),
        }
        comparison_summaries[dataset] = {}
        for name, (point_difference, distribution) in comparisons.items():
            summary = _interval(float(point_difference), distribution)
            summary["positive_favors_pirl"] = True
            summary["minimum_practical_effect"] = PRACTICAL_EFFECTS[name]
            summary["practically_positive_and_ci_excludes_zero"] = bool(
                point_difference >= PRACTICAL_EFFECTS[name]
                and summary["ci95_low"] > 0
            )
            comparison_summaries[dataset][name] = summary
        for replicate in range(replicates):
            for method_index, method in enumerate(METHODS):
                replicate_rows.append(
                    {
                        "dataset": dataset,
                        "replicate": replicate,
                        "method": method,
                        **{
                            endpoint: float(
                                replicate_metrics[
                                    replicate, method_index, endpoint_index
                                ]
                            )
                            for endpoint_index, endpoint in enumerate(ENDPOINTS)
                        },
                    }
                )
        draw_plans.append(_draw_plan(dataset, arrays, choices, slots))
    replicate_frame = pd.DataFrame(replicate_rows)
    draw_plan = pd.concat(draw_plans, ignore_index=True)
    output_directory.mkdir(parents=True, exist_ok=True)
    replicate_path = output_directory / "bootstrap_metric_tensor.parquet"
    draw_path = output_directory / "bootstrap_draw_plan.parquet"
    replicate_frame.to_parquet(replicate_path, index=False)
    draw_plan.to_parquet(draw_path, index=False)
    input_record = {
        "target_predictions": str(target_predictions_path.resolve()),
        "target_predictions_sha256": _sha256(target_predictions_path),
        "selection_decisions": str(selection_decisions_path.resolve()),
        "selection_decisions_sha256": _sha256(selection_decisions_path),
        "paderborn_archive_contents_opened": False,
    }
    if authorization is not None:
        input_record.update(
            {
                "protocol_document": authorization["protocol_document_path"],
                "protocol_document_sha256": authorization["protocol_document"],
                "selective_validation": authorization[
                    "selective_validation_path"
                ],
                "selective_validation_sha256": authorization[
                    "selective_validation"
                ],
                "selective_metrics_sha256": authorization["selective_metrics"],
                "expected_manifest_sha256": authorization["expected_manifest"],
            }
        )
    metrics = {
        "bootstrap_version": BOOTSTRAP_VERSION,
        "generated_at": datetime.now(UTC).isoformat(),
        "protocol_document": (
            "research/protocols/selective_physical_bootstrap_v0.1.md"
        ),
        "input": input_record,
        "configuration": {
            "replicates": replicates,
            "seed": seed,
            "methods": list(METHODS),
            "model_seeds": list(AUDIT_SEEDS),
            "headline_score": HEADLINE_SCORE,
            "headline_source_coverage": HEADLINE_SOURCE_COVERAGE,
            "endpoints": list(ENDPOINTS),
            "stratification": "environment_id",
            "zero_accepted_bootstrap_draw_risk": 1.0,
            "practical_effects": PRACTICAL_EFFECTS,
        },
        "point_results": point_results,
        "paired_comparisons": comparison_summaries,
        "multiplicity": {
            "status": "not applied until the frozen D0/D1/D2 six-test family is complete",
            "planned_family_size": 6,
        },
        "artifacts": {
            "bootstrap_metric_tensor": _artifact(
                replicate_path, rows=len(replicate_frame)
            ),
            "bootstrap_draw_plan": _artifact(draw_path, rows=len(draw_plan)),
        },
    }
    metrics_path = output_directory / "metrics.json"
    metrics_path.write_text(
        json.dumps(metrics, ensure_ascii=False, indent=2, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    return metrics


def run_bootstrap(
    target_predictions_path: Path,
    selection_decisions_path: Path,
    output_directory: Path,
    *,
    target_predictions_sha256: str,
    selection_decisions_sha256: str,
    protocol_document: Path,
    protocol_sha256: str,
    selective_validation: Path,
    selective_validation_sha256: str,
    replicates: int = BOOTSTRAP_REPLICATES,
    seed: int = BOOTSTRAP_SEED,
) -> dict[str, Any]:
    """Run only the exact frozen formal bootstrap configuration."""

    if replicates != BOOTSTRAP_REPLICATES:
        raise ValueError(
            f"formal bootstrap requires exactly {BOOTSTRAP_REPLICATES} replicates"
        )
    if seed != BOOTSTRAP_SEED:
        raise ValueError(f"formal bootstrap requires root seed {BOOTSTRAP_SEED}")
    authorization = validate_execution_authorization(
        target_predictions_path=target_predictions_path,
        target_predictions_sha256=target_predictions_sha256,
        selection_decisions_path=selection_decisions_path,
        selection_decisions_sha256=selection_decisions_sha256,
        protocol_document=protocol_document,
        protocol_sha256=protocol_sha256,
        selective_validation=selective_validation,
        selective_validation_sha256=selective_validation_sha256,
    )
    return _run_bootstrap_core(
        Path(authorization["target_predictions_path"]),
        Path(authorization["selection_decisions_path"]),
        output_directory,
        replicates=replicates,
        seed=seed,
        authorization=authorization,
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--target-predictions", type=Path, required=True)
    parser.add_argument("--target-predictions-sha256", required=True)
    parser.add_argument("--selection-decisions", type=Path, required=True)
    parser.add_argument("--selection-decisions-sha256", required=True)
    parser.add_argument("--protocol-document", type=Path, required=True)
    parser.add_argument("--protocol-sha256", required=True)
    parser.add_argument("--selective-validation", type=Path, required=True)
    parser.add_argument("--selective-validation-sha256", required=True)
    parser.add_argument("--output-directory", type=Path, required=True)
    parser.add_argument("--replicates", type=int, default=BOOTSTRAP_REPLICATES)
    parser.add_argument("--seed", type=int, default=BOOTSTRAP_SEED)
    args = parser.parse_args()
    result = run_bootstrap(
        args.target_predictions,
        args.selection_decisions,
        args.output_directory,
        target_predictions_sha256=args.target_predictions_sha256,
        selection_decisions_sha256=args.selection_decisions_sha256,
        protocol_document=args.protocol_document,
        protocol_sha256=args.protocol_sha256,
        selective_validation=args.selective_validation,
        selective_validation_sha256=args.selective_validation_sha256,
        replicates=args.replicates,
        seed=args.seed,
    )
    print(json.dumps(result["paired_comparisons"], ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
