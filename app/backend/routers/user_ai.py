"""用户自选 AI 接入接口：全部要求登录，配置仅本人可见。"""
import logging
from typing import Optional

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from core import error_codes
from core.database import get_db
from core.exceptions import NotFoundError
from core.user_ai_crypto import decrypt_api_key
from dependencies.auth import get_current_user
from schemas.auth import UserResponse
from schemas.user_ai import (
    AIConfigDeleteResponse,
    AIConfigResponse,
    AIConfigTestRequest,
    AIConfigTestResponse,
    AIConfigUpsert,
)
from services import user_ai_config

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/user/ai-config", tags=["user-ai"])


@router.get("", response_model=AIConfigResponse)
async def read_config(
    current_user: UserResponse = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> AIConfigResponse:
    row = await user_ai_config.load_config(db, current_user.id)
    return AIConfigResponse(**user_ai_config.response_payload(row))


@router.put("", response_model=AIConfigResponse)
async def upsert_config(
    data: AIConfigUpsert,
    current_user: UserResponse = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> AIConfigResponse:
    row = await user_ai_config.save_config(
        db,
        current_user.id,
        base_url=data.base_url,
        api_key=data.api_key,
        model=data.model,
    )
    return AIConfigResponse(
        **user_ai_config.response_payload(row, message="已启用自选接入。")
    )


@router.delete("", response_model=AIConfigDeleteResponse)
async def clear_config(
    current_user: UserResponse = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> AIConfigDeleteResponse:
    deleted = await user_ai_config.delete_config(db, current_user.id)
    if not deleted:
        raise NotFoundError(error_codes.RESOURCE_NOT_FOUND)
    return AIConfigDeleteResponse(
        deleted=True, message="已清除自选接入，后续将使用系统默认供应商。"
    )


@router.post("/test", response_model=AIConfigTestResponse)
async def test_config(
    data: Optional[AIConfigTestRequest] = None,
    current_user: UserResponse = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> AIConfigTestResponse:
    """测试连通性：可传未保存的草稿，缺省时使用已保存配置。"""
    row = await user_ai_config.load_config(db, current_user.id)
    base_url = (data.base_url if data else None) or (row.base_url if row else None)
    model = (data.model if data else None) or (row.model if row else None)
    api_key = (data.api_key if data else None) or None
    if not api_key and row is not None:
        try:
            api_key = decrypt_api_key(row.api_key_encrypted)
        except ValueError:
            api_key = None
    if not base_url or not api_key or not model:
        raise NotFoundError(error_codes.RESOURCE_NOT_FOUND)

    ok, message, status_code, latency = await user_ai_config.probe_config(
        base_url, api_key, model
    )
    return AIConfigTestResponse(
        ok=ok, message=message, status_code=status_code, latency_ms=latency
    )
