"""Retrospective Paderborn split-protocol contrast utilities.

The comparison deliberately holds features, classifiers, prediction rows, and
physical evaluation cells fixed while changing only source/target access.  D2
outcomes were already known when this analysis was designed, so none of the
outputs from this module are confirmatory evidence.
"""

from __future__ import annotations

from dataclasses import dataclass
from itertools import combinations
from time import monotonic

import numpy as np
import pandas as pd
from scipy.stats import kendalltau
from sklearn.base import ClassifierMixin
from sklearn.discriminant_analysis import LinearDiscriminantAnalysis
from sklearn.dummy import DummyClassifier
from sklearn.ensemble import ExtraTreesClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, balanced_accuracy_score, confusion_matrix, f1_score
from sklearn.model_selection import StratifiedKFold
from sklearn.neighbors import NearestCentroid
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.svm import SVC

from smartvalve.data.paderborn_features import main_signal_feature_names
from smartvalve.experiments.domain_data import SourceOnlyFold
from smartvalve.experiments.paderborn_domain import validate_paderborn_feature_frame
from smartvalve.experiments.paderborn_partitions import (
    PADERBORN_LABELS,
    build_paderborn_partitions,
    build_paderborn_source_pairs,
)
from smartvalve.experiments.paderborn_splits import PADERBORN_IDENTITY_FOLDS

SCHEMA_VERSION = "smartvalve-paderborn-protocol-contrast-0.1.0"
RANDOM_SEED = 20260819
RANDOM_FOLD_COUNT = 6
BOOTSTRAP_DRAWS = 2_000
PROTOCOLS = (
    "measurement_random",
    "setting_holdout",
    "identity_holdout",
    "crossed_holdout",
)
MODEL_NAMES = (
    "dummy_prior",
    "nearest_centroid",
    "shrinkage_lda",
    "logistic_l2",
    "linear_svm",
    "rbf_svm",
    "extra_trees",
)
PROBABILITY_COLUMNS = tuple(f"probability_{label}" for label in PADERBORN_LABELS)


@dataclass(frozen=True)
class ProtocolSplit:
    """One source/target split and any deliberately inaccessible cross-arms."""

    protocol: str
    fold_id: str
    source_indices: np.ndarray
    target_indices: np.ndarray
    quarantine_indices: np.ndarray

    def validate(self, frame: pd.DataFrame) -> None:
        if self.protocol not in PROTOCOLS:
            raise ValueError(f"unknown protocol: {self.protocol}")
        arrays = (self.source_indices, self.target_indices, self.quarantine_indices)
        for values in arrays:
            if values.ndim != 1 or not np.issubdtype(values.dtype, np.integer):
                raise ValueError("split coordinates must be one-dimensional integer arrays")
            if len(values) and (values.min() < 0 or values.max() >= len(frame)):
                raise ValueError("split coordinates point outside the feature frame")
        flattened = np.concatenate(arrays)
        if len(flattened) != len(frame) or len(np.unique(flattened)) != len(frame):
            raise ValueError("source, target, and quarantine must partition every row once")
        if len(self.source_indices) == 0 or len(self.target_indices) == 0:
            raise ValueError("source and target partitions must both be non-empty")
        source_labels = set(frame.iloc[self.source_indices]["truth"].astype(str))
        if source_labels != set(PADERBORN_LABELS):
            raise ValueError("a source fold does not contain all pure classes")


@dataclass(frozen=True)
class ProtocolModelFold:
    """A trainer-facing source/target view with immutable full-row provenance."""

    protocol: str
    fold: SourceOnlyFold
    target_global_indices: np.ndarray
    quarantine_global_indices: np.ndarray


def resolve_protocol_feature_names(
    frame: pd.DataFrame,
    feature_names: tuple[str, ...] | None = None,
) -> tuple[str, ...]:
    """Validate a frozen ordered subset of the complete Paderborn feature schema."""

    complete = validate_paderborn_feature_frame(frame)
    if feature_names is None:
        return complete
    requested = tuple(feature_names)
    if not requested:
        raise ValueError("protocol feature subset must be non-empty")
    if len(set(requested)) != len(requested):
        raise ValueError("protocol feature subset contains duplicate names")
    unknown = set(requested) - set(complete)
    if unknown:
        raise ValueError(f"protocol feature subset contains unknown names: {sorted(unknown)}")
    canonical = tuple(name for name in main_signal_feature_names() if name in requested)
    if canonical != requested:
        raise ValueError("protocol feature subset must preserve the frozen feature order")
    return requested


