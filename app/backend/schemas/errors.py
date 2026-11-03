"""统一错误响应契约。"""

from typing import Any

from pydantic import BaseModel, Field


class ErrorResponse(BaseModel):
    code: str = Field(..., description="DOMAIN_REASON 错误码，一码一义")
    message: str = Field(..., description="用户可直接阅读的中文提示")
    details: dict[str, Any] | None = Field(default=None, description="结构化辅助信息（已脱敏）")
