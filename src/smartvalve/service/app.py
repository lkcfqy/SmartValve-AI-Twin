"""Deployable HTTP service with validation, audit persistence and optional API key."""

from __future__ import annotations

import json
import logging
import os
import re
import time
from collections import defaultdict, deque
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from hashlib import sha256
from hmac import compare_digest
from typing import Annotated, Literal
from uuid import uuid4

import numpy as np
import pandas as pd
from fastapi import (
    Depends,
    FastAPI,
    File,
    Form,
    Header,
    HTTPException,
    Query,
    Request,
    Response,
    UploadFile,
    status,
)
from fastapi.responses import JSONResponse, PlainTextResponse

from smartvalve import MODEL_VERSION, __version__
from smartvalve.config import env_bool, production_mode, project_root
from smartvalve.data.contract import EvidenceGrade
from smartvalve.data.cranfield import METADATA as CRANFIELD_METADATA
from smartvalve.data.cranfield import load_cranfield_pair
from smartvalve.data.external import artifact_status
from smartvalve.data.rig import load_canonical_csv
from smartvalve.data.skab import METADATA as SKAB_METADATA
from smartvalve.data.skab import run_skab_validation
from smartvalve.network_twin.model import simulate_network_impact
from smartvalve.pipeline import TwinRun, run_from_frames, run_twin
from smartvalve.reporting import build_diagnostic_pdf
from smartvalve.service.schemas import CranfieldRequest, DiagnosticResponse, SimulationRequest
from smartvalve.simulation.model import FaultConfig
from smartvalve.storage.repository import RunRepository

LOGGER = logging.getLogger("smartvalve.api")
logging.basicConfig(
    level=os.getenv("SMARTVALVE_LOG_LEVEL", "INFO"),
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)


@asynccontextmanager
async def lifespan(application: FastAPI):
    api_key = os.getenv("SMARTVALVE_API_KEY", "")
    if production_mode() and (
        len(api_key) < 32 or api_key == "replace-me-in-shared-environments"
    ):
        raise RuntimeError("production requires SMARTVALVE_API_KEY with at least 32 characters")
    application.state.repository = RunRepository()
    application.state.request_count = 0
    application.state.error_count = 0
    application.state.started_at = time.monotonic()
    application.state.route_metrics = defaultdict(
        lambda: {"count": 0, "latency_sum": 0.0, "buckets": [0] * 7}
    )
    application.state.rate_windows = defaultdict(deque)
    yield


app = FastAPI(
    title="SmartValve AI Twin API",
    version=__version__,
    description="Production-oriented engineering PoC for explainable valve diagnostics.",
    lifespan=lifespan,
)


@app.middleware("http")
async def request_context(request: Request, call_next):
    supplied_id = request.headers.get("X-Correlation-ID", "").strip()
    correlation_id = (
        supplied_id
        if re.fullmatch(r"[A-Za-z0-9._:-]{1,128}", supplied_id)
        else str(uuid4())
    )
    request.state.correlation_id = correlation_id
    request.app.state.request_count += 1
    started = time.perf_counter()
    if production_mode() and request.url.path.startswith("/v1/"):
        now = time.monotonic()
        remote = request.client.host if request.client else "unknown"
        window = request.app.state.rate_windows[remote]
        while window and window[0] <= now - 60.0:
            window.popleft()
        limit = max(1, int(os.getenv("SMARTVALVE_RATE_LIMIT_PER_MINUTE", "120")))
        if len(window) >= limit:
            request.app.state.error_count += 1
            return JSONResponse(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                content={"detail": "rate limit exceeded", "correlation_id": correlation_id},
                headers={"Retry-After": "60", "X-Correlation-ID": correlation_id},
            )
        window.append(now)
    try:
        response = await call_next(request)
    except Exception:
        request.app.state.error_count += 1
        LOGGER.exception("unhandled_request_error correlation_id=%s", correlation_id)
        raise
    elapsed = time.perf_counter() - started
    if response.status_code >= 400:
        request.app.state.error_count += 1
    metric_path = re.sub(r"/v1/runs/[^/]+", "/v1/runs/{run_id}", request.url.path)
    metric = request.app.state.route_metrics[(request.method, metric_path, response.status_code)]
    metric["count"] += 1
    metric["latency_sum"] += elapsed
    for index, boundary in enumerate((0.01, 0.05, 0.1, 0.5, 1.0, 2.0, 5.0)):
        if elapsed <= boundary:
            metric["buckets"][index] += 1
    response.headers["X-Correlation-ID"] = correlation_id
    response.headers["X-Process-Time-Ms"] = f"{elapsed * 1000:.2f}"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; img-src 'self' data:; style-src 'self' 'unsafe-inline' "
        "https://cdn.jsdelivr.net; script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net"
    )
    return response


