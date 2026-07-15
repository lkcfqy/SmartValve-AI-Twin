# Authentication and authorization

SmartValve supports two deliberately separate authentication modes. `api_key` preserves the local
demo and a single-tenant engineering pilot. `oidc` is the production identity boundary for a
multi-user deployment. The service never falls back from OIDC to an API key when OIDC validation
fails.

## OIDC validation contract

The API accepts only `Authorization: Bearer <access-token>`. It selects a signing key from the
operator-configured HTTPS JWKS URL and validates all of the following before a request reaches an
endpoint:

- the header has an approved `typ`, a bounded `kid`, and an explicitly configured asymmetric
  algorithm; `none` and all HMAC algorithms are rejected;
- the signature is valid and the token contains `exp`, `iat`, `iss`, `aud`, and `sub`;
- issuer and audience exactly match the deployment configuration;
- expiry, not-before, issued-at, subject, and configured clock skew checks pass;
- the signed roles/scopes grant the endpoint's required permission.

The JWKS URL is configuration, never token-controlled input. Production refuses HTTP issuer or JWKS
URLs and refuses to start when any required OIDC setting is missing. `/health/ready` includes JWKS
reachability as `authentication_ready`.

## RBAC model

| Effective role | Permissions | Intended use |
|---|---|---|
| `viewer` | `smartvalve.read` | source inventory and validation evidence |
| `operator` | read, `smartvalve.diagnose`, `smartvalve.audit` | execute and inspect diagnostics |
| `auditor` | read, audit | inspect records, reports, and chain integrity |
| `admin` | all permissions | controlled platform administration |

Roles may be named either `viewer` or `smartvalve.viewer`, and likewise for the other roles. Direct
permission scopes are also accepted. The roles claim supports a dotted path such as
`realm_access.roles`.

| API group | Required permission |
|---|---|
| `/v1/sources`, `/v1/validation/*` | `smartvalve.read` |
| `/v1/diagnostics/*` | `smartvalve.diagnose` |
| `/v1/runs*`, `/v1/audit/*`, PDF reports | `smartvalve.audit` |

`X-Operator-ID` is ignored in OIDC mode. The displayed operator comes from the signed username
claim; if that value is absent or unsafe, the API derives a stable pseudonymous identifier from
`sub`. The full signed subject, issuer, effective roles, permissions, authentication mode, and a
SHA-256 digest of `jti` are embedded in the result before its audit hash is calculated. Raw tokens
and raw token IDs are never persisted.

## Required API configuration

```dotenv
SMARTVALVE_AUTH_MODE=oidc
SMARTVALVE_API_KEY=
SMARTVALVE_OIDC_ISSUER=https://identity.example.com/realms/smartvalve
SMARTVALVE_OIDC_AUDIENCE=smartvalve-api
SMARTVALVE_OIDC_JWKS_URL=https://identity.example.com/realms/smartvalve/protocol/openid-connect/certs
SMARTVALVE_OIDC_ALGORITHMS=RS256
SMARTVALVE_OIDC_TOKEN_TYPES=at+jwt,JWT
SMARTVALVE_OIDC_USERNAME_CLAIM=preferred_username
SMARTVALVE_OIDC_ROLES_CLAIM=realm_access.roles
```

The identity provider must issue an access token for the `smartvalve-api` audience and place the
approved roles or permission scopes in that access token. An ID token intended only for the browser
is not an API access token and should not be accepted as one.

## Browser SSO boundary

The optional `compose.sso.yaml` overlay places OAuth2 Proxy between Caddy and Streamlit. Caddy sends
every dashboard request to OAuth2 Proxy, redirects unauthenticated users to the organization's OIDC
provider, and overwrites the internal trusted-token header with the authenticated session's access
token. Streamlit forwards that token to the API, which independently verifies it and enforces RBAC.

OAuth2 Proxy is not exposed on a host port. The dashboard trusts its internal token header only when
`SMARTVALVE_TRUST_PROXY_ACCESS_TOKEN=true`, which the SSO overlay sets. Do not enable this flag when
Streamlit is reachable through an untrusted proxy path.

The supplied cookie session is suitable for one node. Large provider tokens or multiple OAuth2
Proxy replicas require an external Redis-compatible session store and a separate availability and
restore design.

## API-key compatibility mode

In production `api_key` mode, the key must contain at least 32 characters, known example values are
rejected, and `X-Operator-ID` is required. This remains a shared-secret identity and is not suitable
for individual accountability: anyone with the key can assert any syntactically valid operator ID.
Use it only on a trusted single-user workstation or during a controlled pilot, then move to OIDC.
