"""请求体上限中间件：Content-Length 预检 + 流式累计双保险。

超限统一抛出 ``PayloadTooLargeError``（413 / ``PAYLOAD_TOO_LARGE``），
由全局异常处理器输出 Phase 16 的中文错误契约。默认上限来自环境变量
``APP_MAX_REQUEST_BODY_BYTES``，可按部署环境调整。
"""

from __future__ import annotations

import json
from typing import Any, Callable

from core import error_codes
from core.environment import get_env_int
from core.exceptions import PayloadTooLargeError

#: 默认 4 MiB，远高于正常 HTML 产物与消息请求，仍能挡住恶意超大请求。
_DEFAULT_MAX_BYTES = 4 * 1024 * 1024


def max_body_bytes() -> int:
    return get_env_int("APP_MAX_REQUEST_BODY_BYTES", default=_DEFAULT_MAX_BYTES)


def _content_length(scope: dict[str, Any]) -> int | None:
    for key, value in scope.get("headers", []):
        if key.decode("latin-1").lower() == "content-length":
            try:
                return int(value.decode("latin-1").strip())
            except ValueError:
                return None
    return None


async def _send_too_large(send: Callable[[dict[str, Any]], Any]) -> None:
    code = error_codes.PAYLOAD_TOO_LARGE
    body = json.dumps(
        {"code": code, "message": error_codes.ERROR_MESSAGES[code]},
        ensure_ascii=False,
    ).encode("utf-8")
    await send(
        {
            "type": "http.response.start",
            "status": 413,
            "headers": [
                (b"content-type", b"application/json; charset=utf-8"),
                (b"content-length", str(len(body)).encode("latin-1")),
            ],
        }
    )
    await send({"type": "http.response.body", "body": body})


class RequestBodyLimitMiddleware:
    """ASGI 中间件：在路由与鉴权之前拒绝超限请求体。"""

    def __init__(self, app: Any) -> None:
        self.app = app

    async def __call__(self, scope: dict[str, Any], receive: Any, send: Any) -> None:
        if scope.get("type") != "http":
            await self.app(scope, receive, send)
            return

        limit = max_body_bytes()
        if limit <= 0:
            await self.app(scope, receive, send)
            return

        declared = _content_length(scope)
        if declared is not None and declared > limit:
            await _send_too_large(send)
            return

        received = 0

        async def limited_receive() -> dict[str, Any]:
            nonlocal received
            message = await receive()
            if message.get("type") == "http.request":
                received += len(message.get("body") or b"")
                if received > limit:
                    raise PayloadTooLargeError(error_codes.PAYLOAD_TOO_LARGE)
            return message

        await self.app(scope, limited_receive, send)


__all__ = ["RequestBodyLimitMiddleware", "max_body_bytes"]