@app.exception_handler(ValueError)
async def value_error_handler(request: Request, exc: ValueError) -> JSONResponse:
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={"detail": str(exc), "correlation_id": request.state.correlation_id},
    )


@app.exception_handler(FileNotFoundError)
async def missing_artifact_handler(request: Request, exc: FileNotFoundError) -> JSONResponse:
    return JSONResponse(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        content={"detail": str(exc), "correlation_id": request.state.correlation_id},
    )


def require_api_key(
    x_api_key: Annotated[str | None, Header()] = None,
    x_operator_id: Annotated[str | None, Header()] = None,
) -> str:
    expected = os.getenv("SMARTVALVE_API_KEY")
    if production_mode() and not expected:
        raise HTTPException(status_code=503, detail="API authentication is not configured")
    if expected and (x_api_key is None or not compare_digest(expected, x_api_key)):
        raise HTTPException(status_code=401, detail="invalid or missing API key")
    operator_id = (x_operator_id or "local-demo").strip()
    if production_mode() and x_operator_id is None:
        raise HTTPException(status_code=401, detail="missing X-Operator-ID")
    if not re.fullmatch(r"[A-Za-z0-9._@:-]{1,80}", operator_id):
        raise HTTPException(status_code=422, detail="invalid X-Operator-ID")
    return operator_id


MAX_UPLOAD_BYTES = 10 * 1024 * 1024
MAX_TRACE_POINTS = 500
MAX_UPLOAD_ROWS = 200_000


def _json_safe(value: object) -> object:
    if value is None:
        return None
    if isinstance(value, (np.floating, float)):
        return round(float(value), 6) if np.isfinite(value) else None
    if isinstance(value, (np.integer, int)):
        return int(value)
    if isinstance(value, (np.bool_, bool)):
        return bool(value)
    return value


def _frame_records(frame: pd.DataFrame, columns: tuple[str, ...]) -> list[dict[str, object]]:
    """Return bounded, JSON-safe evidence points for the operations console."""

    if frame.empty:
        return []
    indices = np.linspace(0, len(frame) - 1, min(len(frame), MAX_TRACE_POINTS), dtype=int)
    sampled = frame.iloc[np.unique(indices)]
    records: list[dict[str, object]] = []
    for _, row in sampled.iterrows():
        records.append(
            {column: _json_safe(row[column]) for column in columns if column in sampled.columns}
        )
    return records


def _signature_records(frame: pd.DataFrame) -> list[dict[str, object]]:
    return [
        {column: _json_safe(value) for column, value in row.items()}
        for row in frame.to_dict(orient="records")
    ]


def _diagnostic_response(
    run: TwinRun,
    *,
    run_id: str,
    correlation_id: str,
    created_at: str,
    operator_id: str,
    asset_id: str,
    source: str,
    evidence_grade: str,
    limitations: list[str],
) -> DiagnosticResponse:
    return DiagnosticResponse(
        run_id=run_id,
        correlation_id=correlation_id,
        created_at=created_at,
        operator_id=operator_id,
        asset_id=asset_id,
        source=source,
        evidence_grade=evidence_grade,
        model_version=MODEL_VERSION,
        diagnosis=run.diagnosis.to_dict(),
        network=run.network.to_dict(),
        quality={
            "baseline": run.baseline_quality.to_dict(),
            "current": run.current_quality.to_dict(),
        },
        baseline_trace=_frame_records(
            run.baseline_data,
            (
                "timestamp_s",
                "command_pct",
                "position_pct",
                "motor_current_a",
                "flow_lpm",
                "pressure_upstream_kpa",
                "pressure_downstream_kpa",
            ),
        ),
        trace=_frame_records(
            run.current_data,
            (
                "timestamp_s",
                "command_pct",
                "position_pct",
                "motor_current_a",
                "flow_lpm",
                "pressure_upstream_kpa",
                "pressure_downstream_kpa",
            ),
        ),
        signature={
            "baseline": _signature_records(run.signature.baseline_signature),
            "current": _signature_records(run.signature.current_signature),
            "baseline_features": run.signature.baseline_features,
            "current_features": run.signature.current_features,
            "similarity_pct": run.signature.similarity_pct,
            "abnormal_start_pct": run.signature.abnormal_start_pct,
            "abnormal_end_pct": run.signature.abnormal_end_pct,
            "max_current_residual_a": run.signature.max_current_residual_a,
            "residual_rmse_a": run.signature.residual_rmse_a,
        },
        limitations=limitations,
        audit={},
    )


