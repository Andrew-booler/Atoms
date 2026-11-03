"""执行层单元测试：mock subprocess 与 socket，验证 docker run 参数与流程。"""
import asyncio
import os
import socket
import subprocess
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio

# 隔离沙箱根目录，避免污染系统临时目录
os.environ.setdefault("SANDBOX_ROOT", str(Path(tempfile.gettempdir()) / "atoms_sandbox_test"))

from models.execution import Execution
from services.execution import CONTAINER_PREFIX, ExecutionService
from core import error_codes
from core.exceptions import SandboxUnavailableError


def _make_result(returncode: int = 0, stdout: str = "", stderr: str = "") -> subprocess.CompletedProcess:
    return subprocess.CompletedProcess(args=[], returncode=returncode, stdout=stdout, stderr=stderr)


def _scalars_result(items: list) -> MagicMock:
    """构造 async db.execute 的返回值，供 select(...).scalars().all() 使用。"""
    result = MagicMock()
    result.scalars.return_value.all.return_value = items
    return result


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
            with pytest.raises(SandboxUnavailableError) as exc_info:
                service.ensure_image()
        assert exc_info.value.code == error_codes.SANDBOX_IMAGE_PULL_FAILED


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
    @pytest.fixture(autouse=True)
    def skip_capacity_check(self):
        """总量上限逻辑由 TestContainerCap 单独覆盖，这里跳过避免干扰命令序列。"""
        with patch.object(ExecutionService, "_enforce_container_cap", new=AsyncMock(return_value=None)):
            yield

    @pytest.mark.asyncio
    async def test_docker_unavailable_raises(self, service):
        with patch.object(ExecutionService, "is_docker_available", return_value=False):
            with pytest.raises(SandboxUnavailableError) as exc_info:
                await service.run_html("<html></html>", version_id=1)
        assert exc_info.value.code == error_codes.SANDBOX_DOCKER_UNAVAILABLE

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
            assert execution.sandbox_id is not None
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
        container_name = cmd[name_idx + 1]
        assert container_name.startswith(CONTAINER_PREFIX)
        # 标签：孤儿清理与总量统计按 label 精确匹配
        assert "atoms.sandbox=1" in cmd
        assert f"atoms.execution_id={container_name[len(CONTAINER_PREFIX):]}" in cmd

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

            with pytest.raises(SandboxUnavailableError) as exc_info:
                await service.run_html("<html></html>", version_id=1)
        assert exc_info.value.code == error_codes.SANDBOX_START_FAILED
        assert "端口" in exc_info.value.details["reason"]

    @pytest.mark.asyncio
    async def test_commit_failure_removes_container(self, service):
        """容器已启动但落库失败：必须按容器名回收，不能只删工作区。"""
        commands = []

        def fake_run(cmd, **kwargs):
            commands.append(cmd)
            if cmd[:3] == ["docker", "run", "-d"]:
                return _make_result(0, stdout="cid-commit-fail")
            return _make_result(0)

        service.db.commit = AsyncMock(side_effect=RuntimeError("db down"))
        with patch.object(ExecutionService, "is_docker_available", return_value=True), \
             patch.object(ExecutionService, "ensure_image", return_value=None), \
             patch.object(ExecutionService, "_allocate_port", return_value=52341), \
             patch("services.execution.subprocess.run", side_effect=fake_run):

            with pytest.raises(RuntimeError, match="db down"):
                await service.run_html("<html></html>", version_id=1)

        rm_commands = [cmd for cmd in commands if cmd[:3] == ["docker", "rm", "-f"]]
        assert len(rm_commands) == 1
        assert rm_commands[0][3].startswith(CONTAINER_PREFIX)

    @pytest.mark.asyncio
    async def test_run_timeout_removes_partial_container(self, service):
        """docker run 超时：先按容器名回收可能已创建的容器，再重试。"""
        commands = []
        attempts = {"run": 0}

        def fake_run(cmd, **kwargs):
            commands.append(cmd)
            if cmd[:3] == ["docker", "run", "-d"]:
                attempts["run"] += 1
                if attempts["run"] == 1:
                    raise subprocess.TimeoutExpired(cmd=cmd, timeout=30)
                return _make_result(0, stdout="cid-second")
            return _make_result(0)

        with patch.object(ExecutionService, "is_docker_available", return_value=True), \
             patch.object(ExecutionService, "ensure_image", return_value=None), \
             patch.object(ExecutionService, "_allocate_port", side_effect=[1111, 2222]), \
             patch("services.execution.subprocess.run", side_effect=fake_run):

            execution = await service.run_html("<html></html>", version_id=1)

        assert execution.container_id == "cid-second"
        run_names = [cmd[cmd.index("--name") + 1] for cmd in commands if "--name" in cmd]
        assert len(run_names) == 2
        rm_names = [cmd[3] for cmd in commands if cmd[:3] == ["docker", "rm", "-f"]]
        assert rm_names == [run_names[0]]


