"""用户 AI 用量统计接口：要求登录，只返回本人数据。"""
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import get_db
from dependencies.auth import get_current_user
from schemas.ai_usage import AIUsageResponse
from schemas.auth import UserResponse
from services import ai_usage_store

router = APIRouter(prefix="/api/v1/user", tags=["user-usage"])


@router.get("/ai-usage", response_model=AIUsageResponse)
async def read_ai_usage(
    current_user: UserResponse = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> AIUsageResponse:
    """今日 / 近 7 天 / 累计用量与 provider 分布；数据按 user_id 隔离。"""
    payload = await ai_usage_store.collect(db, user_id=current_user.id)
    return AIUsageResponse(**payload)
