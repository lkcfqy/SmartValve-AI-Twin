"""Fail-closed API authentication and authorization primitives."""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from hashlib import sha256
from hmac import compare_digest
from typing import Any, Protocol
from urllib.parse import urlparse

import jwt
from jwt import PyJWKClient

from smartvalve.config import env_bool

READ_PERMISSION = "smartvalve.read"
DIAGNOSE_PERMISSION = "smartvalve.diagnose"
AUDIT_PERMISSION = "smartvalve.audit"
ADMIN_PERMISSION = "smartvalve.admin"
ALL_PERMISSIONS = frozenset(
    {READ_PERMISSION, DIAGNOSE_PERMISSION, AUDIT_PERMISSION, ADMIN_PERMISSION}
)

_IDENTIFIER_PATTERN = re.compile(r"[A-Za-z0-9._@:-]{1,80}")
_KID_PATTERN = re.compile(r"[A-Za-z0-9._:-]{1,128}")
_ASYMMETRIC_ALGORITHMS = frozenset(
    {"RS256", "RS384", "RS512", "PS256", "PS384", "PS512", "ES256", "ES384", "ES512", "EdDSA"}
)
_ROLE_PERMISSIONS = {
    "viewer": frozenset({READ_PERMISSION}),
    "operator": frozenset({READ_PERMISSION, DIAGNOSE_PERMISSION, AUDIT_PERMISSION}),
    "auditor": frozenset({READ_PERMISSION, AUDIT_PERMISSION}),
    "admin": ALL_PERMISSIONS,
}
_API_KEY_PLACEHOLDERS = frozenset(
    {
        "replace-me-in-shared-environments",
        "replace-with-a-random-secret-of-at-least-32-characters",
    }
)


class AuthConfigurationError(RuntimeError):
    """Raised when authentication cannot be configured safely."""


class AuthenticationError(RuntimeError):
    """Raised when presented credentials cannot establish a principal."""


@dataclass(frozen=True)
class Principal:
    """Verified request identity and its effective permissions."""

    operator_id: str
    subject: str
    issuer: str
    permissions: frozenset[str]
    roles: tuple[str, ...]
    auth_mode: str
    token_id_sha256: str | None = None

    def identity_dict(self) -> dict[str, object]:
        return {
            "auth_mode": self.auth_mode,
            "subject": self.subject,
            "issuer": self.issuer,
            "roles": list(self.roles),
            "permissions": sorted(self.permissions),
            "token_id_sha256": self.token_id_sha256,
        }

    def can(self, permission: str) -> bool:
        return permission in self.permissions or ADMIN_PERMISSION in self.permissions


class Authenticator(Protocol):
    mode: str

    def authenticate(
        self,
        *,
        authorization: str | None,
        api_key: str | None,
        operator_id: str | None,
    ) -> Principal: ...

    def ready(self) -> bool: ...


@dataclass(frozen=True)
class ApiKeyAuthenticator:
    """Compatibility authenticator for a local demo or single-tenant pilot."""

    expected_key: str | None
    production: bool
    mode: str = "api_key"

    def __post_init__(self) -> None:
        if self.production and (
            not self.expected_key
            or len(self.expected_key) < 32
            or self.expected_key in _API_KEY_PLACEHOLDERS
        ):
            raise AuthConfigurationError(
                "production requires SMARTVALVE_API_KEY with at least 32 characters in api_key mode"
            )

    def authenticate(
        self,
        *,
        authorization: str | None,
        api_key: str | None,
        operator_id: str | None,
    ) -> Principal:
        del authorization
        if self.expected_key and (
            api_key is None or not compare_digest(self.expected_key, api_key)
        ):
            raise AuthenticationError("invalid credentials")
        if self.production and operator_id is None:
            raise AuthenticationError("invalid credentials")
        verified_operator = (operator_id or "local-demo").strip()
        if not _IDENTIFIER_PATTERN.fullmatch(verified_operator):
            raise AuthenticationError("invalid credentials")
        return Principal(
            operator_id=verified_operator,
            subject=verified_operator,
            issuer="smartvalve-api-key",
            permissions=ALL_PERMISSIONS,
            roles=("legacy-api-key",),
            auth_mode=self.mode,
        )

    def ready(self) -> bool:
        return True


