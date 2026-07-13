from __future__ import annotations

import sqlite3

import pytest
from fastapi.testclient import TestClient

from smartvalve.data.external import cache_directory
from smartvalve.service.app import app
from smartvalve.simulation.model import FaultConfig, ValveSimulator


def test_api_health_diagnosis_and_audit(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("SMARTVALVE_DATABASE", str(tmp_path / "test.db"))
    monkeypatch.delenv("SMARTVALVE_API_KEY", raising=False)
    with TestClient(app) as client:
        assert client.get("/health/live").status_code == 200
        ready = client.get("/health/ready")
        assert ready.status_code == 200
        assert ready.json()["database"] is True

        response = client.post(
            "/v1/diagnostics/simulation",
            json={"asset_id": "TEST-V-01", "fault_type": "obstruction", "severity": 0.8},
        )
        assert response.status_code == 200
        payload = response.json()
        assert payload["run_id"]
        assert payload["correlation_id"]
        assert payload["created_at"]
        assert payload["operator_id"] == "local-demo"
        assert payload["evidence_grade"].startswith("S0")
        assert payload["audit"]["record_sha256"]
        assert payload["baseline_trace"]
        assert payload["quality"]["current"]["status"] == "ACCEPTED"
        assert payload["trace"]
        assert payload["signature"]["current"]

        stored = client.get(f"/v1/runs/{payload['run_id']}").json()
        assert stored["correlation_id"] == payload["correlation_id"]
        assert stored["signature"] == payload["signature"]
        assert stored["audit"] == payload["audit"]
        pdf = client.get(f"/v1/runs/{payload['run_id']}/report.pdf")
        assert pdf.status_code == 200
        assert pdf.headers["content-type"] == "application/pdf"
        assert pdf.content.startswith(b"%PDF")

        audit = client.get("/v1/runs").json()["items"]
        assert audit[0]["asset_id"] == "TEST-V-01"
        assert audit[0]["data_sha256"]
        verified = client.get("/v1/audit/verify")
        assert verified.status_code == 200
        assert verified.json()["valid"] is True

        with (
            sqlite3.connect(tmp_path / "test.db") as connection,
            pytest.raises(sqlite3.IntegrityError, match="append-only"),
        ):
            connection.execute(
                "UPDATE diagnostic_runs SET status = 'TAMPERED' WHERE run_id = ?",
                (payload["run_id"],),
            )

        simulator = ValveSimulator()
        baseline_csv = simulator.simulate(FaultConfig()).to_csv(index=False).encode()
        current_csv = simulator.simulate(
            FaultConfig(fault_type="friction", severity=0.8)
        ).to_csv(index=False).encode()
        uploaded = client.post(
            "/v1/diagnostics/csv",
            data={"asset_id": "RIG-01", "source": "desktop_rig"},
            files={
                "baseline_file": ("baseline.csv", baseline_csv, "text/csv"),
                "current_file": ("current.csv", current_csv, "text/csv"),
            },
        )
        assert uploaded.status_code == 200
        assert uploaded.json()["source"] == "desktop_rig"

        blank = client.post("/v1/diagnostics/simulation", json={"asset_id": "   "})
        assert blank.status_code == 422

        current = simulator.simulate(FaultConfig(fault_type="friction", severity=0.8))
        current.loc[10, "timestamp_s"] = current.loc[9, "timestamp_s"]
        reviewed = client.post(
            "/v1/diagnostics/csv",
            data={"asset_id": "RIG-REVIEW", "source": "desktop_rig"},
            files={
                "baseline_file": ("baseline.csv", baseline_csv, "text/csv"),
                "current_file": ("current.csv", current.to_csv(index=False).encode(), "text/csv"),
            },
        )
        assert reviewed.status_code == 422
        assert "requires review" in reviewed.json()["detail"]

        live = client.get("/health/live")
        assert live.headers["x-content-type-options"] == "nosniff"
        assert live.headers["content-security-policy"].startswith("default-src")


@pytest.mark.skipif(
    not (cache_directory() / "Normal.mat").exists()
    or not (cache_directory() / "skab_valve1_1.csv").exists(),
    reason="public validation cache not synced",
)
def test_public_validation_endpoints(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("SMARTVALVE_DATABASE", str(tmp_path / "public.db"))
    monkeypatch.delenv("SMARTVALVE_API_KEY", raising=False)
    with TestClient(app) as client:
        cranfield = client.post(
            "/v1/diagnostics/cranfield",
            json={"fault": "lack_of_lubrication", "load_kg": 20, "repetition": 1},
        )
        assert cranfield.status_code == 200
        assert cranfield.json()["diagnosis"]["primary_finding"] == "Friction growth"

        records_before_preview = len(client.get("/v1/runs").json()["items"])
        sample = client.get("/v1/validation/cranfield/sample")
        assert sample.status_code == 200
        assert sample.json()["audit"] == {}
        assert sample.json()["source"] == "cranfield_real_actuator_read_only_sample"
        assert len(client.get("/v1/runs").json()["items"]) == records_before_preview

        skab = client.get("/v1/validation/skab")
        assert skab.status_code == 200
        assert skab.json()["split"] == {"training": 400, "evaluation": 745}
        assert skab.json()["trace"]

        benchmark = client.get("/v1/validation/benchmark")
        assert benchmark.status_code == 200
        assert benchmark.json()["matrix"]["total_runs"] == 3000
        challenge = client.get("/v1/validation/benchmark", params={"profile": "challenge"})
        assert challenge.status_code == 200
        assert challenge.json()["matrix"]["total_runs"] == 1500

        grouped_cranfield = client.get("/v1/validation/cranfield")
        assert grouped_cranfield.status_code == 200
        assert grouped_cranfield.json()["dataset"]["trials"] == 180
        assert grouped_cranfield.json()["protocol"]["folds"] == 6


def test_api_key_can_be_enabled(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("SMARTVALVE_DATABASE", str(tmp_path / "secure.db"))
    monkeypatch.setenv("SMARTVALVE_API_KEY", "test-secret")
    with TestClient(app) as client:
        assert client.get("/v1/sources").status_code == 401
        assert client.get("/v1/sources", headers={"X-API-Key": "test-secret"}).status_code == 200


def test_production_refuses_weak_or_missing_authentication(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("SMARTVALVE_DATABASE", str(tmp_path / "production.db"))
    monkeypatch.setenv("SMARTVALVE_ENVIRONMENT", "production")
    monkeypatch.delenv("SMARTVALVE_API_KEY", raising=False)
    with (
        pytest.raises(RuntimeError, match="production requires SMARTVALVE_API_KEY"),
        TestClient(app),
    ):
        pass


def test_degraded_readiness_returns_service_unavailable(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("SMARTVALVE_DATABASE", str(tmp_path / "degraded.db"))
    monkeypatch.delenv("SMARTVALVE_API_KEY", raising=False)
    with TestClient(app) as client:
        repository = app.state.repository
        app.state.repository = type("UnavailableRepository", (), {"ping": lambda self: False})()
        try:
            response = client.get("/health/ready")
        finally:
            app.state.repository = repository
        assert response.status_code == 503
        assert response.json()["status"] == "degraded"
