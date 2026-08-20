#!/usr/bin/env python3
"""Download only the sealed 45-record HUST D3 primary cohort with hash checks."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any
from urllib.parse import urljoin, urlparse

import pandas as pd
import requests

from smartvalve.data.hust import (
    HUST_INVENTORY_SHA256,
    file_sha256,
    select_hust_primary_inventory,
)

RUN_VERSION = "smartvalve-hust-d3-acquisition-0.1.0"
EXPECTED_SEAL_SHA256 = "eb66d23601ba21fe70b125d503ec56c51fbcfc2f5c59d6d1f2bf4335485428ef"
DOWNLOAD_TEMPLATE = (
    "https://data.mendeley.com/public-files/datasets/cbv7jyx4p9/files/{file_id}/"
    "file_downloaded"
)
ALLOWED_DOWNLOAD_HOSTS = {"data.mendeley.com"}
ALLOWED_STORAGE_HOSTS = {
    "prod-dcd-datasets-public-files-eu-west-1.s3.eu-west-1.amazonaws.com"
}
MAX_DOWNLOAD_REDIRECTS = 1


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _verify(path: Path, expected: str, role: str) -> str:
    if not path.is_file():
        raise FileNotFoundError(path)
    observed = _sha256(path)
    if observed != expected:
        raise ValueError(f"{role} SHA-256 changed: expected {expected}, observed {observed}")
    return observed


def _write_json(path: Path, value: Any) -> None:
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _validated_https_url(url: str, *, allowed_hosts: set[str], role: str) -> str:
    parsed = urlparse(url)
    try:
        port = parsed.port
    except ValueError as error:
        raise ValueError(f"{role} URL is not allow-listed: {url}") from error
    if (
        parsed.scheme != "https"
        or parsed.hostname not in allowed_hosts
        or parsed.username is not None
        or parsed.password is not None
        or port not in {None, 443}
    ):
        raise ValueError(f"{role} URL is not allow-listed: {url}")
    return url


def _validated_download_url(url: str) -> str:
    return _validated_https_url(
        url,
        allowed_hosts=ALLOWED_DOWNLOAD_HOSTS,
        role="HUST download",
    )


def _validated_storage_url(url: str) -> str:
    return _validated_https_url(
        url,
        allowed_hosts=ALLOWED_STORAGE_HOSTS,
        role="HUST storage redirect",
    )


def _open_download_response(url: str) -> requests.Response:
    current_url = _validated_download_url(url)
    headers = {"User-Agent": "SmartValve-HUST-D3-acquisition/0.1"}
    for redirect_count in range(MAX_DOWNLOAD_REDIRECTS + 1):
        response = requests.get(
            current_url,
            headers=headers,
            stream=True,
            timeout=120,
            allow_redirects=False,
        )
        if 300 <= response.status_code < 400:
            location = response.headers.get("Location")
            response.close()
            if location is None:
                raise ValueError("HUST download redirect omitted Location")
            if redirect_count >= MAX_DOWNLOAD_REDIRECTS:
                raise ValueError("HUST download exceeded the sealed redirect budget")
            current_url = _validated_storage_url(urljoin(current_url, location))
            continue
        try:
            response.raise_for_status()
            if not 200 <= response.status_code < 300:
                raise ValueError(
                    f"HUST download returned unexpected status {response.status_code}"
                )
        except Exception:
            response.close()
            raise
        return response
    raise AssertionError("unreachable HUST download redirect state")


def _download(url: str, destination: Path) -> None:
    temporary = destination.with_suffix(destination.suffix + ".partial")
    try:
        with (
            _open_download_response(url) as response,
            temporary.open("wb") as output,
        ):
            for chunk in response.iter_content(chunk_size=1024 * 1024):
                if chunk:
                    output.write(chunk)
        temporary.replace(destination)
    except Exception:
        temporary.unlink(missing_ok=True)
        raise


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--inventory", type=Path, required=True)
    parser.add_argument("--seal", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    return parser


def main() -> int:
    arguments = build_parser().parse_args()
    inputs = {
        "inventory": _verify(
            arguments.inventory,
            HUST_INVENTORY_SHA256,
            "EXP-431 official inventory",
        ),
        "seal": _verify(arguments.seal, EXPECTED_SEAL_SHA256, "HUST D3 factorial seal"),
    }
    arguments.output_dir.mkdir(parents=True, exist_ok=True)
    if any(arguments.output_dir.iterdir()):
        raise ValueError("output directory must be empty")
    mat_directory = arguments.output_dir / "mat"
    mat_directory.mkdir()
    primary = select_hust_primary_inventory(pd.read_csv(arguments.inventory))
    records = []
    for number, row in enumerate(primary.itertuples(index=False), start=1):
        destination = mat_directory / str(row.filename)
        url = DOWNLOAD_TEMPLATE.format(file_id=row.file_id)
        _download(url, destination)
        observed_size = destination.stat().st_size
        observed_hash = file_sha256(destination)
        if observed_size != int(row.bytes) or observed_hash != str(row.sha256):
            raise ValueError(f"official payload integrity failed for {row.filename}")
        record = {
            "filename": row.filename,
            "file_id": row.file_id,
            "condition": row.condition,
            "specification_group": row.specification_group,
            "load_w": row.load_w,
            "bearing_code": row.bearing_code,
            "truth": row.truth,
            "download_url": url,
            "bytes": observed_size,
            "sha256": observed_hash,
        }
        records.append(record)
        print(
            json.dumps(
                {"event": "hust_primary_downloaded", "completed": number, **record},
                sort_keys=True,
            ),
            flush=True,
        )
    manifest = pd.DataFrame(records)
    if len(manifest) != 45 or manifest["filename"].nunique() != 45:
        raise ValueError("HUST acquisition did not preserve all 45 primary files")
    manifest.to_csv(
        arguments.output_dir / "acquisition_manifest.csv",
        index=False,
        lineterminator="\n",
    )
    summary = {
        "run_version": RUN_VERSION,
        "status": "complete_primary_payloads_verified_not_opened",
        "inputs_sha256": inputs,
        "downloaded_mat_files": len(manifest),
        "downloaded_bytes": int(manifest["bytes"].sum()),
        "mat_files_opened": 0,
        "signal_bytes_read": 0,
        "manifest_sha256": _sha256(arguments.output_dir / "acquisition_manifest.csv"),
    }
    _write_json(arguments.output_dir / "acquisition_summary.json", summary)
    print(json.dumps(summary, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
