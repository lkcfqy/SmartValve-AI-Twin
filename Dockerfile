FROM cgr.dev/chainguard/python:latest-dev@sha256:93a58bdb02c7c37785752cfab31031331448ab84aeab5d14ca101b381bc49577 AS builder

USER 0
ENV PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_ROOT_USER_ACTION=ignore \
    PYTHONDONTWRITEBYTECODE=1

WORKDIR /build
RUN python -m venv /venv
ENV PATH="/venv/bin:${PATH}"

COPY build-requirements.lock requirements.lock ./
RUN python -m pip install --require-hashes -r build-requirements.lock \
    && python -m pip install --require-hashes --no-build-isolation -r requirements.lock

COPY pyproject.toml README.md LICENSE THIRD_PARTY_NOTICES.md ./
COPY src ./src
RUN python -m build --wheel --no-isolation --outdir /dist \
    && python -m pip install --no-deps /dist/*.whl \
    && python -m pip uninstall --yes pip setuptools wheel build pyproject-hooks

FROM cgr.dev/chainguard/python:latest@sha256:4d908c6a44ba22460e34a2f6dd665b8fcb82bd3e6c887e749bd6fef243e10094 AS runtime

LABEL org.opencontainers.image.title="SmartValve AI Twin" \
      org.opencontainers.image.version="0.6.0" \
      org.opencontainers.image.description="Auditable valve-condition engineering platform" \
      org.opencontainers.image.licenses="Apache-2.0"

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    SMARTVALVE_PROJECT_ROOT=/app \
    SMARTVALVE_DATABASE=/app/data/runtime/smartvalve.db \
    SMARTVALVE_EXTERNAL_DATA=/app/data/external \
    SMARTVALVE_REQUIRE_WNTR=true \
    HOME=/tmp \
    MPLCONFIGDIR=/tmp/matplotlib \
    STREAMLIT_BROWSER_GATHER_USAGE_STATS=false \
    PATH="/venv/bin:${PATH}"

WORKDIR /app
COPY --from=builder --chown=65532:65532 /venv /venv
COPY --chown=65532:65532 networks ./networks
COPY --chown=65532:65532 dashboard ./dashboard
COPY --chown=65532:65532 .streamlit ./.streamlit
COPY --chown=65532:65532 artifacts ./artifacts
COPY --chown=65532:65532 data/runtime/.gitkeep ./data/runtime/.gitkeep
COPY --chown=65532:65532 data/external/.gitkeep ./data/external/.gitkeep
COPY --chown=65532:65532 data/backups/.gitkeep ./data/backups/.gitkeep

USER 65532:65532
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
  CMD ["/venv/bin/python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health/ready', timeout=3)"]

ENTRYPOINT ["/venv/bin/python"]
CMD ["-m", "uvicorn", "smartvalve.service.app:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1", "--no-server-header"]
