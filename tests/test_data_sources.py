from __future__ import annotations

import pandas as pd
import pytest

from smartvalve.config import project_root
from smartvalve.data.contract import validate_valve_frame
from smartvalve.data.cranfield import load_cranfield_pair
from smartvalve.data.external import cache_directory
from smartvalve.data.skab import run_skab_validation
from smartvalve.pipeline import run_from_frames
from smartvalve.simulation.model import FaultConfig, ValveSimulator


def test_simulation_satisfies_canonical_contract() -> None:
    frame = ValveSimulator().simulate(FaultConfig(fault_type="normal", severity=0.0))
    quality = validate_valve_frame(frame)
    assert quality.status == "ACCEPTED"
    assert quality.score == 100.0
    assert quality.data_sha256


def test_contract_rejects_missing_required_columns() -> None:
    with pytest.raises(ValueError, match="missing required columns"):
        validate_valve_frame(pd.DataFrame({"timestamp_s": [0.0, 1.0]}))


@pytest.mark.skipif(
    not (cache_directory() / "Normal.mat").exists(),
    reason="public Cranfield cache not synced",
)
def test_real_cranfield_lubrication_signature_is_detected() -> None:
    baseline, current = load_cranfield_pair()
    run = run_from_frames(baseline, current)
    assert run.current_quality.sample_count == 2000
    assert run.current_quality.sampling_hz == 25.0
    assert run.diagnosis.primary_finding == "Friction growth"
    assert run.diagnosis.evidence["moving_current_ratio"] > 1.15


@pytest.mark.skipif(
    not (cache_directory() / "skab_valve1_1.csv").exists(),
    reason="public SKAB cache not synced",
)
def test_real_skab_validation_reports_honest_metrics() -> None:
    result = run_skab_validation()
    assert result.total_samples == 1145
    assert result.anomaly_samples == 402
    assert 0.5 < result.f1 < 0.9
    assert result.precision > result.recall


def test_external_cache_is_outside_generated_data() -> None:
    cache = cache_directory().resolve()
    generated = (project_root() / "data" / "generated").resolve()
    assert cache != generated
    assert generated not in cache.parents
