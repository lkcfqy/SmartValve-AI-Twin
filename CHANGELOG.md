# Changelog

## 0.4.0 — 2026-07-13

- Added source-correct Cranfield electromechanical animation and removed hydraulic implication
  from public actuator replay.
- Added all-180-trial Cranfield leave-one-load-out development benchmark with its 33.3% weakest
  fold disclosed alongside 87.2% aggregate accuracy.
- Distinguished parameterized simulation runs from unique observable traces.
- Added explicit controlled execution in the dashboard; parameter edits no longer write records.
- Added complete baseline/current evidence payloads, operator identity, correlation IDs, evidence
  grades, and formal PDF limitations.
- Migrated SQLite audit records to an append-only SHA-256 hash chain with verification endpoint.
- Added production authentication gate, bounded uploads, rate limiting, security headers, route
  metrics, and real database/WNTR readiness probes.
- Added pinned and hash-locked runtime/build dependencies, non-root read-only containers, resource
  limits, and localhost-only Compose ports.
- Added public-artifact SHA-256 verification, security scans, SBOM workflow, and repository
  governance documents.
- Replaced the Debian runtime with a digest-pinned shell-less Chainguard Python 3.14 image,
  removed runtime package/build tools, and added reviewed OpenVEX scan evidence.
- Split Cranfield validation replay into a read-only endpoint so workspace navigation never
  creates an implicit audit record.

The diagnostic rule model remains `valvedna-rules-0.3.0`; the software version changed without
misrepresenting the model as retrained.