def _complement(row_count: int, target_indices: np.ndarray) -> np.ndarray:
    mask = np.ones(row_count, dtype=bool)
    mask[target_indices] = False
    return np.flatnonzero(mask)


def _identity_lookup() -> dict[str, str]:
    return {
        bearing_code: fold.fold_id
        for fold in PADERBORN_IDENTITY_FOLDS
        for bearing_code in fold.bearing_codes
    }


def attach_common_cells(frame: pd.DataFrame) -> pd.DataFrame:
    """Attach the frozen identity-fold/setting evaluation cell to each row."""

    result = frame.copy()
    identity = result["bearing_code"].map(_identity_lookup())
    if identity.isna().any():
        raise ValueError("a bearing is absent from the frozen identity folds")
    result["identity_fold_id"] = identity.astype(str)
    result["evaluation_cell"] = (
        result["identity_fold_id"] + "|setting=" + result["setting_code"].astype(str)
    )
    cells = result.groupby("evaluation_cell", sort=True, observed=True)
    if cells.ngroups != 24:
        raise ValueError("the common evaluation topology must contain 24 cells")
    for _, group in cells:
        if set(group["truth"].astype(str)) != set(PADERBORN_LABELS):
            raise ValueError("a common evaluation cell does not contain all pure classes")
    return result


def build_protocol_splits(
    frame: pd.DataFrame,
    *,
    random_seed: int = RANDOM_SEED,
) -> dict[str, tuple[ProtocolSplit, ...]]:
    """Build four complete OOF protocols from the frozen Paderborn metadata."""

    validate_paderborn_feature_frame(frame)
    row_count = len(frame)
    result: dict[str, tuple[ProtocolSplit, ...]] = {}

    random_splits = []
    splitter = StratifiedKFold(
        n_splits=RANDOM_FOLD_COUNT,
        shuffle=True,
        random_state=random_seed,
    )
    for fold_number, (_, target) in enumerate(
        splitter.split(np.zeros(row_count), frame["truth"].to_numpy(dtype=str))
    ):
        target = np.sort(target.astype(np.int64, copy=False))
        random_splits.append(
            ProtocolSplit(
                protocol="measurement_random",
                fold_id=f"random={fold_number}",
                source_indices=_complement(row_count, target),
                target_indices=target,
                quarantine_indices=np.empty(0, dtype=np.int64),
            )
        )
    result["measurement_random"] = tuple(random_splits)

    setting_splits = []
    for setting_code in sorted(frame["setting_code"].astype(str).unique()):
        target = np.flatnonzero(
            frame["setting_code"].to_numpy(dtype=str) == setting_code
        )
        setting_splits.append(
            ProtocolSplit(
                protocol="setting_holdout",
                fold_id=f"setting={setting_code}",
                source_indices=_complement(row_count, target),
                target_indices=target,
                quarantine_indices=np.empty(0, dtype=np.int64),
            )
        )
    result["setting_holdout"] = tuple(setting_splits)

    identity_splits = []
    bearing_values = frame["bearing_code"].to_numpy(dtype=str)
    for identity_fold in PADERBORN_IDENTITY_FOLDS:
        target = np.flatnonzero(np.isin(bearing_values, identity_fold.bearing_codes))
        identity_splits.append(
            ProtocolSplit(
                protocol="identity_holdout",
                fold_id=identity_fold.fold_id,
                source_indices=_complement(row_count, target),
                target_indices=target,
                quarantine_indices=np.empty(0, dtype=np.int64),
            )
        )
    result["identity_holdout"] = tuple(identity_splits)

    crossed_splits = []
    for partition in build_paderborn_partitions(frame):
        crossed_splits.append(
            ProtocolSplit(
                protocol="crossed_holdout",
                fold_id=partition.fold_id,
                source_indices=partition.source_indices.copy(),
                target_indices=partition.target_indices.copy(),
                quarantine_indices=partition.quarantine_indices.copy(),
            )
        )
    result["crossed_holdout"] = tuple(crossed_splits)

    if tuple(result) != PROTOCOLS:
        raise ValueError("protocol construction order changed")
    for protocol, splits in result.items():
        target_counts = np.zeros(row_count, dtype=np.int64)
        for split in splits:
            split.validate(frame)
            target_counts[split.target_indices] += 1
        if not np.all(target_counts == 1):
            raise ValueError(f"{protocol} does not target every row exactly once")
    return result


