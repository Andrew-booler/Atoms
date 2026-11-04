import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

from core.config import settings

logger = logging.getLogger(__name__)


class AuthConfigurationError(RuntimeError):
    """认证配置缺失。启动阶段抛出，避免静默使用随机密钥。"""


class AccessTokenError(Exception):
    """应用 JWT 校验失败；expired 用于区分过期与无效。"""

    def __init__(self, message: str, expired: bool = False):
        self.message = message
        self.expired = expired
        super().__init__(self.message)


def get_auth_secret() -> str:
    """读取 APP_AUTH_SECRET；缺失时直接报错，绝不回退到随机密钥。"""
    secret = (settings.app_auth_secret or "").strip()
    if not secret:
        raise AuthConfigurationError("APP_AUTH_SECRET 未配置，认证服务无法启动。")
    return secret


def ensure_auth_configured() -> None:
    """启动自检：认证密钥缺失时让进程启动失败。"""
    get_auth_secret()


def create_access_token(claims: Dict[str, Any], expires_minutes: Optional[int] = None) -> str:
    """Create signed JWT access token from provided claims."""
    secret = get_auth_secret()

    now = datetime.now(timezone.utc)
    token_claims = claims.copy()

    default_minutes = settings.app_auth_token_expire_minutes
    try:
        default_minutes = int(default_minutes)
    except (TypeError, ValueError):
        default_minutes = 10080
    expiry_minutes = expires_minutes if expires_minutes is not None else default_minutes
    expire_at = now + timedelta(minutes=expiry_minutes)

    token_claims.update(
        {
            "exp": expire_at,
            "iat": now,
            "nbf": now,
        }
    )

    from jose import jwt

    token = jwt.encode(token_claims, secret, algorithm="HS256")
    return token


def decode_access_token(token: str) -> Dict[str, Any]:
    """Decode and validate JWT access token."""
    secret = get_auth_secret()

    from jose import JWTError, jwt
    from jose.exceptions import ExpiredSignatureError

    try:
        payload = jwt.decode(token, secret, algorithms=["HS256"])
        return payload
    except ExpiredSignatureError as exc:
        logger.info("Authentication token has expired")
        raise AccessTokenError("Token has expired", expired=True) from exc
    except JWTError as exc:
        # Log error type only, not the full exception which may contain sensitive token data
        logger.warning("Token validation failed: %s", type(exc).__name__)
        raise AccessTokenError("Invalid authentication token") from exc

