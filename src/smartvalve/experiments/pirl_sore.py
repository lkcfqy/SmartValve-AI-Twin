"""Compact source-only PIRL-SORE tabular model for multi-rig development."""

from __future__ import annotations

import hashlib
import os
from dataclasses import asdict, dataclass
from typing import Any

import numpy as np

os.environ.setdefault("CUBLAS_WORKSPACE_CONFIG", ":4096:8")

import torch
from torch import Tensor, nn

from smartvalve.experiments.domain_data import SourceOnlyFold


@dataclass(frozen=True)
class TrainingConfig:
    """Frozen inputs controlling one deterministic fit."""

    method: str = "pirl_sore"
    representation_dim: int = 32
    hidden_dim: int = 128
    epochs: int = 300
    learning_rate: float = 1e-3
    weight_decay: float = 1e-4
    rho: float = 0.5
    intervention_weight: float = 0.5
    worst_environment_weight: float = 0.5
    fault_margin: float = 1.0
    ratio_term_weight: float = 1.0
    fault_margin_weight: float = 1.0
    response_epsilon: float = 1e-4
    gradient_clip_norm: float = 5.0
    seed: int = 11

    def validate(self) -> None:
        if self.method not in {
            "erm",
            "worst_erm",
            "pirl_only",
            "pirl_sore",
            "pirl_ratio",
        }:
            raise ValueError(f"unsupported method: {self.method}")
        if min(self.representation_dim, self.hidden_dim, self.epochs) < 1:
            raise ValueError("model dimensions and epochs must be positive")
        if self.learning_rate <= 0 or self.weight_decay < 0:
            raise ValueError("optimizer settings are invalid")
        if not 0 <= self.rho <= 1:
            raise ValueError("rho must lie in [0, 1]")
        if min(self.intervention_weight, self.worst_environment_weight) < 0:
            raise ValueError("loss weights must be nonnegative")
        if (
            self.fault_margin <= 0
            or self.ratio_term_weight < 0
            or self.fault_margin_weight < 0
        ):
            raise ValueError("fault-margin settings are invalid")
        if self.response_epsilon <= 0:
            raise ValueError("response epsilon must be positive")
        if self.gradient_clip_norm <= 0:
            raise ValueError("gradient clipping norm must be positive")

    def effective_loss_weights(self) -> tuple[float, float]:
        if self.method == "erm":
            return 0.0, 0.0
        if self.method == "worst_erm":
            return 0.0, self.worst_environment_weight
        if self.method in {"pirl_only", "pirl_ratio"}:
            return self.intervention_weight, 0.0
        return self.intervention_weight, self.worst_environment_weight


@dataclass(frozen=True)
class FeatureStandardizer:
    mean: np.ndarray
    scale: np.ndarray

    @classmethod
    def fit(cls, features: np.ndarray) -> FeatureStandardizer:
        values = np.asarray(features, dtype=np.float64)
        if values.ndim != 2 or len(values) == 0 or not np.isfinite(values).all():
            raise ValueError("standardizer requires a finite non-empty feature matrix")
        mean = values.mean(axis=0)
        scale = values.std(axis=0)
        scale[scale < 1e-8] = 1.0
        return cls(mean=mean, scale=scale)

    def transform(self, features: np.ndarray) -> np.ndarray:
        values = np.asarray(features, dtype=np.float64)
        transformed = (values - self.mean) / self.scale
        if not np.isfinite(transformed).all():
            raise ValueError("standardization produced non-finite values")
        return transformed.astype(np.float32)


class TabularEncoder(nn.Module):
    """Small MLP whose unit-normalized representation exposes intervention responses."""

    def __init__(
        self,
        *,
        input_dimension: int,
        hidden_dimension: int,
        representation_dimension: int,
        class_count: int,
    ) -> None:
        super().__init__()
        self.encoder = nn.Sequential(
            nn.Linear(input_dimension, hidden_dimension),
            nn.GELU(),
            nn.LayerNorm(hidden_dimension),
            nn.Linear(hidden_dimension, representation_dimension),
        )
        self.classifier = nn.Linear(representation_dimension, class_count)

    def forward(self, features: Tensor) -> tuple[Tensor, Tensor]:
        representation = nn.functional.normalize(self.encoder(features), dim=1)
        return self.classifier(representation), representation


@dataclass
class FittedModel:
    config: TrainingConfig
    standardizer: FeatureStandardizer
    network: TabularEncoder
    device: torch.device
    history: list[dict[str, float | int]]
    state_sha256: str


@dataclass(frozen=True)
class PredictionBundle:
    logits: np.ndarray
    probabilities: np.ndarray
    predictions: np.ndarray
    representations: np.ndarray


