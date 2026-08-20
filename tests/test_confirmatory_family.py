from __future__ import annotations

import copy
import hashlib
import json

import pytest

from smartvalve.experiments.confirmatory_family import (
    assemble_family,
    run_confirmatory_family,
)
from smartvalve.experiments.cranfield_causal_audit import AUDIT_SEEDS
from smartvalve.experiments.paderborn_bootstrap import (
    BOOTSTRAP_VERSION as PADERBORN_BOOTSTRAP_VERSION,
)
from smartvalve.experiments.selective_bootstrap import (
    BOOTSTRAP_REPLICATES,
    BOOTSTRAP_SEED,
    HEADLINE_SCORE,
    HEADLINE_SOURCE_COVERAGE,
    METHODS,
)
from smartvalve.experiments.selective_bootstrap import (
    BOOTSTRAP_VERSION as DEVELOPMENT_BOOTSTRAP_VERSION,
)


def _configuration() -> dict:
    return {
        "replicates": BOOTSTRAP_REPLICATES,
        "seed": BOOTSTRAP_SEED,
        "methods": list(METHODS),
        "model_seeds": list(AUDIT_SEEDS),
        "headline_score": HEADLINE_SCORE,
        "headline_source_coverage": HEADLINE_SOURCE_COVERAGE,
    }


def _comparison(p_value: float) -> dict:
    return {
        "point_estimate": 0.02,
        "bootstrap_mean": 0.021,
        "bootstrap_standard_error": 0.004,
        "ci95_low": 0.011,
        "ci95_high": 0.029,
        "two_sided_bootstrap_tail_p": p_value,
        "positive_favors_pirl": True,
        "minimum_practical_effect": 0.01,
        "practically_positive_and_ci_excludes_zero": True,
    }


def _metrics() -> tuple[dict, dict]:
    development = {
        "bootstrap_version": DEVELOPMENT_BOOTSTRAP_VERSION,
        "configuration": _configuration(),
        "paired_comparisons": {
            "cranfield": {
                "pirl_minus_erm_worst_fold_macro_f1": _comparison(0.001),
                "erm_minus_pirl_selective_risk_at_source_50pct": _comparison(
                    0.01
                ),
            },
            "uci_hydraulic": {
                "pirl_minus_erm_worst_fold_macro_f1": _comparison(0.02),
                "erm_minus_pirl_selective_risk_at_source_50pct": _comparison(
                    0.03
                ),
            },
        },
    }
    paderborn_configuration = {
        **_configuration(),
        "resampling_unit": "bearing_identity",
        "stratification": "truth",
    }
    paderborn = {
        "bootstrap_version": PADERBORN_BOOTSTRAP_VERSION,
        "configuration": paderborn_configuration,
        "contract": {
            "pure_bearings": 29,
            "physical_measurements": 2_320,
        },
        "paired_comparisons": {
            "pirl_minus_erm_minimum_setting_macro_f1": _comparison(0.2),
            "erm_minus_pirl_selective_risk_at_source_50pct": _comparison(0.5),
        },
    }
    return development, paderborn


def _write_json(path, value: dict) -> str:
    path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_family_is_exactly_six_and_holm_uses_all_six_p_values() -> None:
    tests, summary = assemble_family(*_metrics())

    assert len(tests) == 6
    assert tests["test_id"].is_unique
    assert tests["holm_adjusted_p"].tolist() == pytest.approx(
        [0.006, 0.05, 0.08, 0.09, 0.4, 0.5]
    )
    assert summary["family_size"] == 6
    assert summary["positive_test_count"] == 2
    assert summary["all_six_confirmatory_positive"] is False
    assert summary["datasets_with_confirmatory_improvement"] == ["cranfield"]
    assert summary["datasets_with_material_harm"] == []
    assert summary["internal_multi_dataset_evidence_gate_passed"] is False


def test_family_rejects_an_inconsistent_practical_gate() -> None:
    development, paderborn = _metrics()
    broken = copy.deepcopy(development)
    broken["paired_comparisons"]["cranfield"][
        "pirl_minus_erm_worst_fold_macro_f1"
    ]["practically_positive_and_ci_excludes_zero"] = False

    with pytest.raises(ValueError, match="inconsistent practical gate"):
        assemble_family(broken, paderborn)


def test_multi_dataset_gate_requires_two_datasets_and_is_vetoed_by_harm() -> None:
    development, paderborn = _metrics()
    development["paired_comparisons"]["cranfield"][
        "erm_minus_pirl_selective_risk_at_source_50pct"
    ] = _comparison(0.5)
    development["paired_comparisons"]["uci_hydraulic"][
        "pirl_minus_erm_worst_fold_macro_f1"
    ] = _comparison(0.002)
    development["paired_comparisons"]["uci_hydraulic"][
        "erm_minus_pirl_selective_risk_at_source_50pct"
    ] = _comparison(0.5)
    paderborn["paired_comparisons"][
        "pirl_minus_erm_minimum_setting_macro_f1"
    ] = _comparison(0.5)

    _, passing = assemble_family(development, paderborn)

    assert passing["datasets_with_confirmatory_improvement"] == [
        "cranfield",
        "uci_hydraulic",
    ]
    assert passing["internal_multi_dataset_evidence_gate_passed"] is True

    harmful = paderborn["paired_comparisons"][
        "pirl_minus_erm_minimum_setting_macro_f1"
    ]
    harmful.update(
        {
            "point_estimate": -0.02,
            "bootstrap_mean": -0.021,
            "ci95_low": -0.03,
            "ci95_high": -0.01,
            "practically_positive_and_ci_excludes_zero": False,
        }
    )
    _, vetoed = assemble_family(development, paderborn)

    assert vetoed["datasets_with_material_harm"] == ["paderborn"]
    assert vetoed["internal_multi_dataset_evidence_gate_passed"] is False


def test_recorded_family_requires_both_sealed_hashes(tmp_path) -> None:
    development, paderborn = _metrics()
    development_path = tmp_path / "development.json"
    paderborn_path = tmp_path / "paderborn.json"
    development_hash = _write_json(development_path, development)
    paderborn_hash = _write_json(paderborn_path, paderborn)

    result = run_confirmatory_family(
        development_path,
        paderborn_path,
        tmp_path / "output",
        expected_development_sha256=development_hash,
        expected_paderborn_sha256=paderborn_hash,
    )

    assert result["summary"]["family_size"] == 6
    assert result["artifacts"]["confirmatory_tests"]["rows"] == 6
    with pytest.raises(ValueError, match="development.*hash"):
        run_confirmatory_family(
            development_path,
            paderborn_path,
            tmp_path / "bad-output",
            expected_development_sha256="0" * 64,
            expected_paderborn_sha256=paderborn_hash,
        )
