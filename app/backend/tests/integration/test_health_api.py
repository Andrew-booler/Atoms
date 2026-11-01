"""后端-集成-08：routers/health.py 与 services/database.py — 数据库探活与启停。

健康分支使用真实 PostgreSQL 执行 SELECT 1；失败分支用受控连接替身触发异常映射。
"""
from contextlib import asynccontextmanager

import pytest

from services import database as database_service
from testing import studio_app as host


class _HealthyManager:
    """把服务层的会话上下文接到集成测试 schema 的受控适配器。"""

    @asynccontextmanager
    async def session(self):
        async with host.sessions() as session:
            yield session


class _BrokenManager:
    def session(self):
        raise RuntimeError("数据库不可用")


class _RecordingManager(_HealthyManager):
    def __init__(self):
        self.connected = 0
        self.closed = 0

    async def ensure_connected(self):
        self.connected += 1

    async def close_db(self):
        self.closed += 1


async def test_database_health_reports_healthy(api_client, monkeypatch):
    monkeypatch.setattr(database_service, "db_manager", _HealthyManager())
    response = await api_client.get("/database/health")

    assert response.status_code == 200
    assert response.json() == {"status": "healthy", "service": "database"}


async def test_database_health_reports_unhealthy(api_client, monkeypatch):
    monkeypatch.setattr(database_service, "db_manager", _BrokenManager())
    response = await api_client.get("/database/health")

    assert response.status_code == 200
    assert response.json() == {"status": "unhealthy", "service": "database"}


async def test_initialize_database_skipped_when_flag_enabled(monkeypatch):
    manager = _RecordingManager()
    monkeypatch.setattr(database_service, "db_manager", manager)
    monkeypatch.setenv("MGX_IGNORE_INIT_DB", "true")

    await database_service.initialize_database()

    assert manager.connected == 0


async def test_initialize_database_connects_when_flag_disabled(monkeypatch):
    manager = _RecordingManager()
    monkeypatch.setattr(database_service, "db_manager", manager)
    monkeypatch.setenv("MGX_IGNORE_INIT_DB", "false")

    await database_service.initialize_database()

    assert manager.connected == 1


async def test_initialize_database_rejects_invalid_flag(monkeypatch):
    manager = _RecordingManager()
    monkeypatch.setattr(database_service, "db_manager", manager)
    monkeypatch.setenv("MGX_IGNORE_INIT_DB", "maybe")

    with pytest.raises(ValueError, match="Invalid boolean value"):
        await database_service.initialize_database()
    assert manager.connected == 0


async def test_close_database_delegates_to_manager(monkeypatch):
    manager = _RecordingManager()
    monkeypatch.setattr(database_service, "db_manager", manager)

    await database_service.close_database()

    assert manager.closed == 1
