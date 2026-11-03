"""邮箱/密码认证服务。不提供 OAuth 或平台令牌交换。"""
import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Tuple
from uuid import uuid4

from core import error_codes
from core.auth import create_access_token
from core.config import settings
from core.exceptions import AuthError, ConflictError
from core.password import hash_password, verify_password
from models.auth import User
from schemas.auth import UserResponse
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


def _now() -> datetime:
    return datetime.now(timezone.utc)


class AuthService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def register(self, email: str, password: str, name: str | None = None) -> User:
        """注册新用户；邮箱唯一，重复时返回 409 AUTH_EMAIL_TAKEN。"""
        normalized = email.strip().lower()
        existing = (
            await self.db.execute(select(User.id).where(User.email == normalized))
        ).scalar_one_or_none()
        if existing is not None:
            raise ConflictError(error_codes.AUTH_EMAIL_TAKEN)

        display_name = (name or "").strip() or normalized.split("@", 1)[0]
        user = User(
            id=uuid4().hex,
            email=normalized,
            name=display_name,
            role="user",
            password_hash=hash_password(password),
            is_legacy=False,
            last_login=_now(),
        )
        self.db.add(user)
        try:
            await self.db.commit()
        except IntegrityError as exc:
            # 并发注册同一邮箱时由唯一索引兜底。
            await self.db.rollback()
            raise ConflictError(error_codes.AUTH_EMAIL_TAKEN) from exc
        await self.db.refresh(user)
        return user

    async def authenticate(self, email: str, password: str) -> User:
        """校验邮箱与密码；失败统一返回 AUTH_INVALID_CREDENTIALS，不区分账号是否存在。"""
        normalized = email.strip().lower()
        user = (
            await self.db.execute(select(User).where(User.email == normalized))
        ).scalar_one_or_none()
        if user is None or not verify_password(password, user.password_hash):
            raise AuthError(error_codes.AUTH_INVALID_CREDENTIALS)

        user.last_login = _now()
        await self.db.commit()
        await self.db.refresh(user)
        return user

    async def issue_app_token(self, user: User) -> Tuple[str, datetime, Dict[str, Any]]:
        """签发 7 天访问令牌（无 refresh token，过期需重新登录）。"""
        try:
            expires_minutes = int(settings.app_auth_token_expire_minutes)
        except (TypeError, ValueError):
            expires_minutes = 10080
        expires_at = _now() + timedelta(minutes=expires_minutes)

        claims: Dict[str, Any] = {
            "sub": user.id,
            "email": user.email,
            "role": user.role,
        }
        if user.name:
            claims["name"] = user.name
        if user.last_login:
            claims["last_login"] = user.last_login.isoformat()
        return create_access_token(claims, expires_minutes=expires_minutes), expires_at, claims

    @staticmethod
    def to_response(user: User) -> UserResponse:
        return UserResponse(
            id=user.id,
            email=user.email,
            name=user.name,
            role=user.role,
            last_login=user.last_login,
        )
