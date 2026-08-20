"""Shared-backbone deterministic trainers for mandatory neural DG baselines."""

from __future__ import annotations

import hashlib
from dataclasses import asdict, dataclass
from typing import Any

import numpy as np
import torch
from torch import Tensor, nn

from smartvalve.experiments.dg_losses import (
    DomainDiscriminator,
    GroupDROWeights,
    beta_mixing_coefficients,
    conditional_contrastive_loss,
    coral_penalty,
    group_mean_losses,
    lisa_mixup,
    matched_alignment_loss,
    vrex_penalty,
)
from smartvalve.experiments.domain_data import SourceOnlyFold
from smartvalve.experiments.pirl_sore import (
    FeatureStandardizer,
    PredictionBundle,
    TabularEncoder,
    _configure_determinism,
    _device,
)

BASELINE_METHODS = (
    "erm",
    "coral",
    "vrex",
    "groupdro",
    "dann",
    "lisa",
    "matchdg",
    "ccdg",
)


@dataclass(frozen=True)
class BaselineConfig:
    method: str
    representation_dim: int = 32
    hidden_dim: int = 128
    epochs: int = 300
    learning_rate: float = 1e-3
    weight_decay: float = 1e-4
    penalty_weight: float = 0.5
    groupdro_step_size: float = 0.01
    dann_coefficient: float = 0.1
    lisa_alpha: float = 2.0
    ccdg_temperature: float = 0.7
    gradient_clip_norm: float = 5.0
    seed: int = 11

    def validate(self) -> None:
        if self.method not in BASELINE_METHODS:
            raise ValueError(f"unsupported DG baseline: {self.method}")
        if min(self.representation_dim, self.hidden_dim, self.epochs) < 1:
            raise ValueError("baseline dimensions and epochs must be positive")
        if self.learning_rate <= 0 or self.weight_decay < 0:
            raise ValueError("baseline optimizer settings are invalid")
        if self.penalty_weight < 0 or self.groupdro_step_size <= 0:
            raise ValueError("baseline penalty settings are invalid")
        if (
            self.dann_coefficient < 0
            or self.lisa_alpha <= 0
            or self.ccdg_temperature <= 0
        ):
            raise ValueError("DANN/LISA settings are invalid")
        if self.gradient_clip_norm <= 0:
            raise ValueError("gradient clipping norm must be positive")


@dataclass
class DGFittedModel:
    config: BaselineConfig
    standardizer: FeatureStandardizer
    network: TabularEncoder
    device: torch.device
    history: list[dict[str, float | int]]
    state_sha256: str
    auxiliary_state_sha256: str | None


def _module_state_sha256(module: nn.Module) -> str:
    digest = hashlib.sha256()
    for name, value in sorted(module.state_dict().items()):
        digest.update(name.encode("utf-8"))
        digest.update(b"\0")
        digest.update(value.detach().cpu().contiguous().numpy().tobytes())
        digest.update(b"\0")
    return digest.hexdigest()


def _as_tensor(values: np.ndarray, device: torch.device) -> Tensor:
    return torch.from_numpy(values).to(device)


