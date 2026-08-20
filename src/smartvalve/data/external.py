"""Download small, traceable public benchmark slices into the local cache."""

from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import asdict, dataclass
from hashlib import sha256
from http.client import HTTPException
from pathlib import Path
from time import sleep
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
    bytes: int
    sha256: str


ARTIFACTS: tuple[ExternalArtifact, ...] = (
    ExternalArtifact(
        source_id="cranfield",
        filename="Normal.mat",
        url=(
            "https://cran-test-dspace.koha-ptfs.co.uk/server/api/core/bitstreams/"
            "e277afc2-444a-403f-bb64-dfc06549353f/content"
        ),
        license_name="CC BY 4.0",
        citation_url="https://doi.org/10.17862/cranfield.rd.5097649",
        description="Cranfield real electromechanical linear-actuator normal tests",
        bytes=1949237,
        sha256="5ec388106129477ca190397df93270fa097ba0fee81ffc040fb0bf9cae98c260",
    ),
    ExternalArtifact(
        source_id="cranfield",
        filename="LackLubrication2.mat",
        url=(
            "https://cran-test-dspace.koha-ptfs.co.uk/server/api/core/bitstreams/"
            "04a1a1ae-7df4-43c8-a03e-25b0987e06a5/content"
        ),
        license_name="CC BY 4.0",
        citation_url="https://doi.org/10.17862/cranfield.rd.5097649",
        description="Cranfield real actuator seeded lack-of-lubrication stage 2 tests",
        bytes=1949871,
        sha256="23b12026d5462c9cfb108d75c4c06d7c117c041d5174229331612b8c204b4208",
    ),
    ExternalArtifact(
        source_id="cranfield",
        filename="Backlash2.mat",
        url=(
            "https://cran-test-dspace.koha-ptfs.co.uk/server/api/core/bitstreams/"
            "4eff4df8-0ec1-48ea-af94-25a8af97f1ed/content"
        ),
        license_name="CC BY 4.0",
        citation_url="https://doi.org/10.17862/cranfield.rd.5097649",
        description="Cranfield real actuator seeded backlash stage 2 tests",
        bytes=1949290,
        sha256="2c11d1275e622289641216e14b57035a6a157007bec716490436cdfdc376bbd7",
    ),
    ExternalArtifact(
        source_id="skab",
        filename="skab_valve1_1.csv",
        url=(
            "https://raw.githubusercontent.com/waico/SKAB/"
            "b2c0d46c2971dcbfe71e26087b6d231998bb91c2/data/valve1/1.csv"
        ),
        license_name="GPL-3.0 repository license",
        citation_url="https://github.com/waico/SKAB",
        description="SKAB real water-loop valve-closure experiment",
        bytes=110330,
        sha256="fe4493bf805baef4e6dfb864094275d8cc2ea80a16b3735e2752b18b6aefd812",
    ),
    ExternalArtifact(
        source_id="uci_hydraulic",
        filename="uci_hydraulic.zip",
        url=(
            "https://archive.ics.uci.edu/static/public/447/"
            "condition%2Bmonitoring%2Bof%2Bhydraulic%2Bsystems.zip"
        ),
        license_name="CC BY 4.0",
        citation_url="https://doi.org/10.24432/C5CW21",
        description=(
            "UCI physical hydraulic-rig cycles with factorial valve and context conditions"
        ),
        bytes=76601704,
        sha256="24128aad2ee45eea7e6b63ebbd9992cdf25d0483a2cebefbfc13bc69079af1f2",
    ),
)

