# Software acceptance report — 0.5.0

Date: 2026-07-13
Model: `valvedna-rules-0.3.0`
Scope: single-node operational-resilience release

## Release outcome

Version 0.5.0 adds a verifiable backup/restore boundary without changing the diagnostic model. It
also fixes audit-chain verification under NTP, RTC, or operator clock rollback. The release is
accepted for a hardened single-node engineering pilot; S2/S3 product evidence and multi-node field
operations remain open gates.

## Code and dependency gates

- Ruff passed for `src`, `tests`, and `dashboard`.
- Pytest passed all 28 tests with 83.42% coverage, above the 75% release gate.
- The clock-rollback regression proves two records whose timestamps move backwards still verify in
  immutable SQLite insertion order.
- Backup regressions cover strong-key enforcement, read-only source connection, wrong-key rejection,
  byte tampering, signed verification, existing-target refusal and restored-chain validation.
- Bandit reported no medium-or-higher findings.
- `pip-audit` reported zero known vulnerabilities for both runtime and CI lock files.
- Compose configuration validation and the 0.5.0 multi-stage image build passed.

## Live backup and restore drill

The final drill ran against the real `smartvalve_runtime` Docker volume while the API was online:

| Evidence | Result |
|---|---|
| Snapshot | `smartvalve-20260713T105937.123546Z-aa8fdae8.db` |
| Bytes | 1,740,800 |
| Database SHA-256 | `f0e37f4c6775623f062d31be1ea944b22421ad2609df710e905f3bd74d4e6810` |
| SQLite integrity | `ok` |
| Signed manifest checks | schema, HMAC, filename, size, SHA-256, SQLite, audit chain and audit anchor all `true` |
| Pre-restore chain | 13 records; head `70c2a79693a1f35c2d4e4548446113a089eab2c1e7f6e7728dba36b9d68a1483` |
| Restored chain | same 13 records and identical head |
| Restart result | API and dashboard healthy; database and WNTR readiness both true |

The first live attempt correctly failed because an OS-level read-only runtime mount prevents SQLite
WAL shared-memory coordination. The corrected service keeps the source SQL connection in
`mode=ro`, while allowing only the directory-level WAL lock access SQLite requires. No failed attempt
published a backup artifact or modified the chain.

## Container and supply-chain gates

- API and dashboard run the same `smartvalve-ai-twin:0.5.0` image at immutable digest
  `sha256:9bd10f977239caaf04fad26ab2e2236682e1978bdecf6cecaa6c0abf2a2d608d`.
- Runtime is Python 3.14.6, application 0.5.0, UID/GID 65532; pip and `/bin/sh` are absent.
- Both services have a read-only root filesystem, all Linux capabilities dropped and
  `no-new-privileges` enabled.
- SPDX 2.3 SBOM contains 100 packages.
- Raw Grype evidence retains three high and four medium CPython findings. The reviewed 0.5.0 VEX
  suppresses all seven unreachable standard-library paths, leaving zero applicable matches; the
  high gate passes.

## Browser acceptance after restore

- Real Chromium rendered all five desktop workspaces with their expected headings and real API
  readiness state.
- The diagnostic, network, overview and validation workspaces each rendered their dynamic iframe;
  the system workspace intentionally rendered none.
- No application console errors, page exceptions or HTTP responses at status 400 or above occurred.
- Desktop `scrollWidth == clientWidth == 1440`; mobile
  `scrollWidth == clientWidth == 390`, proving no horizontal overflow.
- Default sidebar selections are visibly high-contrast in the captured 0.5.0 diagnostic screenshot.
- Controlled-write proof on the final image: the explicit diagnostic button advanced the audit chain
  from 13 to 14; navigation across all five workspaces left it at 14 with the same chain head.

## Remaining production gates

- No S2 owned hardware or S3 Weilong valve dataset has been collected.
- No product-specific Kv/Cv mapping, long-duration reliability, RUL, leakage, or safety validation
  exists.
- Central identity, TLS termination, external secrets management, managed multi-user database,
  alert/log routing, off-host immutable backup scheduling, retention and multi-node failover remain
  field-deployment work.
- A signed single-node restore drill is not equivalent to an off-site disaster-recovery exercise.
