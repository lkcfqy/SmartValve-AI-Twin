"""Runtime configuration helpers shared by local, packaged and container deployments."""

from __future__ import annotations

import os
from pathlib import Path


def project_root() -> Path:
    """Return an explicit application root instead of relying on package install depth."""

    configured = os.getenv("SMARTVALVE_PROJECT_ROOT")
    if configured:
        return Path(configured).expanduser().resolve()
    current = Path.cwd().resolve()
    if (current / "pyproject.toml").is_file():
        return current
    source_root = Path(__file__).resolve().parents[2]
    if (source_root / "pyproject.toml").is_file():
        return source_root
    return current


def env_bool(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def runtime_environment() -> str:
    return os.getenv("SMARTVALVE_ENVIRONMENT", "development").strip().lower()


def production_mode() -> bool:
    return runtime_environment() in {"production", "staging"}
