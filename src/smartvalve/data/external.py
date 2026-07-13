"""Download small, traceable public benchmark slices into the local cache."""

from __future__ import annotations

import argparse
import json
import os
from dataclasses import asdict, dataclass
from hashlib import sha256
from pathlib import Path
from urllib.parse import urlparse
from urllib.request import Request, urlopen

from smartvalve.config import project_root


@dataclass(frozen=True)
class ExternalArtifact:
    source_id: str
    filename: str
    url: str
    license_name: str
    citation_url: str
    description: str


ARTIFACTS: tuple[ExternalArtifact, ...] = (
    ExternalArtifact(
        source_id="cranfield",
        filename="Normal.mat",
        url=(
            "https://cran-test-dspace.koha-ptfs.co.uk/bitstreams/"
            "e277afc2-444a-403f-bb64-dfc06549353f/download"
        ),
        license_name="CC BY 4.0",
        citation_url="https://doi.org/10.17862/cranfield.rd.5097649",
        description="Cranfield real electromechanical linear-actuator normal tests",
    ),
    ExternalArtifact(
        source_id="cranfield",
        filename="LackLubrication2.mat",
        url=(
            "https://cran-test-dspace.koha-ptfs.co.uk/bitstreams/"
            "04a1a1ae-7df4-43c8-a03e-25b0987e06a5/download"
        ),
        license_name="CC BY 4.0",
        citation_url="https://doi.org/10.17862/cranfield.rd.5097649",
        description="Cranfield real actuator seeded lack-of-lubrication stage 2 tests",
    ),
    ExternalArtifact(
        source_id="cranfield",
        filename="Backlash2.mat",
        url=(
            "https://cran-test-dspace.koha-ptfs.co.uk/bitstreams/"
            "4eff4df8-0ec1-48ea-af94-25a8af97f1ed/download"
        ),
        license_name="CC BY 4.0",
        citation_url="https://doi.org/10.17862/cranfield.rd.5097649",
        description="Cranfield real actuator seeded backlash stage 2 tests",
    ),
    ExternalArtifact(
        source_id="skab",
        filename="skab_valve1_1.csv",
        url="https://raw.githubusercontent.com/waico/SKAB/master/data/valve1/1.csv",
        license_name="GPL-3.0 repository license",
        citation_url="https://github.com/waico/SKAB",
        description="SKAB real water-loop valve-closure experiment",
    ),
)

ALLOWED_DOWNLOAD_HOSTS = {
    "cran-test-dspace.koha-ptfs.co.uk",
    "raw.githubusercontent.com",
}


def cache_directory() -> Path:
    configured = os.getenv("SMARTVALVE_EXTERNAL_DATA")
    return Path(configured).expanduser() if configured else project_root() / "data" / "external"


def _digest(path: Path) -> str:
    hasher = sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def sync_artifacts(*, force: bool = False, timeout_s: int = 90) -> list[dict[str, object]]:
    """Download artifacts atomically; never replace a valid cache implicitly."""

    cache = cache_directory()
    cache.mkdir(parents=True, exist_ok=True)
    cache.chmod(0o755)
    records: list[dict[str, object]] = []
    for artifact in ARTIFACTS:
        target = cache / artifact.filename
        if force or not target.exists() or target.stat().st_size == 0:
            temporary = target.with_suffix(target.suffix + ".part")
            parsed_url = urlparse(artifact.url)
            if parsed_url.scheme != "https" or parsed_url.hostname not in ALLOWED_DOWNLOAD_HOSTS:
                raise ValueError(f"artifact download URL is not allow-listed: {artifact.url}")
            request = Request(artifact.url, headers={"User-Agent": "SmartValve-AI-Twin/0.2"})
            # The HTTPS scheme and hostname are allow-listed immediately above.
            remote_response = urlopen(request, timeout=timeout_s)  # nosec B310
            with remote_response as response, temporary.open("wb") as output:
                while chunk := response.read(1024 * 1024):
                    output.write(chunk)
            temporary.replace(target)
        target.chmod(0o644)
        record = asdict(artifact)
        record.update(
            {
                "bytes": target.stat().st_size,
                "sha256": _digest(target),
            }
        )
        records.append(record)
    manifest = cache / "manifest.json"
    manifest.write_text(json.dumps(records, ensure_ascii=False, indent=2), encoding="utf-8")
    manifest.chmod(0o644)
    return records


def artifact_status() -> list[dict[str, object]]:
    cache = cache_directory()
    manifest_path = cache / "manifest.json"
    expected_hashes: dict[str, str] = {}
    if manifest_path.is_file():
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            expected_hashes = {
                str(item["filename"]): str(item["sha256"])
                for item in manifest
                if item.get("filename") and item.get("sha256")
            }
        except (json.JSONDecodeError, OSError, TypeError):
            expected_hashes = {}
    result: list[dict[str, object]] = []
    for artifact in ARTIFACTS:
        path = cache / artifact.filename
        available = path.is_file() and path.stat().st_size > 0
        actual_sha256 = _digest(path) if available else None
        expected_sha256 = expected_hashes.get(artifact.filename)
        result.append(
            {
                **asdict(artifact),
                "available": available,
                "bytes": path.stat().st_size if available else 0,
                "actual_sha256": actual_sha256,
                "expected_sha256": expected_sha256,
                "integrity_verified": bool(
                    actual_sha256 and expected_sha256 and actual_sha256 == expected_sha256
                ),
            }
        )
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("sync", "status"), nargs="?", default="status")
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()
    result = sync_artifacts(force=args.force) if args.command == "sync" else artifact_status()
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
