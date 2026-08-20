from __future__ import annotations

import binascii
import os
from pathlib import Path

import pytest

from smartvalve.experiments.rar_toolchain_validation import (
    EXPECTED_FILE_CONTENT,
    EXPECTED_FILE_SHA256,
    FIXTURE_ARCHIVE_BYTES,
    FIXTURE_ARCHIVE_FILENAME,
    FIXTURE_ARCHIVE_SHA256,
    _download_or_validate_fixture,
    decode_uu_fixture,
    inspect_fixture_tree,
)


def _encoded_fixture(payload: bytes) -> bytes:
    body = b"".join(
        binascii.b2a_uu(payload[offset : offset + 45]) for offset in range(0, len(payload), 45)
    )
    return f"begin 644 {FIXTURE_ARCHIVE_FILENAME}\n".encode() + body + b"`\nend\n"


def _make_expected_tree(root: Path) -> None:
    (root / "testdir").mkdir()
    (root / "testemptydir").mkdir()
    (root / "test.txt").write_bytes(EXPECTED_FILE_CONTENT)
    (root / "testdir" / "test.txt").write_bytes(EXPECTED_FILE_CONTENT)
    os.symlink("test.txt", root / "testlink")


def test_decode_uu_fixture_validates_frozen_decoded_bytes(monkeypatch: pytest.MonkeyPatch) -> None:
    payload = b"R" * FIXTURE_ARCHIVE_BYTES
    encoded = _encoded_fixture(payload)
    monkeypatch.setattr(
        "smartvalve.experiments.rar_toolchain_validation.FIXTURE_ARCHIVE_SHA256",
        __import__("hashlib").sha256(payload).hexdigest(),
    )

    assert decode_uu_fixture(encoded) == payload


def test_decode_uu_fixture_rejects_changed_envelope() -> None:
    with pytest.raises(ValueError, match="envelope"):
        decode_uu_fixture(b"begin 600 changed.rar\n`\nend\n")


def test_inspect_fixture_tree_validates_topology_payload_and_link(tmp_path: Path) -> None:
    _make_expected_tree(tmp_path)

    records = inspect_fixture_tree(tmp_path)

    assert [record["path"] for record in records] == [
        "test.txt",
        "testdir",
        "testdir/test.txt",
        "testemptydir",
        "testlink",
    ]
    assert [record["sha256"] for record in records if record["type"] == "file"] == [
        EXPECTED_FILE_SHA256,
        EXPECTED_FILE_SHA256,
    ]


def test_inspect_fixture_tree_rejects_unexpected_entry(tmp_path: Path) -> None:
    _make_expected_tree(tmp_path)
    (tmp_path / "unexpected.txt").write_text("unexpected", encoding="utf-8")

    with pytest.raises(ValueError, match="entry set"):
        inspect_fixture_tree(tmp_path)


def test_frozen_archive_hash_constant_has_sha256_shape() -> None:
    assert len(FIXTURE_ARCHIVE_SHA256) == 64


def test_fixture_download_rejects_non_https_origin(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        "smartvalve.experiments.rar_toolchain_validation.FIXTURE_URL",
        "file:///etc/passwd",
    )

    with pytest.raises(ValueError, match="frozen HTTPS origin"):
        _download_or_validate_fixture(tmp_path)
