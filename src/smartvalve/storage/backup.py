"""Signed, verifiable SQLite backup and offline restore operations.

The database hash chain detects record changes. The HMAC-signed manifest additionally
anchors a consistent SQLite snapshot so an off-host backup cannot be silently replaced
without access to the independently managed signing key.
"""

from __future__ import annotations

import argparse
import hmac
import json
import os
import shutil
import sqlite3
import sys
from collections.abc import Sequence
from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path
from typing import Any
from uuid import uuid4

from smartvalve import MODEL_VERSION, __version__
from smartvalve.storage.repository import GENESIS_HASH, _canonical_json, verify_chain_rows

BACKUP_SCHEMA_VERSION = 1
MIN_SIGNING_KEY_BYTES = 32
DEFAULT_SIGNING_KEY_ENV = "SMARTVALVE_BACKUP_SIGNING_KEY"


class BackupError(RuntimeError):
    """Raised when a backup or restore operation cannot be completed safely."""


def _file_sha256(path: Path) -> str:
    digest = sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _validated_key(signing_key: str | bytes) -> bytes:
    key = signing_key.encode("utf-8") if isinstance(signing_key, str) else signing_key
    if len(key) < MIN_SIGNING_KEY_BYTES:
        raise BackupError(
            f"backup signing key must contain at least {MIN_SIGNING_KEY_BYTES} bytes"
        )
    return key


def _manifest_signature(payload: dict[str, Any], signing_key: bytes) -> str:
    return hmac.new(
        signing_key,
        _canonical_json(payload).encode("utf-8"),
        sha256,
    ).hexdigest()


def inspect_snapshot(database: str | Path) -> dict[str, Any]:
    """Read a self-contained SQLite snapshot without changing it."""

    path = Path(database).expanduser().resolve()
    if not path.is_file():
        return {
            "valid": False,
            "integrity_check": "missing",
            "checked_records": 0,
            "first_invalid_run_id": None,
            "head_record_sha256": GENESIS_HASH,
        }
    try:
        uri = f"{path.as_uri()}?mode=ro&immutable=1"
        with sqlite3.connect(uri, uri=True, timeout=10.0) as connection:
            connection.row_factory = sqlite3.Row
            integrity = str(connection.execute("PRAGMA integrity_check").fetchone()[0])
            rows = connection.execute(
                "SELECT * FROM diagnostic_runs ORDER BY rowid ASC"
            ).fetchall()
    except (sqlite3.Error, OSError, ValueError, json.JSONDecodeError) as exc:
        return {
            "valid": False,
            "integrity_check": f"error: {type(exc).__name__}",
            "checked_records": 0,
            "first_invalid_run_id": None,
            "head_record_sha256": GENESIS_HASH,
        }
    chain = verify_chain_rows(rows)
    return {
        **chain,
        "valid": integrity == "ok" and chain["valid"],
        "integrity_check": integrity,
    }


def _write_json_atomic(path: Path, value: dict[str, Any]) -> None:
    temporary = path.with_name(f".{path.name}.{uuid4().hex}.tmp")
    try:
        with temporary.open("x", encoding="utf-8") as handle:
            json.dump(value, handle, ensure_ascii=False, indent=2, sort_keys=True)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        temporary.chmod(0o600)
        os.replace(temporary, path)
        _fsync_directory(path.parent)
    finally:
        temporary.unlink(missing_ok=True)


