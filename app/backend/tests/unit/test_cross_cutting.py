"""后端-单元：P0 横切补强（令牌桶、路径白名单、请求体上限、安全响应头）。"""

import json
from typing import Any

import pytest

from core import error_codes
from core.body_limit import RequestBodyLimitMiddleware
from core.exceptions import PayloadTooLargeError
from core.rate_limit import (
    GLOBAL_RATE_LIMITER,
    RateLimiter,
    TokenBucket,
    is_generation_request,
    reset_rate_limiter,
)
from core.security_headers import SECURITY_HEADERS, SecurityHeadersMiddleware


# ---------- 令牌桶 ----------
def test_token_bucket_allows_capacity_then_rejects_with_retry_after():
    bucket = TokenBucket(capacity=3, window_seconds=60, now=100.0)
    assert bucket.consume(now=100.0) == (True, 0.0)
    assert bucket.consume(now=100.0) == (True, 0.0)
    assert bucket.consume(now=100.0) == (True, 0.0)

    allowed, retry_after = bucket.consume(now=100.0)
    assert allowed is False
    # 3 个/分钟 => 每 20 秒补 1 个。
    assert 19.9 <= retry_after <= 20.1


def test_token_bucket_refills_after_window_boundary():
    bucket = TokenBucket(capacity=1, window_seconds=60, now=0.0)
    assert bucket.consume(now=0.0)[0] is True
    assert bucket.consume(now=59.9)[0] is False
    assert bucket.consume(now=60.0)[0] is True


def test_rate_limiter_keys_are_isolated_per_user_and_ip():
    limiter = RateLimiter()
    assert limiter.consume("user:a", limit=1, window_seconds=60)[0] is True
    assert limiter.consume("user:a", limit=1, window_seconds=60)[0] is False
    assert limiter.consume("user:b", limit=1, window_seconds=60)[0] is True
    assert limiter.consume("ip:10.0.0.1", limit=1, window_seconds=60)[0] is True


def test_reset_rate_limiter_clears_global_state():
    GLOBAL_RATE_LIMITER.consume("user:x", limit=1, window_seconds=60)
    assert GLOBAL_RATE_LIMITER.consume("user:x", limit=1, window_seconds=60)[0] is False
    reset_rate_limiter()
    assert GLOBAL_RATE_LIMITER.consume("user:x", limit=1, window_seconds=60)[0] is True


@pytest.mark.parametrize(
    ("method", "path", "expected"),
    [
        ("POST", "/api/v1/studio/projects/1/plan", True),
        ("POST", "/api/v1/studio/projects/1/outline", True),
        ("POST", "/api/v1/studio/projects/1/artifact", True),
        ("POST", "/api/v1/studio/projects/1/artifact/edit", True),
        ("POST", "/api/v1/studio/projects/1/builds", True),
        ("POST", "/api/v1/studio/versions/9/run", True),
        ("POST", "/api/v1/user/ai-config/test", True),
        ("GET", "/api/v1/studio/projects/1/plan", False),
        ("POST", "/api/v1/studio/projects/1/restore", False),
        ("GET", "/api/v1/studio/projects/1/builds/abc/stream", False),
        ("GET", "/health", False),
        ("POST", "/api/v1/auth/login", False),
    ],
)
def test_generation_path_whitelist(method, path, expected):
    assert is_generation_request(method, path) is expected


# ---------- 请求体上限 ----------
def _http_scope(headers: list[tuple[bytes, bytes]] | None = None) -> dict[str, Any]:
    return {
        "type": "http",
        "method": "POST",
        "path": "/test",
        "headers": headers or [],
        "client": ("127.0.0.1", 12345),
    }


async def _read_all(scope, receive, send):
    while True:
        message = await receive()
        if message.get("type") == "http.disconnect":
            return
        if not message.get("more_body"):
            break
    await send({"type": "http.response.start", "status": 200, "headers": []})
    await send({"type": "http.response.body", "body": b"ok"})


def _sent(messages: list[dict[str, Any]]) -> tuple[int, dict[str, str], bytes]:
    start = next(item for item in messages if item["type"] == "http.response.start")
    headers = {key.decode().lower(): value.decode() for key, value in start["headers"]}
    body = b"".join(
        item.get("body", b"") for item in messages if item["type"] == "http.response.body"
    )
    return start["status"], headers, body


async def test_body_limit_rejects_declared_content_length(monkeypatch):
    monkeypatch.setenv("APP_MAX_REQUEST_BODY_BYTES", "64")
    messages: list[dict[str, Any]] = []

    async def send(message):
        messages.append(message)

    async def receive():
        return {"type": "http.request", "body": b"x" * 65, "more_body": False}

    middleware = RequestBodyLimitMiddleware(_read_all)
    await middleware(_http_scope([(b"content-length", b"65")]), receive, send)

    status, headers, body = _sent(messages)
    payload = json.loads(body)
    assert status == 413
    assert payload["code"] == error_codes.PAYLOAD_TOO_LARGE
    assert payload["message"] == error_codes.ERROR_MESSAGES[error_codes.PAYLOAD_TOO_LARGE]
    assert headers["content-type"].startswith("application/json")


async def test_body_limit_allows_exact_content_length(monkeypatch):
    monkeypatch.setenv("APP_MAX_REQUEST_BODY_BYTES", "64")
    messages: list[dict[str, Any]] = []

    async def send(message):
        messages.append(message)

    async def receive():
        return {"type": "http.request", "body": b"x" * 64, "more_body": False}

    middleware = RequestBodyLimitMiddleware(_read_all)
    await middleware(_http_scope([(b"content-length", b"64")]), receive, send)

    status, _, body = _sent(messages)
    assert status == 200
    assert body == b"ok"


async def test_body_limit_streams_and_rejects_without_content_length(monkeypatch):
    monkeypatch.setenv("APP_MAX_REQUEST_BODY_BYTES", "64")
    chunks = [
        {"type": "http.request", "body": b"x" * 40, "more_body": True},
        {"type": "http.request", "body": b"x" * 30, "more_body": False},
    ]

    async def receive():
        return chunks.pop(0)

    async def send(message):  # pragma: no cover - 超限发生在路由响应之前
        pass

    middleware = RequestBodyLimitMiddleware(_read_all)
    with pytest.raises(PayloadTooLargeError) as exc_info:
        await middleware(_http_scope(), receive, send)
    assert exc_info.value.code == error_codes.PAYLOAD_TOO_LARGE


async def test_body_limit_ignores_non_http_scope(monkeypatch):
    monkeypatch.setenv("APP_MAX_REQUEST_BODY_BYTES", "1")
    called = {"value": False}

    async def app(scope, receive, send):
        called["value"] = True

    await RequestBodyLimitMiddleware(app)({"type": "websocket"}, None, None)
    assert called["value"] is True


# ---------- 安全响应头 ----------
async def test_security_headers_are_added_without_overwriting():
    messages: list[dict[str, Any]] = []

    async def app(scope, receive, send):
        await send(
            {
                "type": "http.response.start",
                "status": 200,
                "headers": [(b"x-frame-options", b"SAMEORIGIN")],
            }
        )
        await send({"type": "http.response.body", "body": b"ok"})

    async def send(message):
        messages.append(message)

    await SecurityHeadersMiddleware(app)({"type": "http"}, None, send)

    status, headers, body = _sent(messages)
    assert status == 200
    assert body == b"ok"
    assert headers["x-frame-options"] == "SAMEORIGIN"
    for name, value in SECURITY_HEADERS:
        if name.lower() != "x-frame-options":
            assert headers[name.lower()] == value
