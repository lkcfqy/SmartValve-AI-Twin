"""Auditable loss primitives for the frozen domain-generalization baseline suite."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np
import torch
from torch import Tensor, nn


def group_mean_losses(per_sample_loss: Tensor, group_codes: Tensor) -> Tensor:
    """Return group risks in sorted integer-code order."""

    if per_sample_loss.ndim != 1 or group_codes.shape != per_sample_loss.shape:
        raise ValueError("losses and group codes must be aligned one-dimensional tensors")
    groups = torch.unique(group_codes, sorted=True)
    if len(groups) < 2:
        raise ValueError("domain-generalization losses require at least two groups")
    return torch.stack(
        [per_sample_loss[group_codes == group].mean() for group in groups]
    )


def vrex_penalty(per_sample_loss: Tensor, group_codes: Tensor) -> Tensor:
    """Variance Risk Extrapolation penalty over exact source environments."""

    return group_mean_losses(per_sample_loss, group_codes).var(unbiased=False)


def coral_penalty(representation: Tensor, group_codes: Tensor) -> Tensor:
    """Align source-environment means and covariances around their group average."""

    if representation.ndim != 2 or len(representation) != len(group_codes):
        raise ValueError("representations and group codes must align")
    groups = torch.unique(group_codes, sorted=True)
    if len(groups) < 2:
        raise ValueError("CORAL requires at least two source environments")
    means = []
    covariances = []
    for group in groups:
        values = representation[group_codes == group]
        if len(values) < 2:
            raise ValueError("CORAL requires two or more rows in every environment")
        means.append(values.mean(dim=0))
        centered = values - values.mean(dim=0, keepdim=True)
        covariances.append(centered.T @ centered / (len(values) - 1))
    stacked_means = torch.stack(means)
    stacked_covariances = torch.stack(covariances)
    mean_penalty = (stacked_means - stacked_means.mean(dim=0)).square().mean()
    covariance_penalty = (
        stacked_covariances - stacked_covariances.mean(dim=0)
    ).square().mean()
    return mean_penalty + covariance_penalty


def irm_penalty(logits: Tensor, labels: Tensor, group_codes: Tensor) -> Tensor:
    """IRMv1 gradient penalty using a shared scalar classifier scale."""

    scale = torch.ones((), device=logits.device, requires_grad=True)
    penalties = []
    for group in torch.unique(group_codes, sorted=True):
        mask = group_codes == group
        risk = nn.functional.cross_entropy(logits[mask] * scale, labels[mask])
        gradient = torch.autograd.grad(risk, (scale,), create_graph=True)[0]
        penalties.append(gradient.square())
    if len(penalties) < 2:
        raise ValueError("IRM requires at least two source environments")
    return torch.stack(penalties).mean()


def matched_alignment_loss(representation: Tensor, pairs: Tensor) -> Tensor:
    """MatchDG-style squared response for same-label cross-domain pairs."""

    if pairs.ndim != 2 or pairs.shape[1] != 2 or len(pairs) == 0:
        raise ValueError("matched alignment requires non-empty two-column pairs")
    differences = representation[pairs[:, 0]] - representation[pairs[:, 1]]
    return differences.square().sum(dim=1).mean()


def conditional_contrastive_loss(
    representation: Tensor,
    labels: Tensor,
    *,
    temperature: float = 0.7,
) -> Tensor:
    """CCDG class-conditional contrastive loss over all source-domain rows."""

    if (
        representation.ndim != 2
        or labels.ndim != 1
        or len(representation) != len(labels)
        or len(labels) < 2
    ):
        raise ValueError("CCDG requires aligned non-trivial representations and labels")
    if temperature <= 0:
        raise ValueError("CCDG temperature must be positive")
    normalized = nn.functional.normalize(representation, dim=1)
    logits = normalized @ normalized.T / temperature
    logits = logits - logits.max(dim=1, keepdim=True).values.detach()
    nonself = ~torch.eye(len(labels), dtype=torch.bool, device=labels.device)
    positives = labels[:, None].eq(labels[None, :]) & nonself
    positive_count = positives.sum(dim=1)
    if torch.any(positive_count == 0):
        raise ValueError("CCDG requires a positive partner for every row")
    log_denominator = torch.logsumexp(
        logits.masked_fill(~nonself, -torch.inf), dim=1
    )
    log_probability = logits - log_denominator[:, None]
    return -(
        (log_probability * positives).sum(dim=1) / positive_count
    ).mean()


def lisa_mixup(
    features: Tensor,
    labels: Tensor,
    pairs: Tensor,
    mixing: Tensor,
) -> tuple[Tensor, Tensor]:
    """Same-label, different-domain selective interpolation for LISA."""

    if pairs.ndim != 2 or pairs.shape[1] != 2 or len(pairs) == 0:
        raise ValueError("LISA requires non-empty two-column pairs")
    if mixing.ndim != 1 or len(mixing) != len(pairs):
        raise ValueError("LISA mixing coefficients must align with pairs")
    if torch.any((mixing < 0) | (mixing > 1)):
        raise ValueError("LISA mixing coefficients must lie in [0, 1]")
    left_labels = labels[pairs[:, 0]]
    right_labels = labels[pairs[:, 1]]
    if not torch.equal(left_labels, right_labels):
        raise ValueError("LISA nuisance pairs must preserve labels")
    weight = mixing[:, None]
    mixed_features = (
        weight * features[pairs[:, 0]]
        + (1.0 - weight) * features[pairs[:, 1]]
    )
    return mixed_features, left_labels


class _GradientReverse(torch.autograd.Function):
    @staticmethod
    def forward(ctx: Any, values: Tensor, coefficient: float) -> Tensor:
        ctx.coefficient = coefficient
        return values.view_as(values)

    @staticmethod
    def backward(ctx: Any, gradient: Tensor) -> tuple[Tensor, None]:
        return -float(ctx.coefficient) * gradient, None


def gradient_reverse(values: Tensor, coefficient: float) -> Tensor:
    if coefficient < 0:
        raise ValueError("gradient-reversal coefficient must be nonnegative")
    return _GradientReverse.apply(values, coefficient)


class DomainDiscriminator(nn.Module):
    def __init__(
        self,
        *,
        representation_dimension: int,
        hidden_dimension: int,
        domain_count: int,
    ) -> None:
        super().__init__()
        self.network = nn.Sequential(
            nn.Linear(representation_dimension, hidden_dimension),
            nn.GELU(),
            nn.Linear(hidden_dimension, domain_count),
        )

    def forward(self, representation: Tensor, *, coefficient: float) -> Tensor:
        return self.network(gradient_reverse(representation, coefficient))


@dataclass
class GroupDROWeights:
    """Exponentiated-gradient source-group weights."""

    values: Tensor
    step_size: float

    @classmethod
    def uniform(
        cls,
        group_count: int,
        *,
        step_size: float,
        device: torch.device,
    ) -> GroupDROWeights:
        if group_count < 2 or step_size <= 0:
            raise ValueError("GroupDRO requires multiple groups and a positive step size")
        return cls(
            values=torch.full((group_count,), 1.0 / group_count, device=device),
            step_size=step_size,
        )

    def objective(self, group_losses: Tensor) -> Tensor:
        if group_losses.shape != self.values.shape:
            raise ValueError("GroupDRO loss vector does not match its weights")
        with torch.no_grad():
            self.values.mul_(torch.exp(self.step_size * group_losses.detach()))
            self.values.div_(self.values.sum())
        return torch.sum(self.values * group_losses)


def beta_mixing_coefficients(
    pair_count: int,
    *,
    seed: int,
    epoch: int,
    alpha: float = 2.0,
) -> np.ndarray:
    """Generate deterministic LISA Beta(alpha, alpha) coefficients."""

    if pair_count < 1 or alpha <= 0 or epoch < 0:
        raise ValueError("invalid deterministic mixing configuration")
    sequence = np.random.SeedSequence([seed, epoch, pair_count])
    return np.random.default_rng(sequence).beta(alpha, alpha, size=pair_count)