ALLOWED_DOWNLOAD_HOSTS = {
    "cran-test-dspace.koha-ptfs.co.uk",
    "archive.ics.uci.edu",
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


def _matches_lock(path: Path, artifact: ExternalArtifact) -> bool:
    return (
        path.is_file()
        and path.stat().st_size == artifact.bytes
        and _digest(path) == artifact.sha256
    )


def _download_artifact(
    *,
    artifact: ExternalArtifact,
    target: Path,
    timeout_s: int,
    attempts: int,
    backoff_s: float,
) -> None:
    temporary = target.with_suffix(target.suffix + ".part")
    parsed_url = urlparse(artifact.url)
    if parsed_url.scheme != "https" or parsed_url.hostname not in ALLOWED_DOWNLOAD_HOSTS:
        raise ValueError(f"artifact download URL is not allow-listed: {artifact.url}")
    request = Request(artifact.url, headers={"User-Agent": "SmartValve-AI-Twin/0.2"})
    for attempt_number in range(1, attempts + 1):
        temporary.unlink(missing_ok=True)
        try:
            # The HTTPS scheme and hostname are allow-listed immediately above.
            remote_response = urlopen(request, timeout=timeout_s)  # nosec B310
            with remote_response as response, temporary.open("wb") as output:
                while chunk := response.read(1024 * 1024):
                    output.write(chunk)
            actual_bytes = temporary.stat().st_size
            actual_sha256 = _digest(temporary)
            if actual_bytes != artifact.bytes or actual_sha256 != artifact.sha256:
                raise ValueError(
                    f"integrity check failed for {artifact.filename}: "
                    f"expected {artifact.bytes} bytes/{artifact.sha256}, "
                    f"received {actual_bytes} bytes/{actual_sha256}"
                )
        except (HTTPException, OSError, ValueError) as error:
            if attempt_number >= attempts:
                raise
            print(
                f"retrying {artifact.filename} after attempt {attempt_number}/{attempts}: "
                f"{type(error).__name__}: {error}",
                file=sys.stderr,
            )
            sleep(backoff_s * attempt_number)
            continue
        temporary.replace(target)
        return
    raise RuntimeError("artifact retry loop ended without success or an exception")


def sync_artifacts(
    *,
    force: bool = False,
    timeout_s: int = 90,
    attempts: int = 3,
    backoff_s: float = 1.0,
) -> list[dict[str, object]]:
    """Download artifacts atomically; never replace a valid cache implicitly."""

    if timeout_s < 1:
        raise ValueError("download timeout must be positive")
    if attempts < 1:
        raise ValueError("download attempts must be positive")
    if backoff_s < 0:
        raise ValueError("download backoff must be nonnegative")
    cache = cache_directory()
    cache.mkdir(parents=True, exist_ok=True)
    cache.chmod(0o755)
    records: list[dict[str, object]] = []
    for artifact in ARTIFACTS:
        target = cache / artifact.filename
        if force or not _matches_lock(target, artifact):
            _download_artifact(
                artifact=artifact,
                target=target,
                timeout_s=timeout_s,
                attempts=attempts,
                backoff_s=backoff_s,
            )
        target.chmod(0o644)
        record = asdict(artifact)
        records.append(record)
    manifest = cache / "manifest.json"
    manifest.write_text(json.dumps(records, ensure_ascii=False, indent=2), encoding="utf-8")
    manifest.chmod(0o644)
    return records


def artifact_status() -> list[dict[str, object]]:
    cache = cache_directory()
    result: list[dict[str, object]] = []
    for artifact in ARTIFACTS:
        path = cache / artifact.filename
        available = path.is_file() and path.stat().st_size > 0
        actual_sha256 = _digest(path) if available else None
        result.append(
            {
                **asdict(artifact),
                "available": available,
                "actual_bytes": path.stat().st_size if available else 0,
                "actual_sha256": actual_sha256,
                "expected_bytes": artifact.bytes,
                "expected_sha256": artifact.sha256,
                "integrity_verified": bool(
                    available
                    and path.stat().st_size == artifact.bytes
                    and actual_sha256 == artifact.sha256
                ),
            }
        )
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("sync", "status"), nargs="?", default="status")
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--timeout-s", type=int, default=90)
    parser.add_argument("--attempts", type=int, default=3)
    parser.add_argument("--backoff-s", type=float, default=1.0)
    args = parser.parse_args()
    result = (
        sync_artifacts(
            force=args.force,
            timeout_s=args.timeout_s,
            attempts=args.attempts,
            backoff_s=args.backoff_s,
        )
        if args.command == "sync"
        else artifact_status()
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
