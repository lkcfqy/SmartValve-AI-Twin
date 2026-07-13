from smartvalve.experiments.benchmark import PROFILES, run_benchmark


def test_smoke_benchmark_has_group_holdout_metrics_and_rejection() -> None:
    profile = PROFILES["smoke"]
    records, metrics = run_benchmark(profile)
    assert len(records) == profile.expected_runs
    assert set(records["split"]) == {"development", "holdout"}
    assert metrics["matrix"]["holdout_runs"] > 0
    assert 0.0 <= metrics["holdout"]["macro_f1_including_rejection_as_error"] <= 1.0
    assert metrics["holdout"]["false_positive_rate_normal"] <= 0.05
    assert metrics["holdout"]["out_of_spec_voltage_rejection_recall"] == 1.0
    assert metrics["matrix"]["unique_observable_runs"] < metrics["matrix"]["total_runs"]
    assert metrics["holdout"]["latency_ms"]["p95"] < 100.0
