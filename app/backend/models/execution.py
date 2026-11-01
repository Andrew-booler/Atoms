"""执行层运行态记录：记录每个沙箱容器的生命周期。"""
from datetime import datetime as PyDateTime
from typing import Optional

from core.database import Base
from sqlalchemy import DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column


class Execution(Base):
    """一次沙箱运行记录。状态：running / stopped / failed / expired。"""

    __tablename__ = "executions"
    __table_args__ = {"extend_existing": True}

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True, autoincrement=True, nullable=False)
    version_id: Mapped[int] = mapped_column(Integer, index=True, nullable=False)
    container_id: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    port: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="running")
    preview_url: Mapped[str] = mapped_column(String(255), nullable=False)
    started_at: Mapped[Optional[PyDateTime]] = mapped_column(DateTime(timezone=True), default=PyDateTime.now)
    expires_at: Mapped[Optional[PyDateTime]] = mapped_column(DateTime(timezone=True), nullable=False)
