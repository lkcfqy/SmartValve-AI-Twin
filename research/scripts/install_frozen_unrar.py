"""Install a hash-pinned local unrar binary without system privileges or archive access."""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import tempfile
from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path

from smartvalve.config import project_root

PACKAGE_NAME = "unrar"
PACKAGE_VERSION = "1:7.0.7-1build1"
DEB_FILENAME = "unrar_1%3a7.0.7-1build1_amd64.deb"
DEB_BYTES = 177_964
DEB_SHA256 = "3d05dd213babf0b8b9082a9a7d8663d35d85449b95b8593a4acb52598759e9a6"
EXPECTED_VERSION_TOKEN = "UNRAR 7.00"


def _digest(path: Path) -> str:
    hasher = sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def _validate_deb(path: Path) -> None:
    if path.stat().st_size != DEB_BYTES or _digest(path) != DEB_SHA256:
        raise ValueError("downloaded unrar Debian package differs from the frozen bytes")


def install(cache_directory: Path, output: Path) -> dict[str, object]:
    root = project_root().resolve()
    cache_directory = cache_directory.resolve()
    output = output.resolve()
    cache_directory.mkdir(parents=True, exist_ok=True)
    package = cache_directory / DEB_FILENAME
    if not package.is_file():
        completed = subprocess.run(
            ("apt-get", "download", f"{PACKAGE_NAME}={PACKAGE_VERSION}"),
            cwd=cache_directory,
            check=False,
            capture_output=True,
            text=True,
            timeout=180,
        )
        if completed.returncode != 0:
            raise RuntimeError(f"apt-get download failed: {completed.stderr.strip()}")
    _validate_deb(package)

    installation = cache_directory / "unrar-7.0.7"
    binary = installation / "usr" / "bin" / "unrar-nonfree"
    if not binary.is_file():
        temporary = Path(tempfile.mkdtemp(prefix="unrar-extract-", dir=cache_directory))
        try:
            subprocess.run(
                ("dpkg-deb", "--extract", str(package), str(temporary)),
                check=True,
                capture_output=True,
                text=True,
                timeout=60,
            )
            extracted_binary = temporary / "usr" / "bin" / "unrar-nonfree"
            if not extracted_binary.is_file():
                raise ValueError("frozen unrar package did not contain usr/bin/unrar-nonfree")
            temporary.replace(installation)
        except Exception:
            if temporary.exists():
                shutil.rmtree(temporary)
            raise

    version = subprocess.run(
        (str(binary),),
        check=False,
        capture_output=True,
        text=True,
        timeout=10,
    )
    combined = "\n".join((version.stdout, version.stderr))
    if EXPECTED_VERSION_TOKEN not in combined:
        raise ValueError("installed unrar binary did not report the frozen version")
    result: dict[str, object] = {
        "schema_version": "smartvalve-local-unrar-toolchain-0.1.0",
        "generated_at": datetime.now(UTC).isoformat(),
        "status": "installed_and_version_checked_without_archive_access",
        "package": {
            "name": PACKAGE_NAME,
            "version": PACKAGE_VERSION,
            "source": "Ubuntu 24.04 noble multiverse via apt-get download",
            "filename": DEB_FILENAME,
            "bytes": package.stat().st_size,
            "sha256": _digest(package),
        },
        "binary": {
            "path": binary.relative_to(root).as_posix(),
            "bytes": binary.stat().st_size,
            "sha256": _digest(binary),
            "version_token": EXPECTED_VERSION_TOKEN,
            "probe_exit_code": version.returncode,
        },
        "access_attestation": {
            "archive_path_supplied": False,
            "archive_members_listed": False,
            "archive_members_extracted": False,
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
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = install(args.cache_directory, args.output)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
