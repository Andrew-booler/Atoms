"""认证路由：仅邮箱/密码注册与登录，不提供 OAuth 或平台令牌交换。"""
import logging

from core.database import get_db
from dependencies.auth import get_current_user
from fastapi import APIRouter, Depends, status
from schemas.auth import (
    AuthResponse,
    LoginRequest,
    RegisterRequest,
    UserResponse,
)
from services.auth import AuthService
from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter(prefix="/api/v1/auth", tags=["authentication"])
logger = logging.getLogger(__name__)


@router.post("/register", response_model=AuthResponse, status_code=status.HTTP_201_CREATED)
async def register(payload: RegisterRequest, db: AsyncSession = Depends(get_db)) -> AuthResponse:
    """注册并直接返回访问令牌，避免二次登录。"""
    service = AuthService(db)
    user = await service.register(payload.email, payload.password, payload.name)
    token, expires_at, _ = await service.issue_app_token(user)
    logger.info("用户注册成功 id=%s", user.id)
    return AuthResponse(token=token, expires_at=expires_at, user=service.to_response(user))


@router.post("/login", response_model=AuthResponse)
async def login(payload: LoginRequest, db: AsyncSession = Depends(get_db)) -> AuthResponse:
    """邮箱 + 密码登录，返回 7 天有效的 Bearer Token。"""
    service = AuthService(db)
    user = await service.authenticate(payload.email, payload.password)
    token, expires_at, _ = await service.issue_app_token(user)
    return AuthResponse(token=token, expires_at=expires_at, user=service.to_response(user))


@router.get("/me", response_model=UserResponse)
async def get_current_user_info(current_user: UserResponse = Depends(get_current_user)) -> UserResponse:
    """返回当前登录用户。"""
    return current_user


@router.post("/logout")
async def logout() -> dict:
    """无状态退出：客户端清除本地令牌即可，服务端不维护会话。"""
    return {"ok": True, "message": "已退出登录。"}
