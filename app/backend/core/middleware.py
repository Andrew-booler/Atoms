"""生产与测试共用的中间件装配。

顺序（由外到内）：安全响应头 → CORS → 请求体上限 → 限流。
- CORS 在限流/体积中间件之外，保证 413/429 等错误响应同样带 CORS 头，
  预检与错误响应行为一致。
- 安全头最外层，覆盖包括 CORS 预检在内的所有响应。
"""

from __future__ import annotations

import logging
import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from core.body_limit import RequestBodyLimitMiddleware
from core.environment import get_env_bool
from core.rate_limit import RateLimitMiddleware
from core.security_headers import SecurityHeadersMiddleware

logger = logging.getLogger(__name__)

#: 默认只允许本地开发前端（Vite 默认 3000 端口）。
_DEFAULT_CORS_ORIGINS = "http://localhost:3000,http://127.0.0.1:3000"


def cors_allowed_origins() -> list[str]:
    raw = os.environ.get("APP_CORS_ALLOWED_ORIGINS", _DEFAULT_CORS_ORIGINS)
    origins = [item.strip() for item in raw.split(",") if item.strip()]
    return origins


def configure_app_middlewares(app: FastAPI) -> None:
    """安装限流、体积上限、CORS 与安全头；必须在路由注册前调用。"""

    origins = cors_allowed_origins()
    allow_credentials = get_env_bool("APP_CORS_ALLOW_CREDENTIALS", default=True)
    if "*" in origins and allow_credentials:
        raise RuntimeError(
            "APP_CORS_ALLOWED_ORIGINS 不能包含 '*' 且同时启用凭据；请改为显式来源白名单。"
        )

    app.add_middleware(RateLimitMiddleware)
    app.add_middleware(RequestBodyLimitMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=allow_credentials,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type", "Accept", "X-Requested-With"],
        expose_headers=[
            "Retry-After",
            "X-RateLimit-Limit",
            "X-RateLimit-Remaining",
        ],
    )
    app.add_middleware(SecurityHeadersMiddleware)
    logger.info("已装配 CORS 白名单：%s", ", ".join(origins) or "(空)")


__all__ = ["configure_app_middlewares", "cors_allowed_origins"]
