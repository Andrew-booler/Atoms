"""生成类接口限流：按登录用户 + 未登录 IP 双维度令牌桶。

只覆盖会触发 AI 生成或沙箱重跑的高成本接口；健康检查、SSE 已建立连接等
只读请求不在此列。阈值全部来自环境变量，生产可随时调整，不硬编码。

响应沿用 Phase 16 的错误契约：429 + ``RATE_LIMITED`` + 中文 message，并带
``Retry-After``（秒）。
"""

from __future__ import annotations

import json
import logging
import re
import time
from typing import Any, Callable

from core import error_codes
from core.environment import get_env_bool, get_env_int

logger = logging.getLogger(__name__)

#: 生成类接口路径白名单（方法固定为 POST）。重试（版本重跑）与编辑同样计入。
_GENERATION_PATH_PATTERNS = (
    re.compile(r"^/api/v1/studio/projects/[^/]+/plan$"),
    re.compile(r"^/api/v1/studio/projects/[^/]+/outline$"),
    re.compile(r"^/api/v1/studio/projects/[^/]+/artifact$"),
    re.compile(r"^/api/v1/studio/projects/[^/]+/artifact/edit$"),
    re.compile(r"^/api/v1/studio/projects/[^/]+/builds$"),
    re.compile(r"^/api/v1/studio/versions/[^/]+/run$"),
    re.compile(r"^/api/v1/user/ai-config/test$"),
)

#: 默认阈值：登录用户 10 次/分钟；未登录（含无效令牌）20 次/分钟/ IP。
_DEFAULT_USER_LIMIT = 10
_DEFAULT_IP_LIMIT = 20
_DEFAULT_WINDOW_SECONDS = 60

_MAX_BUCKETS = 5000


def is_generation_request(method: str, path: str) -> bool:
    """判断请求是否属于受限的生成类接口。"""
    if method.upper() != "POST":
        return False
    return any(pattern.match(path) for pattern in _GENERATION_PATH_PATTERNS)


class TokenBucket:
    """固定容量令牌桶：按时间线性补充，非整数令牌保留小数。"""

    def __init__(self, capacity: int, window_seconds: float, *, now: float | None = None) -> None:
        self.capacity = max(1, int(capacity))
        self.window_seconds = max(0.001, float(window_seconds))
        self.tokens = float(self.capacity)
        self.updated_at = time.monotonic() if now is None else now

    @property
    def refill_per_second(self) -> float:
        return self.capacity / self.window_seconds

    def consume(self, *, now: float | None = None) -> tuple[bool, float]:
        """尝试消耗 1 个令牌，返回 ``(是否允许, 建议重试秒数)``。"""
        current = time.monotonic() if now is None else now
        elapsed = max(0.0, current - self.updated_at)
        self.tokens = min(
            float(self.capacity), self.tokens + elapsed * self.refill_per_second
        )
        self.updated_at = current
        if self.tokens >= 1.0:
            self.tokens -= 1.0
            return True, 0.0
        deficit = 1.0 - self.tokens
        return False, max(0.0, deficit / self.refill_per_second)


class RateLimiter:
    """按 ``user_id`` / IP 保存令牌桶；配置变化时用独立键避免旧桶污染。"""

    def __init__(self) -> None:
        self._buckets: dict[str, TokenBucket] = {}

    def consume(
        self, key: str, *, limit: int, window_seconds: int, now: float | None = None
    ) -> tuple[bool, float]:
        bucket_key = f"{key}|{limit}|{window_seconds}"
        bucket = self._buckets.get(bucket_key)
        if bucket is None:
            bucket = TokenBucket(limit, window_seconds, now=now)
            self._buckets[bucket_key] = bucket
            self._prune(now=now, window_seconds=window_seconds)
        return bucket.consume(now=now)

    def reset(self) -> None:
        self._buckets.clear()

    def _prune(self, *, now: float | None, window_seconds: int) -> None:
        if len(self._buckets) <= _MAX_BUCKETS:
            return
        current = time.monotonic() if now is None else now
        stale_before = current - max(1, window_seconds) * 3
        self._buckets = {
            key: bucket
            for key, bucket in self._buckets.items()
            if bucket.updated_at >= stale_before
        }