@dataclass(frozen=True)
class ClassSupport:
    centers: np.ndarray
    scales: np.ndarray


def pair_response(representation: Tensor, pairs: Tensor) -> Tensor:
    """Mean squared unit-representation response over an audited pair set."""

    if pairs.ndim != 2 or pairs.shape[1] != 2 or len(pairs) == 0:
        raise ValueError("pairs must be a non-empty two-column tensor")
    differences = representation[pairs[:, 0]] - representation[pairs[:, 1]]
    return differences.square().sum(dim=1).mean()


def intervention_loss(
    representation: Tensor,
    nuisance_pairs: Tensor,
    fault_pairs: Tensor,
    *,
    rho: float,
) -> tuple[Tensor, Tensor, Tensor]:
    nuisance_response = pair_response(representation, nuisance_pairs)
    fault_response = pair_response(representation, fault_pairs)
    penalty = torch.relu(nuisance_response - rho * fault_response)
    return penalty, nuisance_response, fault_response


def response_ratio_loss(
    representation: Tensor,
    nuisance_pairs: Tensor,
    fault_pairs: Tensor,
    *,
    fault_margin: float,
    fault_margin_weight: float,
    epsilon: float,
    ratio_term_weight: float = 1.0,
) -> tuple[Tensor, Tensor, Tensor]:
    """Non-saturating nuisance/fault ratio plus an anti-collapse fault margin."""

    if (
        fault_margin <= 0
        or ratio_term_weight < 0
        or fault_margin_weight < 0
        or epsilon <= 0
    ):
        raise ValueError("response-ratio loss settings are invalid")
    nuisance_response = pair_response(representation, nuisance_pairs)
    fault_response = pair_response(representation, fault_pairs)
    ratio = nuisance_response / (fault_response + epsilon)
    margin = torch.relu(
        torch.as_tensor(fault_margin, device=fault_response.device)
        - fault_response
    )
    penalty = ratio_term_weight * ratio + fault_margin_weight * margin
    return penalty, nuisance_response, fault_response


def _state_sha256(model: nn.Module) -> str:
    digest = hashlib.sha256()
    for name, value in sorted(model.state_dict().items()):
        digest.update(name.encode("utf-8"))
        digest.update(b"\0")
        digest.update(value.detach().cpu().contiguous().numpy().tobytes())
        digest.update(b"\0")
    return digest.hexdigest()


def _configure_determinism(seed: int) -> None:
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)
    torch.use_deterministic_algorithms(True)
    torch.set_float32_matmul_precision("highest")
    torch.backends.cudnn.benchmark = False
    torch.backends.cudnn.deterministic = True


def _device(requested: str) -> torch.device:
    if requested == "auto":
        return torch.device("cuda:0" if torch.cuda.is_available() else "cpu")
    device = torch.device(requested)
    if device.type == "cuda" and not torch.cuda.is_available():
        raise RuntimeError("CUDA was requested but is not available")
    return device


