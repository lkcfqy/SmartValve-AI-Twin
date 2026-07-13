"""SQLite append-only diagnostic repository with a verifiable SHA-256 hash chain."""

from __future__ import annotations

import json
import os
import sqlite3
from hashlib import sha256
from pathlib import Path
from typing import Any

from smartvalve.config import project_root
from smartvalve.pipeline import TwinRun

GENESIS_HASH = "0" * 64


def _canonical_json(value: object) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def _sha256_text(value: str) -> str:
    return sha256(value.encode("utf-8")).hexdigest()


def _record_hash(
    *,
    previous_hash: str,
    run_id: str,
    created_at: str,
    operator_id: str,
    evidence_grade: str,
    baseline_sha256: str,
    current_sha256: str,
    request_sha256: str,
    result_sha256: str,
) -> str:
    material = "\n".join(
        (
            previous_hash,
            run_id,
            created_at,
            operator_id,
            evidence_grade,
            baseline_sha256,
            current_sha256,
            request_sha256,
            result_sha256,
        )
    )
    return _sha256_text(material)


class RunRepository:
    def __init__(self, path: str | Path | None = None) -> None:
        configured = path or os.getenv("SMARTVALVE_DATABASE")
        if configured is None:
            configured = project_root() / "data" / "runtime" / "smartvalve.db"
        self.path = Path(configured).expanduser()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.initialize()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path, timeout=10.0)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA journal_mode=WAL")
        connection.execute("PRAGMA foreign_keys=ON")
        connection.execute("PRAGMA busy_timeout=10000")
        connection.execute("PRAGMA synchronous=FULL")
        return connection

    def initialize(self) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS diagnostic_runs (
                    run_id TEXT PRIMARY KEY,
                    created_at TEXT NOT NULL,
                    asset_id TEXT NOT NULL,
                    source TEXT NOT NULL,
                    evidence_grade TEXT NOT NULL DEFAULT '',
                    operator_id TEXT NOT NULL DEFAULT 'legacy',
                    model_version TEXT NOT NULL,
                    status TEXT NOT NULL,
                    health_score REAL NOT NULL,
                    network_impact REAL NOT NULL,
                    baseline_sha256 TEXT NOT NULL DEFAULT '',
                    data_sha256 TEXT NOT NULL,
                    request_json TEXT NOT NULL DEFAULT '{}',
                    request_sha256 TEXT NOT NULL DEFAULT '',
                    result_sha256 TEXT NOT NULL DEFAULT '',
                    previous_record_sha256 TEXT NOT NULL DEFAULT '',
                    record_sha256 TEXT NOT NULL DEFAULT '',
                    correlation_id TEXT NOT NULL,
                    result_json TEXT NOT NULL
                )
                """
            )
            required_columns = {
                "evidence_grade": "TEXT NOT NULL DEFAULT ''",
                "operator_id": "TEXT NOT NULL DEFAULT 'legacy'",
                "baseline_sha256": "TEXT NOT NULL DEFAULT ''",
                "request_json": "TEXT NOT NULL DEFAULT '{}'",
                "request_sha256": "TEXT NOT NULL DEFAULT ''",
                "result_sha256": "TEXT NOT NULL DEFAULT ''",
                "previous_record_sha256": "TEXT NOT NULL DEFAULT ''",
                "record_sha256": "TEXT NOT NULL DEFAULT ''",
            }
            existing = {
                row["name"] for row in connection.execute("PRAGMA table_info(diagnostic_runs)")
            }
            for name, definition in required_columns.items():
                if name not in existing:
                    connection.execute(
                        f"ALTER TABLE diagnostic_runs ADD COLUMN {name} {definition}"
                    )
            connection.execute(
                "CREATE INDEX IF NOT EXISTS ix_runs_created_at ON diagnostic_runs(created_at DESC)"
            )
            self._backfill_legacy_chain(connection)
            connection.execute(
                """
                CREATE TRIGGER IF NOT EXISTS diagnostic_runs_block_update
                BEFORE UPDATE ON diagnostic_runs
                BEGIN
                    SELECT RAISE(ABORT, 'diagnostic_runs is append-only');
                END
                """
            )
            connection.execute(
                """
                CREATE TRIGGER IF NOT EXISTS diagnostic_runs_block_delete
                BEFORE DELETE ON diagnostic_runs
                BEGIN
                    SELECT RAISE(ABORT, 'diagnostic_runs is append-only');
                END
                """
            )

    def _backfill_legacy_chain(self, connection: sqlite3.Connection) -> None:
        pending = connection.execute(
            """
            SELECT * FROM diagnostic_runs
            WHERE record_sha256 = ''
            ORDER BY created_at ASC, rowid ASC
            """
        ).fetchall()
        if not pending:
            return
        previous_row = connection.execute(
            """
            SELECT record_sha256 FROM diagnostic_runs
            WHERE record_sha256 != ''
            ORDER BY created_at DESC, rowid DESC LIMIT 1
            """
        ).fetchone()
        previous = previous_row["record_sha256"] if previous_row else GENESIS_HASH
        for row in pending:
            request_json = row["request_json"] or "{}"
            result_payload = json.loads(row["result_json"])
            result_payload.pop("audit", None)
            result_sha = _sha256_text(_canonical_json(result_payload))
            request_sha = _sha256_text(request_json)
            baseline_sha = row["baseline_sha256"] or "legacy-unavailable"
            evidence_grade = row["evidence_grade"] or "legacy-unclassified"
            operator_id = row["operator_id"] or "legacy"
            current = _record_hash(
                previous_hash=previous,
                run_id=row["run_id"],
                created_at=row["created_at"],
                operator_id=operator_id,
                evidence_grade=evidence_grade,
                baseline_sha256=baseline_sha,
                current_sha256=row["data_sha256"],
                request_sha256=request_sha,
                result_sha256=result_sha,
            )
            connection.execute(
                """
                UPDATE diagnostic_runs
                SET evidence_grade = ?, operator_id = ?, baseline_sha256 = ?,
                    request_sha256 = ?, result_sha256 = ?, previous_record_sha256 = ?,
                    record_sha256 = ?
                WHERE run_id = ?
                """,
                (
                    evidence_grade,
                    operator_id,
                    baseline_sha,
                    request_sha,
                    result_sha,
                    previous,
                    current,
                    row["run_id"],
                ),
            )
            previous = current

    def ping(self) -> bool:
        try:
            with self._connect() as connection:
                return connection.execute("SELECT 1").fetchone()[0] == 1
        except sqlite3.Error:
            return False

    def record(
        self,
        run: TwinRun,
        *,
        result: dict[str, Any],
        request_payload: dict[str, Any],
        operator_id: str,
        evidence_grade: str,
    ) -> dict[str, str]:
        base_result = dict(result)
        base_result.pop("audit", None)
        run_id = str(base_result["run_id"])
        created_at = str(base_result["created_at"])
        request_json = _canonical_json(request_payload)
        result_sha = _sha256_text(_canonical_json(base_result))
        request_sha = _sha256_text(request_json)
        baseline_sha = run.baseline_quality.data_sha256
        current_sha = run.current_quality.data_sha256

        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            previous_row = connection.execute(
                "SELECT record_sha256 FROM diagnostic_runs ORDER BY rowid DESC LIMIT 1"
            ).fetchone()
            previous = previous_row["record_sha256"] if previous_row else GENESIS_HASH
            current = _record_hash(
                previous_hash=previous,
                run_id=run_id,
                created_at=created_at,
                operator_id=operator_id,
                evidence_grade=evidence_grade,
                baseline_sha256=baseline_sha,
                current_sha256=current_sha,
                request_sha256=request_sha,
                result_sha256=result_sha,
            )
            seal = {
                "baseline_sha256": baseline_sha,
                "current_sha256": current_sha,
                "request_sha256": request_sha,
                "result_sha256": result_sha,
                "previous_record_sha256": previous,
                "record_sha256": current,
            }
            stored_result = {**base_result, "audit": seal}
            connection.execute(
                """
                INSERT INTO diagnostic_runs (
                    run_id, created_at, asset_id, source, evidence_grade, operator_id,
                    model_version, status, health_score, network_impact,
                    baseline_sha256, data_sha256, request_json, request_sha256,
                    result_sha256, previous_record_sha256, record_sha256, result_json
                    , correlation_id
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    run_id,
                    created_at,
                    base_result["asset_id"],
                    base_result["source"],
                    evidence_grade,
                    operator_id,
                    base_result["model_version"],
                    run.diagnosis.ne107_status,
                    run.diagnosis.health_score,
                    run.network.impact_score,
                    baseline_sha,
                    current_sha,
                    request_json,
                    request_sha,
                    result_sha,
                    previous,
                    current,
                    _canonical_json(stored_result),
                    base_result["correlation_id"],
                ),
            )
        return seal

    def list(self, limit: int = 50) -> list[dict[str, Any]]:
        bounded_limit = min(max(int(limit), 1), 200)
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT run_id, created_at, asset_id, source, evidence_grade, operator_id,
                       model_version, status, health_score, network_impact,
                       baseline_sha256, data_sha256, result_sha256, record_sha256,
                       correlation_id
                FROM diagnostic_runs
                ORDER BY created_at DESC LIMIT ?
                """,
                (bounded_limit,),
            ).fetchall()
        return [dict(row) for row in rows]

    def get(self, run_id: str) -> dict[str, Any] | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT result_json FROM diagnostic_runs WHERE run_id = ?", (run_id,)
            ).fetchone()
        return json.loads(row["result_json"]) if row else None

    def verify_chain(self) -> dict[str, Any]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT * FROM diagnostic_runs ORDER BY created_at ASC, rowid ASC"
            ).fetchall()
        previous = GENESIS_HASH
        for index, row in enumerate(rows, start=1):
            request_json = row["request_json"]
            result_payload = json.loads(row["result_json"])
            result_payload.pop("audit", None)
            result_sha = _sha256_text(_canonical_json(result_payload))
            request_sha = _sha256_text(request_json)
            expected = _record_hash(
                previous_hash=previous,
                run_id=row["run_id"],
                created_at=row["created_at"],
                operator_id=row["operator_id"],
                evidence_grade=row["evidence_grade"],
                baseline_sha256=row["baseline_sha256"],
                current_sha256=row["data_sha256"],
                request_sha256=request_sha,
                result_sha256=result_sha,
            )
            valid = (
                row["previous_record_sha256"] == previous
                and row["request_sha256"] == request_sha
                and row["result_sha256"] == result_sha
                and row["record_sha256"] == expected
            )
            if not valid:
                return {
                    "valid": False,
                    "checked_records": index,
                    "first_invalid_run_id": row["run_id"],
                    "head_record_sha256": previous,
                }
            previous = expected
        return {
            "valid": True,
            "checked_records": len(rows),
            "first_invalid_run_id": None,
            "head_record_sha256": previous,
        }
