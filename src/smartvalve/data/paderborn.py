"""Outcome-blind acquisition and integrity locking for Paderborn bearing archives."""

from __future__ import annotations

import argparse
import json
import os
from dataclasses import dataclass
from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path
from typing import Any
from urllib.request import Request, urlopen

from smartvalve.data.external import cache_directory

ACQUISITION_VERSION = "paderborn-acquisition-0.1.0"
BASE_URL = "https://groups.uni-paderborn.de/kat/BearingDataCenter"
LANDING_PAGE = "https://mb.uni-paderborn.de/en/kat/research/bearing-datacenter"
LICENSE_NAME = "CC BY-NC 4.0"
ARCHIVE_NAMES = (
    "K001.rar",
    "K002.rar",
    "K003.rar",
    "K004.rar",
    "K005.rar",
    "K006.rar",
    "KA01.rar",
    "KA03.rar",
    "KA04.rar",
    "KA05.rar",
    "KA06.rar",
    "KA07.rar",
    "KA08.rar",
    "KA09.rar",
    "KA15.rar",
    "KA16.rar",
    "KA22.rar",
    "KA30.rar",
    "KB23.rar",
    "KB24.rar",
    "KB27.rar",
    "KI01.rar",
    "KI03.rar",
    "KI04.rar",
    "KI05.rar",
    "KI07.rar",
    "KI08.rar",
    "KI14.rar",
    "KI16.rar",
    "KI17.rar",
    "KI18.rar",
    "KI21.rar",
)


@dataclass(frozen=True)
class OperatingSetting:
    code: str
    speed_rpm: int
    torque_nm: float
    radial_force_n: int


@dataclass(frozen=True)
class BearingMetadata:
    code: str
    primary_label: str
    damage_origin: str
    component: str
    damage_extent: int | None


OPERATING_SETTINGS = (
    OperatingSetting("N15_M07_F10", 1500, 0.7, 1000),
    OperatingSetting("N09_M07_F10", 900, 0.7, 1000),
    OperatingSetting("N15_M01_F10", 1500, 0.1, 1000),
    OperatingSetting("N15_M07_F04", 1500, 0.7, 400),
)

# Outcome-blind labels transcribed from Tables 4-5 of Lessmeier et al. (2016).
# Compound KB bearings are deliberately not forced into the three-class primary task.
BEARING_METADATA = (
    BearingMetadata("K001", "healthy", "healthy", "none", None),
    BearingMetadata("K002", "healthy", "healthy", "none", None),
    BearingMetadata("K003", "healthy", "healthy", "none", None),
    BearingMetadata("K004", "healthy", "healthy", "none", None),
    BearingMetadata("K005", "healthy", "healthy", "none", None),
    BearingMetadata("K006", "healthy", "healthy", "none", None),
    BearingMetadata("KA01", "outer", "artificial", "outer", 1),
    BearingMetadata("KA03", "outer", "artificial", "outer", 2),
    BearingMetadata("KA04", "outer", "real", "outer", 1),
    BearingMetadata("KA05", "outer", "artificial", "outer", 1),
    BearingMetadata("KA06", "outer", "artificial", "outer", 2),
    BearingMetadata("KA07", "outer", "artificial", "outer", 1),
    BearingMetadata("KA08", "outer", "artificial", "outer", 2),
    BearingMetadata("KA09", "outer", "artificial", "outer", 2),
    BearingMetadata("KA15", "outer", "real", "outer", 1),
    BearingMetadata("KA16", "outer", "real", "outer", 2),
    BearingMetadata("KA22", "outer", "real", "outer", 1),
    BearingMetadata("KA30", "outer", "real", "outer", 1),
    BearingMetadata("KB23", "compound", "real", "inner+outer", 2),
    BearingMetadata("KB24", "compound", "real", "inner+outer", 3),
    BearingMetadata("KB27", "compound", "real", "outer+inner", 1),
    BearingMetadata("KI01", "inner", "artificial", "inner", 1),
    BearingMetadata("KI03", "inner", "artificial", "inner", 1),
    BearingMetadata("KI04", "inner", "real", "inner", 1),
    BearingMetadata("KI05", "inner", "artificial", "inner", 1),
    BearingMetadata("KI07", "inner", "artificial", "inner", 2),
    BearingMetadata("KI08", "inner", "artificial", "inner", 2),
    BearingMetadata("KI14", "inner", "real", "inner", 1),
    BearingMetadata("KI16", "inner", "real", "inner", 3),
    BearingMetadata("KI17", "inner", "real", "inner", 1),
    BearingMetadata("KI18", "inner", "real", "inner", 2),
    BearingMetadata("KI21", "inner", "real", "inner", 1),
)

