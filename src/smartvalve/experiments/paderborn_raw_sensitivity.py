"""Knap-style raw-vibration architecture sensitivity for Paderborn protocols.

The layer definitions adapt the MIT-licensed ``pdm-bench`` implementation pinned in
``THIRD_PARTY_NOTICES.md``. SmartValve supplies a different factorial split, deterministic
whole-record window sampler, prediction aggregation, and physical-bearing inference.
"""

from __future__ import annotations

from collections.abc import Mapping

import numpy as np
import pandas as pd
import torch
from sklearn.metrics import confusion_matrix
from torch import nn

from smartvalve.experiments.paderborn_partitions import PADERBORN_LABELS
from smartvalve.experiments.paderborn_protocol_contrast import (
    PROBABILITY_COLUMNS,
    _macro_f1_from_confusions,
)

RAW_SENSITIVITY_VERSION = "smartvalve-paderborn-raw-sensitivity-0.1.0"
UPSTREAM_COMMIT = "ca524087219fd47bb7fb51ce63563c05b34cd6ee"
RAW_MODELS = ("cnn1d", "fft", "stft")
RAW_PROTOCOLS = ("measurement_random", "crossed_holdout")
RAW_SEEDS = (41, 42, 43)
WINDOW_SIZE = 8_192
WINDOWS_PER_RECORD = 4
EPOCHS = 50
BATCH_SIZE = 128