def _persisted_diagnostic_response(
    run: TwinRun,
    request: Request,
    *,
    asset_id: str,
    source: str,
    evidence_grade: str,
    limitations: list[str],
    request_payload: dict[str, object],
) -> DiagnosticResponse:
    operator_id = request.headers.get("X-Operator-ID", "local-demo").strip()
    response = _diagnostic_response(
        run,
        run_id=str(uuid4()),
        correlation_id=request.state.correlation_id,
        created_at=datetime.now(UTC).isoformat(),
        operator_id=operator_id,
        asset_id=asset_id,
        source=source,
        evidence_grade=evidence_grade,
        limitations=limitations,
    )
    seal = request.app.state.repository.record(
        run,
        result=response.model_dump(mode="json"),
        request_payload=request_payload,
        operator_id=operator_id,
        evidence_grade=evidence_grade,
    )
    return response.model_copy(update={"audit": seal})


@app.get("/health/live", tags=["health"])
def live() -> dict[str, str]:
    return {"status": "live", "version": app.version}


@app.get("/health/ready", tags=["health"])
def ready(request: Request) -> JSONResponse:
    database_ready = request.app.state.repository.ping()
    try:
        network_probe = simulate_network_impact(100.0)
        hydraulic_engine = network_probe.engine
        hydraulic_ready = network_probe.engine.startswith("WNTR") or not env_bool(
            "SMARTVALVE_REQUIRE_WNTR", production_mode()
        )
    except Exception:
        LOGGER.exception("hydraulic_readiness_failed")
        hydraulic_engine = "unavailable"
        hydraulic_ready = False
    is_ready = database_ready and hydraulic_ready
    payload = {
        "status": "ready" if is_ready else "degraded",
        "database": database_ready,
        "hydraulic_ready": hydraulic_ready,
        "hydraulic_engine": hydraulic_engine,
        "model_version": MODEL_VERSION,
    }
    return JSONResponse(status_code=200 if is_ready else 503, content=payload)


@app.get("/metrics", response_class=PlainTextResponse, tags=["operations"])
def metrics(request: Request) -> str:
    uptime = time.monotonic() - request.app.state.started_at
    lines = [
        "# TYPE smartvalve_requests_total counter",
        f"smartvalve_requests_total {request.app.state.request_count}",
        "# TYPE smartvalve_errors_total counter",
        f"smartvalve_errors_total {request.app.state.error_count}",
        "# TYPE smartvalve_uptime_seconds gauge",
        f"smartvalve_uptime_seconds {uptime:.3f}",
        "# TYPE smartvalve_http_requests_total counter",
    ]
    for (method, path, response_status), values in sorted(request.app.state.route_metrics.items()):
        labels = f'method="{method}",path="{path}",status="{response_status}"'
        lines.append(f"smartvalve_http_requests_total{{{labels}}} {values['count']}")
        lines.append(
            f"smartvalve_http_request_duration_seconds_sum{{{labels}}} "
            f"{values['latency_sum']:.6f}"
        )
        lines.append(
            f"smartvalve_http_request_duration_seconds_count{{{labels}}} {values['count']}"
        )
    lines.append("")
    return "\n".join(lines)


@app.get("/v1/sources", dependencies=[Depends(require_api_key)], tags=["sources"])
def sources() -> dict[str, object]:
    return {
        "sources": [
            {
                "source_id": "simulation",
                "name": "Deterministic valve simulator",
                "evidence_grade": EvidenceGrade.S0_SIMULATION.value,
                "available": True,
            },
            CRANFIELD_METADATA.to_dict(),
            SKAB_METADATA.to_dict(),
            {
                "source_id": "desktop-rig",
                "name": "CNY 200 desktop rig",
                "evidence_grade": EvidenceGrade.S2_OWN_RIG.value,
                "available": False,
            },
        ],
        "artifacts": artifact_status(),
    }


@app.post(
    "/v1/diagnostics/simulation",
    response_model=DiagnosticResponse,
    dependencies=[Depends(require_api_key)],
    tags=["diagnostics"],
)
def diagnose_simulation(payload: SimulationRequest, request: Request) -> DiagnosticResponse:
    fault = FaultConfig(
        fault_type=payload.fault_type,
        severity=payload.severity,
        location_pct=payload.location_pct,
        width_pct=payload.width_pct,
        supply_voltage_v=payload.supply_voltage_v,
        load_factor=payload.load_factor,
        seed=payload.seed,
    )
    run = run_twin(fault)
    return _persisted_diagnostic_response(
        run,
        request,
        asset_id=payload.asset_id,
        source="simulation",
        evidence_grade=EvidenceGrade.S0_SIMULATION.value,
        limitations=[
            "Simulation is not manufacturer-specific validation",
            "Valve travel to hydraulic loss is illustrative until calibrated",
        ],
        request_payload=payload.model_dump(mode="json"),
    )


