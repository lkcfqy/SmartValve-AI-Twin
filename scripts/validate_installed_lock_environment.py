#!/usr/bin/env python3
"""Require installed distributions to equal the union of one or more hash locks."""

from __future__ import annotations

import argparse
import json
import re
from importlib.metadata import distributions
from pathlib import Path

from packaging.utils import canonicalize_name

PIN_PATTERN = re.compile(r"^([A-Za-z0-9][A-Za-z0-9_.-]*)==([^\\\s]+)")


def locked_versions(paths: list[Path]) -> dict[str, str]:
    expected: dict[str, str] = {}
    for path in paths:
        for line in path.read_text(encoding="utf-8").splitlines():
            match = PIN_PATTERN.match(line)
            if match is None:
                continue
            name = canonicalize_name(match.group(1))
            version = match.group(2)
            previous = expected.setdefault(name, version)
            if previous != version:
                raise ValueError(
                    f"conflicting locked versions for {name}: {previous} versus {version}"
                )
    if not expected:
        raise ValueError("no exact package pins were found in the supplied locks")
    return expected


def installed_versions() -> dict[str, str]:
    result: dict[str, str] = {}
    for distribution in distributions():
        raw_name = distribution.metadata.get("Name")
        if not raw_name:
            continue
        name = canonicalize_name(raw_name)
        version = distribution.version
        previous = result.setdefault(name, version)
        if previous != version:
            raise ValueError(
                f"multiple installed versions for {name}: {previous} versus {version}"
            )
    return result


def validate_environment(
    *, lock_paths: list[Path], allowed_packages: set[str]
) -> dict[str, object]:
    expected = locked_versions(lock_paths)
    observed = installed_versions()
    allowed = {canonicalize_name(name) for name in allowed_packages}
    missing = sorted(set(expected) - set(observed))
    unexpected = sorted(set(observed) - set(expected) - allowed)
    mismatched = {
        name: {"expected": expected[name], "observed": observed[name]}
        for name in sorted(set(expected) & set(observed))
        if expected[name] != observed[name]
    }
    result: dict[str, object] = {
        "status": "passed_installed_lock_environment_validation",
        "lock_paths": [path.as_posix() for path in lock_paths],
        "locked_package_count": len(expected),
        "installed_package_count": len(observed),
        "allowed_unlocked_packages": sorted(allowed),
        "missing_packages": missing,
        "unexpected_packages": unexpected,
        "version_mismatches": mismatched,
    }
    if missing or unexpected or mismatched:
        result["status"] = "failed_installed_lock_environment_validation"
        raise RuntimeError(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--lock", action="append", required=True, type=Path)
    parser.add_argument("--allow-package", action="append", default=[])
    args = parser.parse_args()
    result = validate_environment(
        lock_paths=[path.resolve(strict=True) for path in args.lock],
        allowed_packages=set(args.allow_package),
    )
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