def fit_fold(
    fold: SourceOnlyFold,
    config: TrainingConfig,
    *,
    device: str = "auto",
) -> FittedModel:
    """Fit only on the declared source partition and its source-local pairs."""

    fold.validate()
    config.validate()
    _configure_determinism(config.seed)
    selected_device = _device(device)
    if selected_device.type == "cuda":
        torch.cuda.init()

    standardizer = FeatureStandardizer.fit(fold.source_features)
    features = torch.from_numpy(
        standardizer.transform(fold.source_features)
    ).to(selected_device)
    labels = torch.from_numpy(fold.source_labels).to(selected_device)
    nuisance_pairs = torch.from_numpy(fold.nuisance_pairs).to(selected_device)
    fault_pairs = torch.from_numpy(fold.fault_pairs).to(selected_device)
    environment_values, environment_codes = np.unique(
        fold.source_environments, return_inverse=True
    )
    environment_masks = [
        torch.from_numpy(environment_codes == index).to(selected_device)
        for index in range(len(environment_values))
    ]

    model = TabularEncoder(
        input_dimension=features.shape[1],
        hidden_dimension=config.hidden_dim,
        representation_dimension=config.representation_dim,
        class_count=len(fold.label_names),
    ).to(selected_device)
    optimizer = torch.optim.AdamW(
        model.parameters(),
        lr=config.learning_rate,
        weight_decay=config.weight_decay,
    )
    intervention_weight, worst_weight = config.effective_loss_weights()
    history: list[dict[str, float | int]] = []
    checkpoints = {0, config.epochs - 1, *range(24, config.epochs, 25)}
    for epoch in range(config.epochs):
        model.train()
        optimizer.zero_grad(set_to_none=True)
        logits, representation = model(features)
        per_sample_loss = nn.functional.cross_entropy(logits, labels, reduction="none")
        empirical_risk = per_sample_loss.mean()
        worst_environment_risk = torch.stack(
            [per_sample_loss[mask].mean() for mask in environment_masks]
        ).max()
        if config.method == "pirl_ratio":
            pirl, nuisance_response, fault_response = response_ratio_loss(
                representation,
                nuisance_pairs,
                fault_pairs,
                fault_margin=config.fault_margin,
                ratio_term_weight=config.ratio_term_weight,
                fault_margin_weight=config.fault_margin_weight,
                epsilon=config.response_epsilon,
            )
        else:
            pirl, nuisance_response, fault_response = intervention_loss(
                representation,
                nuisance_pairs,
                fault_pairs,
                rho=config.rho,
            )
        objective = (
            empirical_risk
            + worst_weight * worst_environment_risk
            + intervention_weight * pirl
        )
        objective.backward()
        gradient_norm = nn.utils.clip_grad_norm_(
            model.parameters(), config.gradient_clip_norm
        )
        optimizer.step()
        if epoch in checkpoints:
            history.append(
                {
                    "epoch": epoch + 1,
                    "objective": float(objective.detach().cpu()),
                    "empirical_risk": float(empirical_risk.detach().cpu()),
                    "worst_environment_risk": float(
                        worst_environment_risk.detach().cpu()
                    ),
                    "intervention_loss": float(pirl.detach().cpu()),
                    "nuisance_response": float(nuisance_response.detach().cpu()),
                    "fault_response": float(fault_response.detach().cpu()),
                    "gradient_norm_before_clip": float(gradient_norm.detach().cpu()),
                }
            )
    if selected_device.type == "cuda":
        torch.cuda.synchronize(selected_device)
    return FittedModel(
        config=config,
        standardizer=standardizer,
        network=model,
        device=selected_device,
        history=history,
        state_sha256=_state_sha256(model),
    )


def predict(model: FittedModel, features: np.ndarray) -> PredictionBundle:
    model.network.eval()
    values = torch.from_numpy(model.standardizer.transform(features)).to(model.device)
    with torch.inference_mode():
        logits, representation = model.network(values)
        probabilities = torch.softmax(logits, dim=1)
    return PredictionBundle(
        logits=logits.cpu().numpy(),
        probabilities=probabilities.cpu().numpy(),
        predictions=probabilities.argmax(dim=1).cpu().numpy().astype(np.int64),
        representations=representation.cpu().numpy(),
    )


def fit_class_support(
    representations: np.ndarray,
    labels: np.ndarray,
    *,
    class_count: int,
    scale_floor: float = 1e-3,
) -> ClassSupport:
    values = np.asarray(representations, dtype=np.float64)
    truth = np.asarray(labels, dtype=np.int64)
    if values.ndim != 2 or len(values) != len(truth) or not np.isfinite(values).all():
        raise ValueError("class support requires aligned finite representations and labels")
    centers = []
    scales = []
    for label in range(class_count):
        class_values = values[truth == label]
        if len(class_values) < 2:
            raise ValueError("every source class needs at least two support points")
        center = np.median(class_values, axis=0)
        mad = 1.4826 * np.median(np.abs(class_values - center), axis=0)
        centers.append(center)
        scales.append(np.maximum(mad, scale_floor))
    return ClassSupport(centers=np.vstack(centers), scales=np.vstack(scales))


def robust_class_distance(
    representations: np.ndarray,
    support: ClassSupport,
) -> np.ndarray:
    values = np.asarray(representations, dtype=np.float64)
    standardized = (
        values[:, None, :] - support.centers[None, :, :]
    ) / support.scales[None, :, :]
    distances = np.sqrt(np.mean(standardized**2, axis=2))
    if not np.isfinite(distances).all():
        raise ValueError("robust class distance produced non-finite values")
    return distances


def risk_envelope_score(
    probabilities: np.ndarray,
    representations: np.ndarray,
    support: ClassSupport,
    *,
    beta: float,
) -> np.ndarray:
    if beta < 0:
        raise ValueError("beta must be nonnegative")
    probability_values = np.asarray(probabilities, dtype=np.float64)
    if (
        probability_values.ndim != 2
        or not np.isfinite(probability_values).all()
        or not np.allclose(probability_values.sum(axis=1), 1.0, atol=1e-6)
    ):
        raise ValueError("risk envelope requires finite normalized probabilities")
    uncertainty = 1.0 - probability_values.max(axis=1)
    distance = robust_class_distance(representations, support).min(axis=1)
    return uncertainty + beta * distance


def configuration_record(config: TrainingConfig) -> dict[str, Any]:
    return asdict(config)
