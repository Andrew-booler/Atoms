"""后端-单元-13：core/auth.py — OIDC 参数、应用 JWT 与 ID Token 校验。

本层不发起真实网络请求：JWKS 由本地生成的 RSA 公钥替身返回，配置来自临时环境变量。
"""
import base64
import hashlib
import json
from datetime import datetime, timedelta, timezone
from urllib.parse import parse_qs, urlparse

import httpx
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from jose import jwt

from core import auth
from core.config import settings

ISSUER = "https://issuer.example.test"
CLIENT_ID = "client-abc"

_ENV = {
    "APP_AUTH_SECRET": "unit-secret-key",
    "OIDC_ISSUER_URL": ISSUER,
    "OIDC_CLIENT_ID": CLIENT_ID,
    "OIDC_CLIENT_SECRET": "client-secret",
    "OIDC_SCOPE": "openid profile email",
    "FRONTEND_URL": "https://frontend.example.test",
}


@pytest.fixture
def auth_env(monkeypatch):
    for key, value in _ENV.items():
        monkeypatch.setenv(key, value)
        settings.__dict__.pop(key.lower(), None)
    yield
    for key in _ENV:
        settings.__dict__.pop(key.lower(), None)


def _b64url(data: dict) -> str:
    raw = json.dumps(data, separators=(",", ":")).encode("utf-8")
    return base64.urlsafe_b64encode(raw).decode("utf-8").rstrip("=")


def _rsa_key():
    return rsa.generate_private_key(public_exponent=65537, key_size=2048)


def _private_pem(key) -> bytes:
    return key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )


def _public_jwk(key, kid: str) -> dict:
    numbers = key.public_key().public_numbers()

    def encode(value: int) -> str:
        size = (value.bit_length() + 7) // 8
        return base64.urlsafe_b64encode(value.to_bytes(size, "big")).decode("utf-8").rstrip("=")

    return {"kty": "RSA", "kid": kid, "alg": "RS256", "use": "sig", "n": encode(numbers.n), "e": encode(numbers.e)}


def _claims(**overrides) -> dict:
    now = datetime.now(timezone.utc)
    claims = {
        "sub": "user-1",
        "email": "user@example.test",
        "iss": ISSUER,
        "aud": CLIENT_ID,
        "iat": now,
        "exp": now + timedelta(minutes=5),
        "nonce": "nonce-1",
    }
    claims.update(overrides)
    return claims


@pytest.fixture
def rsa_key():
    return _rsa_key()


@pytest.fixture
def jwks(monkeypatch, rsa_key):
    jwk = _public_jwk(rsa_key, "kid-1")

    async def fake_get_jwks():
        return {"keys": [jwk]}

    monkeypatch.setattr(auth, "get_jwks", fake_get_jwks)
    return jwk


def _id_token(key, claims: dict, *, kid: str | None = "kid-1") -> str:
    headers = {"kid": kid} if kid else {}
    return jwt.encode(claims, _private_pem(key), algorithm="RS256", headers=headers)


def test_oidc_values_are_random_and_challenge_is_s256():
    state_a, state_b = auth.generate_state(), auth.generate_state()
    nonce_a, nonce_b = auth.generate_nonce(), auth.generate_nonce()
    verifier_a, verifier_b = auth.generate_code_verifier(), auth.generate_code_verifier()

    assert state_a and state_b and state_a != state_b
    assert nonce_a and nonce_b and nonce_a != nonce_b
    assert verifier_a and verifier_b and verifier_a != verifier_b

    challenge = auth.generate_code_challenge(verifier_a)
    expected = base64.urlsafe_b64encode(hashlib.sha256(verifier_a.encode("utf-8")).digest()).decode("utf-8")
    assert challenge == expected.rstrip("=")
    assert "=" not in challenge


def test_create_and_decode_access_token_roundtrip(auth_env):
    token = auth.create_access_token({"sub": "user-1", "role": "admin"}, expires_minutes=5)
    payload = auth.decode_access_token(token)

    assert payload["sub"] == "user-1"
    assert payload["role"] == "admin"
    assert {"exp", "iat", "nbf"} <= set(payload)


def test_decode_expired_access_token_is_rejected(auth_env):
    token = auth.create_access_token({"sub": "user-1"}, expires_minutes=-1)
    with pytest.raises(auth.AccessTokenError, match="Token has expired"):
        auth.decode_access_token(token)