def deterministic_window_offsets(
    signal_length: int,
    *,
    window_size: int = WINDOW_SIZE,
    window_count: int = WINDOWS_PER_RECORD,
) -> tuple[int, ...]:
    """Place fixed windows from the first through the last valid sample."""

    if signal_length < window_size:
        raise ValueError("raw signal is shorter than one sensitivity window")
    if window_count < 1:
        raise ValueError("window count must be positive")
    maximum_start = signal_length - window_size
    if window_count == 1:
        return (maximum_start // 2,)
    offsets = tuple(
        int(round(value))
        for value in np.linspace(0, maximum_start, window_count, dtype=np.float64)
    )
    if len(set(offsets)) != window_count:
        raise ValueError("raw sensitivity windows are not distinct")
    return offsets


def standardize_raw_windows(values: torch.Tensor) -> torch.Tensor:
    """Apply the upstream per-window, per-channel normalization contract."""

    if values.ndim != 3:
        raise ValueError("raw model input must have shape (batch, channel, sample)")
    mean = values.mean(dim=-1, keepdim=True)
    std = values.std(dim=-1, keepdim=True, unbiased=False)
    return (values - mean) / (std + 1e-8)


class KnapCnn1d(nn.Module):
    """MIT-derived 1D CNN used as an architecture sensitivity."""

    def __init__(self, in_channels: int = 1, class_count: int = 3) -> None:
        super().__init__()
        self.features = nn.Sequential(
            nn.Conv1d(in_channels, 32, 7, padding=3),
            nn.BatchNorm1d(32),
            nn.ReLU(),
            nn.Conv1d(32, 64, 5, padding=2),
            nn.BatchNorm1d(64),
            nn.ReLU(),
            nn.Conv1d(64, 128, 3, padding=1),
            nn.BatchNorm1d(128),
            nn.ReLU(),
            nn.AdaptiveAvgPool1d(1),
        )
        self.classifier = nn.Sequential(
            nn.Flatten(),
            nn.Linear(128, 64),
            nn.ReLU(),
            nn.Dropout(0.4),
            nn.Linear(64, class_count),
        )

    def forward(self, values: torch.Tensor) -> torch.Tensor:
        return self.classifier(self.features(values))


class LogFftFrontEnd(nn.Module):
    """Log-amplitude real FFT from the upstream FFT architecture."""

    def __init__(self, epsilon: float = 1e-6) -> None:
        super().__init__()
        self.epsilon = epsilon

    def forward(self, values: torch.Tensor) -> torch.Tensor:
        return torch.fft.rfft(values, dim=-1).abs().clamp_min(self.epsilon).log()


class KnapFftCnn(nn.Module):
    """MIT-derived log-FFT CNN used as an architecture sensitivity."""

    def __init__(self, in_channels: int = 1, class_count: int = 3) -> None:
        super().__init__()
        self.front_end = LogFftFrontEnd()
        self.input_norm = nn.InstanceNorm1d(in_channels, affine=False, eps=1e-5)
        self.features = nn.Sequential(
            nn.Conv1d(in_channels, 32, 7, padding=3),
            nn.BatchNorm1d(32),
            nn.ReLU(),
            nn.Conv1d(32, 64, 5, padding=2),
            nn.BatchNorm1d(64),
            nn.ReLU(),
            nn.Conv1d(64, 128, 3, padding=1),
            nn.BatchNorm1d(128),
            nn.ReLU(),
            nn.AdaptiveAvgPool1d(1),
        )
        self.classifier = nn.Sequential(
            nn.Flatten(),
            nn.Linear(128, 64),
            nn.ReLU(),
            nn.Dropout(0.4),
            nn.Linear(64, class_count),
        )

    def forward(self, values: torch.Tensor) -> torch.Tensor:
        spectra = self.input_norm(self.front_end(values))
        return self.classifier(self.features(spectra))


class LogStftFrontEnd(nn.Module):
    """Log-magnitude STFT from the upstream STFT architecture."""

    def __init__(self, n_fft: int = 1_024, epsilon: float = 1e-6) -> None:
        super().__init__()
        self.n_fft = n_fft
        self.hop_length = n_fft // 4
        self.epsilon = epsilon
        self.register_buffer("window", torch.hann_window(n_fft), persistent=False)

    def forward(self, values: torch.Tensor) -> torch.Tensor:
        batch, channels, length = values.shape
        flattened = values.reshape(batch * channels, length).float()
        spectrum = torch.stft(
            flattened,
            n_fft=self.n_fft,
            hop_length=self.hop_length,
            win_length=self.n_fft,
            window=self.window.float(),
            return_complex=True,
            center=True,
        ).abs()
        log_spectrum = spectrum.clamp_min(self.epsilon).log()
        return log_spectrum.reshape(
            batch,
            channels,
            log_spectrum.shape[-2],
            log_spectrum.shape[-1],
        )


class KnapStftCnn(nn.Module):
    """MIT-derived log-STFT CNN used as an architecture sensitivity."""

    def __init__(
        self,
        in_channels: int = 1,
        class_count: int = 3,
        *,
        n_fft: int = 1_024,
    ) -> None:
        super().__init__()
        self.front_end = LogStftFrontEnd(n_fft=n_fft)
        self.input_norm = nn.InstanceNorm2d(in_channels, affine=False, eps=1e-5)
        self.features = nn.Sequential(
            nn.Conv2d(in_channels, 32, 3, padding=1),
            nn.BatchNorm2d(32),
            nn.ReLU(),
            nn.MaxPool2d(2),
            nn.Conv2d(32, 64, 3, padding=1),
            nn.BatchNorm2d(64),
            nn.ReLU(),
            nn.MaxPool2d(2),
            nn.Conv2d(64, 128, 3, padding=1),
            nn.BatchNorm2d(128),
            nn.ReLU(),
            nn.AdaptiveAvgPool2d((1, 1)),
        )
        self.classifier = nn.Sequential(
            nn.Flatten(),
            nn.Linear(128, 64),
            nn.ReLU(),
            nn.Dropout(0.4),
            nn.Linear(64, class_count),
        )

    def forward(self, values: torch.Tensor) -> torch.Tensor:
        spectra = self.input_norm(self.front_end(values))
        return self.classifier(self.features(spectra))


def build_raw_sensitivity_model(
    name: str,
    *,
    n_fft: int = 1_024,
) -> nn.Module:
    """Construct one of the three frozen architecture references."""

    if name == "cnn1d":
        return KnapCnn1d()
    if name == "fft":
        return KnapFftCnn()
    if name == "stft":
        return KnapStftCnn(n_fft=n_fft)
    raise ValueError(f"unknown raw sensitivity model: {name}")


def aggregate_raw_window_predictions(
    predictions: pd.DataFrame,
    *,
    windows_per_record: int = WINDOWS_PER_RECORD,
) -> pd.DataFrame:
    """Average window probabilities to one seed-level recording prediction."""

    key = ["protocol", "method", "seed", "row_index"]
    metadata = [
        "fold_id",
        "filename",
        "bearing_code",
        "setting_code",
        "measurement_index",
        "truth",
        "identity_fold_id",
        "evaluation_cell",
    ]
    required = {*key, "window_index", *metadata, *PROBABILITY_COLUMNS}
    missing = required - set(predictions)
    if missing:
        raise ValueError(f"raw window predictions are missing columns: {sorted(missing)}")
    counts = predictions.groupby(key, observed=True).size()
    if not counts.eq(windows_per_record).all():
        raise ValueError("a raw recording does not contain every deterministic window")
    if predictions.duplicated([*key, "window_index"]).any():
        raise ValueError("raw window predictions contain a duplicate window")
    metadata_counts = predictions.groupby(key, observed=True)[metadata].nunique(dropna=False)
    if (metadata_counts > 1).any().any():
        raise ValueError("raw recording metadata change across windows")
    probabilities = predictions.loc[:, PROBABILITY_COLUMNS].to_numpy(dtype=float)
    if not np.isfinite(probabilities).all():
        raise ValueError("raw window probabilities contain non-finite values")
    if float(np.max(np.abs(probabilities.sum(axis=1) - 1.0))) > 2e-6:
        raise ValueError("raw window probabilities do not sum to one")
    aggregation: dict[str, str] = {column: "first" for column in metadata}
    aggregation.update({column: "mean" for column in PROBABILITY_COLUMNS})
    records = predictions.groupby(key, sort=True, observed=True).agg(aggregation).reset_index()
    values = records.loc[:, PROBABILITY_COLUMNS].to_numpy(dtype=float)
    records["prediction"] = np.asarray(PADERBORN_LABELS)[values.argmax(axis=1)]
    return records


def paired_raw_protocol_bootstrap(
    predictions: pd.DataFrame,
    *,
    draws: int = 2_000,
    random_seed: int = 2_026_081_8,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Pair random and crossed scores on class-stratified physical-bearing draws."""

    if draws < 1:
        raise ValueError("raw sensitivity bootstrap draws must be positive")
    if set(predictions["protocol"].astype(str)) != set(RAW_PROTOCOLS):
        raise ValueError("raw sensitivity predictions change the two frozen protocols")
    if set(predictions["method"].astype(str)) != set(RAW_MODELS):
        raise ValueError("raw sensitivity predictions change the frozen architecture set")
    bearing_truth = (
        predictions.loc[:, ["bearing_code", "truth"]]
        .drop_duplicates()
        .sort_values("bearing_code", kind="stable")
        .reset_index(drop=True)
    )
    if not bearing_truth.groupby("bearing_code", observed=True)["truth"].nunique().eq(1).all():
        raise ValueError("a raw sensitivity bearing has more than one label")
    bearing_codes = bearing_truth["bearing_code"].astype(str).to_numpy()
    lookup = {bearing: index for index, bearing in enumerate(bearing_codes)}
    weights = np.zeros((draws, len(bearing_codes)), dtype=np.int16)
    generator = np.random.default_rng(random_seed)
    for label in PADERBORN_LABELS:
        candidates = np.flatnonzero(bearing_truth["truth"].to_numpy(dtype=str) == label)
        sampled = generator.choice(candidates, size=(draws, len(candidates)), replace=True)
        for draw_index, values in enumerate(sampled):
            weights[draw_index] += np.bincount(
                values,
                minlength=len(bearing_codes),
            ).astype(np.int16)

    confusions: dict[tuple[str, str], np.ndarray] = {}
    for (protocol, method), rows in predictions.groupby(
        ["protocol", "method"], sort=True, observed=True
    ):
        matrices = np.zeros((len(bearing_codes), 3, 3), dtype=np.int64)
        for bearing, bearing_rows in rows.groupby("bearing_code", sort=True, observed=True):
            matrices[lookup[str(bearing)]] = confusion_matrix(
                bearing_rows["truth"],
                bearing_rows["prediction"],
                labels=PADERBORN_LABELS,
            )
        confusions[(str(protocol), str(method))] = matrices

    summaries = []
    draw_rows = []
    for method in RAW_MODELS:
        comparison_confusions = confusions[("measurement_random", method)]
        reference_confusions = confusions[("crossed_holdout", method)]
        comparison = _macro_f1_from_confusions(
            np.einsum("db,bij->dij", weights, comparison_confusions, optimize=True)
        )
        reference = _macro_f1_from_confusions(
            np.einsum("db,bij->dij", weights, reference_confusions, optimize=True)
        )
        differences = comparison - reference
        observed = float(
            _macro_f1_from_confusions(comparison_confusions.sum(axis=0)[None])[0]
            - _macro_f1_from_confusions(reference_confusions.sum(axis=0)[None])[0]
        )
        lower, upper = np.quantile(differences, (0.025, 0.975))
        summaries.append(
            {
                "comparison_protocol": "measurement_random",
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
        draw_rows.extend(
            {
                "draw": draw,
                "method": method,
                "effect_comparison_minus_reference": float(value),
            }
            for draw, value in enumerate(differences)
        )
    return (
        pd.DataFrame(summaries),
        pd.DataFrame(draw_rows),
        pd.DataFrame(weights, columns=bearing_codes),
    )


def raw_sensitivity_gate(bootstrap: pd.DataFrame) -> Mapping[str, object]:
    """Apply the frozen representation-sensitivity advancement rule."""

    if set(bootstrap["method"].astype(str)) != set(RAW_MODELS):
        raise ValueError("raw sensitivity gate received another model family")
    effects = bootstrap["effect_comparison_minus_reference"].to_numpy(dtype=float)
    lower = bootstrap["bootstrap_lower_95"].to_numpy(dtype=float)
    return {
        "positive_model_count": int((effects > 0).sum()),
        "positive_interval_count": int((lower > 0).sum()),
        "median_random_minus_crossed_macro_f1": float(np.median(effects)),
        "representation_sensitivity_rule_passed": bool(
            (effects > 0).all() and (lower > 0).all() and np.median(effects) >= 0.15
        ),
    }