def _fsync_directory(directory: Path) -> None:
    """Persist directory entry changes on the Linux production target."""

    flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0)
    descriptor = os.open(directory, flags)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def create_backup(
    database: str | Path,
    output_directory: str | Path,
    signing_key: str | bytes,
    *,
    created_at: datetime | None = None,
) -> dict[str, Any]:
    """Create a consistent SQLite snapshot and an HMAC-signed manifest."""

    key = _validated_key(signing_key)
    source = Path(database).expanduser().resolve()
    if not source.is_file():
        raise BackupError(f"database does not exist: {source}")
    destination_directory = Path(output_directory).expanduser().resolve()
    destination_directory.mkdir(parents=True, exist_ok=True)
    requested_timestamp = created_at or datetime.now(UTC)
    if requested_timestamp.tzinfo is None:
        raise BackupError("backup timestamp must be timezone-aware")
    timestamp = requested_timestamp.astimezone(UTC)
    stamp = timestamp.strftime("%Y%m%dT%H%M%S.%fZ")
    backup = destination_directory / f"smartvalve-{stamp}-{uuid4().hex[:8]}.db"
    temporary = destination_directory / f".{backup.name}.{uuid4().hex}.tmp"
    manifest = backup.with_name(f"{backup.name}.manifest.json")

    try:
        with (
            sqlite3.connect(
                f"{source.as_uri()}?mode=ro", uri=True, timeout=30.0
            ) as source_connection,
            sqlite3.connect(temporary) as destination_connection,
        ):
            source_connection.execute("PRAGMA busy_timeout=30000")
            source_connection.backup(destination_connection)
            destination_connection.execute("PRAGMA journal_mode=DELETE")
            destination_connection.execute("PRAGMA synchronous=FULL")
        temporary.chmod(0o600)
        snapshot = inspect_snapshot(temporary)
        if not snapshot["valid"]:
            raise BackupError(f"new snapshot failed verification: {snapshot}")
        os.replace(temporary, backup)
        _fsync_directory(backup.parent)

        payload: dict[str, Any] = {
            "schema_version": BACKUP_SCHEMA_VERSION,
            "created_at": timestamp.isoformat(),
            "software_version": __version__,
            "model_version": MODEL_VERSION,
            "database_file": backup.name,
            "database_bytes": backup.stat().st_size,
            "database_sha256": _file_sha256(backup),
            "sqlite_integrity_check": snapshot["integrity_check"],
            "audit_record_count": snapshot["checked_records"],
            "audit_head_record_sha256": snapshot["head_record_sha256"],
        }
        document = {
            **payload,
            "signature": {
                "algorithm": "HMAC-SHA256",
                "value": _manifest_signature(payload, key),
            },
        }
        _write_json_atomic(manifest, document)
    except (sqlite3.Error, OSError) as exc:
        backup.unlink(missing_ok=True)
        manifest.unlink(missing_ok=True)
        raise BackupError(f"backup failed: {exc}") from exc
    finally:
        temporary.unlink(missing_ok=True)

    return {"backup": str(backup), "manifest": str(manifest), **document}


def verify_backup(
    backup: str | Path,
    manifest: str | Path,
    signing_key: str | bytes,
) -> dict[str, Any]:
    """Verify manifest authenticity, snapshot bytes, SQLite integrity and audit chain."""

    key = _validated_key(signing_key)
    backup_path = Path(backup).expanduser().resolve()
    manifest_path = Path(manifest).expanduser().resolve()
    checks = {
        "schema": False,
        "manifest_signature": False,
        "filename": False,
        "size": False,
        "sha256": False,
        "sqlite_integrity": False,
        "audit_chain": False,
        "audit_anchor": False,
    }
    signed_manifest: dict[str, Any] | None = None
    try:
        document = json.loads(manifest_path.read_text(encoding="utf-8"))
        signature = document.pop("signature")
        checks["schema"] = document.get("schema_version") == BACKUP_SCHEMA_VERSION
        checks["manifest_signature"] = (
            signature.get("algorithm") == "HMAC-SHA256"
            and isinstance(signature.get("value"), str)
            and hmac.compare_digest(signature["value"], _manifest_signature(document, key))
        )
        if checks["manifest_signature"]:
            signed_manifest = dict(document)
        checks["filename"] = document.get("database_file") == backup_path.name
        checks["size"] = document.get("database_bytes") == backup_path.stat().st_size
        checks["sha256"] = document.get("database_sha256") == _file_sha256(backup_path)
        snapshot = inspect_snapshot(backup_path)
        checks["sqlite_integrity"] = snapshot["integrity_check"] == "ok"
        checks["audit_chain"] = bool(snapshot["valid"])
        checks["audit_anchor"] = (
            document.get("audit_record_count") == snapshot["checked_records"]
            and document.get("audit_head_record_sha256") == snapshot["head_record_sha256"]
        )
    except (AttributeError, OSError, KeyError, TypeError, ValueError, json.JSONDecodeError):
        snapshot = inspect_snapshot(backup_path)
    return {
        "valid": all(checks.values()),
        "checks": checks,
        "backup": str(backup_path),
        "manifest": str(manifest_path),
        "snapshot": snapshot,
        "signed_manifest": signed_manifest,
    }