@app.post(
    "/v1/diagnostics/cranfield",
    response_model=DiagnosticResponse,
    dependencies=[Depends(require_api_key)],
    tags=["diagnostics"],
)
def diagnose_cranfield(payload: CranfieldRequest, request: Request) -> DiagnosticResponse:
    filename = (
        "LackLubrication2.mat" if payload.fault == "lack_of_lubrication" else "Backlash2.mat"
    )
    baseline, current = load_cranfield_pair(
        fault_filename=filename,
        motion=payload.motion,
        load_kg=payload.load_kg,
        repetition=payload.repetition,
    )
    run = run_from_frames(baseline, current)
    return _persisted_diagnostic_response(
        run,
        request,
        asset_id=payload.asset_id,
        source="cranfield_real_actuator",
        evidence_grade=EvidenceGrade.S1_PUBLIC_RIG.value,
        limitations=[
            "Physical electromechanical actuator data, but not a water valve",
            "Hydraulic consequence is not validated by this source",
            "Generic ValveDNA finding is not a calibrated Cranfield fault classifier",
        ],
        request_payload=payload.model_dump(mode="json"),
    )


@app.get(
    "/v1/validation/cranfield/sample",
    response_model=DiagnosticResponse,
    dependencies=[Depends(require_api_key)],
    tags=["validation"],
)
def cranfield_validation_sample(request: Request) -> DiagnosticResponse:
    """Return a fixed read-only evidence sample without creating an audit record."""

    baseline, current = load_cranfield_pair(
        fault_filename="LackLubrication2.mat",
        motion="trap",
        load_kg=20,
        repetition=1,
    )
    run = run_from_frames(baseline, current)
    return _diagnostic_response(
        run,
        run_id=f"preview-{uuid4()}",
        correlation_id=request.state.correlation_id,
        created_at=datetime.now(UTC).isoformat(),
        operator_id=request.headers.get("X-Operator-ID", "local-demo").strip(),
        asset_id="CRANFIELD-EMA-01",
        source="cranfield_real_actuator_read_only_sample",
        evidence_grade=EvidenceGrade.S1_PUBLIC_RIG.value,
        limitations=[
            "Read-only validation sample; this response is intentionally not audit-persisted",
            "Physical electromechanical actuator data, but not a water valve",
            "Hydraulic consequence is not validated by this source",
        ],
    )


@app.post(
    "/v1/diagnostics/csv",
    response_model=DiagnosticResponse,
    dependencies=[Depends(require_api_key)],
    tags=["diagnostics"],
)
async def diagnose_csv(
    request: Request,
    asset_id: Annotated[str, Form(min_length=1, max_length=80)],
    source: Annotated[Literal["desktop_rig", "enterprise_valve"], Form()],
    baseline_file: Annotated[UploadFile, File()],
    current_file: Annotated[UploadFile, File()],
) -> DiagnosticResponse:
    asset_id = asset_id.strip()
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._:-]{0,79}", asset_id):
        raise HTTPException(status_code=422, detail="asset_id contains unsupported characters")
    for uploaded in (baseline_file, current_file):
        if uploaded.filename and not uploaded.filename.lower().endswith(".csv"):
            raise HTTPException(status_code=415, detail="baseline and current files must be CSV")
    baseline_bytes = await baseline_file.read(MAX_UPLOAD_BYTES + 1)
    current_bytes = await current_file.read(MAX_UPLOAD_BYTES + 1)
    if len(baseline_bytes) > MAX_UPLOAD_BYTES or len(current_bytes) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="each CSV must be 10 MiB or smaller")
    baseline, baseline_report = load_canonical_csv(baseline_bytes)
    current, current_report = load_canonical_csv(current_bytes)
    if len(baseline) > MAX_UPLOAD_ROWS or len(current) > MAX_UPLOAD_ROWS:
        raise HTTPException(status_code=413, detail="each CSV must contain at most 200000 rows")
    if not env_bool("SMARTVALVE_ALLOW_REVIEW_DATA", False):
        review_reports = [
            name
            for name, report in (("baseline", baseline_report), ("current", current_report))
            if report.status != "ACCEPTED"
        ]
        if review_reports:
            raise HTTPException(
                status_code=422,
                detail=f"data quality requires review: {', '.join(review_reports)}",
            )
    baseline = baseline.copy()
    current = current.copy()
    baseline["source"] = source
    current["source"] = source
    baseline["valve_id"] = asset_id
    current["valve_id"] = asset_id
    run = run_from_frames(baseline, current)
    evidence_grade = (
        EvidenceGrade.S2_OWN_RIG.value
        if source == "desktop_rig"
        else "S3 candidate · Operator-declared enterprise source"
    )
    return _persisted_diagnostic_response(
        run,
        request,
        asset_id=asset_id,
        source=source,
        evidence_grade=evidence_grade,
        limitations=[
            "Uploaded source identity is operator-declared and must be verified",
            "Hydraulic mapping remains illustrative until product calibration",
        ],
        request_payload={
            "asset_id": asset_id,
            "source": source,
            "baseline_filename": baseline_file.filename or "baseline.csv",
            "current_filename": current_file.filename or "current.csv",
            "baseline_bytes": len(baseline_bytes),
            "current_bytes": len(current_bytes),
            "baseline_raw_sha256": sha256(baseline_bytes).hexdigest(),
            "current_raw_sha256": sha256(current_bytes).hexdigest(),
        },
    )