#: 进程内单例；中间件与测试共用同一份状态。
GLOBAL_RATE_LIMITER = RateLimiter()


def reset_rate_limiter() -> None:
    """清空全部令牌桶（测试隔离用）。"""
    GLOBAL_RATE_LIMITER.reset()


def _headers(scope: dict[str, Any]) -> dict[str, str]:
    return {
        key.decode("latin-1").lower(): value.decode("latin-1")
        for key, value in scope.get("headers", [])
    }


def _resolve_identity(scope: dict[str, Any]) -> tuple[str, int]:
    """返回 ``(限流键, 阈值)``：有效令牌按用户，其余按客户端 IP。"""
    headers = _headers(scope)
    authorization = headers.get("authorization", "")
    token = ""
    if authorization.lower().startswith("bearer "):
        token = authorization[7:].strip()
    if token:
        try:
            from core.auth import decode_access_token

            payload = decode_access_token(token)
        except Exception:  # noqa: BLE001 - 无效令牌交给鉴权层返回 401
            payload = {}
        user_id = payload.get("sub") if isinstance(payload, dict) else None
        if user_id:
            limit = get_env_int(
                "APP_RATE_LIMIT_GENERATION_PER_MINUTE", default=_DEFAULT_USER_LIMIT
            )
            return f"user:{user_id}", max(1, limit)

    client = scope.get("client")
    ip = client[0] if client else "unknown"
    limit = get_env_int("APP_RATE_LIMIT_IP_PER_MINUTE", default=_DEFAULT_IP_LIMIT)
    return f"ip:{ip}", max(1, limit)


def _window_seconds() -> int:
    """固定 60 秒窗口；上下限通过 ``*_PER_MINUTE`` 环境变量按分钟调整。"""
    return _DEFAULT_WINDOW_SECONDS


async def _send_error(
    send: Callable[[dict[str, Any]], Any],
    *,
    status_code: int,
    code: str,
    headers: dict[str, str] | None = None,
) -> None:
    body = json.dumps(
        {"code": code, "message": error_codes.ERROR_MESSAGES[code]},
        ensure_ascii=False,
    ).encode("utf-8")
    response_headers = [
        (b"content-type", b"application/json; charset=utf-8"),
        (b"content-length", str(len(body)).encode("latin-1")),
    ]
    for key, value in (headers or {}).items():
        response_headers.append((key.encode("latin-1"), value.encode("latin-1")))
    await send(
        {"type": "http.response.start", "status": status_code, "headers": response_headers}
    )
    await send({"type": "http.response.body", "body": body})


class RateLimitMiddleware:
    """ASGI 中间件：在鉴权之前按用户/IP 做令牌桶预检。"""

    def __init__(self, app: Any) -> None:
        self.app = app

    async def __call__(self, scope: dict[str, Any], receive: Any, send: Any) -> None:
        if scope.get("type") != "http":
            await self.app(scope, receive, send)
            return

        method = str(scope.get("method") or "")
        path = str(scope.get("path") or "")
        if not is_generation_request(method, path):
            await self.app(scope, receive, send)
            return

        try:
            enabled = get_env_bool("APP_RATE_LIMIT_ENABLED", default=True)
        except ValueError as exc:
            logger.error("限流开关配置无效：%s", exc)
            enabled = True
        if not enabled:
            await self.app(scope, receive, send)
            return

        key, limit = _resolve_identity(scope)
        window = _window_seconds()
        allowed, retry_after = GLOBAL_RATE_LIMITER.consume(
            key, limit=limit, window_seconds=window
        )
        if not allowed:
            retry_seconds = max(1, int(retry_after) + (1 if retry_after % 1 else 0))
            logger.warning("触发生成接口限流：%s %s key=%s", method, path, key.split(":", 1)[0])
            await _send_error(
                send,
                status_code=429,
                code=error_codes.RATE_LIMITED,
                headers={"retry-after": str(retry_seconds)},
            )
            return

        await self.app(scope, receive, send)


__all__ = [
    "GLOBAL_RATE_LIMITER",
    "RateLimitMiddleware",
    "RateLimiter",
    "TokenBucket",
    "is_generation_request",
    "reset_rate_limiter",
]