def restore_backup(
    backup: str | Path,
    manifest: str | Path,
    destination: str | Path,
    signing_key: str | bytes,
    *,
    replace_existing: bool = False,
) -> dict[str, Any]:
    """Restore a verified snapshot atomically; callers must stop all DB users first."""

    verification = verify_backup(backup, manifest, signing_key)
    if not verification["valid"]:
        raise BackupError(f"backup verification failed: {verification['checks']}")
    signed_manifest = verification["signed_manifest"]
    if not isinstance(signed_manifest, dict):  # Defensive: valid verification must bind one.
        raise BackupError("verified backup is missing its signed manifest payload")
    source = Path(backup).expanduser().resolve()
    target = Path(destination).expanduser().resolve()
    target.parent.mkdir(parents=True, exist_ok=True)
    sidecars = [Path(f"{target}-wal"), Path(f"{target}-shm")]
    if (target.exists() or any(path.exists() for path in sidecars)) and not replace_existing:
        raise BackupError("destination or SQLite sidecar exists; use explicit replace_existing")
    temporary = target.with_name(f".{target.name}.{uuid4().hex}.restore")
    previous_files: list[tuple[Path, Path]] = []
    published = False
    try:
        shutil.copyfile(source, temporary)
        temporary.chmod(0o600)
        with temporary.open("rb") as handle:
            os.fsync(handle.fileno())
        restored_snapshot = inspect_snapshot(temporary)
        copied_snapshot_matches = (
            restored_snapshot["valid"]
            and temporary.stat().st_size == signed_manifest["database_bytes"]
            and _file_sha256(temporary) == signed_manifest["database_sha256"]
            and restored_snapshot["checked_records"] == signed_manifest["audit_record_count"]
            and restored_snapshot["head_record_sha256"]
            == signed_manifest["audit_head_record_sha256"]
        )
        if not copied_snapshot_matches:
            raise BackupError("copied snapshot no longer matches the signed manifest")
        for existing in (target, *sidecars):
            if existing.exists():
                staged = existing.with_name(f".{existing.name}.{uuid4().hex}.pre-restore")
                os.replace(existing, staged)
                previous_files.append((existing, staged))
        os.replace(temporary, target)
        published = True
        _fsync_directory(target.parent)
    except OSError as exc:
        if not published:
            for original, staged in reversed(previous_files):
                if staged.exists():
                    os.replace(staged, original)
        raise BackupError(f"restore failed: {exc}") from exc
    finally:
        temporary.unlink(missing_ok=True)
        if published:
            for _, staged in previous_files:
                staged.unlink(missing_ok=True)
    return {"valid": True, "destination": str(target), "snapshot": restored_snapshot}


def _key_from_environment(name: str) -> str:
    value = os.getenv(name, "")
    if not value:
        raise BackupError(f"required signing key environment variable is empty: {name}")
    return value


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="SmartValve signed backup operations")
    parser.add_argument("--signing-key-env", default=DEFAULT_SIGNING_KEY_ENV)
    commands = parser.add_subparsers(dest="command", required=True)

    backup = commands.add_parser("backup", help="create a consistent signed snapshot")
    backup.add_argument("--database", required=True)
    backup.add_argument("--output-directory", required=True)

    verify = commands.add_parser("verify", help="verify a snapshot and its signed manifest")
    verify.add_argument("--backup", required=True)
    verify.add_argument("--manifest", required=True)

    restore = commands.add_parser("restore", help="restore a verified snapshot while offline")
    restore.add_argument("--backup", required=True)
    restore.add_argument("--manifest", required=True)
    restore.add_argument("--database", required=True)
    restore.add_argument("--replace-existing", action="store_true")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        key = _key_from_environment(args.signing_key_env)
        if args.command == "backup":
            result = create_backup(args.database, args.output_directory, key)
        elif args.command == "verify":
            result = verify_backup(args.backup, args.manifest, key)
        else:
            result = restore_backup(
                args.backup,
                args.manifest,
                args.database,
                key,
                replace_existing=args.replace_existing,
            )
    except BackupError as exc:
        print(json.dumps({"valid": False, "error": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 2
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0 if result.get("valid", True) else 2


if __name__ == "__main__":  # pragma: no cover - exercised through the console entry point
    raise SystemExit(main())
