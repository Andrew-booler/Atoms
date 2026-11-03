"""安全响应头中间件。

预览页面由沙箱容器在独立端口提供（``http://<SANDBOX_HOST>:<端口>/``），
与前端/后端应用不同源，也不是本应用返回的响应，因此这里给 API 与 SPA
加 ``X-Frame-Options: DENY`` 不会拦掉 iframe 预览。基于同一事实，不额外
下发 ``frame-ancestors``，避免与沙箱预览策略混淆。
"""

from __future__ import annotations

from typing import Any

SECURITY_HEADERS: tuple[tuple[str, str], ...] = (
    ("X-Content-Type-Options", "nosniff"),
    ("Referrer-Policy", "strict-origin-when-cross-origin"),
    ("X-Frame-Options", "DENY"),
    ("Permissions-Policy", "camera=(), microphone=(), geolocation=()"),
)


class SecurityHeadersMiddleware:
    """为所有 HTTP 响应补充安全头；已存在的同名头不覆盖。"""

    def __init__(self, app: Any) -> None:
        self.app = app

    async def __call__(self, scope: dict[str, Any], receive: Any, send: Any) -> None:
        if scope.get("type") != "http":
            await self.app(scope, receive, send)
            return

        async def send_with_headers(message: dict[str, Any]) -> None:
            if message.get("type") == "http.response.start":
                headers = message.setdefault("headers", [])
                existing = {
                    key.decode("latin-1").lower() for key, _ in headers
                }
                for name, value in SECURITY_HEADERS:
                    if name.lower() not in existing:
                        headers.append((name.encode("latin-1"), value.encode("latin-1")))
            await send(message)

        await self.app(scope, receive, send_with_headers)


__all__ = ["SECURITY_HEADERS", "SecurityHeadersMiddleware"]
