"""执行层单元测试：mock subprocess 与 socket，验证 docker run 参数与流程。"""
import asyncio
import os
import socket
import subprocess
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio

# 隔离沙箱根目录，避免污染系统临时目录
os.environ.setdefault("SANDBOX_ROOT", str(Path(tempfile.gettempdir()) / "atoms_sandbox_test"))

from models.execution import Execution
from services.execution import CONTAINER_PREFIX, DockerNotAvailableError, ExecutionService


def _make_result(returncode: int = 0, stdout: str = "", stderr: str = "") -> subprocess.CompletedProcess:
    return subprocess.CompletedProcess(args=[], returncode=returncode, stdout=stdout, stderr=stderr)


@pytest.fixture(autouse=True)
def reset_image_cache():
    """每个测试前重置镜像可用性缓存，避免跨测试污染。"""
    import services.execution as ex
    ex._image_available = None
    ex._image_checked_at = 0.0
    yield


@pytest_asyncio.fixture
async def service():
    db = MagicMock()
    db.add = MagicMock()
    db.commit = AsyncMock()
    db.refresh = AsyncMock()
    db.execute = AsyncMock()
    svc = ExecutionService(db)
    yield svc


class TestDockerAvailability:
    def test_docker_available_when_info_succeeds(self):
        with patch("services.execution.subprocess.run", return_value=_make_result(0)):
            assert ExecutionService.is_docker_available() is True

    def test_docker_unavailable_when_info_fails(self):
        with patch("services.execution.subprocess.run", return_value=_make_result(1)):
            assert ExecutionService.is_docker_available() is False

    def test_docker_unavailable_when_cli_missing(self):
        with patch("services.execution.subprocess.run", side_effect=FileNotFoundError):
            assert ExecutionService.is_docker_available() is False


class TestEnsureImage:
    def test_image_exists_returns_none(self, service):
        with patch("services.execution.subprocess.run", return_value=_make_result(0)):
            # inspect 成功 → 不抛异常
            service.ensure_image()

    def test_image_pull_success(self, service):
        calls = [
            _make_result(1),  # inspect 失败
            _make_result(0),  # pull 成功
        ]
        with patch("services.execution.subprocess.run", side_effect=calls):
            service.ensure_image()

    def test_image_pull_failure_raises(self, service):
        calls = [
            _make_result(1),  # inspect 失败
            _make_result(1, stderr="pull failed"),  # pull 失败
        ]
        with patch("services.execution.subprocess.run", side_effect=calls):
            with pytest.raises(DockerNotAvailableError):
                service.ensure_image()


class TestPortAllocation:
    def test_port_from_socket(self):
        mock_sock = MagicMock()
        mock_sock.getsockname.return_value = ("127.0.0.1", 52341)
        mock_sock.__enter__ = MagicMock(return_value=mock_sock)
        mock_sock.__exit__ = MagicMock(return_value=False)
        with patch("services.execution.socket.socket", return_value=mock_sock):
            port = ExecutionService._allocate_port()
            assert port == 52341
            mock_sock.bind.assert_called_once_with(("127.0.0.1", 0))


