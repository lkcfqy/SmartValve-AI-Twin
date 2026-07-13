"""Typed HTTP client and dashboard view models for the SmartValve API."""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any

import httpx
import pandas as pd


class ApiClientError(RuntimeError):
    """Base error raised for a failed API operation."""


class ApiUnavailableError(ApiClientError):
    """Raised when the API process cannot be reached."""


class AttributeRecord:
    """Dictionary payload with attribute access and stable export."""

    def __init__(self, values: dict[str, Any]) -> None:
        self._values = values

    def __getattr__(self, name: str) -> Any:
        try:
            values = object.__getattribute__(self, "_values")
        except AttributeError as exc:
            raise AttributeError(name) from exc
        try:
            return values[name]
        except KeyError as exc:
            raise AttributeError(name) from exc

    def to_dict(self) -> dict[str, Any]:
        return dict(self._values)


@dataclass(frozen=True)
class SignatureView:
    baseline_signature: pd.DataFrame
    current_signature: pd.DataFrame
    baseline_features: dict[str, float]
    current_features: dict[str, float]
    similarity_pct: float
    abnormal_start_pct: float | None
    abnormal_end_pct: float | None
    max_current_residual_a: float
    residual_rmse_a: float


@dataclass(frozen=True)
class RemoteTwinRun:
    """Subset of TwinRun returned to presentation clients through HTTP."""

    run_id: str
    correlation_id: str
    created_at: str
    operator_id: str
    asset_id: str
    source: str
    evidence_grade: str
    model_version: str
    baseline_data: pd.DataFrame
    current_data: pd.DataFrame
    signature: SignatureView
    diagnosis: AttributeRecord
    network: AttributeRecord
    baseline_quality: AttributeRecord
    current_quality: AttributeRecord
    limitations: tuple[str, ...]
    audit: AttributeRecord

    @classmethod
    def from_payload(cls, payload: dict[str, Any]) -> RemoteTwinRun:
        trace = pd.DataFrame(payload["trace"])
        baseline_trace = pd.DataFrame(payload["baseline_trace"])
        trace["source"] = payload["source"]
        baseline_trace["source"] = payload["source"]
        signature = payload["signature"]
        quality = payload["quality"]
        return cls(
            run_id=payload["run_id"],
            correlation_id=payload["correlation_id"],
            created_at=payload["created_at"],
            operator_id=payload["operator_id"],
            asset_id=payload["asset_id"],
            source=payload["source"],
            evidence_grade=payload["evidence_grade"],
            model_version=payload["model_version"],
            baseline_data=baseline_trace,
            current_data=trace,
            signature=SignatureView(
                baseline_signature=pd.DataFrame(signature["baseline"]),
                current_signature=pd.DataFrame(signature["current"]),
                baseline_features=signature["baseline_features"],
                current_features=signature["current_features"],
                similarity_pct=float(signature["similarity_pct"]),
                abnormal_start_pct=signature["abnormal_start_pct"],
                abnormal_end_pct=signature["abnormal_end_pct"],
                max_current_residual_a=float(signature["max_current_residual_a"]),
                residual_rmse_a=float(signature["residual_rmse_a"]),
            ),
            diagnosis=AttributeRecord(payload["diagnosis"]),
            network=AttributeRecord(payload["network"]),
            baseline_quality=AttributeRecord(quality["baseline"]),
            current_quality=AttributeRecord(quality["current"]),
            limitations=tuple(payload["limitations"]),
            audit=AttributeRecord(payload["audit"]),
        )


@dataclass(frozen=True)
class SkabView:
    data: pd.DataFrame
    score: pd.Series
    threshold: float
    precision: float
    recall: float
    f1: float
    total_samples: int
    training_samples: int
    evaluation_samples: int
    source: dict[str, Any]
    limitation: str

    @classmethod
    def from_payload(cls, payload: dict[str, Any]) -> SkabView:
        frame = pd.DataFrame(payload["trace"])
        metrics = payload["metrics"]
        return cls(
            data=frame,
            score=pd.Series(frame["score"], index=frame.index, name="anomaly_score"),
            threshold=float(metrics["threshold"]),
            precision=float(metrics["precision"]),
            recall=float(metrics["recall"]),
            f1=float(metrics["f1"]),
            total_samples=int(metrics["total_samples"]),
            training_samples=int(metrics["training_samples"]),
            evaluation_samples=int(metrics["evaluation_samples"]),
            source=payload["source"],
            limitation=payload["limitation"],
        )