PRIMARY_BEARING_CODES = tuple(
    bearing.code
    for bearing in BEARING_METADATA
    if bearing.primary_label != "compound"
)
COMPOUND_BEARING_CODES = tuple(
    bearing.code
    for bearing in BEARING_METADATA
    if bearing.primary_label == "compound"
)


def paderborn_cache_directory() -> Path:
    return cache_directory() / "paderborn"


def _digest(path: Path) -> str:
    hasher = sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(4 * 1024 * 1024), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def _url(name: str) -> str:
    if name not in ARCHIVE_NAMES:
        raise ValueError(f"archive is outside the frozen Paderborn list: {name}")
    return f"{BASE_URL}/{name}"


def _head_metadata(name: str, timeout_s: int) -> dict[str, Any]:
    request = Request(
        _url(name),
        method="HEAD",
        headers={"User-Agent": "SmartValve-AI-Twin/0.6"},
    )
    # The scheme, official host and filename are fixed by _url and ARCHIVE_NAMES.
    with urlopen(request, timeout=timeout_s) as response:  # nosec B310
        length = response.headers.get("Content-Length")
        if length is None or int(length) <= 0:
            raise ValueError(f"official server omitted a valid Content-Length for {name}")
        return {
            "bytes": int(length),
            "etag": response.headers.get("ETag"),
            "last_modified": response.headers.get("Last-Modified"),
            "content_type": response.headers.get("Content-Type"),
        }


def _content_range_total(value: str | None) -> int | None:
    if value is None or "/" not in value:
        return None
    total = value.rsplit("/", maxsplit=1)[1]
    return int(total) if total.isdigit() else None


def _download(name: str, target: Path, expected_bytes: int, timeout_s: int) -> None:
    temporary = target.with_suffix(target.suffix + ".part")
    start = temporary.stat().st_size if temporary.is_file() else 0
    if start > expected_bytes:
        raise ValueError(f"partial file is larger than the official archive: {temporary}")
    if start == expected_bytes:
        os.replace(temporary, target)
        return
    headers = {"User-Agent": "SmartValve-AI-Twin/0.6"}
    if start:
        headers["Range"] = f"bytes={start}-"
    request = Request(_url(name), headers=headers)
    # The scheme, official host and filename are fixed by _url and ARCHIVE_NAMES.
    with urlopen(request, timeout=timeout_s) as response:  # nosec B310
        status = getattr(response, "status", response.getcode())
        if start and status == 206:
            total = _content_range_total(response.headers.get("Content-Range"))
            if total != expected_bytes:
                raise ValueError(f"range response changed total size for {name}: {total}")
            mode = "ab"
        elif status == 200:
            response_bytes = response.headers.get("Content-Length")
            if response_bytes is None or int(response_bytes) != expected_bytes:
                raise ValueError(f"download response changed total size for {name}")
            mode = "wb"
        else:
            raise ValueError(f"unexpected HTTP status {status} for {name}")
        with temporary.open(mode) as output:
            while chunk := response.read(4 * 1024 * 1024):
                output.write(chunk)
    if temporary.stat().st_size != expected_bytes:
        raise ValueError(
            f"incomplete archive {name}: {temporary.stat().st_size}/{expected_bytes} bytes"
        )
    os.replace(temporary, target)


def _load_lock(path: Path) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    lock = json.loads(path.read_text(encoding="utf-8"))
    if lock.get("acquisition_version") != ACQUISITION_VERSION:
        raise ValueError("Paderborn lock uses an unexpected acquisition version")
    entries = lock.get("archives")
    if not isinstance(entries, list):
        raise ValueError("Paderborn lock has no archive list")
    names = tuple(entry.get("filename") for entry in entries)
    if names != ARCHIVE_NAMES:
        raise ValueError("Paderborn lock filename order differs from the frozen list")
    return lock


