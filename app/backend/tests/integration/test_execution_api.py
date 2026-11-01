"""执行层集成测试：真实 Docker 起容器，验证 HTML 可访问。

Docker 不可用或镜像拉取失败时跳过。
"""
import os
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

import httpx
import pytest
import pytest_asyncio

os.environ.setdefault("SANDBOX_ROOT", str(Path(tempfile.gettempdir()) / "atoms_sandbox_integration"))

from models.execution import Execution
from services.execution import DockerNotAvailableError, ExecutionService
from sqlalchemy import select
from testing import studio_app as host

pytestmark = pytest.mark.asyncio


def _docker_available() -> bool:
    import subprocess
    try:
        result = subprocess.run(["docker", "info"], capture_output=True, text=True, timeout=10)
        return result.returncode == 0
    except Exception:
        return False


def _image_available(image: str) -> bool:
    import subprocess
    try:
        result = subprocess.run(["docker", "image", "inspect", image], capture_output=True, text=True, timeout=15)
        return result.returncode == 0
    except Exception:
        return False


@pytest_asyncio.fixture
async def service():
    """直接用 host.engine 创建会话。"""
    async with host.sessions() as session:
        svc = ExecutionService(session)
        yield svc
        # 清理：停止所有运行中的执行
        result = await session.execute(select(Execution).where(Execution.status == "running"))
        for ex in result.scalars().all():
            await svc.stop(ex.id)


@pytest.fixture(scope="module")
def docker_required():
    if not _docker_available():
        pytest.skip("Docker 不可用，跳过执行层集成测试")
    image = os.environ.get("SANDBOX_IMAGE", "nginx:alpine")
    if not _image_available(image):
        pytest.skip(f"沙箱镜像 {image} 不存在，跳过")


async def test_run_html_serves_via_docker(service, docker_required):
    """真实起容器，GET preview_url 应返回写入的 HTML。"""
    html = "<html><body><h1>sandbox-ok</h1></body></html>"
    execution = await service.run_html(html, version_id=1)

    assert execution.status == "running"
    assert execution.preview_url.startswith("http://127.0.0.1:")

    import asyncio
    resp = None
    for _ in range(20):
        try:
            async with httpx.AsyncClient(timeout=5) as client:
                resp = await client.get(execution.preview_url)
                if resp.status_code == 200:
                    break
        except Exception:
            pass
        await asyncio.sleep(0.5)
    else:
        pytest.fail("沙箱服务未在 10 秒内响应")

    assert "sandbox-ok" in resp.text


async def test_stop_execution_removes_container(service, docker_required):
    """停止后容器应被移除。"""
    import subprocess
    html = "<html><body>stop-me</body></html>"
    execution = await service.run_html(html, version_id=2)
    container_id = execution.container_id

    stopped = await service.stop(execution.id)
    assert stopped.status == "stopped"

    result = subprocess.run(
        ["docker", "inspect", container_id],
        capture_output=True, text=True, timeout=10,
    )
    assert result.returncode != 0, "容器未被移除"


async def test_expired_execution_cleanup(service, docker_required):
    """过期执行应被 cleanup_expired 停止。"""
    html = "<html><body>expire</body></html>"
    execution = await service.run_html(html, version_id=3)

    execution.expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)
    await service.db.commit()

    count = await service.cleanup_expired()
    assert count == 1

    await service.db.refresh(execution)
    assert execution.status == "expired"


async def test_run_and_stop_via_api(client, docker_required):
    """通过 API 调用 /run 和 DELETE /executions/{id}。"""
    from services import studio_output
    proj = (await client.post("/api/v1/studio/projects", json={"name": "exec-api-test", "description": ""})).json()
    pid = proj["id"]

    req = "执行层API测试"
    plan_summary = studio_output.fixture(req)["plan"]["summary"]
    outline = studio_output.fixture(req)["outline"]
    await client.post(f"/api/v1/studio/projects/{pid}/plan", json={"requirement": req})
    artifact_resp = await client.post(
        f"/api/v1/studio/projects/{pid}/artifact",
        json={"requirement": req, "plan_summary": plan_summary, "outline": outline},
    )
    assert artifact_resp.status_code == 200
    version_id = artifact_resp.json()["version"]["id"]

    run_resp = await client.post(f"/api/v1/studio/versions/{version_id}/run")
    assert run_resp.status_code == 200
    data = run_resp.json()
    assert data["preview_url"].startswith("http://127.0.0.1:")
    assert data["status"] == "running"

    exec_id = data["id"]
    stop_resp = await client.delete(f"/api/v1/studio/executions/{exec_id}")
    assert stop_resp.status_code == 200
    assert stop_resp.json()["status"] == "stopped"
