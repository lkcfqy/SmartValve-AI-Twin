#!/usr/bin/env python3
"""Fail unless every allow-listed public fixture matches its byte and SHA-256 lock."""

from __future__ import annotations

import json

from smartvalve.data.external import ARTIFACTS, artifact_status


def main() -> None:
    records = artifact_status()
    result = {
        "status": "passed_external_artifact_status_validation",
        "expected_artifact_count": len(ARTIFACTS),
        "observed_artifact_count": len(records),
        "records": records,
    }
    if len(records) != len(ARTIFACTS) or not all(
        record["integrity_verified"] is True for record in records
    ):
        result["status"] = "failed_external_artifact_status_validation"
        raise RuntimeError(json.dumps(result, ensure_ascii=False, sort_keys=True))
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
