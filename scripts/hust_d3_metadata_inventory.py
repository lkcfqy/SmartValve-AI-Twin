#!/usr/bin/env python3
"""Inventory HUST Bearing v3 metadata without downloading signal contents."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from collections.abc import Sequence
from itertools import combinations
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import pandas as pd
import requests

SCHEMA_VERSION = "smartvalve-hust-d3-metadata-inventory-0.1.0"
DATASET_ID = "cbv7jyx4p9"
VERSION = 3
DOI = "10.17632/cbv7jyx4p9.3"
DATASET_PAGE = f"https://data.mendeley.com/datasets/{DATASET_ID}/{VERSION}"
PUBLIC_API = "https://data.mendeley.com/public-api"
API_ACCEPT = "application/vnd.mendeley-public-dataset.1+json"
ALLOWED_API_HOSTS = {"data.mendeley.com"}
FOLDER_NAME = "HUST bearing dataset"
LICENSE = "CC BY 4.0"
CONDITIONS = ("N", "I", "O", "B", "IO", "IB", "OB")
PRIMARY_CONDITIONS = ("N", "I", "O")
BEARING_TYPES = (4, 5, 6, 7, 8)
LOADS_W = (0, 200, 400)
EXPECTED_TYPES = {
    "N": BEARING_TYPES,
    "I": BEARING_TYPES,
    "O": BEARING_TYPES,
    "B": (5, 6, 7, 8),
    "IO": BEARING_TYPES,
    "IB": (5, 6, 7, 8),
    "OB": BEARING_TYPES,
}
FILENAME_PATTERN = re.compile(
    r"^(?P<condition>IO|IB|OB|N|I|O|B)(?P<bearing_type>[4-8])0(?P<load>[024])\.mat$"
)


def _validated_api_url(url: str) -> str:
    parsed = urlparse(url)
    try:
        port = parsed.port
    except ValueError as error:
        raise ValueError(f"HUST metadata URL is not allow-listed: {url}") from error
    if (
        parsed.scheme != "https"
        or parsed.hostname not in ALLOWED_API_HOSTS
        or parsed.username is not None
        or parsed.password is not None
        or port not in {None, 443}
    ):
        raise ValueError(f"HUST metadata URL is not allow-listed: {url}")
    return url


def _fetch_json(url: str) -> Any:
    with requests.get(
        _validated_api_url(url),
        headers={"Accept": API_ACCEPT, "User-Agent": "SmartValve-D3-metadata-audit/0.1"},
        timeout=60,
        allow_redirects=False,
    ) as response:
        if 300 <= response.status_code < 400:
            raise ValueError("HUST metadata API redirect is not allowed")
        response.raise_for_status()
        if not 200 <= response.status_code < 300:
            raise ValueError(
                f"HUST metadata API returned unexpected status {response.status_code}"
            )
        return response.json()


def _canonical_sha256(value: Any) -> str:
    payload = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _string_list_sha256(values: Sequence[str]) -> str:
    payload = "\n".join(sorted(values)).encode("utf-8") + b"\n"
    return hashlib.sha256(payload).hexdigest()


def _parse_file(record: dict[str, Any], *, folder_id: str) -> dict[str, Any]:
    filename = str(record.get("filename", ""))
    match = FILENAME_PATTERN.fullmatch(filename)
    if match is None:
        raise ValueError(f"unexpected HUST MAT filename: {filename}")
    details = record.get("content_details", {})
    size = int(details.get("size", -1))
    sha256 = str(details.get("sha256_hash", ""))
    if size <= 0 or not re.fullmatch(r"[0-9a-f]{64}", sha256):
        raise ValueError(f"invalid official size/hash metadata for {filename}")
    return {
        "filename": filename,
        "file_id": str(record.get("id", "")),
        "folder_id": folder_id,
        "condition": match.group("condition"),
        "bearing_type": int(match.group("bearing_type")),
        "load_w": {"0": 0, "2": 200, "4": 400}[match.group("load")],
        "bytes": size,
        "sha256": sha256,
    }


def _validate_inventory(inventory: pd.DataFrame) -> None:
    if len(inventory) != 99 or inventory["filename"].nunique() != 99:
        raise ValueError("HUST v3 must expose exactly 99 unique MAT files")
    expected = {
        (condition, bearing_type, load)
        for condition, types in EXPECTED_TYPES.items()
        for bearing_type in types
        for load in LOADS_W
    }
    actual = set(
        inventory.loc[:, ["condition", "bearing_type", "load_w"]].itertuples(
            index=False,
            name=None,
        )
    )
    if actual != expected:
        raise ValueError("HUST v3 filename factorial differs from the frozen metadata contract")


def _pair_counts(source: pd.DataFrame) -> tuple[int, int]:
    nuisance = 0
    for _, group in source.groupby(
        ["condition", "bearing_type"], sort=True, observed=True
    ):
        nuisance += len(tuple(combinations(group.index, 2)))
    fault = 0
    for _, group in source.groupby(
        ["bearing_type", "load_w"], sort=True, observed=True
    ):
        fault += len(tuple(combinations(group.index, 2)))
    return nuisance, fault


def _candidate_splits(inventory: pd.DataFrame) -> pd.DataFrame:
    primary = inventory.loc[
        inventory["condition"].isin(PRIMARY_CONDITIONS)
    ].reset_index(drop=True)
    if len(primary) != 45:
        raise ValueError("the N/I/O primary cohort must contain 45 recordings")
    records = []
    for held_type in BEARING_TYPES:
        for held_load in LOADS_W:
            type_mask = primary["bearing_type"].to_numpy(dtype=int) == held_type
            load_mask = primary["load_w"].to_numpy(dtype=int) == held_load
            source = primary.loc[~type_mask & ~load_mask]
            target = primary.loc[type_mask & load_mask]
            quarantine = primary.loc[type_mask ^ load_mask]
            if (len(source), len(target), len(quarantine)) != (24, 3, 18):
                raise ValueError("candidate D3 split counts changed")
            if set(target["condition"]) != set(PRIMARY_CONDITIONS):
                raise ValueError("candidate D3 target loses a primary class")
            nuisance_pairs, fault_pairs = _pair_counts(source)
            if (nuisance_pairs, fault_pairs) != (12, 24):
                raise ValueError("candidate D3 source pair topology changed")
            records.append(
                {
                    "fold_id": f"bearing_type={held_type}|load_w={held_load}",
                    "held_bearing_type": held_type,
                    "held_load_w": held_load,
                    "source_recordings": len(source),
                    "target_recordings": len(target),
                    "quarantine_recordings": len(quarantine),
                    "source_nuisance_pairs": nuisance_pairs,
                    "source_fault_pairs": fault_pairs,
                    "source_filenames_sha256": _string_list_sha256(
                        source["filename"].astype(str).tolist()
                    ),
                    "target_filenames_sha256": _string_list_sha256(
                        target["filename"].astype(str).tolist()
                    ),
                    "quarantine_filenames_sha256": _string_list_sha256(
                        quarantine["filename"].astype(str).tolist()
                    ),
                }
            )
    return pd.DataFrame(records)


def _write_json(path: Path, value: Any) -> None:
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, required=True)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    arguments = build_parser().parse_args(argv)
    arguments.output_dir.mkdir(parents=True, exist_ok=True)
    if any(arguments.output_dir.iterdir()):
        raise ValueError("output directory must be empty")

    folders_url = f"{PUBLIC_API}/datasets/{DATASET_ID}/folders/{VERSION}"
    root_files_url = (
        f"{PUBLIC_API}/datasets/{DATASET_ID}/files?version={VERSION}&folder_id=root"
    )
    folders = _fetch_json(folders_url)
    root_files = _fetch_json(root_files_url)
    if not isinstance(folders, list) or len(folders) != 1:
        raise ValueError("HUST v3 must expose exactly one signal folder")
    folder = folders[0]
    folder_id = str(folder.get("id", ""))
    if folder.get("name") != FOLDER_NAME or not folder_id:
        raise ValueError("HUST v3 signal folder identity changed")
    signal_files_url = (
        f"{PUBLIC_API}/datasets/{DATASET_ID}/files?version={VERSION}"
        f"&folder_id={folder_id}"
    )
    signal_files = _fetch_json(signal_files_url)
    if not isinstance(signal_files, list):
        raise ValueError("HUST v3 signal-file response is not a list")
    inventory = pd.DataFrame(
        _parse_file(record, folder_id=folder_id) for record in signal_files
    ).sort_values("filename", kind="stable")
    inventory = inventory.reset_index(drop=True)
    _validate_inventory(inventory)
    splits = _candidate_splits(inventory)

    root_names = sorted(str(record.get("filename", "")) for record in root_files)
    if root_names != ["defects.png", "testbench.png"]:
        raise ValueError("HUST v3 root documentation files changed")
    inventory_records = inventory.to_dict(orient="records")
    metadata = {
        "schema_version": SCHEMA_VERSION,
        "status": "metadata_only_candidate_not_sealed",
        "dataset_id": DATASET_ID,
        "version": VERSION,
        "doi": DOI,
        "dataset_page": DATASET_PAGE,
        "license": LICENSE,
        "api_urls": {
            "folders": folders_url,
            "root_files": root_files_url,
            "signal_files": signal_files_url,
        },
        "signal_content_access": {
            "mat_files_downloaded": 0,
            "mat_files_opened": 0,
            "signal_bytes_read": 0,
        },
        "official_inventory": {
            "mat_file_count": len(inventory),
            "mat_total_bytes": int(inventory["bytes"].sum()),
            "canonical_inventory_sha256": _canonical_sha256(inventory_records),
            "root_documentation_files": root_names,
        },
        "candidate_primary_protocol": {
            "labels": list(PRIMARY_CONDITIONS),
            "bearing_types": list(BEARING_TYPES),
            "loads_w": list(LOADS_W),
            "recording_count": 45,
            "outer_fold_count": len(splits),
            "split_rule": (
                "source=(not held bearing type) AND (not held load); "
                "target=(held bearing type) AND (held load); "
                "quarantine=exclusive OR cross-arms"
            ),
            "window_policy": (
                "not yet frozen; any windows must remain nested within recordings, "
                "and inference must use recording/bearing groups"
            ),
        },
        "candidate_open_set_protocol": {
            "reserved_conditions": ["B", "IO", "IB", "OB"],
            "recording_count": int(
                inventory["condition"].isin(["B", "IO", "IB", "OB"]).sum()
            ),
            "status": "stress_set_only_not_closed_set_labels",
        },
        "authorization": (
            "This inventory does not authorize signal download or evaluation. "
            "A method, feature, split, inference, and execution seal is required first."
        ),
    }
    inventory.to_csv(
        arguments.output_dir / "official_file_inventory.csv",
        index=False,
        lineterminator="\n",
    )
    splits.to_csv(
        arguments.output_dir / "candidate_split_topology.csv",
        index=False,
        lineterminator="\n",
    )
    _write_json(arguments.output_dir / "metadata_inventory.json", metadata)
    print(json.dumps(metadata, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