def build_protocol_model_folds(
    frame: pd.DataFrame,
    *,
    random_seed: int = RANDOM_SEED,
    feature_names: tuple[str, ...] | None = None,
) -> dict[str, tuple[ProtocolModelFold, ...]]:
    """Materialize source-local neural folds for all four split protocols.

    The environment definition remains the operating-setting code in every
    protocol.  Only the access split changes.  Pair indices are rebuilt using
    source rows alone, and quarantine rows are never inserted into the trainer
    view.
    """

    indexed = frame.reset_index(drop=True).copy()
    selected_features = resolve_protocol_feature_names(indexed, feature_names)
    splits = build_protocol_splits(indexed, random_seed=random_seed)
    label_index = {label: index for index, label in enumerate(PADERBORN_LABELS)}
    result: dict[str, tuple[ProtocolModelFold, ...]] = {}
    for protocol, protocol_splits in splits.items():
        model_folds = []
        for fold_number, split in enumerate(protocol_splits):
            retained_global = np.concatenate((split.source_indices, split.target_indices))
            retained = indexed.iloc[retained_global].reset_index(drop=True)
            labels = retained["truth"].map(label_index)
            if labels.isna().any():
                raise ValueError("protocol fold contains a non-primary label")
            source_count = len(split.source_indices)
            target_count = len(split.target_indices)
            source = retained.iloc[:source_count].reset_index(drop=True)
            nuisance_pairs, fault_pairs = build_paderborn_source_pairs(source)
            source_only = SourceOnlyFold(
                dataset="paderborn",
                fold_id=split.fold_id,
                held_factor=protocol,
                held_level=fold_number,
                features=retained.loc[:, selected_features].to_numpy(dtype=np.float32),
                labels=labels.to_numpy(dtype=np.int64),
                label_names=tuple(PADERBORN_LABELS),
                feature_names=selected_features,
                environment_ids=retained["setting_code"].to_numpy(dtype=str),
                block_ids=(
                    retained.loc[
                        :, ["bearing_code", "setting_code", "measurement_index"]
                    ]
                    .astype(str)
                    .agg("|".join, axis=1)
                    .to_numpy(dtype=str)
                ),
                source_indices=np.arange(source_count, dtype=np.int64),
                target_indices=np.arange(
                    source_count,
                    source_count + target_count,
                    dtype=np.int64,
                ),
                nuisance_pairs=nuisance_pairs,
                fault_pairs=fault_pairs,
            )
            source_only.validate()
            model_folds.append(
                ProtocolModelFold(
                    protocol=protocol,
                    fold=source_only,
                    target_global_indices=split.target_indices.copy(),
                    quarantine_global_indices=split.quarantine_indices.copy(),
                )
            )
        target_counts = np.zeros(len(indexed), dtype=np.int64)
        for model_fold in model_folds:
            target_counts[model_fold.target_global_indices] += 1
        if not np.all(target_counts == 1):
            raise ValueError(f"{protocol} neural folds do not target each row exactly once")
        result[protocol] = tuple(model_folds)
    return result


def build_classifier(name: str, *, random_seed: int = RANDOM_SEED) -> ClassifierMixin:
    """Instantiate one frozen, untuned classical comparison model."""

    if name == "dummy_prior":
        return DummyClassifier(strategy="prior")
    if name == "nearest_centroid":
        return make_pipeline(StandardScaler(), NearestCentroid(metric="euclidean"))
    if name == "shrinkage_lda":
        return make_pipeline(
            StandardScaler(),
            LinearDiscriminantAnalysis(solver="lsqr", shrinkage="auto"),
        )
    if name == "logistic_l2":
        return make_pipeline(
            StandardScaler(),
            LogisticRegression(
                C=1.0,
                solver="lbfgs",
                max_iter=5_000,
                random_state=random_seed,
            ),
        )
    if name == "linear_svm":
        return make_pipeline(
            StandardScaler(),
            SVC(C=1.0, kernel="linear", random_state=random_seed),
        )
    if name == "rbf_svm":
        return make_pipeline(
            StandardScaler(),
            SVC(
                C=1.0,
                kernel="rbf",
                gamma="scale",
                random_state=random_seed,
            ),
        )
    if name == "extra_trees":
        return ExtraTreesClassifier(
            n_estimators=256,
            max_features="sqrt",
            min_samples_leaf=1,
            bootstrap=False,
            random_state=random_seed,
            n_jobs=1,
        )
    raise ValueError(f"unknown fixed classifier: {name}")


