from __future__ import annotations

import time
from typing import Any

import httpx
import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi.testclient import TestClient
from jwt.algorithms import RSAAlgorithm

from smartvalve.service.app import app
from smartvalve.service.auth import (
    AUDIT_PERMISSION,
    DIAGNOSE_PERMISSION,
    READ_PERMISSION,
    AuthConfigurationError,
    AuthenticationError,
    OidcAuthenticator,
    OidcConfig,
)
from smartvalve.service.client import SmartValveApiClient


class FakeJwksClient:
    def __init__(self, public_key: Any, kid: str = "integration-key-1") -> None:
        jwk = RSAAlgorithm.to_jwk(public_key, as_dict=True)
        jwk.update({"kid": kid, "use": "sig", "alg": "RS256"})
        self.key = jwt.PyJWK.from_dict(jwk)
        self.kid = kid

    def get_signing_key(self, kid: str) -> jwt.PyJWK:
        if kid != self.kid:
            raise jwt.PyJWKClientError("key not found")
        return self.key

    def get_signing_keys(self) -> list[jwt.PyJWK]:
        return [self.key]


@pytest.fixture(scope="module")
def oidc_material() -> tuple[Any, OidcAuthenticator]:
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    config = OidcConfig(
        issuer="https://identity.example.test/realms/industrial",
        audience="smartvalve-api",
        jwks_url="https://identity.example.test/jwks",
        algorithms=("RS256",),
        allowed_types=frozenset({"at+jwt"}),
        username_claim="preferred_username",
        roles_claim="realm_access.roles",
        clock_skew_seconds=0,
        jwks_timeout_seconds=1,
        jwks_cache_seconds=300,
    )
    return private_key, OidcAuthenticator(config, FakeJwksClient(private_key.public_key()))


def _token(
    private_key: Any,
    *,
    roles: list[str] | None = None,
    issuer: str = "https://identity.example.test/realms/industrial",
    audience: str = "smartvalve-api",
    expires_in: int = 300,
    scopes: str = "",
) -> str:
    now = int(time.time())
    return jwt.encode(
        {
            "iss": issuer,
            "aud": audience,
            "sub": "directory-subject-73d1",
            "preferred_username": "verified.operator",
            "realm_access": {"roles": roles or []},
            "scope": scopes,
            "iat": now,
            "exp": now + expires_in,
            "jti": "token-instance-123",
        },
        private_key,
        algorithm="RS256",
        headers={"kid": "integration-key-1", "typ": "at+jwt"},
    )


def _authenticate(authenticator: OidcAuthenticator, token: str):
    return authenticator.authenticate(
        authorization=f"Bearer {token}", api_key=None, operator_id="forged.header"
    )


def test_oidc_validates_identity_roles_and_scopes(oidc_material) -> None:
    private_key, authenticator = oidc_material
    principal = _authenticate(
        authenticator,
        _token(
            private_key,
            roles=["smartvalve.auditor"],
            scopes=f"{READ_PERMISSION} {DIAGNOSE_PERMISSION}",
        ),
    )
    assert principal.operator_id == "verified.operator"
    assert principal.subject == "directory-subject-73d1"
    assert principal.can(READ_PERMISSION)
    assert principal.can(DIAGNOSE_PERMISSION)
    assert principal.can(AUDIT_PERMISSION)
    assert principal.token_id_sha256 != "token-instance-123"


@pytest.mark.parametrize(
    ("overrides", "expires_in"),
    [
        ({"issuer": "https://attacker.example.test"}, 300),
        ({"audience": "different-api"}, 300),
        ({}, -10),
    ],
)
def test_oidc_rejects_invalid_registered_claims(
    oidc_material, overrides: dict[str, str], expires_in: int
) -> None:
    private_key, authenticator = oidc_material
    with pytest.raises(AuthenticationError, match="invalid credentials"):
        _authenticate(authenticator, _token(private_key, expires_in=expires_in, **overrides))


