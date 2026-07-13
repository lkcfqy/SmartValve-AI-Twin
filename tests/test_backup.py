from __future__ import annotations

import sqlite3
from datetime import UTC, datetime
from pathlib import Path

import pytest

import smartvalve.storage.backup as backup_module
from smartvalve import MODEL_VERSION
from smartvalve.pipeline import run_twin
from smartvalve.storage.backup import (
    BackupError,
    create_backup,
    inspect_snapshot,
    restore_backup,
    verify_backup,
)
from smartvalve.storage.repository import RunRepository

SIGNING_KEY = "test-only-backup-signing-key-0123456789abcdef"


def _record(repository: RunRepository, *, run_id: str, created_at: str) -> None:
    run = run_twin()
    repository.record(
        run,
        result={
            "run_id": run_id,
            "created_at": created_at,
            "asset_id": "TEST-V-01",
            "source": "simulation",
            "model_version": MODEL_VERSION,
            "correlation_id": f"correlation-{run_id}",
        },
        request_payload={"asset_id": "TEST-V-01"},
        operator_id="test-operator",
        evidence_grade="S0",
    )


def test_chain_verification_uses_append_order_when_clock_moves_back(tmp_path: Path) -> None:
    repository = RunRepository(tmp_path / "clock.db")
    _record(repository, run_id="later-clock", created_at="2026-07-13T10:00:00+00:00")
    _record(repository, run_id="earlier-clock", created_at="2026-07-13T09:00:00+00:00")

    verification = repository.verify_chain()

    assert verification["valid"] is True
    assert verification["checked_records"] == 2


def test_chain_verification_reports_malformed_payload_as_invalid(tmp_path: Path) -> None:
    database = tmp_path / "tampered.db"
    repository = RunRepository(database)
    _record(repository, run_id="run-1", created_at="2026-07-13T10:00:00+00:00")
    with sqlite3.connect(database) as connection:
        connection.execute("DROP TRIGGER diagnostic_runs_block_update")
        connection.execute("UPDATE diagnostic_runs SET result_json = '{'")

    verification = repository.verify_chain()

    assert verification["valid"] is False
    assert verification["first_invalid_run_id"] == "run-1"


def test_signed_backup_verify_restore_and_tamper_detection(tmp_path: Path) -> None:
    database = tmp_path / "live.db"
    repository = RunRepository(database)
    _record(repository, run_id="run-1", created_at="2026-07-13T10:00:00+00:00")
    _record(repository, run_id="run-2", created_at="2026-07-13T10:01:00+00:00")

    created = create_backup(
        database,
        tmp_path / "backups",
        SIGNING_KEY,
        created_at=datetime(2026, 7, 13, 10, 2, tzinfo=UTC),
    )
    backup = Path(created["backup"])
    manifest = Path(created["manifest"])

    verified = verify_backup(backup, manifest, SIGNING_KEY)
    assert verified["valid"] is True
    assert verified["snapshot"]["checked_records"] == 2
    assert all(verified["checks"].values())

    destination = tmp_path / "restored" / "smartvalve.db"
    restored = restore_backup(backup, manifest, destination, SIGNING_KEY)
    assert restored["valid"] is True
    assert inspect_snapshot(destination)["valid"] is True
    assert RunRepository(destination).verify_chain()["checked_records"] == 2

    with pytest.raises(BackupError, match="destination or SQLite sidecar exists"):
        restore_backup(backup, manifest, destination, SIGNING_KEY)

    Path(f"{destination}-wal").write_bytes(b"stale-wal")
    Path(f"{destination}-shm").write_bytes(b"stale-shm")
    replaced = restore_backup(
        backup,
        manifest,
        destination,
        SIGNING_KEY,
        replace_existing=True,
    )
    assert replaced["valid"] is True
    assert not Path(f"{destination}-wal").exists()
    assert not Path(f"{destination}-shm").exists()

    wrong_key = verify_backup(
        backup, manifest, "wrong-key-that-is-still-at-least-32-bytes"
    )
    assert wrong_key["valid"] is False
    with backup.open("r+b") as handle:
        handle.seek(128)
        original = handle.read(1)
        handle.seek(128)
        handle.write(bytes([original[0] ^ 0xFF]))
    tampered = verify_backup(backup, manifest, SIGNING_KEY)
    assert tampered["valid"] is False
    assert tampered["checks"]["sha256"] is False


def test_backup_source_can_be_read_only(tmp_path: Path) -> None:
    database = tmp_path / "read-only.db"
    repository = RunRepository(database)
    _record(repository, run_id="run-1", created_at="2026-07-13T10:00:00+00:00")
    database.chmod(0o444)

    created = create_backup(database, tmp_path / "backups", SIGNING_KEY)

    assert verify_backup(created["backup"], created["manifest"], SIGNING_KEY)["valid"] is True


def test_restore_rechecks_copied_bytes_against_signed_manifest(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    database = tmp_path / "signed.db"
    repository = RunRepository(database)
    _record(repository, run_id="signed-run", created_at="2026-07-13T10:00:00+00:00")
    created = create_backup(database, tmp_path / "backups", SIGNING_KEY)

    replacement = tmp_path / "replacement.db"
    replacement_repository = RunRepository(replacement)
    _record(
        replacement_repository,
        run_id="replacement-run",
        created_at="2026-07-13T10:01:00+00:00",
    )
    real_copyfile = backup_module.shutil.copyfile

    def replace_during_copy(_source: object, destination: object) -> str:
        return str(real_copyfile(replacement, destination))

    monkeypatch.setattr(backup_module.shutil, "copyfile", replace_during_copy)

    with pytest.raises(BackupError, match="no longer matches the signed manifest"):
        restore_backup(
            created["backup"],
            created["manifest"],
            tmp_path / "restored.db",
            SIGNING_KEY,
        )


def test_backup_requires_independent_strong_signing_key(tmp_path: Path) -> None:
    database = tmp_path / "live.db"
    RunRepository(database)

    with pytest.raises(BackupError, match="at least 32 bytes"):
        create_backup(database, tmp_path / "backups", "too-short")
