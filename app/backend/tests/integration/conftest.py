"""接口集成测试夹具：进程内 ASGI + 真实 PostgreSQL，AI 边界仍由受控提供者。

studio 与 auth 测试宿主共用独立 schema studio_test_api，每次启动重建 schema，
避免模型新增列后撞上上一轮遗留的旧表结构。PostgreSQL 不可用时跳过整组。
"""
import os
from contextlib import asynccontextmanager

import httpx
import pytest
import pytest_asyncio
from fastapi import FastAPI
from sqlalchemy import text

os.environ["STUDIO_TEST_SCHEMA"] = "studio_test_api"
os.environ.setdefault(
    "DATABASE_URL",
    "postgresql+asyncpg://postgres:postgres@127.0.0.1:5432/postgres",
)
os.environ.setdefault("APP_AUTH_SECRET", "test-auth-secret")

from core.auth import create_access_token  # noqa: E402
from core.database import get_db  # noqa: E402
from core.exception_handlers import register_exception_handlers  # noqa: E402
from routers import auth, health  # noqa: E402
from routers import settings as settings_router  # noqa: E402
from testing import studio_app as host  # noqa: E402


def _token(user_id: str) -> str:
    return create_access_token({"sub": user_id})


def _api_app() -> FastAPI:
    """认证/健康/配置接口的测试宿主，复用同一 schema 与数据库会话。"""

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        async with host.engine.begin() as connection:
            await host.rebuild_schema(connection)
        yield
        # 逐例释放连接池，避免连接被带到下一条用例的新事件循环（与测试宿主 lifespan 一致）。
        await host.engine.dispose()

    app = FastAPI(lifespan=lifespan)
    app.dependency_overrides[get_db] = host.database
    app.include_router(auth.router)
    app.include_router(health.router)
    app.include_router(settings_router.router)
    register_exception_handlers(app)
    return app


@pytest_asyncio.fixture
async def api_client():
    """认证/健康/配置接口的进程内客户端；PostgreSQL 不可用时跳过。"""
    try:
        async with host.engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
    except Exception as exc:
        pytest.skip(f"PostgreSQL 不可用，跳过接口集成测试: {exc}")

    app = _api_app()
    async with app.router.lifespan_context(app):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as ac:
            yield ac


@pytest_asyncio.fixture
async def client():
    # 先探测 PostgreSQL 可用性，避免连接失败伪装成用例失败。
    try:
        async with host.engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
    except Exception:
        pytest.skip("PostgreSQL 不可用，跳过接口集成测试")

    headers = {"Authorization": f"Bearer {_token(host.TEST_USER_ID)}"}
    async with host.lifespan(host.app):
        transport = httpx.ASGITransport(app=host.app)
        async with httpx.AsyncClient(
            transport=transport, base_url="http://test", headers=headers
        ) as ac:
            reset = await ac.post("/__test/reset")
            assert reset.status_code == 200
            yield ac


@pytest.fixture
def test_user_id() -> str:
    return host.TEST_USER_ID


@pytest.fixture
def other_headers() -> dict[str, str]:
    return {"Authorization": f"Bearer {_token(host.OTHER_USER_ID)}"}


@pytest.fixture
def admin_headers() -> dict[str, str]:
    return {"Authorization": f"Bearer {_token(host.ADMIN_USER_ID)}"}