@dataclass(frozen=True)
class OidcConfig:
    issuer: str
    audience: str
    jwks_url: str
    algorithms: tuple[str, ...]
    allowed_types: frozenset[str]
    username_claim: str
    roles_claim: str
    clock_skew_seconds: float
    jwks_timeout_seconds: float
    jwks_cache_seconds: float

    @classmethod
    def from_env(cls, *, production: bool) -> OidcConfig:
        issuer = os.getenv("SMARTVALVE_OIDC_ISSUER", "").strip()
        audience = os.getenv("SMARTVALVE_OIDC_AUDIENCE", "").strip()
        jwks_url = os.getenv("SMARTVALVE_OIDC_JWKS_URL", "").strip()
        missing = [
            name
            for name, value in (
                ("SMARTVALVE_OIDC_ISSUER", issuer),
                ("SMARTVALVE_OIDC_AUDIENCE", audience),
                ("SMARTVALVE_OIDC_JWKS_URL", jwks_url),
            )
            if not value
        ]
        if missing:
            raise AuthConfigurationError(f"oidc mode requires {', '.join(missing)}")

        parsed = urlparse(jwks_url)
        if (
            parsed.scheme not in {"http", "https"}
            or not parsed.netloc
            or parsed.username
            or parsed.password
            or parsed.fragment
        ):
            raise AuthConfigurationError("SMARTVALVE_OIDC_JWKS_URL must be an absolute safe URL")
        if parsed.scheme != "https" and (
            production or not env_bool("SMARTVALVE_OIDC_ALLOW_INSECURE_JWKS", False)
        ):
            raise AuthConfigurationError("OIDC JWKS retrieval requires HTTPS")
        issuer_url = urlparse(issuer)
        if (
            issuer_url.scheme not in {"http", "https"}
            or not issuer_url.netloc
            or issuer_url.username
            or issuer_url.password
            or issuer_url.fragment
        ):
            raise AuthConfigurationError("SMARTVALVE_OIDC_ISSUER must be an absolute URL")
        if production and issuer_url.scheme != "https":
            raise AuthConfigurationError("production OIDC issuer requires HTTPS")

        algorithms = tuple(
            part.strip()
            for part in os.getenv("SMARTVALVE_OIDC_ALGORITHMS", "RS256").split(",")
            if part.strip()
        )
        if not algorithms or any(item not in _ASYMMETRIC_ALGORITHMS for item in algorithms):
            raise AuthConfigurationError(
                "OIDC algorithms must use an approved asymmetric allowlist"
            )
        allowed_types = frozenset(
            part.strip()
            for part in os.getenv("SMARTVALVE_OIDC_TOKEN_TYPES", "at+jwt,JWT").split(",")
            if part.strip()
        )
        if not allowed_types:
            raise AuthConfigurationError("SMARTVALVE_OIDC_TOKEN_TYPES must not be empty")
        username_claim = os.getenv("SMARTVALVE_OIDC_USERNAME_CLAIM", "preferred_username").strip()
        roles_claim = os.getenv("SMARTVALVE_OIDC_ROLES_CLAIM", "roles").strip()
        if not username_claim or not roles_claim:
            raise AuthConfigurationError("OIDC claim names must not be empty")

        clock_skew = _bounded_float("SMARTVALVE_OIDC_CLOCK_SKEW_SECONDS", 30.0, 0.0, 120.0)
        timeout = _bounded_float("SMARTVALVE_OIDC_JWKS_TIMEOUT_SECONDS", 5.0, 0.1, 30.0)
        cache = _bounded_float("SMARTVALVE_OIDC_JWKS_CACHE_SECONDS", 300.0, 1.0, 3600.0)
        return cls(
            issuer=issuer,
            audience=audience,
            jwks_url=jwks_url,
            algorithms=algorithms,
            allowed_types=allowed_types,
            username_claim=username_claim,
            roles_claim=roles_claim,
            clock_skew_seconds=clock_skew,
            jwks_timeout_seconds=timeout,
            jwks_cache_seconds=cache,
        )


