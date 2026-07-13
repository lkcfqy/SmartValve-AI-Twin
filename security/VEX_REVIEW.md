# SmartValve AI Twin 0.4.0 VEX review

Review date: 2026-07-13
Image: `smartvalve-ai-twin:0.4.0`
Immutable image digest: `sha256:89ee728b34f32f310854521d7aa7130c3ca559d145e8ff05f1aa32e56a2b064f`

The raw Grype scan reports three high-severity CPython findings and four medium findings. All seven findings are retained in the raw report and assessed in `openvex.json`; they are not silently deleted.

## Threat-path assessment

| CVE | Affected standard-library path | SmartValve exposure | Decision |
|---|---|---|---|
| CVE-2026-11940 | `tarfile` extraction path traversal | The API accepts bounded CSV only. Application code does not import `tarfile`, call `extract`/`extractall`, install packages, or unpack request artifacts. | Not affected: vulnerable code not in execute path |
| CVE-2026-11972 | `tarfile` resource-exhaustion path | Same controls as above; no archive processing path exists. | Not affected: vulnerable code not in execute path |
| CVE-2026-15308 | `html.parser` CPU denial of service | No endpoint passes request or CSV content to `html.parser.HTMLParser`. Dashboard HTML comes from fixed templates, and dynamic diagnostic text is escaped. | Not affected: vulnerable code not in execute path |
| CVE-2025-15366 | `imaplib` command injection | The application has no IMAP client or mail-command path. | Not affected: vulnerable code not in execute path |
| CVE-2025-15367 | `poplib` command injection | The application has no POP client or mail-command path. | Not affected: vulnerable code not in execute path |
| CVE-2026-4360 | `tarfile.extract()` hardlink ownership handling | The application has no archive ingestion or extraction path. | Not affected: vulnerable code not in execute path |
| CVE-2026-0864 | `configparser` multiline-value injection | Request data is never written through `configparser`; runtime config is immutable or supplied by the operator. | Not affected: vulnerable code cannot be controlled by adversary |

## Compensating controls

- shell-less Chainguard runtime, UID/GID 65532;
- pip, setuptools, wheel and build tooling removed from the runtime virtual environment;
- read-only root filesystem, all Linux capabilities dropped, `no-new-privileges`, PID/memory/CPU limits;
- API key, operator identity, request-size and row-count bounds, rate limiting;
- localhost-only published ports in the reference Compose deployment.

## Mandatory re-review triggers

Reassess and update the VEX before release if any of these changes occur:

- archive upload/extraction, package installation or model-bundle ingestion is added;
- arbitrary HTML/Markdown or rich text becomes user-controlled;
- the Python base package, image digest, API ingestion contract, or dashboard rendering path changes;
- a patched Python release becomes available. Prefer upgrading over retaining VEX status.
