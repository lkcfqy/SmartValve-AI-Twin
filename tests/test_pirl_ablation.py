from __future__ import annotations

import pytest

pytest.importorskip("torch")

from smartvalve.experiments.pirl_ablation import (  # noqa: E402
    _attribution_decision,
)


def _method(
    macro_f1: float,
    worst_f1: float,
    response_ratio: float,
) -> dict:
    return {
        "summary": {
            "mean_fold_macro_f1": {"mean": macro_f1},
            "worst_fold_macro_f1": {"mean": worst_f1},
            "mean_source_representation_response_ratio": {
                "mean": response_ratio
            },
        }
    }


def test_attribution_rejects_hinge_when_only_worst_term_recovers_gain() -> None:
    reference = {
        "results": {
            dataset: {
                "erm": _method(0.70, 0.30, 0.20),
                "pirl_sore": _method(0.75, 0.35, 0.25),
            }
            for dataset in ("cranfield", "uci_hydraulic")
        }
    }
    new_results = {
        dataset: {
            "worst_erm": _method(0.745, 0.34, 0.25),
            "pirl_only": _method(0.705, 0.30, 0.15),
        }
        for dataset in ("cranfield", "uci_hydraulic")
    }

    decision = _attribution_decision(reference, new_results)

    assert decision[
        "full_gain_attributed_primarily_to_worst_environment_term"
    ]
    assert decision["headline_current_hinge_rejected"]


def test_attribution_supports_hinge_only_with_both_mechanism_and_efficacy() -> None:
    reference = {
        "results": {
            dataset: {
                "erm": _method(0.70, 0.30, 0.20),
                "pirl_sore": _method(0.75, 0.35, 0.15),
            }
            for dataset in ("cranfield", "uci_hydraulic")
        }
    }
    new_results = {
        dataset: {
            "worst_erm": _method(0.71, 0.30, 0.20),
            "pirl_only": _method(0.74, 0.34, 0.10),
        }
        for dataset in ("cranfield", "uci_hydraulic")
    }

    decision = _attribution_decision(reference, new_results)

    assert not decision[
        "full_gain_attributed_primarily_to_worst_environment_term"
    ]
    assert decision["current_intervention_hinge_mechanistically_supported"]
    assert not decision["headline_current_hinge_rejected"]
