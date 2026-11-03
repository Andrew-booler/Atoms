"""AI 调用用量记录：每次真实返回 usage 的调用一行。

token 字段允许为 NULL：模拟输出或供应商未返回 usage 时显式记录 NULL，
绝不伪造 0 值。user_id + build_id 用于按用户/构建聚合与隔离。
"""
from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from core.database import Base


class AiUsageRecord(Base):
    __tablename__ = "ai_usage_records"
    __table_args__ = {"extend_existing": True}

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(String(255), index=True, nullable=False)
    build_id: Mapped[Optional[str]] = mapped_column(String(64), index=True, nullable=True)
    stage: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    provider: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    prompt_tokens: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    completion_tokens: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    reasoning_tokens: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    created_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), default=datetime.now, index=True
    )
