# Changelog

## 0.5.0 — 2026-07-13

- Fixed audit-chain verification to follow immutable insertion order, so NTP/RTC clock rollback no
  longer reorders valid records and produces a false tamper alarm.
- Added consistent online SQLite snapshots with mode-0600 output and atomic publication.
- Added HMAC-SHA256 manifests covering file hash/size, SQLite integrity, audit record count and chain
  head; signing keys must be independent and at least 32 bytes.
- Added fail-closed verification, explicit offline atomic restore, tamper/wrong-key regression tests,
  independent backup volume and one-shot Compose operations services.

The diagnostic rule model remains `valvedna-rules-0.3.0`; this is an operational-resilience release,
not an algorithm retraining claim.

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