class TestContainerCap:
    @pytest.mark.asyncio
    async def test_rejects_when_limit_still_reached(self, service):
        """回收后仍达到上限（存在无 DB 记录的孤儿）：拒绝新建。"""
        service.db.execute = AsyncMock(return_value=_scalars_result([]))
        with patch.object(ExecutionService, "_count_sandbox_containers", return_value=4):
            with pytest.raises(SandboxUnavailableError) as exc_info:
                await service._enforce_container_cap()

        assert exc_info.value.code == error_codes.SANDBOX_START_FAILED
        assert exc_info.value.details["reason"] == "container_limit_reached"

    @pytest.mark.asyncio
    async def test_reaps_oldest_running(self, service):
        """达到上限时先回收最旧的 running 执行，再允许新建。"""
        now = datetime.now(timezone.utc)
        oldest = Execution(id=1, version_id=1, container_id="c1", sandbox_id="s1", port=1,
                           status="running", preview_url="u1", started_at=now, expires_at=now)
        newer = Execution(id=2, version_id=2, container_id="c2", sandbox_id="s2", port=2,
                          status="running", preview_url="u2", started_at=now, expires_at=now)
        service.db.execute = AsyncMock(return_value=_scalars_result([oldest, newer]))

        with patch.object(ExecutionService, "_count_sandbox_containers", side_effect=[4, 2]), \
             patch("services.execution.subprocess.run", return_value=_make_result(0)):
            await service._enforce_container_cap()

        assert oldest.status == "stopped"
        assert newer.status == "running"
        service.db.commit.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_no_limit_when_disabled(self, service):
        """上限 <= 0 时直接跳过，不调用 docker。"""
        with patch.object(ExecutionService, "max_containers", new=0), \
             patch.object(ExecutionService, "_count_sandbox_containers") as count:
            await service._enforce_container_cap()
        count.assert_not_called()


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

    @pytest.mark.asyncio
    async def test_stop_reaps_workspace_with_sandbox_id(self, service, tmp_path, monkeypatch):
        """有 sandbox_id 时直接按名称删容器并删工作区，不再依赖 inspect 反查。"""
        monkeypatch.setenv("SANDBOX_ROOT", str(tmp_path))
        workspace = tmp_path / "s1"
        workspace.mkdir()
        execution = Execution(
            id=1, version_id=1, container_id="c1", sandbox_id="s1", port=8080,
            status="running", preview_url="http://127.0.0.1:8080/",
            started_at=datetime.now(timezone.utc),
            expires_at=datetime.now(timezone.utc),
        )
        result_mock = MagicMock()
        result_mock.scalar_one_or_none.return_value = execution
        service.db.execute.return_value = result_mock

        with patch("services.execution.subprocess.run", return_value=_make_result(0)) as run:
            result = await service.stop(1)

        assert result.status == "stopped"
        assert not workspace.exists()
        # 只有一次 docker rm -f，没有 inspect
        assert run.call_count == 1
        assert run.call_args[0][0] == ["docker", "rm", "-f", "c1"]

    @pytest.mark.asyncio
    async def test_stop_legacy_execution_resolves_name_before_remove(self, service, tmp_path, monkeypatch):
        """旧记录没有 sandbox_id：必须先 inspect 拿名字，再删容器并删工作区。"""
        monkeypatch.setenv("SANDBOX_ROOT", str(tmp_path))
        workspace = tmp_path / "legacy1"
        workspace.mkdir()
        execution = Execution(
            id=1, version_id=1, container_id="c1", port=8080,
            status="running", preview_url="http://127.0.0.1:8080/",
            started_at=datetime.now(timezone.utc),
            expires_at=datetime.now(timezone.utc),
        )
        result_mock = MagicMock()
        result_mock.scalar_one_or_none.return_value = execution
        service.db.execute.return_value = result_mock

        inspect_result = _make_result(0, stdout="/atoms-sandbox-legacy1\n")
        with patch("services.execution.subprocess.run",
                   side_effect=[inspect_result, _make_result(0)]) as run:
            result = await service.stop(1)

        assert result.status == "stopped"
        assert not workspace.exists()
        assert run.call_args_list[0][0][0][:3] == ["docker", "inspect", "--format"]
        assert run.call_args_list[1][0][0] == ["docker", "rm", "-f", "c1"]


