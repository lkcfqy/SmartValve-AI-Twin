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
- Base-profile ports bind to loopback. Remote exposure must use the supplied TLS overlay or an
  equivalently reviewed ingress; changing the bind address alone is not sufficient.
- Production supports a guarded 32+ character API key or fail-closed OIDC/JWT with RBAC. Example
  secrets are rejected. See [authentication and authorization](authentication.md).
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

## Public TLS ingress

The TLS overlay uses a digest-pinned Caddy 2.10.2 image, runs it as UID/GID 65532 with all Linux
capabilities dropped, and persists only certificate/config state. Caddy obtains and renews public
certificates, redirects HTTP to HTTPS, proxies WebSockets, emits structured access logs, redacts
sensitive authorization/cookie headers by default, and adds HSTS and browser security headers.

Before starting, create public DNS records for two names, allow inbound TCP 80/443 and UDP 443, and
replace all example values in `.env`:

```dotenv
SMARTVALVE_DASHBOARD_DOMAIN=valve.your-domain.example
SMARTVALVE_API_DOMAIN=api.valve.your-domain.example
SMARTVALVE_TLS_EMAIL=operations@your-domain.example
```

Then run:

```bash
docker compose -f compose.yaml -f compose.tls.yaml build
docker compose -f compose.yaml -f compose.tls.yaml up -d
docker compose -f compose.yaml -f compose.tls.yaml ps
```

The two original ports remain available only on `127.0.0.1` for break-glass diagnostics. Do not
publish API, dashboard, OAuth2 Proxy, or database ports directly to an untrusted network. Protect
the Caddy certificate volumes in host backups; never add `tls_insecure_skip_verify`.

## OIDC browser SSO

Register a confidential OIDC client with this exact redirect URI:

```text
https://<SMARTVALVE_DASHBOARD_DOMAIN>/oauth2/callback
```

Configure the provider to issue an access token whose issuer, API audience, signature algorithm,
token type and roles match the API settings in [authentication.md](authentication.md). Generate a
cookie secret separately from every other secret:

```bash
python -c "import os,base64; print(base64.urlsafe_b64encode(os.urandom(32)).decode())"
```

Set `SMARTVALVE_OIDC_CLIENT_ID`, `SMARTVALVE_OIDC_CLIENT_SECRET`,
`SMARTVALVE_OIDC_COOKIE_SECRET`, `SMARTVALVE_OIDC_ALLOWED_EMAIL_DOMAINS`, and the API OIDC fields.
Do not retain these values in a production `.env`; inject them from the approved secret manager.
Validate the complete merged configuration, then start all three overlays in order:

```bash
docker compose -f compose.yaml -f compose.tls.yaml -f compose.sso.yaml config --quiet
docker compose -f compose.yaml -f compose.tls.yaml -f compose.sso.yaml up -d --build
docker compose -f compose.yaml -f compose.tls.yaml -f compose.sso.yaml ps
```

Test one viewer, operator and auditor account. Confirm a viewer receives HTTP 403 from diagnostic
and audit endpoints, an operator-created record contains the signed directory subject rather than a
client header, and `/v1/audit/verify` remains valid. Identity-provider MFA, conditional access,
joiner/mover/leaver workflows and break-glass policy remain the deploying organization's controls.

## Scale boundary

The audit store is SQLite WAL and the API deliberately runs one worker. OIDC/RBAC, browser SSO and
TLS reference deployments are now supplied, but they are not complete until tested against the
organization's real DNS, identity provider and access policies. Before multi-node field deployment,
migrate audit persistence to a managed transactional database, add external secrets management,
scheduled off-host immutable backup export, alert routing, log aggregation, external session state,
load/failover testing, and an agreed retention policy. Safety actions remain under human control.