@app.get(
    "/v1/validation/skab",
    dependencies=[Depends(require_api_key)],
    tags=["validation"],
)
def validate_skab() -> dict[str, object]:
    result = run_skab_validation()
    trace = result.data.loc[:, ["timestamp_s", "FlowLPM", "anomaly"]].copy()
    trace["score"] = result.score
    return {
        "source": SKAB_METADATA.to_dict(),
        "split": {"training": result.training_samples, "evaluation": result.evaluation_samples},
        "metrics": result.summary(),
        "trace": _frame_records(trace, ("timestamp_s", "FlowLPM", "anomaly", "score")),
        "limitation": "Process anomaly benchmark; not valve mechanical root-cause validation",
    }


@app.get(
    "/v1/validation/benchmark",
    dependencies=[Depends(require_api_key)],
    tags=["validation"],
)
def validation_benchmark(
    profile: Annotated[Literal["full", "challenge"], Query()] = "full",
) -> dict[str, object]:
    metrics_path = project_root() / "artifacts" / "benchmark" / profile / "metrics.json"
    if not metrics_path.is_file():
        command = "make benchmark" if profile == "full" else "make benchmark-challenge"
        raise HTTPException(status_code=503, detail=f"{profile} benchmark missing; run `{command}`")
    return json.loads(metrics_path.read_text(encoding="utf-8"))


@app.get(
    "/v1/validation/cranfield",
    dependencies=[Depends(require_api_key)],
    tags=["validation"],
)
def validation_cranfield() -> dict[str, object]:
    metrics_path = (
        project_root() / "artifacts" / "validation" / "cranfield" / "metrics.json"
    )
    if not metrics_path.is_file():
        raise HTTPException(
            status_code=503,
            detail="Cranfield grouped benchmark missing; run `make benchmark-cranfield`",
        )
    return json.loads(metrics_path.read_text(encoding="utf-8"))


@app.get("/v1/runs", dependencies=[Depends(require_api_key)], tags=["audit"])
def list_runs(
    request: Request,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
) -> dict[str, object]:
    return {"items": request.app.state.repository.list(limit)}


@app.get("/v1/audit/verify", dependencies=[Depends(require_api_key)], tags=["audit"])
def verify_audit_chain(request: Request) -> dict[str, object]:
    return request.app.state.repository.verify_chain()


@app.get("/v1/runs/{run_id}", dependencies=[Depends(require_api_key)], tags=["audit"])
def get_run(run_id: str, request: Request) -> dict[str, object]:
    result = request.app.state.repository.get(run_id)
    if result is None:
        raise HTTPException(status_code=404, detail="run not found")
    return result


@app.get(
    "/v1/runs/{run_id}/report.pdf",
    dependencies=[Depends(require_api_key)],
    response_class=Response,
    tags=["audit"],
)
def get_run_pdf(run_id: str, request: Request) -> Response:
    result = request.app.state.repository.get(run_id)
    if result is None:
        raise HTTPException(status_code=404, detail="run not found")
    return Response(
        content=build_diagnostic_pdf(result),
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{run_id}.pdf"'},
    )


@app.get("/openapi.snapshot.json", include_in_schema=False)
def openapi_snapshot() -> Response:
    return Response(
        content=json.dumps(app.openapi(), ensure_ascii=False), media_type="application/json"
    )
