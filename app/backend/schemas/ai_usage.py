"""AI 用量统计的响应形状。token 字段为 None 表示“未统计”，不是 0。"""
from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel


class UsageTotals(BaseModel):
    calls: int
    prompt_tokens: Optional[int] = None
    completion_tokens: Optional[int] = None
    reasoning_tokens: Optional[int] = None
    total_tokens: Optional[int] = None
    has_data: bool


class ProviderUsage(UsageTotals):
    provider: str


class WindowUsage(BaseModel):
    totals: UsageTotals
    providers: List[ProviderUsage]


class BuildUsage(BaseModel):
    build_id: str
    recorded_at: Optional[datetime] = None
    totals: UsageTotals
    providers: List[ProviderUsage]


class AIUsageResponse(BaseModel):
    today: WindowUsage
    last_7_days: WindowUsage
    total: WindowUsage
    latest_build: Optional[BuildUsage] = None
    generated_at: datetime
