"""后端-集成-07：routers/auth.py 与 services/auth.py — 真实路由 + 真实 PostgreSQL。

OIDC 外部 HTTP 与 ID Token 校验使用替身；用户、OIDC state 的存取走真实服务与数据库。
"""
from datetime import datetime, timedelta, timezone
from urllib.parse import parse_qs, urlparse

import httpx
import pytest
from sqlalchemy import func, select

from core import auth as core_auth
from core.config import settings
from models.auth import OIDCState, User
from services.auth import AuthService
from testing import studio_app as host

API = "/api/v1/auth"

_ENV = {
    "JWT_SECRET_KEY": "integration-secret-key",
    "JWT_ALGORITHM": "HS256",
    "JWT_EXPIRE_MINUTES": "60",
    "OIDC_ISSUER_URL": "https://issuer.example.test",
    "OIDC_CLIENT_ID": "client-abc",
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


def _access_token(role: str = "user", **extra) -> str:
    claims = {"sub": "user-1", "email": "user@example.test", "name": "测试用户", "role": role}
    claims.update(extra)
    return core_auth.create_access_token(claims)


class _FakeResponse:
    def __init__(self, payload, status_code: int = 200):
        self._payload = payload
        self.status_code = status_code

    def json(self):
        if isinstance(self._payload, Exception):
            raise self._payload
        return self._payload

    @property
    def text(self) -> str:
        return str(self._payload)


class _FakeClient:
    def __init__(self, *, response=None, error=None):
        self._response = response
        self._error = error

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False

    async def post(self, url, json=None, data=None, headers=None):
        if self._error is not None:
            raise self._error
        return self._response


def _patch_oidc_http(monkeypatch, *, response=None, error=None):
    monkeypatch.setattr(httpx, "AsyncClient", lambda **kwargs: _FakeClient(response=response, error=error))


async def _count_users() -> int:
    async with host.sessions() as session:
        return await session.scalar(select(func.count()).select_from(User.__table__))


# ---------------------------------------------------------------- /me 与 /logout


async def test_me_requires_bearer_token(api_client, auth_env):
    response = await api_client.get(f"{API}/me")

    assert response.status_code == 401
    assert response.json()["detail"] == "Authentication credentials were not provided"


async def test_me_returns_token_claims(api_client, auth_env):
    login_time = datetime.now(timezone.utc).isoformat()
    token = _access_token(role="admin", last_login=login_time)
    response = await api_client.get(f"{API}/me", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 200
    body = response.json()
    assert body["id"] == "user-1"
    assert body["email"] == "user@example.test"
    assert body["role"] == "admin"
    assert body["last_login"] is not None


async def test_me_tolerates_unparsable_last_login(api_client, auth_env):
    token = _access_token(last_login="not-a-date")
    response = await api_client.get(f"{API}/me", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 200
    assert response.json()["last_login"] is None


async def test_me_rejects_invalid_token(api_client, auth_env):
    response = await api_client.get(f"{API}/me", headers={"Authorization": "Bearer invalid-token"})

    assert response.status_code == 401


async def test_logout_returns_provider_logout_url(api_client, auth_env):
    response = await api_client.get(f"{API}/logout")
    params = parse_qs(urlparse(response.json()["redirect_url"]).query)

    assert response.status_code == 200
    assert params["post_logout_redirect_uri"] == ["https://frontend.example.test/logout-callback"]


# --------------------------------------------------------------------- /login


async def test_login_redirects_with_pkce_and_persists_state(api_client, auth_env):
    response = await api_client.get(f"{API}/login")

    assert response.status_code == 302
    params = parse_qs(urlparse(response.headers["location"]).query)
    assert params["client_id"] == ["client-abc"]
    assert params["redirect_uri"] == ["https://test/api/v1/auth/callback"]
    assert params["code_challenge_method"] == ["S256"]
    assert params["code_challenge"][0] and params["state"][0] and params["nonce"][0]

    state = params["state"][0]
    async with host.sessions() as session:
        stored = await session.scalar(select(OIDCState).where(OIDCState.state == state))
    assert stored is not None
    assert stored.nonce == params["nonce"][0]
    assert core_auth.generate_code_challenge(stored.code_verifier) == params["code_challenge"][0]


# ------------------------------------------------------------- /token/exchange


async def test_token_exchange_issues_user_token(api_client, auth_env, monkeypatch):
    monkeypatch.setenv("ADMIN_USER_ID", "admin-1")
    settings.__dict__.pop("admin_user_id", None)
    _patch_oidc_http(
        monkeypatch,
        response=_FakeResponse(
            {"success": True, "data": {"user_id": "user-9", "email": "user9@example.test", "name": "用户九"}}
        ),
    )

    response = await api_client.post(f"{API}/token/exchange", json={"platform_token": "platform-token-1"})

    assert response.status_code == 200
    payload = core_auth.decode_access_token(response.json()["token"])
    assert payload["sub"] == "user-9"
    assert payload["role"] == "user"
    assert payload["name"] == "用户九"
    assert await _count_users() == 0  # 应用令牌发放不落库，用户由 OIDC 回调创建


async def test_token_exchange_grants_admin_role(api_client, auth_env, monkeypatch):
    monkeypatch.setenv("ADMIN_USER_ID", "user-9")
    settings.__dict__.pop("admin_user_id", None)
    monkeypatch.setenv("ADMIN_USER_EMAIL", "admin@example.test")
    settings.__dict__.pop("admin_user_email", None)
    _patch_oidc_http(monkeypatch, response=_FakeResponse({"success": True, "data": {"user_id": "user-9"}}))

    response = await api_client.post(f"{API}/token/exchange", json={"platform_token": "platform-token-2"})

    assert response.status_code == 200
    payload = core_auth.decode_access_token(response.json()["token"])
    assert payload["role"] == "admin"
    assert payload["email"] == "admin@example.test"


async def test_token_exchange_rejects_failed_verification(api_client, auth_env, monkeypatch):
    _patch_oidc_http(
        monkeypatch,
        response=_FakeResponse({"success": False, "message": "令牌无效"}, status_code=401),
    )

    response = await api_client.post(f"{API}/token/exchange", json={"platform_token": "bad-token"})

    assert response.status_code == 401
    assert response.json()["detail"] == "令牌无效"


async def test_token_exchange_rejects_non_json_response(api_client, auth_env, monkeypatch):
    _patch_oidc_http(monkeypatch, response=_FakeResponse(ValueError("not json")))
    response = await api_client.post(f"{API}/token/exchange", json={"platform_token": "token"})

    assert response.status_code == 502
    assert "Invalid response" in response.json()["detail"]


async def test_token_exchange_rejects_unexpected_body_type(api_client, auth_env, monkeypatch):
    _patch_oidc_http(monkeypatch, response=_FakeResponse(["unexpected"]))
    response = await api_client.post(f"{API}/token/exchange", json={"platform_token": "token"})

    assert response.status_code == 502
    assert "Unexpected response" in response.json()["detail"]


async def test_token_exchange_rejects_missing_user_id(api_client, auth_env, monkeypatch):
    _patch_oidc_http(monkeypatch, response=_FakeResponse({"success": True, "data": {}}))
    response = await api_client.post(f"{API}/token/exchange", json={"platform_token": "token"})

    assert response.status_code == 401
    assert "missing user_id" in response.json()["detail"]


async def test_token_exchange_maps_http_error_to_502(api_client, auth_env, monkeypatch):
    _patch_oidc_http(monkeypatch, error=httpx.ConnectError("连接失败"))
    response = await api_client.post(f"{API}/token/exchange", json={"platform_token": "token"})

    assert response.status_code == 502
    assert response.json()["detail"] == "Unable to verify platform token"


# ------------------------------------------------------------------ services/auth


async def test_auth_service_creates_and_updates_user(api_client, auth_env, monkeypatch):
    monkeypatch.delenv("ADMIN_USER_ID", raising=False)
    settings.__dict__.pop("admin_user_id", None)

    async with host.sessions() as session:
        service = AuthService(session)
        created = await service.get_or_create_user("platform-user-1", "first@example.test", "甲")

    assert created.id == "platform-user-1"
    assert created.role == "user"
    assert created.last_login is not None

    async with host.sessions() as session:
        service = AuthService(session)
        updated = await service.get_or_create_user("platform-user-1", "second@example.test", "乙")

    assert updated.email == "second@example.test"
    assert updated.name == "乙"
    assert updated.role == "user"
    assert await _count_users() == 1


async def test_auth_service_promotes_configured_admin(api_client, auth_env, monkeypatch):
    monkeypatch.setenv("ADMIN_USER_ID", "platform-admin")
    settings.__dict__.pop("admin_user_id", None)

    async with host.sessions() as session:
        service = AuthService(session)
        user = await service.get_or_create_user("platform-admin", "admin@example.test", "管理员")

    assert user.role == "admin"

    # 已存在用户再次登录时也会被提升为管理员。
    async with host.sessions() as session:
        service = AuthService(session)
        promoted = await service.get_or_create_user("platform-admin", "admin2@example.test", "管理员二")

    assert promoted.role == "admin"
    assert promoted.email == "admin2@example.test"


async def test_oidc_state_is_one_time_and_cleans_expired(api_client, auth_env):
    async with host.sessions() as session:
        service = AuthService(session)
        await service.store_oidc_state("state-live", "nonce-live", "verifier-live")
        session.add(
            OIDCState(
                state="state-expired",
                nonce="nonce-expired",
                code_verifier="verifier-expired",
                expires_at=datetime.now(timezone.utc) - timedelta(minutes=1),
            )
        )
        await session.commit()

        assert await service.get_and_delete_oidc_state("state-live") == {
            "nonce": "nonce-live",
            "code_verifier": "verifier-live",
        }
        assert await service.get_and_delete_oidc_state("state-live") is None

        remaining = await session.scalar(select(func.count()).select_from(OIDCState.__table__))
        assert remaining == 0  # 已用过与已过期的记录都被清理


async def test_issue_app_token_includes_user_claims(api_client, auth_env):
    login_time = datetime.now(timezone.utc)
    user = User(id="user-7", email="user7@example.test", name=None, role="user", last_login=login_time)

    async with host.sessions() as session:
        token, expires_at, claims = await AuthService(session).issue_app_token(user)

    payload = core_auth.decode_access_token(token)
    assert claims == {
        "sub": "user-7",
        "email": "user7@example.test",
        "role": "user",
        "last_login": login_time.isoformat(),
    }
    assert payload["sub"] == "user-7"
    assert "name" not in claims
    assert timedelta(minutes=59) < expires_at - datetime.now(timezone.utc) < timedelta(minutes=61)


async def test_issue_app_token_falls_back_on_invalid_expire_setting(api_client, auth_env, monkeypatch):
    monkeypatch.setenv("JWT_EXPIRE_MINUTES", "not-a-number")
    settings.__dict__.pop("jwt_expire_minutes", None)
    user = User(id="user-8", email="user8@example.test", name="八", role="admin")

    async with host.sessions() as session:
        _, expires_at, _ = await AuthService(session).issue_app_token(user)

    assert timedelta(minutes=59) < expires_at - datetime.now(timezone.utc) < timedelta(minutes=61)