class SmartValveApiClient:
    def __init__(
        self,
        base_url: str | None = None,
        api_key: str | None = None,
        timeout_s: float = 45.0,
    ) -> None:
        self.base_url = (base_url or os.getenv("SMARTVALVE_API_URL", "http://127.0.0.1:8000")).rstrip(
            "/"
        )
        self.api_key = api_key if api_key is not None else os.getenv("SMARTVALVE_API_KEY")
        self.operator_id = os.getenv("SMARTVALVE_OPERATOR_ID", "dashboard-demo")
        self.timeout_s = timeout_s

    @property
    def headers(self) -> dict[str, str]:
        headers = {"X-Operator-ID": self.operator_id}
        if self.api_key:
            headers["X-API-Key"] = self.api_key
        return headers

    def _send(self, method: str, path: str, **kwargs: Any) -> httpx.Response:
        headers = dict(kwargs.pop("headers", {}))
        headers.update(self.headers)
        try:
            response = httpx.request(
                method,
                f"{self.base_url}{path}",
                headers=headers,
                timeout=self.timeout_s,
                **kwargs,
            )
        except httpx.RequestError as exc:
            raise ApiUnavailableError(f"diagnostic API unavailable at {self.base_url}") from exc
        if response.is_error:
            try:
                detail = response.json().get("detail", response.text)
            except ValueError:
                detail = response.text
            raise ApiClientError(f"API {response.status_code}: {detail}")
        return response

    def _request(self, method: str, path: str, **kwargs: Any) -> dict[str, Any]:
        response = self._send(method, path, **kwargs)
        return response.json()

    def readiness(self) -> dict[str, Any]:
        return self._request("GET", "/health/ready")

    def diagnose_simulation(self, payload: dict[str, Any]) -> RemoteTwinRun:
        response = self._request("POST", "/v1/diagnostics/simulation", json=payload)
        return RemoteTwinRun.from_payload(response)

    def diagnose_cranfield(self, payload: dict[str, Any]) -> RemoteTwinRun:
        response = self._request("POST", "/v1/diagnostics/cranfield", json=payload)
        return RemoteTwinRun.from_payload(response)

    def cranfield_validation_sample(self) -> RemoteTwinRun:
        response = self._request("GET", "/v1/validation/cranfield/sample")
        return RemoteTwinRun.from_payload(response)

    def diagnose_csv(
        self,
        *,
        asset_id: str,
        source: str,
        baseline: bytes,
        current: bytes,
    ) -> RemoteTwinRun:
        response = self._request(
            "POST",
            "/v1/diagnostics/csv",
            data={"asset_id": asset_id, "source": source},
            files={
                "baseline_file": ("baseline.csv", baseline, "text/csv"),
                "current_file": ("current.csv", current, "text/csv"),
            },
        )
        return RemoteTwinRun.from_payload(response)

    def validate_skab(self) -> SkabView:
        return SkabView.from_payload(self._request("GET", "/v1/validation/skab"))

    def validation_benchmark(self, profile: str = "full") -> dict[str, Any]:
        return self._request("GET", "/v1/validation/benchmark", params={"profile": profile})

    def validation_cranfield(self) -> dict[str, Any]:
        return self._request("GET", "/v1/validation/cranfield")

    def sources(self) -> dict[str, Any]:
        return self._request("GET", "/v1/sources")

    def list_runs(self, limit: int = 50) -> list[dict[str, Any]]:
        return self._request("GET", "/v1/runs", params={"limit": limit})["items"]

    def verify_audit_chain(self) -> dict[str, Any]:
        return self._request("GET", "/v1/audit/verify")

    def diagnostic_pdf(self, run_id: str) -> bytes:
        return self._send("GET", f"/v1/runs/{run_id}/report.pdf").content