class OidcAuthenticator:
    """Validate signed access tokens against an operator-controlled JWKS endpoint."""

    mode = "oidc"

    def __init__(self, config: OidcConfig, jwks_client: Any | None = None) -> None:
        self.config = config
        self.jwks_client = jwks_client or PyJWKClient(
            config.jwks_url,
            cache_keys=True,
            cache_jwk_set=True,
            lifespan=config.jwks_cache_seconds,
            timeout=config.jwks_timeout_seconds,
        )

    def authenticate(
        self,
        *,
        authorization: str | None,
        api_key: str | None,
        operator_id: str | None,
    ) -> Principal:
        del api_key, operator_id
        token = self._bearer_token(authorization)
        try:
            header = jwt.get_unverified_header(token)
            algorithm = header.get("alg")
            token_type = header.get("typ")
            kid = header.get("kid")
            if algorithm not in self.config.algorithms:
                raise AuthenticationError("invalid credentials")
            if token_type not in self.config.allowed_types:
                raise AuthenticationError("invalid credentials")
            if not isinstance(kid, str) or not _KID_PATTERN.fullmatch(kid):
                raise AuthenticationError("invalid credentials")
            signing_key = self.jwks_client.get_signing_key(kid)
            claims = jwt.decode(
                token,
                signing_key,
                algorithms=self.config.algorithms,
                audience=self.config.audience,
                issuer=self.config.issuer,
                leeway=self.config.clock_skew_seconds,
                options={
                    "require": ["exp", "iat", "iss", "aud", "sub"],
                    "verify_signature": True,
                    "verify_exp": True,
                    "verify_iat": True,
                    "verify_nbf": True,
                    "verify_iss": True,
                    "verify_aud": True,
                    "verify_sub": True,
                    "enforce_minimum_key_length": True,
                },
            )
        except AuthenticationError:
            raise
        except (jwt.PyJWTError, ValueError, TypeError) as exc:
            raise AuthenticationError("invalid credentials") from exc
        return self._principal(claims)

    @staticmethod
    def _bearer_token(authorization: str | None) -> str:
        if not authorization:
            raise AuthenticationError("invalid credentials")
        parts = authorization.split()
        if len(parts) != 2 or parts[0].lower() != "bearer" or not parts[1]:
            raise AuthenticationError("invalid credentials")
        return parts[1]

    def _principal(self, claims: dict[str, Any]) -> Principal:
        subject = claims.get("sub")
        if not isinstance(subject, str) or not subject or len(subject) > 255:
            raise AuthenticationError("invalid credentials")
        username = _nested_claim(claims, self.config.username_claim)
        operator_id = username.strip() if isinstance(username, str) else ""
        if not _IDENTIFIER_PATTERN.fullmatch(operator_id):
            operator_id = f"oidc:{sha256(subject.encode()).hexdigest()[:20]}"

        roles = _claim_values(_nested_claim(claims, self.config.roles_claim))
        scopes = _claim_values(claims.get("scope")) | _claim_values(claims.get("scp"))
        permissions = {value for value in scopes if value in ALL_PERMISSIONS}
        normalized_roles: set[str] = set()
        for role in roles:
            normalized = role.removeprefix("smartvalve.").lower()
            normalized_roles.add(normalized)
            permissions.update(_ROLE_PERMISSIONS.get(normalized, frozenset()))
        token_id = claims.get("jti")
        token_id_sha256 = (
            sha256(token_id.encode()).hexdigest()
            if isinstance(token_id, str) and token_id
            else None
        )
        return Principal(
            operator_id=operator_id,
            subject=subject,
            issuer=self.config.issuer,
            permissions=frozenset(permissions),
            roles=tuple(sorted(normalized_roles)),
            auth_mode=self.mode,
            token_id_sha256=token_id_sha256,
        )

    def ready(self) -> bool:
        try:
            return bool(self.jwks_client.get_signing_keys())
        except (jwt.PyJWTError, OSError, ValueError):
            return False


def build_authenticator(*, production: bool) -> Authenticator:
    mode = os.getenv("SMARTVALVE_AUTH_MODE", "api_key").strip().lower()
    if mode == "api_key":
        return ApiKeyAuthenticator(os.getenv("SMARTVALVE_API_KEY"), production)
    if mode == "oidc":
        return OidcAuthenticator(OidcConfig.from_env(production=production))
    raise AuthConfigurationError("SMARTVALVE_AUTH_MODE must be api_key or oidc")


def _nested_claim(claims: dict[str, Any], claim_path: str) -> Any:
    value: Any = claims
    for part in claim_path.split("."):
        if not isinstance(value, dict) or part not in value:
            return None
        value = value[part]
    return value


def _claim_values(value: Any) -> set[str]:
    if isinstance(value, str):
        return {part for part in value.split() if part}
    if isinstance(value, list):
        return {part for part in value if isinstance(part, str) and part}
    return set()


def _bounded_float(name: str, default: float, minimum: float, maximum: float) -> float:
    try:
        value = float(os.getenv(name, str(default)))
    except ValueError as exc:
        raise AuthConfigurationError(f"{name} must be numeric") from exc
    if not minimum <= value <= maximum:
        raise AuthConfigurationError(f"{name} must be between {minimum} and {maximum}")
    return value
