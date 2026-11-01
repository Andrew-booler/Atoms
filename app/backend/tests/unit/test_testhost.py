"""后端-单元-12：testing/studio_app.py 测试宿主故障控制。

SCHEMA 前缀校验需在独立进程中以不同环境变量导入模块，故用 subprocess。
TestSession.commit 与 ControlledProvider 的故障分支均不需要真实数据库连接。
"""
import os
import subprocess
import sys

import pytest
from fastapi import HTTPException

from testing import studio_app as host

BACKEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))


def _probe_import(schema: str) -> subprocess.CompletedProcess:
    env = os.environ.copy()
    env["STUDIO_TEST_SCHEMA"] = schema
    env.setdefault(
        "DATABASE_URL",
        "postgresql+asyncpg://postgres:postgres@127.0.0.1:5432/postgres",
    )
    code = (
        "import sys;"
        "sys.path.insert(0, {backend!r});"
        "import testing.studio_app;"
        "print('IMPORT_OK')"
    ).format(backend=BACKEND_DIR)
    return subprocess.run([sys.executable, "-c", code], env=env, capture_output=True, text=True)


def test_testhost_schema_prefix_validation():
    ok = _probe_import("studio_test_unit")
    assert ok.returncode == 0
    assert "IMPORT_OK" in ok.stdout

    bad = _probe_import("public")
    assert bad.returncode != 0
    assert "测试命名空间必须以studio_test_开头" in bad.stderr


async def test_testhost_commit_fault():
    host.state.update(stage="commit", mode="fail", remaining=1)
    session = host.TestSession()
    with pytest.raises(RuntimeError, match="受控提交失败"):
        await session.commit()
    assert host.state["remaining"] == 0
    host.state.update(stage="", mode="", remaining=0)


async def test_controlled_provider_fail():
    provider = host.ControlledProvider()
    host.state.update(stage="plan", mode="fail", remaining=1)
    with pytest.raises(HTTPException) as exc_info:
        await provider.plan("req")
    assert exc_info.value.status_code == 502
    assert exc_info.value.detail == "受控模拟阶段失败"
    host.state.update(stage="", mode="", remaining=0)


async def test_controlled_provider_invalid():
    provider = host.ControlledProvider()
    host.state.update(stage="plan", mode="invalid", remaining=1)
    assert await provider.plan("req") == {"summary": "缺字段"}
    host.state.update(stage="outline", mode="invalid", remaining=1)
    assert await provider.outline("req", {}) == {"title": "缺字段"}
    host.state.update(stage="artifact", mode="invalid", remaining=1)
    assert await provider.artifact("req", {}, {}) == ""
    host.state.update(stage="", mode="", remaining=0)


async def test_controlled_provider_delay():
    provider = host.ControlledProvider()
    host.state.update(stage="plan", mode="delay", remaining=1)
    result = await provider.plan("一个记录每日饮水量的追踪器，带进度环")
    assert result["summary"] == "做一个带进度环的每日饮水追踪器"  # 延迟后仍返回正常示例结果
    host.state.update(stage="", mode="", remaining=0)


async def test_controlled_provider_crash():
    provider = host.ControlledProvider()
    host.state.update(stage="plan", mode="crash", remaining=1)
    with pytest.raises(RuntimeError, match="受控非HTTP异常"):
        await provider.plan("req")
    host.state.update(stage="", mode="", remaining=0)