class TestCleanupExpired:
    @pytest.mark.asyncio
    async def test_cleanup_stops_expired(self, service):
        exec1 = Execution(id=1, version_id=1, container_id="c1", sandbox_id="s1", port=1,
                          status="running", preview_url="u1",
                          started_at=datetime.now(timezone.utc), expires_at=datetime.now(timezone.utc))
        exec2 = Execution(id=2, version_id=2, container_id="c2", sandbox_id="s2", port=2,
                          status="running", preview_url="u2",
                          started_at=datetime.now(timezone.utc), expires_at=datetime.now(timezone.utc))
        service.db.execute = AsyncMock(side_effect=[
            _scalars_result([exec1, exec2]),
            _scalars_result([]),
        ])

        with patch("services.execution.subprocess.run", return_value=_make_result(0)):
            count = await service.cleanup_expired()

        assert count == 2
        assert exec1.status == "expired"
        assert exec2.status == "expired"
        service.db.commit.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_cleanup_removes_expired_workspace(self, service, tmp_path, monkeypatch):
        """过期执行的工作区必须被删除（原实现只 stop 容器，漏删目录）。"""
        monkeypatch.setenv("SANDBOX_ROOT", str(tmp_path))
        workspace = tmp_path / "s1"
        workspace.mkdir()
        expired_exec = Execution(id=1, version_id=1, container_id="c1", sandbox_id="s1", port=1,
                                 status="running", preview_url="u1",
                                 started_at=datetime.now(timezone.utc),
                                 expires_at=datetime.now(timezone.utc))
        service.db.execute = AsyncMock(side_effect=[
            _scalars_result([expired_exec]),
            _scalars_result([]),
        ])

        with patch("services.execution.subprocess.run", return_value=_make_result(0)):
            assert await service.cleanup_expired() == 1

        assert not workspace.exists()

    @pytest.mark.asyncio
    async def test_cleanup_prunes_orphan_workspaces_with_grace(self, service, tmp_path, monkeypatch):
        """无 running 记录且超过保护窗口的目录被清理；近期目录与在用目录保留。"""
        monkeypatch.setenv("SANDBOX_ROOT", str(tmp_path))
        old_time = time.time() - 600
        orphan = tmp_path / "orphan1"
        orphan.mkdir()
        os.utime(orphan, (old_time, old_time))
        known = tmp_path / "known1"
        known.mkdir()
        os.utime(known, (old_time, old_time))
        recent = tmp_path / "recent1"
        recent.mkdir()

        kept_exec = Execution(id=1, version_id=1, container_id="c1", sandbox_id="known1", port=1,
                              status="running", preview_url="u1",
                              started_at=datetime.now(timezone.utc),
                              expires_at=datetime.now(timezone.utc))
        service.db.execute = AsyncMock(side_effect=[
            _scalars_result([]),
            _scalars_result([kept_exec]),
        ])

        with patch("services.execution.subprocess.run", return_value=_make_result(0)):
            assert await service.cleanup_expired() == 0

        assert not orphan.exists()
        assert known.exists()
        assert recent.exists()


class TestCleanupOrphans:
    def test_cleanup_orphans_filters_by_label(self):
        """按 label 精确过滤，不再用名称子串匹配。"""
        ps_result = _make_result(0, stdout="cid1\ncid2\n")
        with patch.object(ExecutionService, "is_docker_available", return_value=True), \
             patch("services.execution.subprocess.run",
                   side_effect=[ps_result, _make_result(0), _make_result(0)]) as run:
            ExecutionService.cleanup_orphan_containers()

        ps_cmd = run.call_args_list[0][0][0]
        assert ps_cmd[:4] == ["docker", "ps", "-aq", "--filter"]
        assert ps_cmd[4] == "label=atoms.sandbox=1"
        assert run.call_args_list[1][0][0] == ["docker", "rm", "-f", "cid1"]
        assert run.call_args_list[2][0][0] == ["docker", "rm", "-f", "cid2"]