class TestRunHtml:
    @pytest.mark.asyncio
    async def test_docker_unavailable_raises(self, service):
        with patch.object(ExecutionService, "is_docker_available", return_value=False):
            with pytest.raises(DockerNotAvailableError):
                await service.run_html("<html></html>", version_id=1)

    @pytest.mark.asyncio
    async def test_successful_run_records_execution(self, service):
        """成功路径：docker run 返回容器 ID，Execution 行写入。"""
        with patch.object(ExecutionService, "is_docker_available", return_value=True), \
             patch.object(ExecutionService, "ensure_image", return_value=None), \
             patch.object(ExecutionService, "_allocate_port", return_value=52341), \
             patch("services.execution.subprocess.run", return_value=_make_result(0, stdout="abc123def456")):

            execution = await service.run_html("<html><body>hi</body></html>", version_id=42)

            assert execution is not None
            assert execution.version_id == 42
            assert execution.port == 52341
            assert execution.status == "running"
            assert execution.preview_url == "http://127.0.0.1:52341/"
            assert execution.container_id == "abc123def456"
            assert execution.expires_at is not None
            service.db.add.assert_called_once()
            service.db.commit.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_docker_run_command_contains_security_flags(self, service):
        """验证 docker run 命令包含所有安全参数。"""
        captured = {}

        def fake_run(cmd, **kwargs):
            captured["cmd"] = cmd
            return _make_result(0, stdout="container-id")

        with patch.object(ExecutionService, "is_docker_available", return_value=True), \
             patch.object(ExecutionService, "ensure_image", return_value=None), \
             patch.object(ExecutionService, "_allocate_port", return_value=52341), \
             patch("services.execution.subprocess.run", side_effect=fake_run):

            await service.run_html("<html></html>", version_id=1)

        cmd = captured["cmd"]
        assert "--read-only" in cmd
        assert "--cap-drop=ALL" in cmd
        assert "--security-opt=no-new-privileges" in cmd
        assert "-p" in cmd
        assert "127.0.0.1:52341:80" in cmd
        assert ":ro" in " ".join(cmd)
        assert "--tmpfs" in cmd
        assert f"--cpus={service.cpu_limit}" in cmd
        assert f"--memory={service.memory_limit}" in cmd
        assert f"--pids-limit={service.pids_limit}" in cmd
        # 隔离友好的 nginx 运行方式：绕过官方 entrypoint，挂载自定义只读配置
        assert "--entrypoint" in cmd
        assert "nginx" in cmd
        assert "/etc/nginx/nginx.conf:ro" in " ".join(cmd)
        assert "-g" in cmd and "daemon off;" in " ".join(cmd)
        # 容器名前缀
        name_idx = cmd.index("--name")
        assert cmd[name_idx + 1].startswith(CONTAINER_PREFIX)

    @pytest.mark.asyncio
    async def test_port_conflict_retries(self, service):
        """端口被占用时重试最多 3 次。"""
        results = [
            _make_result(1, stderr="port is already allocated"),
            _make_result(1, stderr="address already in use"),
            _make_result(0, stdout="ok-container"),
        ]
        with patch.object(ExecutionService, "is_docker_available", return_value=True), \
             patch.object(ExecutionService, "ensure_image", return_value=None), \
             patch.object(ExecutionService, "_allocate_port", side_effect=[1111, 2222, 3333]), \
             patch("services.execution.subprocess.run", side_effect=results):

            execution = await service.run_html("<html></html>", version_id=1)
            assert execution.port == 3333

    @pytest.mark.asyncio
    async def test_all_retries_exhausted_raises(self, service):
        """3 次重试都失败则抛出最后一次错误。"""
        results = [_make_result(1, stderr="port is already allocated")] * 3
        with patch.object(ExecutionService, "is_docker_available", return_value=True), \
             patch.object(ExecutionService, "ensure_image", return_value=None), \
             patch.object(ExecutionService, "_allocate_port", side_effect=[1, 2, 3]), \
             patch("services.execution.subprocess.run", side_effect=results):

            with pytest.raises(RuntimeError, match="端口"):
                await service.run_html("<html></html>", version_id=1)


class TestStop:
    @pytest.mark.asyncio
    async def test_stop_nonexistent_returns_none(self, service):
        result_mock = MagicMock()
        result_mock.scalar_one_or_none.return_value = None
        service.db.execute.return_value = result_mock

        result = await service.stop(999)
        assert result is None

    @pytest.mark.asyncio
    async def test_stop_running_execution(self, service):
        execution = Execution(
            id=1, version_id=1, container_id="abc", port=8080,
            status="running", preview_url="http://127.0.0.1:8080/",
            started_at=datetime.now(timezone.utc),
            expires_at=datetime.now(timezone.utc),
        )
        result_mock = MagicMock()
        result_mock.scalar_one_or_none.return_value = execution
        service.db.execute.return_value = result_mock

        with patch("services.execution.subprocess.run", return_value=_make_result(0)):
            result = await service.stop(1)

        assert result.status == "stopped"
        service.db.commit.assert_awaited_once()


class TestCleanupExpired:
    @pytest.mark.asyncio
    async def test_cleanup_stops_expired(self, service):
        exec1 = Execution(id=1, version_id=1, container_id="c1", port=1, status="running",
                          preview_url="u1", started_at=datetime.now(timezone.utc),
                          expires_at=datetime.now(timezone.utc))
        exec2 = Execution(id=2, version_id=2, container_id="c2", port=2, status="running",
                          preview_url="u2", started_at=datetime.now(timezone.utc),
                          expires_at=datetime.now(timezone.utc))
        result_mock = MagicMock()
        result_mock.scalars.return_value.all.return_value = [exec1, exec2]
        service.db.execute.return_value = result_mock

        with patch("services.execution.subprocess.run", return_value=_make_result(0)):
            count = await service.cleanup_expired()

        assert count == 2
        assert exec1.status == "expired"
        assert exec2.status == "expired"
        service.db.commit.assert_awaited_once()


class TestCleanupOrphans:
    def test_cleanup_orphans_removes_prefixed_containers(self):
        ps_result = _make_result(0, stdout="cid1\ncid2\n")
        with patch("services.execution.subprocess.run", side_effect=[ps_result, _make_result(0), _make_result(0)]):
            ExecutionService.cleanup_orphan_containers()
            # ps + 两个 rm -f
            assert True  # 不抛异常即通过