def test_oidc_rejects_algorithm_confusion_and_malformed_bearer(oidc_material) -> None:
    _, authenticator = oidc_material
    now = int(time.time())
    confused = jwt.encode(
        {"iss": authenticator.config.issuer, "aud": "smartvalve-api", "exp": now + 60},
        "attacker-controlled-secret-longer-than-32-bytes",
        algorithm="HS256",
        headers={"kid": "integration-key-1", "typ": "at+jwt"},
    )
    with pytest.raises(AuthenticationError):
        _authenticate(authenticator, confused)
    with pytest.raises(AuthenticationError):
        authenticator.authenticate(authorization="Basic abc", api_key=None, operator_id=None)


def test_oidc_rbac_and_signed_operator_are_enforced(tmp_path, monkeypatch, oidc_material) -> None:
    private_key, authenticator = oidc_material
    monkeypatch.setenv("SMARTVALVE_DATABASE", str(tmp_path / "oidc.db"))
    monkeypatch.delenv("SMARTVALVE_API_KEY", raising=False)
    with TestClient(app) as client:
        app.state.authenticator = authenticator
        missing = client.get("/v1/sources")
        assert missing.status_code == 401
        assert missing.headers["www-authenticate"].startswith("Bearer")

        viewer_headers = {"Authorization": f"Bearer {_token(private_key, roles=['viewer'])}"}
        assert client.get("/v1/sources", headers=viewer_headers).status_code == 200
        assert (
            client.post("/v1/diagnostics/simulation", json={}, headers=viewer_headers).status_code
            == 403
        )
        assert client.get("/v1/runs", headers=viewer_headers).status_code == 403

        operator_headers = {
            "Authorization": f"Bearer {_token(private_key, roles=['operator'])}",
            "X-Operator-ID": "forged.header",
        }
        diagnosed = client.post(
            "/v1/diagnostics/simulation",
            json={"asset_id": "OIDC-V-01", "fault_type": "stiction"},
            headers=operator_headers,
        )
        assert diagnosed.status_code == 200
        payload = diagnosed.json()
        assert payload["operator_id"] == "verified.operator"
        assert payload["identity"]["subject"] == "directory-subject-73d1"
        assert payload["identity"]["issuer"] == authenticator.config.issuer
        assert payload["identity"]["auth_mode"] == "oidc"

        auditor_headers = {"Authorization": f"Bearer {_token(private_key, roles=['auditor'])}"}
        assert client.get("/v1/runs", headers=auditor_headers).status_code == 200
        assert (
            client.post("/v1/diagnostics/simulation", json={}, headers=auditor_headers).status_code
            == 403
        )


def test_oidc_configuration_is_fail_closed(monkeypatch) -> None:
    monkeypatch.setenv("SMARTVALVE_AUTH_MODE", "oidc")
    for name in (
        "SMARTVALVE_OIDC_ISSUER",
        "SMARTVALVE_OIDC_AUDIENCE",
        "SMARTVALVE_OIDC_JWKS_URL",
    ):
        monkeypatch.delenv(name, raising=False)
    with pytest.raises(AuthConfigurationError, match="oidc mode requires"), TestClient(app):
        pass


def test_http_client_sends_only_bearer_when_access_token_is_set(monkeypatch) -> None:
    captured: dict[str, Any] = {}

    def fake_request(method: str, url: str, **kwargs: Any) -> httpx.Response:
        captured.update({"method": method, "url": url, **kwargs})
        return httpx.Response(200, json={"sources": [], "artifacts": {}})

    monkeypatch.setattr(httpx, "request", fake_request)
    client = SmartValveApiClient(
        base_url="https://valve.example.test",
        api_key="must-not-be-forwarded",
        access_token="signed-access-token",
    )
    client.sources()
    assert captured["headers"] == {"Authorization": "Bearer signed-access-token"}
