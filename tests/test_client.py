import pickle

from fastapi.testclient import TestClient

from smartvalve.service.app import app
from smartvalve.service.client import RemoteTwinRun


def test_remote_run_survives_streamlit_style_cache_roundtrip(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("SMARTVALVE_DATABASE", str(tmp_path / "client.db"))
    monkeypatch.delenv("SMARTVALVE_API_KEY", raising=False)
    with TestClient(app) as client:
        response = client.post(
            "/v1/diagnostics/simulation",
            json={"asset_id": "CACHE-V-01", "fault_type": "stiction", "severity": 0.75},
        )
    run = RemoteTwinRun.from_payload(response.json())
    restored = pickle.loads(pickle.dumps(run))  # noqa: S301 - trusted local cache regression test
    assert restored.asset_id == "CACHE-V-01"
    assert restored.diagnosis.primary_finding == run.diagnosis.primary_finding
    assert not restored.current_data.empty