def verify_cached_lock(lock_path: Path | None = None) -> dict[str, Any]:
    cache = paderborn_cache_directory()
    resolved_lock = lock_path or cache / "archive_lock.json"
    lock = _load_lock(resolved_lock)
    if lock is None:
        raise FileNotFoundError(f"missing Paderborn archive lock: {resolved_lock}")
    for entry in lock["archives"]:
        path = cache / entry["filename"]
        if not path.is_file():
            raise FileNotFoundError(f"missing locked Paderborn archive: {path}")
        if path.stat().st_size != entry["bytes"] or _digest(path) != entry["sha256"]:
            raise ValueError(f"Paderborn archive differs from lock: {path.name}")
    return lock


def acquire_archives(
    output_lock: Path,
    *,
    timeout_s: int = 180,
) -> dict[str, Any]:
    """Download but never open all archives and establish or verify the TOFU lock."""

    cache = paderborn_cache_directory()
    cache.mkdir(parents=True, exist_ok=True)
    cache_lock_path = cache / "archive_lock.json"
    existing_lock = _load_lock(cache_lock_path)
    locked_entries = (
        {entry["filename"]: entry for entry in existing_lock["archives"]}
        if existing_lock is not None
        else {}
    )
    entries = []
    for index, name in enumerate(ARCHIVE_NAMES, start=1):
        metadata = _head_metadata(name, timeout_s)
        locked = locked_entries.get(name)
        if locked is not None and metadata["bytes"] != locked["bytes"]:
            raise ValueError(f"official Content-Length changed for locked archive {name}")
        expected_bytes = int(locked["bytes"] if locked is not None else metadata["bytes"])
        target = cache / name
        if target.is_file():
            if target.stat().st_size != expected_bytes:
                raise ValueError(f"existing Paderborn archive has unexpected size: {name}")
            digest = _digest(target)
            if locked is not None and digest != locked["sha256"]:
                raise ValueError(f"existing Paderborn archive fails its lock: {name}")
        else:
            print(f"[{index:02d}/{len(ARCHIVE_NAMES)}] downloading {name}", flush=True)
            _download(name, target, expected_bytes, timeout_s)
            digest = _digest(target)
        entry = {
            "filename": name,
            "url": _url(name),
            "bytes": expected_bytes,
            "sha256": digest,
            "etag": metadata["etag"],
            "last_modified": metadata["last_modified"],
            "content_type": metadata["content_type"],
        }
        if locked is not None and entry["sha256"] != locked["sha256"]:
            raise ValueError(f"new Paderborn archive digest differs from lock: {name}")
        entries.append(entry)
        print(f"[{index:02d}/{len(ARCHIVE_NAMES)}] locked {name} {digest}", flush=True)
    lock = {
        "acquisition_version": ACQUISITION_VERSION,
        "generated_at": datetime.now(UTC).isoformat(),
        "status": "archives byte-locked; archive contents not opened",
        "source": {
            "base_url": BASE_URL,
            "landing_page": LANDING_PAGE,
            "license": LICENSE_NAME,
            "integrity_model": "official HTTPS trust on first use, then SHA-256 lock",
        },
        "archive_count": len(entries),
        "total_bytes": sum(entry["bytes"] for entry in entries),
        "archives": entries,
        "prospective_seal": {
            "archive_contents_opened": False,
            "signal_features_computed": False,
            "model_outcomes_inspected": False,
            "evaluation_protocol_required_before_open": True,
        },
    }
    payload = json.dumps(lock, ensure_ascii=False, indent=2) + "\n"
    temporary_lock = cache_lock_path.with_suffix(".json.part")
    temporary_lock.write_text(payload, encoding="utf-8")
    os.replace(temporary_lock, cache_lock_path)
    output_lock.parent.mkdir(parents=True, exist_ok=True)
    output_lock.write_text(payload, encoding="utf-8")
    return lock


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("acquire", "verify"))
    parser.add_argument("--output-lock", type=Path)
    parser.add_argument("--timeout", type=int, default=180)
    args = parser.parse_args()
    if args.command == "acquire":
        if args.output_lock is None:
            parser.error("--output-lock is required for acquisition")
        result = acquire_archives(args.output_lock, timeout_s=args.timeout)
    else:
        result = verify_cached_lock()
    print(
        json.dumps(
            {
                "status": result["status"],
                "archive_count": result["archive_count"],
                "total_bytes": result["total_bytes"],
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
