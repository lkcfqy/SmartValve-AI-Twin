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

## Signed backup and disaster-recovery drill

First verify the live chain:

```bash
curl -H "X-API-Key: $SMARTVALVE_API_KEY" \
  -H "X-Operator-ID: backup-operator" \
  http://127.0.0.1:8000/v1/audit/verify
```

Generate `SMARTVALVE_BACKUP_SIGNING_KEY` independently from the API key. In the supplied
single-node profile it may be injected through `.env`; a field deployment must inject it from a
secret manager and keep it separate from backup storage. The key is never accepted as a command-line
argument, so it does not enter shell history.

Create a consistent snapshot while the API remains online:

```bash
docker compose --profile operations run --rm backup
docker volume inspect smartvalve_backups
```

The backup service opens the database through SQLite `mode=ro`. Its runtime volume is nevertheless
mounted writable because SQLite WAL readers must coordinate through `-shm` lock state in the same
directory; an OS-level read-only mount would make a correct online snapshot fail before reading.

The command writes a mode-0600 `smartvalve-*.db` and matching
`smartvalve-*.db.manifest.json` into the independent `smartvalve_backups` volume. The manifest binds
the file name, byte length, SHA-256, SQLite integrity result, audit record count and audit-chain head,
then signs all fields with HMAC-SHA256.

Verify a selected backup before transfer or restoration:

```bash
BACKUP_FILE=smartvalve-YYYYMMDDTHHMMSS.ffffffZ-xxxxxxxx.db
docker compose --profile operations run --rm backup \
  -m smartvalve.storage.backup verify \
  --backup "/app/data/backups/$BACKUP_FILE" \
  --manifest "/app/data/backups/$BACKUP_FILE.manifest.json"
```

Restore is deliberately offline and requires an explicit file name and replacement flag embedded in
the one-shot service. Do not run it while either application service is active:

```bash
docker compose stop dashboard api
SMARTVALVE_BACKUP_FILE="$BACKUP_FILE" \
  docker compose --profile operations run --rm restore
docker compose up -d api dashboard
curl -H "X-API-Key: $SMARTVALVE_API_KEY" \
  -H "X-Operator-ID: restore-verifier" \
  http://127.0.0.1:8000/v1/audit/verify
```

HMAC provides authenticity, not confidentiality. Copy both files to encrypted, access-controlled,
off-host immutable storage; keep the signing key elsewhere; define retention; and schedule a restore
drill. A successful command alone is not evidence until the restored API becomes ready and returns
the same record count and chain head.

## Scale boundary

The audit store is SQLite WAL and the API deliberately runs one worker. Before multi-user field
deployment, migrate audit persistence to a managed transactional database, add centralized identity,
TLS termination, external secrets management, scheduled off-host immutable backup export, alert
routing, log aggregation, load/failover testing, and an agreed retention policy. Safety actions remain
under human control.
