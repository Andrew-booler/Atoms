"""后端-单元-13：core/auth.py — 应用 JWT 的签发与校验。

OIDC 登录路径已移除，本文件只覆盖仍在使用的 HS256 访问令牌。
"""
import base64
import json

import pytest

from core import auth
from core.config import settings

_SECRET = "unit-secret-key"


@pytest.fixture
def auth_env(monkeypatch):
    monkeypatch.setattr(settings, "app_auth_secret", _SECRET)


def _b64url(data: dict) -> str:
    raw = json.dumps(data, separators=(",", ":")).encode("utf-8")
    return base64.urlsafe_b64encode(raw).decode("utf-8").rstrip("=")


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
    monkeypatch.setattr(settings, "app_auth_secret", None)

    with pytest.raises(auth.AuthConfigurationError, match="APP_AUTH_SECRET"):
        auth.create_access_token({"sub": "user-1"})
    with pytest.raises(auth.AuthConfigurationError, match="APP_AUTH_SECRET"):
        auth.decode_access_token("any-token")
