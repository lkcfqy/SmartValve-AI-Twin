# Software acceptance report — 0.4.0

Date: 2026-07-13
Model: `valvedna-rules-0.3.0`
Scope: hardened single-node engineering pilot

## Verified results

- Ruff: passed for `src`, `tests`, and `dashboard`.
- Pytest: 22 passed; core coverage 84.46%; no deprecation warnings after the `httpx2` test-client migration.
- Bandit: no medium-or-higher findings after HTTPS allow-list and loopback binding controls.
- pip-audit: no known vulnerabilities in `requirements.lock` after upgrading PyArrow to 23.0.1.
- API: anonymous `/v1/*` request rejected; missing operator rejected; authenticated request accepted.
- Readiness: database and WNTR 1.5 PDD both ready.
- Audit: complete payload persisted; append-only update trigger enforced; SHA-256 chain verified.
- Container: shell-less Chainguard Python 3.14.6 runtime, UID/GID 65532, pip removed, read-only
  root, all capabilities dropped, `no-new-privileges`, writable tmpfs and audit volume only.
- Image digest: `sha256:89ee728b34f32f310854521d7aa7130c3ca559d145e8ff05f1aa32e56a2b064f`.
- Supply chain: SPDX 2.3 SBOM contains 100 packages. Raw Grype evidence contains three high and
  four medium CPython matches; OpenVEX path review retains all seven as suppressed evidence and
  leaves zero applicable findings. The high-severity gate passes.
- Public evidence: four artifacts matched synchronization-manifest SHA-256 values.
- Browser: five desktop workspaces exercised, controlled execution verified, no application-level
  JavaScript/console/HTTP errors, 390 px viewport without horizontal overflow.
- Controlled-write proof: landing-page load left the chain at nine records; one explicit execution
  advanced it to ten; navigating all five workspaces, including validation replay, left it at ten.

## Scientific evidence

| Layer | Result | Claim boundary |
|---|---:|---|
| S0 full regression | 3,000 parameterizations / 2,100 unique traces; macro F1 0.953 | deterministic simulation |
| S0 locked challenge | 1,500 / 1,050 unique traces; macro F1 0.874 | not physical accuracy |
| S1 Cranfield | 180 trials; leave-one-load-out dev CV accuracy 87.2% | actuator, not water valve |
| S1 weakest fold | trap / -40 kgf accuracy 33.3% | domain-transfer failure disclosed |
| S1 SKAB | fixed 400-point fit / 745-point evaluation | process anomaly, not mechanical root cause |

## Open acceptance gates

- No S2 owned-hardware dataset has been collected.
- No S3 Weilong data, product calibration, or verified Kv/Cv mapping exists.
- No field high availability, long-duration reliability, RUL, leakage, or safety certification has
  been completed.
- Demo video, two-page proposal, and physical sample remain separate visit-package deliverables.
