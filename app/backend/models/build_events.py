"""构建终端事件：一次构建（build_id）内按 seq 递增的结构化事件。

事件是纯追加日志，不修改既有 message/version 数据；user_id 用于多用户隔离。
"""
from datetime import datetime as PyDateTime
from typing import Optional

from sqlalchemy import DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from core.database import Base


class BuildEvent(Base):
    __tablename__ = "build_events"
    __table_args__ = {"extend_existing": True}

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True, autoincrement=True, nullable=False)
    user_id: Mapped[str] = mapped_column(String, index=True, nullable=False)
    project_id: Mapped[int] = mapped_column(Integer, index=True, nullable=False)
    build_id: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    seq: Mapped[int] = mapped_column(Integer, nullable=False)
    type: Mapped[str] = mapped_column(String(32), nullable=False)
    stage: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    data: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[Optional[PyDateTime]] = mapped_column(
        DateTime(timezone=True), default=PyDateTime.now
    )