def test_decode_tampered_access_token_is_rejected(auth_env):
    token = auth.create_access_token({"sub": "user-1"})
    head, body, signature = token.split(".")
    replacement = "A" if signature[0] != "A" else "B"
    tampered = f"{head}.{body}.{replacement}{signature[1:]}"

    with pytest.raises(auth.AccessTokenError, match="Invalid authentication token"):
        auth.decode_access_token(tampered)


def test_decode_unsigned_alg_none_token_is_rejected(auth_env):
    token = f"{_b64url({'alg': 'none', 'typ': 'JWT'})}.{_b64url({'sub': 'user-1'})}."

    with pytest.raises(auth.AccessTokenError, match="Invalid authentication token"):
        auth.decode_access_token(token)


def test_access_token_requires_configured_secret(monkeypatch):
    monkeypatch.setenv("APP_AUTH_SECRET", "")
    settings.__dict__.pop("app_auth_secret", None)

    with pytest.raises(auth.AuthConfigurationError, match="APP_AUTH_SECRET"):
        auth.create_access_token({"sub": "user-1"})
    with pytest.raises(auth.AuthConfigurationError, match="APP_AUTH_SECRET"):
        auth.decode_access_token("any-token")


async def test_validate_id_token_accepts_valid_rs256_token(auth_env, rsa_key, jwks):
    token = _id_token(rsa_key, _claims())
    payload = await auth.validate_id_token(token)

    assert payload["sub"] == "user-1"
    assert payload["email"] == "user@example.test"


async def test_validate_id_token_requires_kid(auth_env, rsa_key, jwks):
    token = _id_token(rsa_key, _claims(), kid=None)
    with pytest.raises(auth.IDTokenValidationError) as exc_info:
        await auth.validate_id_token(token)

    assert exc_info.value.error_type == "missing_kid"


async def test_validate_id_token_reports_jwks_fetch_error(auth_env, rsa_key, monkeypatch):
    async def broken_get_jwks():
        raise Exception("网络不可用")

    monkeypatch.setattr(auth, "get_jwks", broken_get_jwks)
    token = _id_token(rsa_key, _claims())

    with pytest.raises(auth.IDTokenValidationError) as exc_info:
        await auth.validate_id_token(token)

    assert exc_info.value.error_type == "jwks_fetch_error"


async def test_validate_id_token_reports_key_not_found(auth_env, rsa_key, monkeypatch):
    other_key = _rsa_key()

    async def other_jwks():
        return {"keys": [_public_jwk(other_key, "kid-other")]}

    monkeypatch.setattr(auth, "get_jwks", other_jwks)
    token = _id_token(rsa_key, _claims())

    with pytest.raises(auth.IDTokenValidationError) as exc_info:
        await auth.validate_id_token(token)

    assert exc_info.value.error_type == "key_not_found"


async def test_validate_id_token_reports_key_conversion_error(auth_env, rsa_key, monkeypatch):
    async def incomplete_jwks():
        return {"keys": [{"kid": "kid-1"}]}  # 缺少 n/e

    monkeypatch.setattr(auth, "get_jwks", incomplete_jwks)
    token = _id_token(rsa_key, _claims())

    with pytest.raises(auth.IDTokenValidationError) as exc_info:
        await auth.validate_id_token(token)

    assert exc_info.value.error_type == "key_conversion_error"


async def test_validate_id_token_rejects_expired_token(auth_env, rsa_key, jwks):
    token = _id_token(rsa_key, _claims(exp=datetime.now(timezone.utc) - timedelta(minutes=5)))

    with pytest.raises(auth.IDTokenValidationError) as exc_info:
        await auth.validate_id_token(token)

    assert exc_info.value.error_type == "token_expired"


async def test_validate_id_token_rejects_foreign_signature(auth_env, rsa_key, jwks):
    token = _id_token(_rsa_key(), _claims())

    with pytest.raises(auth.IDTokenValidationError) as exc_info:
        await auth.validate_id_token(token)

    # python-jose 3.5 对 RS256 验签失败抛 JWTError（非 JWSSignatureError），故落到 jwt_error。
    assert exc_info.value.error_type == "jwt_error"


