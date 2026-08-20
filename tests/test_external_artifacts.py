from __future__ import annotations

import io
import json
from hashlib import sha256
from urllib.error import URLError

import pytest

from smartvalve.data import external


def _artifact(payload: bytes) -> external.ExternalArtifact:
    return external.ExternalArtifact(
        source_id="fixture",
        filename="fixture.bin",
        url="https://raw.githubusercontent.com/example/project/main/fixture.bin",
        license_name="test-only",
        citation_url="https://example.test/citation",
        description="integrity test fixture",
        bytes=len(payload),
        sha256=sha256(payload).hexdigest(),
    )


def test_sync_verifies_payload_before_atomic_replacement(tmp_path, monkeypatch) -> None:
    payload = b"locked research payload"
    artifact = _artifact(payload)
    target = tmp_path / artifact.filename
    target.write_bytes(b"corrupt cache")
    monkeypatch.setattr(external, "ARTIFACTS", (artifact,))
    monkeypatch.setattr(external, "cache_directory", lambda: tmp_path)
    monkeypatch.setattr(external, "urlopen", lambda request, timeout: io.BytesIO(payload))

    records = external.sync_artifacts()

    assert target.read_bytes() == payload
    assert records == [external.asdict(artifact)]
    assert json.loads((tmp_path / "manifest.json").read_text()) == records
    assert external.artifact_status()[0]["integrity_verified"] is True


def test_sync_rejects_bad_payload_without_replacing_target(tmp_path, monkeypatch) -> None:
    artifact = _artifact(b"expected payload")
    target = tmp_path / artifact.filename
    original = b"existing corrupt cache retained for diagnosis"
    target.write_bytes(original)
    monkeypatch.setattr(external, "ARTIFACTS", (artifact,))
    monkeypatch.setattr(external, "cache_directory", lambda: tmp_path)
    monkeypatch.setattr(external, "urlopen", lambda request, timeout: io.BytesIO(b"bad"))

    with pytest.raises(ValueError, match="integrity check failed"):
        external.sync_artifacts(attempts=1, backoff_s=0)

    assert target.read_bytes() == original
    assert target.with_suffix(".bin.part").read_bytes() == b"bad"


def test_sync_retries_transient_download_failure(tmp_path, monkeypatch) -> None:
    payload = b"locked payload after a transient TLS failure"
    artifact = _artifact(payload)
    calls = 0
    monkeypatch.setattr(external, "ARTIFACTS", (artifact,))
    monkeypatch.setattr(external, "cache_directory", lambda: tmp_path)

    def flaky_download(request, timeout):
        nonlocal calls
        calls += 1
        if calls == 1:
            raise URLError("transient TLS EOF")
        return io.BytesIO(payload)

    monkeypatch.setattr(external, "urlopen", flaky_download)

    records = external.sync_artifacts(attempts=2, backoff_s=0)

    assert calls == 2
    assert records == [external.asdict(artifact)]
    assert (tmp_path / artifact.filename).read_bytes() == payload
    assert not (tmp_path / "fixture.bin.part").exists()


@pytest.mark.parametrize(
    ("keyword", "value", "message"),
    (("timeout_s", 0, "timeout"), ("attempts", 0, "attempts"), ("backoff_s", -1, "backoff")),
)
def test_sync_rejects_invalid_retry_configuration(keyword, value, message) -> None:
    with pytest.raises(ValueError, match=message):
        external.sync_artifacts(**{keyword: value})


def test_sync_does_not_redownload_valid_cache(tmp_path, monkeypatch) -> None:
    payload = b"already valid"
    artifact = _artifact(payload)
    (tmp_path / artifact.filename).write_bytes(payload)
    monkeypatch.setattr(external, "ARTIFACTS", (artifact,))
    monkeypatch.setattr(external, "cache_directory", lambda: tmp_path)

    def unexpected_download(request, timeout):
        raise AssertionError("valid cache must not be downloaded again")

    monkeypatch.setattr(external, "urlopen", unexpected_download)

    assert external.sync_artifacts() == [external.asdict(artifact)]
