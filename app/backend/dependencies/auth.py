"""认证依赖：从 Bearer Token 解析当前用户，并强制查库确认用户仍存在。"""
import logging
from typing import Optional

from core import error_codes
from core.auth import AccessTokenError, AuthConfigurationError, decode_access_token
from core.database import get_db
from core.exceptions import AuthError
from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from models.auth import User
from schemas.auth import UserResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)

bearer_scheme = HTTPBearer(auto_error=False)


def _user_response(user: User) -> UserResponse:
    return UserResponse(
        id=user.id,
        email=user.email,
        name=user.name,
        role=user.role,
        last_login=user.last_login,
    )


async def _load_user(db: AsyncSession, user_id: str) -> User:
    user = (
        await db.execute(select(User).where(User.id == user_id))
    ).scalar_one_or_none()
    if user is None:
        # 令牌有效但用户已被删除：视为令牌失效。
        raise AuthError(error_codes.AUTH_INVALID_TOKEN)
    return user


async def get_bearer_token(
    request: Request, credentials: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme)
) -> str:
    if credentials and credentials.scheme.lower() == "bearer":
        return credentials.credentials
    logger.debug("Authentication required for request %s %s", request.method, request.url.path)
    raise AuthError(error_codes.AUTH_REQUIRED)


async def _authenticate(token: str, db: AsyncSession) -> UserResponse:
    """校验令牌并确认用户仍存在；细节错误码保持一致。"""
    if not token.strip():
        raise AuthError(error_codes.AUTH_REQUIRED)
    try:
        payload = decode_access_token(token)
    except AuthConfigurationError:
        logger.error("APP_AUTH_SECRET 未配置，无法校验访问令牌")
        raise AuthError(error_codes.AUTH_INVALID_TOKEN)
    except AccessTokenError as exc:
        code = error_codes.AUTH_TOKEN_EXPIRED if exc.expired else error_codes.AUTH_INVALID_TOKEN
        logger.warning("Token validation failed: %s", type(exc).__name__)
        raise AuthError(code) from exc

    user_id = payload.get("sub")
    if not user_id:
        raise AuthError(error_codes.AUTH_INVALID_TOKEN)
    return _user_response(await _load_user(db, str(user_id)))


async def get_current_user(
    token: str = Depends(get_bearer_token),
    db: AsyncSession = Depends(get_db),
) -> UserResponse:
    """必需登录：令牌无效 401，过期返回 AUTH_TOKEN_EXPIRED。"""
    return await _authenticate(token, db)


async def get_stream_user(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme),
    db: AsyncSession = Depends(get_db),
) -> UserResponse:
    """SSE 场景：优先 Authorization 头，浏览器原生 EventSource 可用 access_token 查询参数。

    校验逻辑与 get_current_user 完全相同，不引入新的令牌类型。
    """
    token = credentials.credentials if credentials and credentials.scheme.lower() == "bearer" else ""
    if not token:
        token = (request.query_params.get("access_token") or "").strip()
    return await _authenticate(token, db)


async def get_admin_user(current_user: UserResponse = Depends(get_current_user)) -> UserResponse:
    if current_user.role != "admin":
        raise AuthError(error_codes.AUTH_FORBIDDEN, http_status=403)
    return current_user