async def test_validate_id_token_rejects_wrong_issuer(auth_env, rsa_key, jwks):
    token = _id_token(rsa_key, _claims(iss="https://evil.example.test"))

    with pytest.raises(auth.IDTokenValidationError) as exc_info:
        await auth.validate_id_token(token)

    assert exc_info.value.error_type == "invalid_issuer"


async def test_validate_id_token_rejects_wrong_audience(auth_env, rsa_key, jwks):
    token = _id_token(rsa_key, _claims(aud="other-client"))

    with pytest.raises(auth.IDTokenValidationError) as exc_info:
        await auth.validate_id_token(token)

    assert exc_info.value.error_type == "invalid_audience"


async def test_validate_id_token_rejects_malformed_token(auth_env, jwks):
    with pytest.raises(auth.IDTokenValidationError) as exc_info:
        await auth.validate_id_token("not-a-jwt")

    assert exc_info.value.error_type == "jwt_error"


def test_build_authorization_url_contains_pkce_and_state(auth_env):
    url = auth.build_authorization_url(
        "state-1", "nonce-1", "challenge-1", redirect_uri="https://backend.example.test/api/v1/auth/callback"
    )
    params = parse_qs(urlparse(url).query)

    assert url.startswith(f"{ISSUER}/authorize?")
    assert params["client_id"] == [CLIENT_ID]
    assert params["response_type"] == ["code"]
    assert params["scope"] == ["openid profile email"]
    assert params["redirect_uri"] == ["https://backend.example.test/api/v1/auth/callback"]
    assert params["state"] == ["state-1"]
    assert params["nonce"] == ["nonce-1"]
    assert params["code_challenge"] == ["challenge-1"]
    assert params["code_challenge_method"] == ["S256"]


def test_build_authorization_url_without_pkce(auth_env):
    url = auth.build_authorization_url("state-1", "nonce-1")
    params = parse_qs(urlparse(url).query)

    assert "code_challenge" not in params
    assert "code_challenge_method" not in params
    assert params["redirect_uri"] == ["http://127.0.0.1:8000/api/v1/auth/callback"]


def test_build_logout_url_uses_frontend_and_optional_id_token(auth_env):
    url = auth.build_logout_url("id-token-1")
    params = parse_qs(urlparse(url).query)

    assert url.startswith(f"{ISSUER}/logout?")
    assert params["post_logout_redirect_uri"] == ["https://frontend.example.test/logout-callback"]
    assert params["id_token_hint"] == ["id-token-1"]

    without_hint = parse_qs(urlparse(auth.build_logout_url()).query)
    assert "id_token_hint" not in without_hint


class _FakeResponse:
    def __init__(self, payload):
        self._payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self._payload


class _FakeClient:
    def __init__(self, *, result=None, error=None):
        self._result = result
        self._error = error

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False

    async def get(self, url):
        if self._error is not None:
            raise self._error
        return self._result


def _patch_httpx(monkeypatch, *, result=None, error=None):
    monkeypatch.setattr(
        httpx, "AsyncClient", lambda **kwargs: _FakeClient(result=result, error=error)
    )


async def test_get_jwks_returns_provider_keys(auth_env, monkeypatch, rsa_key):
    _patch_httpx(monkeypatch, result=_FakeResponse({"keys": [_public_jwk(rsa_key, "kid-1")]}))
    data = await auth.get_jwks()

    assert data["keys"][0]["kid"] == "kid-1"


async def test_get_jwks_maps_timeout_to_error(auth_env, monkeypatch):
    _patch_httpx(monkeypatch, error=httpx.TimeoutException("timeout"))

    with pytest.raises(Exception, match="Unable to retrieve authentication keys"):
        await auth.get_jwks()


async def test_get_jwks_maps_http_status_error(auth_env, monkeypatch):
    request = httpx.Request("GET", f"{ISSUER}/.well-known/jwks.json")
    error = httpx.HTTPStatusError("status", request=request, response=httpx.Response(503, request=request))
    _patch_httpx(monkeypatch, error=error)

    with pytest.raises(Exception, match="Unable to retrieve authentication keys"):
        await auth.get_jwks()


async def test_get_jwks_maps_generic_error(auth_env, monkeypatch):
    _patch_httpx(monkeypatch, error=RuntimeError("boom"))

    with pytest.raises(Exception, match="Unable to retrieve authentication keys"):
        await auth.get_jwks()
