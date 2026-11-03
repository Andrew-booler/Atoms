"""用户自选 AI 配置：存取、加密、优先级与连通性探测。

- 配置按 user_id 唯一，密钥只以密文落库；
- 生成调用期间通过 ContextVar 把用户 provider 置为第一优先级，
  失败后 aihub 仍按系统默认链降级；
- 连通性探测只请求 /models，不发送消息体，不回显密钥。
"""
import logging
import time
from contextlib import asynccontextmanager
from typing import Any, AsyncIterator, Dict, Optional, Tuple

import httpx
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from core import error_codes
from core.exceptions import ValidationError
from core.user_ai_crypto import decrypt_api_key, encrypt_api_key, mask_api_key
from models.user_ai_config import UserAIConfig
from services import aihub
from services.aihub import ProviderConfig

logger = logging.getLogger(__name__)

USER_PROVIDER_NAME = "user_custom"
#: 测试注入点：单元/集成测试通过替换该 transport 保证零真实网络请求。
HTTP_TRANSPORT: Optional[httpx.AsyncBaseTransport] = None


async def load_config(db: AsyncSession, user_id: str) -> Optional[UserAIConfig]:
    return (
        await db.execute(select(UserAIConfig).where(UserAIConfig.user_id == user_id))
    ).scalar_one_or_none()


async def save_config(
    db: AsyncSession, user_id: str, *, base_url: str, api_key: str, model: str
) -> UserAIConfig:
    """新增或覆盖当前用户配置；密钥加密后落库。"""
    row = await load_config(db, user_id)
    encrypted = encrypt_api_key(api_key) if api_key.strip() else None
    if row is None:
        if encrypted is None:
            raise ValidationError(error_codes.INTERNAL_VALIDATION_FAILED)
        row = UserAIConfig(
            user_id=user_id,
            base_url=base_url,
            api_key_encrypted=encrypted,
            model=model,
        )
        db.add(row)
    else:
        row.base_url = base_url
        row.model = model
        if encrypted is not None:
            row.api_key_encrypted = encrypted
    await db.commit()
    await db.refresh(row)
    logger.info("用户 %s 更新了自选 AI 接入配置", user_id)
    return row


async def delete_config(db: AsyncSession, user_id: str) -> bool:
    result = await db.execute(delete(UserAIConfig).where(UserAIConfig.user_id == user_id))
    await db.commit()
    return bool(result.rowcount)


def response_payload(row: Optional[UserAIConfig], *, message: Optional[str] = None) -> Dict[str, Any]:
    """对外响应：只暴露掩码后的 key，绝不返回密文或明文。"""
    if row is None:
        return {"configured": False, "message": message}
    try:
        plain = decrypt_api_key(row.api_key_encrypted)
    except ValueError:
        # 密钥轮换后仍能展示配置存在，但掩码无法计算，避免回显密文。
        masked = "****"
    else:
        masked = mask_api_key(plain)
    return {
        "configured": True,
        "base_url": row.base_url,
        "model": row.model,
        "api_key_masked": masked,
        "updated_at": row.updated_at,
        "message": message,
    }


def to_provider(row: UserAIConfig) -> ProviderConfig:
    """把用户配置转成第一优先级 provider；密钥在此刻才解密到内存。"""
    return ProviderConfig(
        name=USER_PROVIDER_NAME,
        base_url=row.base_url,
        api_key=decrypt_api_key(row.api_key_encrypted),
        model=row.model,
        max_completion_tokens=None,
        max_concurrency=2,
        timeout=60.0,
        thinking_enabled=False,
    )


@asynccontextmanager
async def activate_user_provider(db: AsyncSession, user_id: str) -> AsyncIterator[Optional[ProviderConfig]]:
    """请求内激活用户自选 provider：优先调用它，失败再走系统默认链。"""
    row = await load_config(db, user_id)
    provider: Optional[ProviderConfig] = None
    if row is not None:
        try:
            provider = to_provider(row)
        except ValueError:
            logger.warning("用户 %s 的自选 AI 密钥无法解密，本次回退系统默认", user_id)
    token = aihub.set_user_provider(provider)
    try:
        yield provider
    finally:
        aihub.reset_user_provider(token)


def _test_failure_message(status_code: Optional[int], exc: Optional[Exception]) -> str:
    """把连通性失败映射为可定位的中文提示，不包含密钥或请求体。"""
    if isinstance(exc, httpx.TimeoutException):
        return "连接超时，请检查网络或 Base URL 是否可达。"
    if isinstance(exc, httpx.ConnectError):
        return "无法连接到服务，请检查 Base URL 与网络。"
    if status_code == 401:
        return "API Key 无效或已过期（401），请重新填写。"
    if status_code == 403:
        return "API Key 无权访问该服务（403），请检查账号权限。"
    if status_code == 404:
        return "接口地址不存在（404），请检查 Base URL 是否包含正确的版本路径。"
    if status_code == 429:
        return "请求过于频繁（429），请稍后重试。"
    if status_code:
        return f"服务返回异常状态（{status_code}），请检查 Base URL 与模型配置。"
    return "连通性测试失败，请检查 Base URL、API Key 与网络。"


async def probe_config(
    base_url: str, api_key: str, model: str, *, timeout: float = 10.0
) -> Tuple[bool, str, Optional[int], int]:
    """用 GET /models 做轻量探测；只带鉴权头，不发送提示词或请求体。"""
    started = time.monotonic()
    status_code: Optional[int] = None
    exc: Optional[Exception] = None
    url = f"{base_url.rstrip('/')}/models"
    try:
        async with httpx.AsyncClient(timeout=timeout, transport=HTTP_TRANSPORT) as client:
            response = await client.get(url, headers={"Authorization": f"Bearer {api_key}"})
        status_code = response.status_code
    except Exception as failure:  # noqa: BLE001 - 只用于分类提示
        exc = failure
        logger.warning("自选 AI 连通性测试失败：%s", type(failure).__name__)

    latency = int((time.monotonic() - started) * 1000)
    if status_code is not None and 200 <= status_code < 300:
        return True, f"连接成功，模型 {model} 可用。", status_code, latency
    return False, _test_failure_message(status_code, exc), status_code, latency
