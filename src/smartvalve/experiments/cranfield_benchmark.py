"""Reproducible grouped benchmark over all synced Cranfield actuator trials.

This is an offline evidence generator, not a model served by the diagnostic API.  It
evaluates whether source-specific current/position features transfer to an unseen
load while a healthy reference from that operating condition remains available.
"""

from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import sklearn
from sklearn.ensemble import ExtraTreesClassifier
from sklearn.metrics import accuracy_score, classification_report, confusion_matrix

from smartvalve.config import project_root
from smartvalve.data.cranfield import load_cranfield_frame
from smartvalve.data.external import cache_directory

LABELS = ("normal", "lack_of_lubrication", "backlash")
FILES = {
    "normal": "Normal.mat",
    "lack_of_lubrication": "LackLubrication2.mat",
    "backlash": "Backlash2.mat",
}
MOTIONS = ("trap", "sin")
LOADS = (-40, 20, 40)
REPETITIONS = tuple(range(1, 11))
BENCHMARK_VERSION = "cranfield-extra-trees-dev-0.1.0"


def _file_sha256(path: Path) -> str:
    digest = sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _raw_features(frame: pd.DataFrame) -> dict[str, float]:
    """Extract fixed, interpretable distribution and travel-bin features."""

    current = frame["motor_current_a"].to_numpy(dtype=float)
    error = (frame["command_pct"] - frame["position_pct"]).to_numpy(dtype=float)
    position = frame["position_pct"].to_numpy(dtype=float)
    velocity = frame["velocity_pct_s"].to_numpy(dtype=float)
    absolute_velocity = np.abs(velocity)
    moving = absolute_velocity > np.percentile(absolute_velocity, 50)
    direction_threshold = np.percentile(absolute_velocity, 60)
    opening = velocity > direction_threshold
    closing = velocity < -direction_threshold
    features: dict[str, float] = {}

    signals = {
        "current": current,
        "error": error,
        "absolute_error": np.abs(error),
        "velocity": velocity,
        "absolute_velocity": absolute_velocity,
    }
    for name, values in signals.items():
        for quantile in (5, 10, 25, 50, 75, 90, 95, 99):
            features[f"{name}_q{quantile}"] = float(np.percentile(values, quantile))
        features[f"{name}_mean"] = float(np.mean(values))
        features[f"{name}_std"] = float(np.std(values))
        features[f"{name}_rms"] = float(np.sqrt(np.mean(values**2)))

    for direction, mask in (("moving", moving), ("opening", opening), ("closing", closing)):
        for name, values in {
            "current": current,
            "error": error,
            "absolute_error": np.abs(error),
            "velocity": velocity,
        }.items():
            selected = values[mask]
            features[f"{direction}_{name}_mean"] = float(np.mean(selected))
            features[f"{direction}_{name}_std"] = float(np.std(selected))
            features[f"{direction}_{name}_rms"] = float(np.sqrt(np.mean(selected**2)))
            features[f"{direction}_{name}_q90"] = float(np.percentile(selected, 90))

    for lower in range(0, 100, 10):
        mask = (position >= lower) & (position < lower + 10) & moving
        features[f"travel_{lower}_current_mean"] = float(np.mean(current[mask]))
        features[f"travel_{lower}_error_mean"] = float(np.mean(error[mask]))
        features[f"travel_{lower}_absolute_error_mean"] = float(np.mean(np.abs(error[mask])))

    features["opening_closing_current_delta"] = float(
        np.mean(current[opening]) - np.mean(current[closing])
    )
    features["opening_closing_error_delta"] = float(
        np.mean(error[opening]) - np.mean(error[closing])
    )
    features["current_error_correlation"] = float(np.corrcoef(current, error)[0, 1])
    return features


def _relative_features(
    current: dict[str, float], baseline: dict[str, float]
) -> dict[str, float]:
    features: dict[str, float] = {}
    for name, value in current.items():
        reference = baseline[name]
        features[f"delta_{name}"] = value - reference
        features[f"relative_{name}"] = (value - reference) / (abs(reference) + 1e-6)
    return features


def build_matrix() -> pd.DataFrame:
    """Build 180 labelled trials with a non-identical matched healthy reference."""

    raw: dict[tuple[str, str, int, int], dict[str, float]] = {}
    for motion in MOTIONS:
        for label, filename in FILES.items():
            for load_kg in LOADS:
                for repetition in REPETITIONS:
                    frame = load_cranfield_frame(
                        filename,
                        motion=motion,
                        load_kg=load_kg,
                        repetition=repetition,
                    )
                    raw[(motion, label, load_kg, repetition)] = _raw_features(frame)

    rows: list[dict[str, Any]] = []
    for motion in MOTIONS:
        for label in LABELS:
            for load_kg in LOADS:
                for repetition in REPETITIONS:
                    baseline_repetition = repetition % len(REPETITIONS) + 1
                    rows.append(
                        {
                            "motion": motion,
                            "load_kg": load_kg,
                            "repetition": repetition,
                            "baseline_repetition": baseline_repetition,
                            "truth": label,
                            **_relative_features(
                                raw[(motion, label, load_kg, repetition)],
                                raw[(motion, "normal", load_kg, baseline_repetition)],
                            ),
                        }
                    )
    return pd.DataFrame(rows).replace([np.inf, -np.inf], np.nan).fillna(0.0)


