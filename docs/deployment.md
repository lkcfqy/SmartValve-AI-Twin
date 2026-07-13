# Hardened single-node deployment

The supplied Compose profile is suitable for an engineering pilot on one trusted workstation. It
is intentionally not described as a plant-wide high-availability deployment.

## Start

```bash
cp .env.example .env
python -c "import secrets; print(secrets.token_urlsafe(48))"
# Put the generated value in SMARTVALVE_API_KEY inside .env.
make data
docker compose build
docker compose up -d
docker compose ps
```

Open `http://127.0.0.1:8501`. API health is at
`http://127.0.0.1:8000/health/ready`. Never commit `.env`.

## Security properties

- API and dashboard use a digest-pinned, shell-less Chainguard Python 3.14 runtime as UID/GID
  65532 with a read-only root filesystem. pip and build tooling are absent from the runtime.
- All Linux capabilities are dropped and `no-new-privileges` is enabled.
- Only `/tmp` and the named `smartvalve_runtime` audit volume are writable.
- Ports bind to loopback. A remote pilot must add an authenticated TLS reverse proxy or VPN;
  changing the bind address alone is not sufficient.
- Production mode requires a 32+ character API key and an operator identifier.
- Public benchmark files are mounted read-only and checked against their SHA-256 manifest.
- `make sbom` creates SPDX 2.3 evidence. `make image-scan` applies the reviewed OpenVEX document;
  the raw and VEX-filtered reports remain under `artifacts/security/` for audit comparison.

## Backup and verification

First verify the live chain:

```bash
curl -H "X-API-Key: $SMARTVALVE_API_KEY" \
  -H "X-Operator-ID: backup-operator" \
  http://127.0.0.1:8000/v1/audit/verify
```

For a consistent pilot backup, stop the dashboard/API, archive the Docker named volume with an
approved backup tool, then restart. Store backups off-host with encryption and access controls.
Test restoration and `/v1/audit/verify` before relying on the procedure.

## Scale boundary

The audit store is SQLite WAL and the API deliberately runs one worker. Before multi-user field
deployment, migrate audit persistence to a managed transactional database, add centralized identity,
TLS termination, secrets management, off-host immutable backups, alert routing, log aggregation,
load/failover testing, and an agreed retention policy. Safety actions remain under human control.
