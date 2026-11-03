"""用户自选 AI 接入的请求/响应形状。"""
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field, field_validator


def _normalize_base_url(value: str) -> str:
    url = value.strip().rstrip("/")
    if not url.startswith(("http://", "https://")):
        raise ValueError("Base URL 必须以 http:// 或 https:// 开头")
    return url


class AIConfigUpsert(BaseModel):
    base_url: str = Field(min_length=1, max_length=500)
    # 留空表示沿用已保存的密钥；首次配置必须填写。
    api_key: str = Field(default="", max_length=500)
    model: str = Field(min_length=1, max_length=200)

    @field_validator("base_url")
    @classmethod
    def _validate_base_url(cls, value: str) -> str:
        return _normalize_base_url(value)

    @field_validator("model")
    @classmethod
    def _validate_model(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("模型名称不能为空")
        return cleaned


class AIConfigTestRequest(BaseModel):
    """可测试尚未保存的配置；字段缺省时回退到已保存配置。"""

    base_url: Optional[str] = None
    api_key: Optional[str] = None
    model: Optional[str] = None

    @field_validator("base_url")
    @classmethod
    def _validate_base_url(cls, value: Optional[str]) -> Optional[str]:
        return _normalize_base_url(value) if value else None


class AIConfigResponse(BaseModel):
    configured: bool
    base_url: Optional[str] = None
    model: Optional[str] = None
    api_key_masked: Optional[str] = None
    updated_at: Optional[datetime] = None
    message: Optional[str] = None


class AIConfigDeleteResponse(BaseModel):
    deleted: bool
    message: str


class AIConfigTestResponse(BaseModel):
    ok: bool
    message: str
    status_code: Optional[int] = None
    latency_ms: Optional[int] = None
