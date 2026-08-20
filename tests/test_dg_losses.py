from __future__ import annotations

import numpy as np
import pytest

torch = pytest.importorskip("torch")

from smartvalve.experiments.dg_losses import (  # noqa: E402
    GroupDROWeights,
    beta_mixing_coefficients,
    conditional_contrastive_loss,
    coral_penalty,
    gradient_reverse,
    group_mean_losses,
    lisa_mixup,
    matched_alignment_loss,
    vrex_penalty,
)


def test_group_risks_and_vrex_use_exact_environment_means() -> None:
    losses = torch.tensor([1.0, 3.0, 2.0, 6.0])
    groups = torch.tensor([0, 0, 1, 1])

    means = group_mean_losses(losses, groups)

    assert means.tolist() == pytest.approx([2.0, 4.0])
    assert vrex_penalty(losses, groups).item() == pytest.approx(1.0)


def test_coral_is_zero_for_identical_group_moments() -> None:
    representation = torch.tensor(
        [[0.0, 1.0], [1.0, 0.0], [0.0, 1.0], [1.0, 0.0]]
    )
    groups = torch.tensor([0, 0, 1, 1])

    assert coral_penalty(representation, groups).item() == pytest.approx(0.0)


def test_matchdg_and_lisa_follow_audited_pairs() -> None:
    features = torch.tensor([[0.0], [2.0], [4.0]])
    labels = torch.tensor([0, 0, 1])
    pairs = torch.tensor([[0, 1]])

    assert matched_alignment_loss(features, pairs).item() == pytest.approx(4.0)
    mixed, mixed_labels = lisa_mixup(
        features,
        labels,
        pairs,
        torch.tensor([0.25]),
    )
    assert mixed.item() == pytest.approx(1.5)
    assert mixed_labels.tolist() == [0]


def test_ccdg_conditional_contrastive_loss_is_finite_and_differentiable() -> None:
    representation = torch.tensor(
        [[1.0, 0.0], [0.9, 0.1], [0.0, 1.0], [0.1, 0.9]],
        requires_grad=True,
    )
    labels = torch.tensor([0, 0, 1, 1])

    loss = conditional_contrastive_loss(representation, labels)
    loss.backward()

    assert torch.isfinite(loss)
    assert representation.grad is not None
    assert torch.isfinite(representation.grad).all()


def test_gradient_reversal_changes_only_backward_sign_and_scale() -> None:
    values = torch.tensor([2.0, 3.0], requires_grad=True)

    reversed_values = gradient_reverse(values, 0.25)
    reversed_values.sum().backward()

    assert reversed_values.detach().tolist() == pytest.approx([2.0, 3.0])
    assert values.grad.tolist() == pytest.approx([-0.25, -0.25])


def test_group_dro_weights_move_toward_higher_risk_group() -> None:
    state = GroupDROWeights.uniform(
        2, step_size=0.1, device=torch.device("cpu")
    )

    objective = state.objective(torch.tensor([1.0, 3.0]))

    assert state.values[1] > state.values[0]
    assert 1.0 < objective.item() < 3.0


def test_lisa_beta_schedule_is_deterministic_and_epoch_specific() -> None:
    first = beta_mixing_coefficients(20, seed=11, epoch=3)
    repeat = beta_mixing_coefficients(20, seed=11, epoch=3)
    later = beta_mixing_coefficients(20, seed=11, epoch=4)

    assert np.array_equal(first, repeat)
    assert not np.array_equal(first, later)
    assert np.all((first >= 0) & (first <= 1))
