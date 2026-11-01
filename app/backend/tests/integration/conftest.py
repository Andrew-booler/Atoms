"""接口集成测试夹具：进程内 ASGI + 真实 PostgreSQL，AI 边界仍由受控提供者。

此处覆盖根 conftest 的默认值：使用独立 schema studio_test_api，与界面集成的
studio_test_t1 分开；逐例调用 /__test/reset 归零。PostgreSQL 不可用时跳过整组。
"""
import os

import httpx
import pytest
import pytest_asyncio
from sqlalchemy import text

os.environ["STUDIO_TEST_SCHEMA"] = "studio_test_api"
os.environ.setdefault(
    "DATABASE_URL",
    "postgresql+asyncpg://postgres:postgres@127.0.0.1:5432/postgres",
)

from testing import studio_app as host  # noqa: E402


@pytest_asyncio.fixture
async def client():
    # 先探测 PostgreSQL 可用性，避免连接失败伪装成用例失败。
    try:
        async with host.engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
    except Exception:
        pytest.skip("PostgreSQL 不可用，跳过接口集成测试")

    async with host.lifespan(host.app):
        transport = httpx.ASGITransport(app=host.app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as ac:
            reset = await ac.post("/__test/reset")
            assert reset.status_code == 200
            yield ac