def run_benchmark(output_directory: Path | None = None) -> dict[str, Any]:
    """Evaluate six motion/load folds and persist transparent evidence artifacts."""

    output_directory = output_directory or (
        project_root() / "artifacts" / "validation" / "cranfield"
    )
    matrix = build_matrix()
    metadata_columns = {
        "motion",
        "load_kg",
        "repetition",
        "baseline_repetition",
        "truth",
    }
    feature_columns = [column for column in matrix if column not in metadata_columns]
    predictions = pd.Series(index=matrix.index, dtype="object")
    evidence_scores = pd.Series(index=matrix.index, dtype=float)
    folds: list[dict[str, Any]] = []

    for motion in MOTIONS:
        for held_out_load in LOADS:
            test_mask = (matrix["motion"] == motion) & (matrix["load_kg"] == held_out_load)
            train_mask = (matrix["motion"] == motion) & (matrix["load_kg"] != held_out_load)
            classifier = ExtraTreesClassifier(
                n_estimators=500,
                min_samples_leaf=2,
                max_features="sqrt",
                class_weight="balanced",
                random_state=42,
                n_jobs=-1,
            )
            classifier.fit(matrix.loc[train_mask, feature_columns], matrix.loc[train_mask, "truth"])
            fold_prediction = classifier.predict(matrix.loc[test_mask, feature_columns])
            fold_scores = classifier.predict_proba(
                matrix.loc[test_mask, feature_columns]
            ).max(axis=1)
            predictions.loc[test_mask] = fold_prediction
            evidence_scores.loc[test_mask] = fold_scores
            folds.append(
                {
                    "motion": motion,
                    "held_out_load_kg": held_out_load,
                    "training_trials": int(train_mask.sum()),
                    "test_trials": int(test_mask.sum()),
                    "accuracy": round(
                        float(accuracy_score(matrix.loc[test_mask, "truth"], fold_prediction)), 4
                    ),
                }
            )

    records = matrix.loc[:, ["motion", "load_kg", "repetition", "baseline_repetition", "truth"]]
    records = records.assign(
        prediction=predictions,
        correct=predictions == matrix["truth"],
        uncalibrated_evidence_score=evidence_scores.round(6),
    )
    report = classification_report(
        records["truth"],
        records["prediction"],
        labels=list(LABELS),
        output_dict=True,
        zero_division=0,
    )
    per_class = {
        label: {
            metric: round(float(report[label][metric]), 4)
            for metric in ("precision", "recall", "f1-score", "support")
        }
        for label in LABELS
    }
    confusion_values = confusion_matrix(
        records["truth"], records["prediction"], labels=list(LABELS)
    )
    confusion = {
        truth: {
            prediction: int(confusion_values[row, column])
            for column, prediction in enumerate(LABELS)
        }
        for row, truth in enumerate(LABELS)
    }
    cache = cache_directory()
    metrics: dict[str, Any] = {
        "benchmark_version": BENCHMARK_VERSION,
        "generated_at": datetime.now(UTC).isoformat(),
        "dataset": {
            "name": "Cranfield Real Linear Actuator Rig",
            "license": "CC BY 4.0",
            "citation_url": "https://doi.org/10.17862/cranfield.rd.5097649",
            "physical_scope": "Electromechanical ball-screw actuator; not a water valve",
            "trials": len(records),
            "motion_load_groups": len(MOTIONS) * len(LOADS),
            "classes": len(LABELS),
            "samples_per_trial": 2000,
            "input_sha256": {
                filename: _file_sha256(cache / filename) for filename in FILES.values()
            },
        },
        "protocol": {
            "name": "motion-specific leave-one-load-out development cross-validation",
            "folds": len(folds),
            "feature_count": len(feature_columns),
            "healthy_reference": (
                "Each trial is compared with a different normal repetition from the same "
                "motion/load condition; the evaluated current trial is never its own baseline."
            ),
            "leakage_control": (
                "Every fold excludes all labelled trials at the test load from model fitting."
            ),
            "estimator": (
                "ExtraTreesClassifier(n_estimators=500, min_samples_leaf=2, "
                "max_features='sqrt', class_weight='balanced', random_state=42)"
            ),
            "library_version": f"scikit-learn {sklearn.__version__}",
        },
        "results": {
            "accuracy": round(float(accuracy_score(records["truth"], records["prediction"])), 4),
            "macro_f1": round(float(report["macro avg"]["f1-score"]), 4),
            "per_class": per_class,
            "confusion_matrix": confusion,
            "folds": folds,
        },
        "limitations": [
            "Development cross-validation, not a locked independent final test.",
            "Hyperparameters were selected while observing this dataset and these group folds.",
            "Trials are repeated experiments from one public actuator rig, not independent assets.",
            "The -40 kg trapezoidal fold is a documented failure mode, not hidden from reporting.",
            (
                "Evidence scores are uncalibrated tree-vote strengths and must not be read "
                "as probabilities."
            ),
            (
                "This benchmark is not served as the generic ValveDNA diagnosis and does "
                "not prove water-valve performance."
            ),
        ],
    }

    output_directory.mkdir(parents=True, exist_ok=True)
    records.to_csv(output_directory / "records.csv", index=False)
    (output_directory / "metrics.json").write_text(
        json.dumps(metrics, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (output_directory / "model_card.md").write_text(
        "\n".join(
            (
                "# Cranfield source-specific development benchmark",
                "",
                f"- Version: `{BENCHMARK_VERSION}`",
                f"- Trials: {len(records)} across six motion/load groups",
                f"- Leave-one-load-out accuracy: {metrics['results']['accuracy']:.4f}",
                f"- Macro F1: {metrics['results']['macro_f1']:.4f}",
                "- Scope: electromechanical ball-screw actuator, not a water valve",
                "",
                "## Split and leakage boundary",
                "",
                metrics["protocol"]["healthy_reference"],
                metrics["protocol"]["leakage_control"],
                "",
                "## Limitations",
                "",
                *(f"- {item}" for item in metrics["limitations"]),
                "",
            )
        ),
        encoding="utf-8",
    )
    return metrics


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-directory", type=Path)
    args = parser.parse_args()
    result = run_benchmark(args.output_directory)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
