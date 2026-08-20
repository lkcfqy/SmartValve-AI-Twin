from __future__ import annotations

import runpy
from collections.abc import Callable
from pathlib import Path
from typing import Any, cast
from unittest.mock import Mock

import pytest
import requests

PROJECT_ROOT = Path(__file__).resolve().parents[1]
ACQUISITION_SCRIPT = runpy.run_path(str(PROJECT_ROOT / "scripts/acquire_hust_d3_primary.py"))
INVENTORY_SCRIPT = runpy.run_path(str(PROJECT_ROOT / "scripts/hust_d3_metadata_inventory.py"))
_validated_download_url = cast(
    Callable[[str], str],
    ACQUISITION_SCRIPT["_validated_download_url"],
)
_validated_storage_url = cast(
    Callable[[str], str],
    ACQUISITION_SCRIPT["_validated_storage_url"],
)
_open_download_response = cast(
    Callable[[str], requests.Response],
    ACQUISITION_SCRIPT["_open_download_response"],
)
_validated_api_url = cast(
    Callable[[str], str],
    INVENTORY_SCRIPT["_validated_api_url"],
)
_fetch_json = cast(
    Callable[[str], Any],
    INVENTORY_SCRIPT["_fetch_json"],
)


def _response(
    status_code: int,
    *,
    url: str,
    location: str | None = None,
) -> requests.Response:
    response = requests.Response()
    response.status_code = status_code
    response.url = url
    response.raw = Mock()
    if location is not None:
        response.headers["Location"] = location
    return response


@pytest.mark.parametrize(
    "url",
    (
        "file:///etc/passwd",
        "http://data.mendeley.com/public-api/datasets/example",
        "https://data.mendeley.com.evil.example/public-api/datasets/example",
        "https://data.mendeley.com@evil.example/public-api/datasets/example",
        "https://user:secret@data.mendeley.com/public-api/datasets/example",
        "https://data.mendeley.com:444/public-api/datasets/example",
    ),
)
def test_hust_remote_helpers_reject_non_allowlisted_urls(url: str) -> None:
    with pytest.raises(ValueError, match="not allow-listed"):
        _validated_download_url(url)
    with pytest.raises(ValueError, match="not allow-listed"):
        _validated_api_url(url)


def test_hust_remote_helpers_accept_mendeley_https_urls() -> None:
    download = (
        "https://data.mendeley.com/public-files/datasets/cbv7jyx4p9/files/example/"
        "file_downloaded"
    )
    api = "https://data.mendeley.com/public-api/datasets/cbv7jyx4p9/folders/3"

    assert _validated_download_url(download) == download
    assert _validated_api_url(api) == api


def test_hust_download_accepts_only_the_observed_exact_storage_host() -> None:
    storage = (
        "https://prod-dcd-datasets-public-files-eu-west-1.s3.eu-west-1.amazonaws.com/"
        "16ddf73b-ee52-45e5-a08c-d678814ec09b"
    )

    assert _validated_storage_url(storage) == storage
    with pytest.raises(ValueError, match="not allow-listed"):
        _validated_storage_url("https://evil.example/object")


def test_hust_download_disables_automatic_redirects_and_validates_the_hop(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    initial = (
        "https://data.mendeley.com/public-files/datasets/cbv7jyx4p9/files/"
        "2fc56e6a-4eb8-49a2-acf4-a869db8f812d/file_downloaded"
    )
    storage = (
        "https://prod-dcd-datasets-public-files-eu-west-1.s3.eu-west-1.amazonaws.com/"
        "16ddf73b-ee52-45e5-a08c-d678814ec09b"
    )
    responses = [
        _response(302, url=initial, location=storage),
        _response(200, url=storage),
    ]
    calls: list[tuple[str, dict[str, Any]]] = []

    def fake_get(url: str, **kwargs: Any) -> requests.Response:
        calls.append((url, kwargs))
        return responses.pop(0)

    monkeypatch.setattr(ACQUISITION_SCRIPT["requests"], "get", fake_get)

    with _open_download_response(initial) as response:
        assert response.status_code == 200

    assert [url for url, _ in calls] == [initial, storage]
    assert all(kwargs["allow_redirects"] is False for _, kwargs in calls)


def test_hust_download_rejects_an_unallowlisted_redirect_before_following_it(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    initial = (
        "https://data.mendeley.com/public-files/datasets/cbv7jyx4p9/files/"
        "2fc56e6a-4eb8-49a2-acf4-a869db8f812d/file_downloaded"
    )
    calls: list[str] = []

    def fake_get(url: str, **_: Any) -> requests.Response:
        calls.append(url)
        return _response(302, url=url, location="https://evil.example/object")

    monkeypatch.setattr(ACQUISITION_SCRIPT["requests"], "get", fake_get)

    with pytest.raises(ValueError, match="not allow-listed"):
        _open_download_response(initial)
    assert calls == [initial]


def test_hust_metadata_disables_and_rejects_redirects(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    api = "https://data.mendeley.com/public-api/datasets/cbv7jyx4p9"
    calls: list[dict[str, Any]] = []

    def fake_get(url: str, **kwargs: Any) -> requests.Response:
        assert url == api
        calls.append(kwargs)
        return _response(302, url=url, location="https://evil.example/api")

    monkeypatch.setattr(INVENTORY_SCRIPT["requests"], "get", fake_get)

    with pytest.raises(ValueError, match="redirect is not allowed"):
        _fetch_json(api)
    assert calls[0]["allow_redirects"] is False
