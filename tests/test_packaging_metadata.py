import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_distribution_and_container_preserve_the_license_boundary() -> None:
    metadata = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))

    assert metadata["build-system"]["requires"] == ["setuptools>=77", "wheel"]
    assert metadata["project"]["license"] == "Apache-2.0"
    assert metadata["project"]["license-files"] == [
        "LICENSE",
        "THIRD_PARTY_NOTICES.md",
    ]
    for relative_path in metadata["project"]["license-files"]:
        notice = ROOT / relative_path
        assert notice.is_file()
        assert notice.stat().st_size > 0

    dockerfile = (ROOT / "Dockerfile").read_text(encoding="utf-8")
    license_copy = "COPY pyproject.toml README.md LICENSE THIRD_PARTY_NOTICES.md ./"
    assert license_copy in dockerfile
    assert dockerfile.index(license_copy) < dockerfile.index("RUN python -m build")

    docker_exclusions = {
        line.strip()
        for line in (ROOT / ".dockerignore").read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    }
    assert {"artifacts/external/", "artifacts/research/"} <= docker_exclusions
