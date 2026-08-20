"""Validate the frozen local RAR reader on a hash-pinned upstream fixture.

This module deliberately accepts no Paderborn archive path.  It exercises listing,
CRC testing, extraction, regular-file bytes, directories, and a safe symbolic link
using a tiny libarchive test fixture pinned to an immutable upstream commit.
"""

from __future__ import annotations

import argparse
import binascii
import json
import os
import stat
import subprocess
import tempfile
import urllib.request
from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

from smartvalve.config import project_root

UPSTREAM_REPOSITORY = "https://github.com/libarchive/libarchive"
UPSTREAM_COMMIT = "34c4a536a88d5114cfab7ca9bff48c0d235fd53a"
UPSTREAM_PATH = "libarchive/test/test_read_format_rar.rar.uu"
FIXTURE_URL = (
    f"https://raw.githubusercontent.com/libarchive/libarchive/{UPSTREAM_COMMIT}/{UPSTREAM_PATH}"
)
FIXTURE_UU_FILENAME = "test_read_format_rar.rar.uu"
FIXTURE_UU_BYTES = 505
FIXTURE_UU_SHA256 = "d1e75b4120995bce82fc4e72ebf8b80d18ea69fa34ac62de383b8393f92afa09"
FIXTURE_ARCHIVE_FILENAME = "test_read_format_rar.rar"
FIXTURE_ARCHIVE_BYTES = 336
FIXTURE_ARCHIVE_SHA256 = "d421b86f6290aefad61b2a36737253b2b30fe27c156bd95abfc230f24fe0307e"
UNRAR_BYTES = 376_144
UNRAR_SHA256 = "c02de05961b3d6f2a6309b4c40faaaad7891b1a44acdf0f57b882cf2b3612c26"
UNRAR_VERSION_TOKEN = "UNRAR 7.00"
EXPECTED_FILE_CONTENT = b"test text document\r\n"
EXPECTED_FILE_SHA256 = "5a5f16e01faf8adf92eb4499a2d3e93010c4b41dbb7f698f4a8466d9f58e6dd2"
EXPECTED_ENTRY_TYPES = {
    "test.txt": "file",
    "testdir": "directory",
    "testdir/test.txt": "file",
    "testemptydir": "directory",
    "testlink": "symlink",
}


def _digest_bytes(value: bytes) -> str:
    return sha256(value).hexdigest()


def _digest(path: Path) -> str:
    hasher = sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def decode_uu_fixture(encoded: bytes) -> bytes:
    """Decode and validate the exact outer uuencode envelope."""

    lines = encoded.splitlines()
    expected_header = f"begin 644 {FIXTURE_ARCHIVE_FILENAME}".encode()
    if len(lines) < 3 or lines[0] != expected_header or lines[-1] != b"end":
        raise ValueError("fixture does not have the frozen uuencode envelope")
    try:
        decoded = b"".join(binascii.a2b_uu(line) for line in lines[1:-1])
    except binascii.Error as error:
        raise ValueError("fixture contains invalid uuencoded data") from error
    if len(decoded) != FIXTURE_ARCHIVE_BYTES:
        raise ValueError("decoded fixture byte count differs from the frozen value")
    if _digest_bytes(decoded) != FIXTURE_ARCHIVE_SHA256:
        raise ValueError("decoded fixture hash differs from the frozen value")
    return decoded


def _download_or_validate_fixture(cache_directory: Path) -> tuple[Path, bytes, bool]:
    cache_directory.mkdir(parents=True, exist_ok=True)
    fixture_path = cache_directory / FIXTURE_UU_FILENAME
    downloaded = False
    if fixture_path.is_file():
        encoded = fixture_path.read_bytes()
    else:
        parsed = urlsplit(FIXTURE_URL)
        if (
            parsed.scheme != "https"
            or parsed.netloc != "raw.githubusercontent.com"
            or parsed.query
            or parsed.fragment
        ):
            raise ValueError("fixture URL is outside the frozen HTTPS origin")
        # The exact HTTPS origin is validated immediately above.
        with urllib.request.urlopen(FIXTURE_URL, timeout=30) as response:  # nosec B310
            encoded = response.read(FIXTURE_UU_BYTES + 1)
        if len(encoded) > FIXTURE_UU_BYTES:
            raise ValueError("downloaded fixture exceeds the frozen byte count")
        temporary = fixture_path.with_suffix(fixture_path.suffix + ".tmp")
        temporary.write_bytes(encoded)
        temporary.replace(fixture_path)
        downloaded = True
    if len(encoded) != FIXTURE_UU_BYTES or _digest_bytes(encoded) != FIXTURE_UU_SHA256:
        raise ValueError("upstream uuencoded fixture differs from the frozen bytes")
    return fixture_path, encoded, downloaded


def _run(
    command: tuple[str, ...], *, cwd: Path, timeout: int = 30
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        cwd=cwd,
        check=False,
        capture_output=True,
        text=True,
        timeout=timeout,
    )


def _command_record(completed: subprocess.CompletedProcess[str]) -> dict[str, Any]:
    stdout = completed.stdout.encode("utf-8")
    stderr = completed.stderr.encode("utf-8")
    return {
        "exit_code": completed.returncode,
        "stdout_bytes": len(stdout),
        "stdout_sha256": _digest_bytes(stdout),
        "stderr_bytes": len(stderr),
        "stderr_sha256": _digest_bytes(stderr),
    }


