"""后端-接口-认证：注册、登录、当前用户、退出与历史账户边界。

全部使用真实 PostgreSQL（studio_test_api schema），不触发任何真实 AI 调用。
"""
from datetime import datetime, timedelta, timezone

import pytest

from core.auth import create_access_token
from models.auth import User
from testing import studio_app as host

API = "/api/v1/auth"


async def _register(api_client, email="alice@example.test", password="password123", name="Alice"):
    return await api_client.post(
        f"{API}/register",
        json={"email": email, "password": password, "name": name},
    )


async def test_register_returns_token_and_user(api_client):
    response = await _register(api_client, email="Alice@Example.test")

    assert response.status_code == 201
    body = response.json()
    assert body["token_type"] == "Bearer"
    assert body["user"]["email"] == "alice@example.test"
    assert body["user"]["name"] == "Alice"
    assert body["user"]["role"] == "user"
    assert {"id", "email", "role"} <= set(body["user"])
    assert body["expires_at"]

    # 注册即登录：返回令牌可直接访问 /me。
    me = await api_client.get(f"{API}/me", headers={"Authorization": f"Bearer {body['token']}"})
    assert me.status_code == 200
    assert me.json()["email"] == "alice@example.test"


async def test_access_token_lifetime_is_seven_days(api_client):
    response = await _register(api_client)
    expires_at = datetime.fromisoformat(response.json()["expires_at"])
    remaining = expires_at - datetime.now(timezone.utc)

    assert timedelta(days=6, hours=23) < remaining <= timedelta(days=7, minutes=1)


async def test_register_duplicate_email_returns_409(api_client):
    assert (await _register(api_client)).status_code == 201

    duplicate = await _register(api_client)

    assert duplicate.status_code == 409
    body = duplicate.json()
    assert body["code"] == "AUTH_EMAIL_TAKEN"
    assert body["message"] == "该邮箱已被注册，请直接登录或更换邮箱。"


@pytest.mark.parametrize("email", ["not-an-email", "missing-domain@", "@missing-local"])
async def test_register_rejects_invalid_email(api_client, email):
    response = await _register(api_client, email=email)
    assert response.status_code == 422
    assert response.json()["code"] == "INTERNAL_VALIDATION_FAILED"


async def test_register_rejects_short_password(api_client):
    response = await _register(api_client, password="short")
    assert response.status_code == 422


async def test_login_succeeds_with_correct_credentials(api_client):
    await _register(api_client)

    response = await api_client.post(
        f"{API}/login",
        json={"email": "ALICE@EXAMPLE.TEST", "password": "password123"},
    )

    assert response.status_code == 200
    assert response.json()["user"]["email"] == "alice@example.test"


async def test_login_wrong_password_is_generic_401(api_client):
    await _register(api_client)

    response = await api_client.post(
        f"{API}/login",
        json={"email": "alice@example.test", "password": "wrong-password"},
    )

    assert response.status_code == 401
    body = response.json()
    assert body["code"] == "AUTH_INVALID_CREDENTIALS"
    assert body["message"] == "邮箱或密码不正确，请检查后重试。"


async def test_login_unknown_email_is_generic_401(api_client):
    response = await api_client.post(
        f"{API}/login",
        json={"email": "nobody@example.test", "password": "password123"},
    )

    assert response.status_code == 401
    assert response.json()["code"] == "AUTH_INVALID_CREDENTIALS"


async def test_legacy_user_cannot_login(api_client):
    async with host.sessions() as session:
        session.add(
            User(
                id="legacy",
                email="legacy@atoms.local",
                name="历史共享数据",
                role="user",
                password_hash=None,
                is_legacy=True,
            )
        )
        await session.commit()

    response = await api_client.post(
        f"{API}/login",
        json={"email": "legacy@atoms.local", "password": "anything"},
    )

    assert response.status_code == 401
    assert response.json()["code"] == "AUTH_INVALID_CREDENTIALS"


async def test_me_requires_token(api_client):
    response = await api_client.get(f"{API}/me")
    assert response.status_code == 401
    assert response.json()["code"] == "AUTH_REQUIRED"


async def test_me_rejects_invalid_token(api_client):
    response = await api_client.get(
        f"{API}/me", headers={"Authorization": "Bearer not-a-real-token"}
    )
    assert response.status_code == 401
    assert response.json()["code"] == "AUTH_INVALID_TOKEN"


async def test_me_reports_expired_token(api_client):
    token = create_access_token({"sub": host.TEST_USER_ID}, expires_minutes=-1)

    response = await api_client.get(
        f"{API}/me", headers={"Authorization": f"Bearer {token}"}
    )

    assert response.status_code == 401
    assert response.json()["code"] == "AUTH_TOKEN_EXPIRED"


async def test_logout_is_stateless(api_client):
    response = await api_client.post(f"{API}/logout")
    assert response.status_code == 200
    assert response.json() == {"ok": True, "message": "已退出登录。"}
