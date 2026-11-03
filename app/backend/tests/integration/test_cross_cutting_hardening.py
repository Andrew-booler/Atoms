"""后端-集成：P0 横切补强的真实 ASGI 行为（429/413/CORS/安全响应头）。"""
import pytest

from core import error_codes
from core.rate_limit import reset_rate_limiter

API = "/api/v1/studio"
ALLOWED_ORIGIN = "http://localhost:3000"


@pytest.fixture()
def low_generation_limit(monkeypatch):
    """把生成接口阈值临时降到 2 次/分钟，并在用例前后清空令牌桶。"""
    monkeypatch.setenv("APP_RATE_LIMIT_GENERATION_PER_MINUTE", "2")
    reset_rate_limiter()
    yield
    reset_rate_limiter()


async def test_generation_rate_limit_returns_429_with_contract(client, low_generation_limit):
    project = (
        await client.post(f"{API}/projects", json={"name": "限流", "description": ""})
    ).json()

    for _ in range(2):
        response = await client.post(f"{API}/projects/{project['id']}/builds")
        assert response.status_code == 201

    blocked = await client.post(f"{API}/projects/{project['id']}/builds")
    assert blocked.status_code == 429
    body = blocked.json()
    assert body["code"] == error_codes.RATE_LIMITED
    assert body["message"] == error_codes.ERROR_MESSAGES[error_codes.RATE_LIMITED]
    assert int(blocked.headers["retry-after"]) >= 1


async def test_oversized_body_returns_413_with_cors_header(client, monkeypatch):
    monkeypatch.setenv("APP_MAX_REQUEST_BODY_BYTES", "64")
    project = (
        await client.post(f"{API}/projects", json={"name": "体积", "description": ""})
    ).json()

    response = await client.post(
        f"{API}/projects/{project['id']}/messages",
        json={"role": "user", "kind": "requirement", "content": "x" * 200},
        headers={"Origin": ALLOWED_ORIGIN},
    )
    assert response.status_code == 413
    body = response.json()
    assert body["code"] == error_codes.PAYLOAD_TOO_LARGE
    assert body["message"] == error_codes.ERROR_MESSAGES[error_codes.PAYLOAD_TOO_LARGE]
    # 预检与错误响应一致：413 同样经 CORS 中间件带上允许来源。
    assert response.headers["access-control-allow-origin"] == ALLOWED_ORIGIN


async def test_security_headers_present_on_success_and_error(client, monkeypatch):
    monkeypatch.setenv("APP_MAX_REQUEST_BODY_BYTES", "64")

    ok = await client.get(f"{API}/projects")
    assert ok.headers["x-content-type-options"] == "nosniff"
    assert ok.headers["referrer-policy"] == "strict-origin-when-cross-origin"
    assert ok.headers["x-frame-options"] == "DENY"

    too_large = await client.post(
        f"{API}/projects/1/messages",
        json={"role": "user", "kind": "requirement", "content": "x" * 200},
    )
    assert too_large.status_code == 413
    assert too_large.headers["x-content-type-options"] == "nosniff"
    assert too_large.headers["x-frame-options"] == "DENY"


async def test_health_is_not_rate_limited(api_client, monkeypatch):
    monkeypatch.setenv("APP_RATE_LIMIT_IP_PER_MINUTE", "1")
    reset_rate_limiter()
    for _ in range(3):
        response = await api_client.get("/database/health")
        assert response.status_code == 200
    reset_rate_limiter()


async def test_cors_allowed_origin_and_disallowed_origin(api_client):
    allowed = await api_client.get("/health", headers={"Origin": ALLOWED_ORIGIN})
    assert allowed.headers["access-control-allow-origin"] == ALLOWED_ORIGIN
    assert allowed.headers["access-control-allow-credentials"] == "true"

    blocked = await api_client.get("/health", headers={"Origin": "http://evil.example"})
    assert "access-control-allow-origin" not in blocked.headers


async def test_cors_preflight_and_error_response_are_consistent(api_client):
    preflight = await api_client.options(
        "/api/v1/user/ai-config",
        headers={
            "Origin": ALLOWED_ORIGIN,
            "Access-Control-Request-Method": "PUT",
            "Access-Control-Request-Headers": "authorization,content-type",
        },
    )
    assert preflight.status_code == 200
    assert preflight.headers["access-control-allow-origin"] == ALLOWED_ORIGIN
    assert preflight.headers["access-control-allow-credentials"] == "true"

    unauthorized = await api_client.post(
        "/api/v1/user/ai-config/test", headers={"Origin": ALLOWED_ORIGIN}
    )
    assert unauthorized.status_code == 401
    assert unauthorized.headers["access-control-allow-origin"] == ALLOWED_ORIGIN
    assert unauthorized.json()["code"] == error_codes.AUTH_REQUIRED