def inspect_fixture_tree(root: Path) -> list[dict[str, Any]]:
    """Validate the exact extracted topology without following symbolic links."""

    observed_paths = {path.relative_to(root).as_posix(): path for path in root.rglob("*")}
    if set(observed_paths) != set(EXPECTED_ENTRY_TYPES):
        raise ValueError("extracted fixture entry set differs from the frozen topology")

    root_resolved = root.resolve(strict=True)
    records: list[dict[str, Any]] = []
    for relative, expected_type in sorted(EXPECTED_ENTRY_TYPES.items()):
        path = observed_paths[relative]
        mode = path.lstat().st_mode
        record: dict[str, Any] = {"path": relative, "type": expected_type}
        if stat.S_ISLNK(mode):
            actual_type = "symlink"
            target = os.readlink(path)
            resolved_target = (path.parent / target).resolve(strict=True)
            if not resolved_target.is_relative_to(root_resolved):
                raise ValueError("fixture symbolic link escapes the extraction root")
            record["target"] = target
        elif stat.S_ISDIR(mode):
            actual_type = "directory"
        elif stat.S_ISREG(mode):
            actual_type = "file"
            content = path.read_bytes()
            record["bytes"] = len(content)
            record["sha256"] = _digest_bytes(content)
        else:
            actual_type = "other"
        if actual_type != expected_type:
            raise ValueError(f"unexpected extracted type for {relative}")
        records.append(record)

    file_records = [record for record in records if record["type"] == "file"]
    if len(file_records) != 2 or any(
        record["bytes"] != len(EXPECTED_FILE_CONTENT) or record["sha256"] != EXPECTED_FILE_SHA256
        for record in file_records
    ):
        raise ValueError("fixture regular-file payload differs from the frozen bytes")
    symlink_record = next(record for record in records if record["type"] == "symlink")
    if symlink_record["target"] != "test.txt":
        raise ValueError("fixture symbolic-link target differs from the frozen target")
    return records


def validate_toolchain(
    *,
    cache_directory: Path,
    unrar_binary: Path,
    output: Path,
) -> dict[str, Any]:
    """Run the hash-pinned, non-Paderborn extraction validation."""

    root = project_root().resolve()
    cache_directory = cache_directory.resolve()
    unrar_binary = unrar_binary.resolve(strict=True)
    output = output.resolve()
    if not unrar_binary.is_file():
        raise ValueError("unrar path is not a regular file")
    if unrar_binary.stat().st_size != UNRAR_BYTES or _digest(unrar_binary) != UNRAR_SHA256:
        raise ValueError("unrar binary differs from the frozen bytes")

    version = _run((str(unrar_binary),), cwd=root, timeout=10)
    if UNRAR_VERSION_TOKEN not in f"{version.stdout}\n{version.stderr}":
        raise ValueError("unrar binary did not report the frozen version")

    fixture_path, encoded, downloaded = _download_or_validate_fixture(cache_directory)
    archive = decode_uu_fixture(encoded)
    with tempfile.TemporaryDirectory(prefix="smartvalve-rar-fixture-") as temporary_name:
        temporary = Path(temporary_name)
        archive_path = temporary / FIXTURE_ARCHIVE_FILENAME
        extraction_root = temporary / "extracted"
        extraction_root.mkdir()
        archive_path.write_bytes(archive)

        crc_test = _run(
            (str(unrar_binary), "t", "-idq", "-p-", str(archive_path)),
            cwd=temporary,
        )
        if crc_test.returncode != 0:
            raise RuntimeError("unrar CRC test failed on the frozen fixture")
        extraction = _run(
            (
                str(unrar_binary),
                "x",
                "-idq",
                "-o-",
                "-p-",
                str(archive_path),
                f"{extraction_root}{os.sep}",
            ),
            cwd=temporary,
        )
        if extraction.returncode != 0:
            raise RuntimeError("unrar extraction failed on the frozen fixture")
        entries = inspect_fixture_tree(extraction_root)

    result: dict[str, Any] = {
        "schema_version": "smartvalve-rar-toolchain-validation-0.1.0",
        "generated_at": datetime.now(UTC).isoformat(),
        "status": "passed_on_hash_pinned_non_paderborn_fixture",
        "upstream_fixture": {
            "repository": UPSTREAM_REPOSITORY,
            "commit": UPSTREAM_COMMIT,
            "path": UPSTREAM_PATH,
            "raw_url": FIXTURE_URL,
            "cache_path": fixture_path.relative_to(root).as_posix(),
            "downloaded_this_run": downloaded,
            "uuencoded_bytes": len(encoded),
            "uuencoded_sha256": _digest_bytes(encoded),
            "decoded_bytes": len(archive),
            "decoded_sha256": _digest_bytes(archive),
        },
        "unrar": {
            "path": unrar_binary.relative_to(root).as_posix(),
            "bytes": unrar_binary.stat().st_size,
            "sha256": _digest(unrar_binary),
            "version_token": UNRAR_VERSION_TOKEN,
            "version_probe": _command_record(version),
        },
        "fixture_validation": {
            "crc_test": _command_record(crc_test),
            "extraction": _command_record(extraction),
            "entries": entries,
        },
        "access_attestation": {
            "archive_path_class": "libarchive_upstream_test_fixture_only",
            "paderborn_archive_path_supplied": False,
            "paderborn_archive_members_listed": False,
            "paderborn_archive_members_extracted": False,
            "paderborn_mat_opened": False,
        },
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary_output = output.with_suffix(output.suffix + ".tmp")
    temporary_output.write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    temporary_output.replace(output)
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cache-directory", type=Path, required=True)
    parser.add_argument("--unrar-binary", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = validate_toolchain(
        cache_directory=args.cache_directory,
        unrar_binary=args.unrar_binary,
        output=args.output,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