def fit_dg_fold(
    fold: SourceOnlyFold,
    config: BaselineConfig,
    *,
    device: str = "auto",
) -> DGFittedModel:
    fold.validate()
    config.validate()
    _configure_determinism(config.seed)
    selected_device = _device(device)
    if selected_device.type == "cuda":
        torch.cuda.init()
    standardizer = FeatureStandardizer.fit(fold.source_features)
    features = _as_tensor(
        standardizer.transform(fold.source_features), selected_device
    )
    labels = _as_tensor(fold.source_labels, selected_device)
    nuisance_pairs = _as_tensor(fold.nuisance_pairs, selected_device)
    _, environment_codes_array = np.unique(
        fold.source_environments, return_inverse=True
    )
    environment_codes = _as_tensor(
        environment_codes_array.astype(np.int64), selected_device
    )
    domain_count = int(environment_codes.max().item()) + 1

    network = TabularEncoder(
        input_dimension=features.shape[1],
        hidden_dimension=config.hidden_dim,
        representation_dimension=config.representation_dim,
        class_count=len(fold.label_names),
    ).to(selected_device)
    discriminator = (
        DomainDiscriminator(
            representation_dimension=config.representation_dim,
            hidden_dimension=config.hidden_dim,
            domain_count=domain_count,
        ).to(selected_device)
        if config.method == "dann"
        else None
    )
    parameters = list(network.parameters())
    if discriminator is not None:
        parameters.extend(discriminator.parameters())
    optimizer = torch.optim.AdamW(
        parameters,
        lr=config.learning_rate,
        weight_decay=config.weight_decay,
    )
    groupdro = (
        GroupDROWeights.uniform(
            domain_count,
            step_size=config.groupdro_step_size,
            device=selected_device,
        )
        if config.method == "groupdro"
        else None
    )
    history: list[dict[str, float | int]] = []
    checkpoints = {0, config.epochs - 1, *range(24, config.epochs, 25)}
    for epoch in range(config.epochs):
        network.train()
        if discriminator is not None:
            discriminator.train()
        optimizer.zero_grad(set_to_none=True)
        logits, representation = network(features)
        per_sample_loss = nn.functional.cross_entropy(
            logits, labels, reduction="none"
        )
        empirical_risk = per_sample_loss.mean()
        penalty = torch.zeros((), device=selected_device)
        if config.method == "erm":
            objective = empirical_risk
        elif config.method == "coral":
            penalty = coral_penalty(representation, environment_codes)
            objective = empirical_risk + config.penalty_weight * penalty
        elif config.method == "vrex":
            penalty = vrex_penalty(per_sample_loss, environment_codes)
            objective = empirical_risk + config.penalty_weight * penalty
        elif config.method == "groupdro":
            if groupdro is None:
                raise AssertionError("GroupDRO state was not initialized")
            group_losses = group_mean_losses(per_sample_loss, environment_codes)
            objective = groupdro.objective(group_losses)
            penalty = objective - empirical_risk
        elif config.method == "dann":
            if discriminator is None:
                raise AssertionError("DANN discriminator was not initialized")
            domain_logits = discriminator(
                representation, coefficient=config.dann_coefficient
            )
            penalty = nn.functional.cross_entropy(
                domain_logits, environment_codes
            )
            objective = empirical_risk + config.penalty_weight * penalty
        elif config.method == "lisa":
            mixing = beta_mixing_coefficients(
                len(fold.nuisance_pairs),
                seed=config.seed,
                epoch=epoch,
                alpha=config.lisa_alpha,
            ).astype(np.float32)
            mixed_features, mixed_labels = lisa_mixup(
                features,
                labels,
                nuisance_pairs,
                _as_tensor(mixing, selected_device),
            )
            mixed_logits, _ = network(mixed_features)
            penalty = nn.functional.cross_entropy(
                mixed_logits, mixed_labels
            )
            objective = empirical_risk + config.penalty_weight * penalty
        elif config.method == "matchdg":
            penalty = matched_alignment_loss(
                representation, nuisance_pairs
            )
            objective = empirical_risk + config.penalty_weight * penalty
        elif config.method == "ccdg":
            penalty = conditional_contrastive_loss(
                representation,
                labels,
                temperature=config.ccdg_temperature,
            )
            objective = empirical_risk + config.penalty_weight * penalty
        else:
            raise AssertionError(f"unhandled DG baseline: {config.method}")
        objective.backward()
        gradient_norm = nn.utils.clip_grad_norm_(
            parameters, config.gradient_clip_norm
        )
        optimizer.step()
        if epoch in checkpoints:
            history.append(
                {
                    "epoch": epoch + 1,
                    "objective": float(objective.detach().cpu()),
                    "empirical_risk": float(empirical_risk.detach().cpu()),
                    "method_penalty": float(penalty.detach().cpu()),
                    "gradient_norm_before_clip": float(
                        gradient_norm.detach().cpu()
                    ),
                }
            )
    if selected_device.type == "cuda":
        torch.cuda.synchronize(selected_device)
    return DGFittedModel(
        config=config,
        standardizer=standardizer,
        network=network,
        device=selected_device,
        history=history,
        state_sha256=_module_state_sha256(network),
        auxiliary_state_sha256=(
            _module_state_sha256(discriminator)
            if discriminator is not None
            else None
        ),
    )


def predict_dg(model: DGFittedModel, features: np.ndarray) -> PredictionBundle:
    model.network.eval()
    values = _as_tensor(
        model.standardizer.transform(features), model.device
    )
    with torch.inference_mode():
        logits, representation = model.network(values)
        probabilities = torch.softmax(logits, dim=1)
    return PredictionBundle(
        logits=logits.cpu().numpy(),
        probabilities=probabilities.cpu().numpy(),
        predictions=probabilities.argmax(dim=1).cpu().numpy().astype(np.int64),
        representations=representation.cpu().numpy(),
    )


def configuration_record(config: BaselineConfig) -> dict[str, Any]:
    return asdict(config)
