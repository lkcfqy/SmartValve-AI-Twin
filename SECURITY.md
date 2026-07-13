# Security policy

## Supported versions

Security fixes are applied to the current `0.5.x` engineering-pilot line. Older local
snapshots are unsupported.

## Reporting a vulnerability

Do not include credentials, enterprise data, exploit payloads, or customer details in a
public issue. Contact the repository maintainer through a private channel and include the
affected version, reproduction conditions, impact, and a safe proof of concept. The target
acknowledgement time is three business days.

## Deployment assumptions

- Compose binds API and dashboard ports to `127.0.0.1`; remote access requires a separately
  reviewed TLS reverse proxy or VPN.
- Production mode refuses startup without an API key of at least 32 characters and requires
  an `X-Operator-ID` for every `/v1/*` request.
- The supplied Compose profile is a hardened single-node engineering pilot. It is not a
  high-availability, multi-tenant, or safety-instrumented deployment.
- Uploaded files are bounded to 10 MiB and 200,000 rows per CSV, pass a strict data contract,
  and are never executed.
- Public data downloads are restricted to an explicit HTTPS hostname allow-list and are
  verified against the local synchronization manifest.
- Diagnostic records are append-only and SHA-256 chained. Signed snapshot manifests anchor the
  chain head and detect replacement without the independent HMAC key; neither mechanism encrypts
  data or replaces access-controlled, immutable off-host storage.

## Maintainer checks

Run `make security`, `make test`, `make docker-build`, `make sbom`, and `make image-scan`
before a tagged handoff. Rotate any credential that may have entered logs or screenshots.