def generate_oof_predictions(
    frame: pd.DataFrame,
    *,
    random_seed: int = RANDOM_SEED,
    model_names: tuple[str, ...] = MODEL_NAMES,
    feature_names: tuple[str, ...] | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Fit source-only classifiers and return complete per-record OOF predictions."""

    selected_features = resolve_protocol_feature_names(frame, feature_names)
    indexed = attach_common_cells(frame.reset_index(drop=True))
    protocols = build_protocol_splits(indexed, random_seed=random_seed)
    features = indexed.loc[:, selected_features].to_numpy(dtype=np.float64)
    labels = indexed["truth"].to_numpy(dtype=str)
    prediction_records = []
    fit_records = []
    metadata_columns = (
        "filename",
        "bearing_code",
        "setting_code",
        "measurement_index",
        "truth",
        "identity_fold_id",
        "evaluation_cell",
    )
    for protocol, splits in protocols.items():
        for split in splits:
            source_features = features[split.source_indices]
            source_labels = labels[split.source_indices]
            target_features = features[split.target_indices]
            for model_name in model_names:
                started = monotonic()
                classifier = build_classifier(model_name, random_seed=random_seed)
                classifier.fit(source_features, source_labels)
                predicted = np.asarray(classifier.predict(target_features), dtype=str)
                duration = monotonic() - started
                if len(predicted) != len(split.target_indices):
                    raise ValueError("classifier prediction count differs from target count")
                if not set(predicted).issubset(PADERBORN_LABELS):
                    raise ValueError("classifier emitted an unknown pure-class label")
                target = indexed.iloc[split.target_indices].loc[:, metadata_columns].copy()
                target.insert(0, "row_index", split.target_indices)
                target.insert(0, "fold_id", split.fold_id)
                target.insert(0, "method", model_name)
                target.insert(0, "protocol", protocol)
                target["prediction"] = predicted
                prediction_records.append(target)
                fit_records.append(
                    {
                        "protocol": protocol,
                        "fold_id": split.fold_id,
                        "method": model_name,
                        "source_count": len(split.source_indices),
                        "target_count": len(split.target_indices),
                        "quarantine_count": len(split.quarantine_indices),
                        "fit_predict_duration_s": duration,
                    }
                )
    predictions = pd.concat(prediction_records, ignore_index=True)
    fits = pd.DataFrame(fit_records)
    expected_rows = len(frame) * len(PROTOCOLS) * len(model_names)
    if len(predictions) != expected_rows:
        raise ValueError("OOF prediction matrix has an unexpected row count")
    key = ["protocol", "method", "row_index"]
    if predictions.duplicated(key).any():
        raise ValueError("OOF prediction matrix contains duplicate row keys")
    counts = predictions.groupby(["protocol", "method"], observed=True).size()
    if not (counts == len(frame)).all():
        raise ValueError("a protocol/method does not predict every row exactly once")
    return (
        predictions.sort_values(key, kind="stable").reset_index(drop=True),
        fits.sort_values(["protocol", "fold_id", "method"], kind="stable").reset_index(
            drop=True
        ),
    )


def _minimum_class_recall(truth: np.ndarray, predicted: np.ndarray) -> float:
    matrix = confusion_matrix(truth, predicted, labels=PADERBORN_LABELS)
    denominators = matrix.sum(axis=1)
    recalls = np.divide(
        np.diag(matrix),
        denominators,
        out=np.zeros(len(PADERBORN_LABELS), dtype=float),
        where=denominators > 0,
    )
    return float(recalls.min())


def _score_rows(rows: pd.DataFrame) -> dict[str, float | int]:
    truth = rows["truth"].to_numpy(dtype=str)
    predicted = rows["prediction"].to_numpy(dtype=str)
    return {
        "row_count": len(rows),
        "macro_f1": float(
            f1_score(
                truth,
                predicted,
                labels=PADERBORN_LABELS,
                average="macro",
                zero_division=0,
            )
        ),
        "balanced_accuracy": float(balanced_accuracy_score(truth, predicted)),
        "accuracy": float(accuracy_score(truth, predicted)),
        "minimum_class_recall": _minimum_class_recall(truth, predicted),
    }


def score_oof_predictions(
    predictions: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Score pooled predictions and the same 24 physical cells for every protocol."""

    required = {
        "protocol",
        "method",
        "row_index",
        "truth",
        "prediction",
        "evaluation_cell",
    }
    missing = required - set(predictions.columns)
    if missing:
        raise ValueError(f"prediction frame is missing columns: {sorted(missing)}")
    aggregate_records = []
    cell_records = []
    for (protocol, method), group in predictions.groupby(
        ["protocol", "method"], sort=True, observed=True
    ):
        pooled = _score_rows(group)
        cell_values = []
        for cell_id, cell in group.groupby("evaluation_cell", sort=True, observed=True):
            metrics = _score_rows(cell)
            cell_values.append(float(metrics["macro_f1"]))
            cell_records.append(
                {
                    "protocol": protocol,
                    "method": method,
                    "evaluation_cell": cell_id,
                    **metrics,
                }
            )
        if len(cell_values) != 24:
            raise ValueError("a protocol/method does not contain 24 evaluation cells")
        aggregate_records.append(
            {
                "protocol": protocol,
                "method": method,
                "row_count": pooled["row_count"],
                "pooled_macro_f1": pooled["macro_f1"],
                "pooled_balanced_accuracy": pooled["balanced_accuracy"],
                "pooled_accuracy": pooled["accuracy"],
                "pooled_minimum_class_recall": pooled["minimum_class_recall"],
                "mean_cell_macro_f1": float(np.mean(cell_values)),
                "median_cell_macro_f1": float(np.median(cell_values)),
                "minimum_cell_macro_f1": float(np.min(cell_values)),
                "q25_cell_macro_f1": float(np.quantile(cell_values, 0.25)),
            }
        )
    aggregate = pd.DataFrame(aggregate_records).sort_values(
        ["protocol", "method"], kind="stable"
    )
    for metric in ("pooled_macro_f1", "mean_cell_macro_f1"):
        aggregate[f"rank_{metric}"] = aggregate.groupby("protocol", observed=True)[
            metric
        ].rank(method="average", ascending=False)
    cells = pd.DataFrame(cell_records).sort_values(
        ["protocol", "method", "evaluation_cell"], kind="stable"
    )
    return aggregate.reset_index(drop=True), cells.reset_index(drop=True)


def ensemble_seed_predictions(
    predictions: pd.DataFrame,
    *,
    expected_seeds: tuple[int, ...],
) -> pd.DataFrame:
    """Average complete seed probabilities without changing physical metadata."""

    required = {
        "protocol",
        "method",
        "seed",
        "fold_id",
        "row_index",
        "filename",
        "bearing_code",
        "setting_code",
        "measurement_index",
        "truth",
        "identity_fold_id",
        "evaluation_cell",
        *PROBABILITY_COLUMNS,
    }
    missing = required - set(predictions.columns)
    if missing:
        raise ValueError(f"seed prediction frame is missing columns: {sorted(missing)}")
    if set(predictions["seed"].astype(int)) != set(expected_seeds):
        raise ValueError("seed prediction frame differs from the expected seed set")
    key = ["protocol", "method", "row_index"]
    counts = predictions.groupby(key, sort=False, observed=True)["seed"].nunique()
    if not (counts == len(expected_seeds)).all():
        raise ValueError("a protocol/method/row does not contain every expected seed")
    if predictions.duplicated([*key, "seed"]).any():
        raise ValueError("seed prediction frame contains a duplicate seed-level row")
    probabilities = predictions.loc[:, PROBABILITY_COLUMNS].to_numpy(dtype=float)
    if not np.isfinite(probabilities).all():
        raise ValueError("seed prediction frame contains non-finite probabilities")
    if float(np.max(np.abs(probabilities.sum(axis=1) - 1.0))) > 2e-6:
        raise ValueError("seed probabilities do not sum to one")

    metadata_columns = [
        "fold_id",
        "filename",
        "bearing_code",
        "setting_code",
        "measurement_index",
        "truth",
        "identity_fold_id",
        "evaluation_cell",
    ]
    metadata_counts = predictions.groupby(key, sort=False, observed=True)[
        metadata_columns
    ].nunique(dropna=False)
    if (metadata_counts > 1).any().any():
        raise ValueError("physical metadata change across seeds")
    aggregation = {column: "first" for column in metadata_columns}
    aggregation.update({column: "mean" for column in PROBABILITY_COLUMNS})
    ensemble = (
        predictions.groupby(key, sort=True, observed=True)
        .agg(aggregation)
        .reset_index()
    )
    ensemble_probabilities = ensemble.loc[:, PROBABILITY_COLUMNS].to_numpy(dtype=float)
    ensemble["prediction"] = np.asarray(PADERBORN_LABELS)[
        ensemble_probabilities.argmax(axis=1)
    ]
    return ensemble


def protocol_effect_table(
    aggregate: pd.DataFrame,
    *,
    reference_protocol: str = "crossed_holdout",
) -> pd.DataFrame:
    """Return every fixed metric contrast against one reference protocol."""

    metrics = (
        "pooled_macro_f1",
        "mean_cell_macro_f1",
        "median_cell_macro_f1",
        "minimum_cell_macro_f1",
        "q25_cell_macro_f1",
    )
    if reference_protocol not in set(aggregate["protocol"].astype(str)):
        raise ValueError("reference protocol is absent from aggregate metrics")
    reference = aggregate.loc[aggregate["protocol"] == reference_protocol].set_index(
        "method"
    )
    records = []
    for protocol in PROTOCOLS:
        if protocol == reference_protocol:
            continue
        comparison = aggregate.loc[aggregate["protocol"] == protocol].set_index("method")
        if set(comparison.index) != set(reference.index):
            raise ValueError("method set changes between protocol contrasts")
        for method in sorted(reference.index.astype(str)):
            for metric in metrics:
                records.append(
                    {
                        "comparison_protocol": protocol,
                        "reference_protocol": reference_protocol,
                        "method": method,
                        "metric": metric,
                        "effect_comparison_minus_reference": float(
                            comparison.loc[method, metric] - reference.loc[method, metric]
                        ),
                    }
                )
    return pd.DataFrame(records)


def protocol_rank_concordance(aggregate: pd.DataFrame) -> pd.DataFrame:
    """Compute pairwise method-rank agreement for the two frozen rank endpoints."""

    records = []
    for metric in ("pooled_macro_f1", "mean_cell_macro_f1"):
        ranks = aggregate.pivot(index="method", columns="protocol", values=metric).rank(
            ascending=False,
            method="average",
        )
        if set(ranks.columns) != set(PROTOCOLS):
            raise ValueError("rank table does not contain all frozen protocols")
        for left, right in combinations(PROTOCOLS, 2):
            result = kendalltau(ranks[left], ranks[right])
            records.append(
                {
                    "metric": metric,
                    "left_protocol": left,
                    "right_protocol": right,
                    "kendall_tau": float(result.statistic),
                    "method_count": len(ranks),
                }
            )
    return pd.DataFrame(records)


def _macro_f1_from_confusions(matrices: np.ndarray) -> np.ndarray:
    values = np.asarray(matrices, dtype=np.float64)
    true_positive = np.diagonal(values, axis1=-2, axis2=-1)
    false_positive = values.sum(axis=-2) - true_positive
    false_negative = values.sum(axis=-1) - true_positive
    denominator = 2.0 * true_positive + false_positive + false_negative
    per_class = np.divide(
        2.0 * true_positive,
        denominator,
        out=np.zeros_like(true_positive),
        where=denominator > 0,
    )
    return per_class.mean(axis=-1)


def paired_bearing_bootstrap(
    predictions: pd.DataFrame,
    *,
    draws: int = BOOTSTRAP_DRAWS,
    random_seed: int = RANDOM_SEED,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Bootstrap paired protocol effects using class-stratified bearing identities."""

    if draws < 1:
        raise ValueError("bootstrap draw count must be positive")
    bearing_truth = (
        predictions.loc[:, ["bearing_code", "truth"]]
        .drop_duplicates()
        .sort_values("bearing_code", kind="stable")
        .reset_index(drop=True)
    )
    counts = bearing_truth.groupby("bearing_code", observed=True)["truth"].nunique()
    if not (counts == 1).all():
        raise ValueError("a physical bearing is associated with multiple pure labels")
    bearing_codes = bearing_truth["bearing_code"].astype(str).to_numpy()
    bearing_index = {code: index for index, code in enumerate(bearing_codes)}
    draw_weights = np.zeros((draws, len(bearing_codes)), dtype=np.int16)
    generator = np.random.default_rng(random_seed)
    for label in PADERBORN_LABELS:
        candidates = np.flatnonzero(bearing_truth["truth"].to_numpy(dtype=str) == label)
        sampled = generator.choice(candidates, size=(draws, len(candidates)), replace=True)
        for draw_index, row in enumerate(sampled):
            draw_weights[draw_index] += np.bincount(
                row,
                minlength=len(bearing_codes),
            ).astype(np.int16)
    if not np.all(draw_weights.sum(axis=1) == len(bearing_codes)):
        raise ValueError("bearing bootstrap draw size changed")

    confusion_by_key: dict[tuple[str, str], np.ndarray] = {}
    for (protocol, method), group in predictions.groupby(
        ["protocol", "method"], sort=True, observed=True
    ):
        matrices = np.zeros(
            (len(bearing_codes), len(PADERBORN_LABELS), len(PADERBORN_LABELS)),
            dtype=np.int64,
        )
        for bearing_code, bearing_rows in group.groupby(
            "bearing_code", sort=True, observed=True
        ):
            matrices[bearing_index[str(bearing_code)]] = confusion_matrix(
                bearing_rows["truth"],
                bearing_rows["prediction"],
                labels=PADERBORN_LABELS,
            )
        confusion_by_key[(str(protocol), str(method))] = matrices

    draw_records = []
    summary_records = []
    effect_records = []
    methods = sorted(predictions["method"].astype(str).unique())
    for protocol in PROTOCOLS:
        if protocol == "crossed_holdout":
            continue
        for method in methods:
            comparison = np.einsum(
                "db,bij->dij",
                draw_weights,
                confusion_by_key[(protocol, method)],
                optimize=True,
            )
            reference = np.einsum(
                "db,bij->dij",
                draw_weights,
                confusion_by_key[("crossed_holdout", method)],
                optimize=True,
            )
            values = _macro_f1_from_confusions(comparison) - _macro_f1_from_confusions(
                reference
            )
            observed = float(
                _macro_f1_from_confusions(
                    confusion_by_key[(protocol, method)].sum(axis=0)[None, :, :]
                )[0]
                - _macro_f1_from_confusions(
                    confusion_by_key[("crossed_holdout", method)].sum(axis=0)[None, :, :]
                )[0]
            )
            lower, upper = np.quantile(values, (0.025, 0.975))
            summary_records.append(
                {
                    "comparison_protocol": protocol,
                    "reference_protocol": "crossed_holdout",
                    "method": method,
                    "metric": "pooled_macro_f1",
                    "effect_comparison_minus_reference": observed,
                    "bootstrap_lower_95": float(lower),
                    "bootstrap_upper_95": float(upper),
                    "bootstrap_draws": draws,
                    "resampling_unit": "bearing_code_stratified_by_truth",
                }
            )
            effect_records.append(values)
            draw_records.extend(
                {
                    "draw": draw_index,
                    "comparison_protocol": protocol,
                    "reference_protocol": "crossed_holdout",
                    "method": method,
                    "effect_comparison_minus_reference": float(value),
                }
                for draw_index, value in enumerate(values)
            )
    draw_plan = pd.DataFrame(draw_weights, columns=bearing_codes)
    raw_draws = pd.DataFrame(draw_records)
    summaries = pd.DataFrame(summary_records)
    if len(effect_records) != (len(PROTOCOLS) - 1) * len(methods):
        raise ValueError("bootstrap effect family size changed")
    return summaries, raw_draws, draw_plan
