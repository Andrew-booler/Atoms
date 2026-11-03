"""执行与隔离层：把 HTML 产物放进 Docker 沙箱运行，返回预览 URL。

安全边界：工作区只读挂载、容器根文件系统 --read-only、--cap-drop=ALL、
no-new-privileges、端口仅绑定 127.0.0.1、CPU/内存/PID 限制。
不引入 docker Python 包，直接通过 subprocess 调用 docker CLI。
"""
import logging
import os
import shutil
import socket
import subprocess
import tempfile
import time
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

from core import error_codes
from core.config import settings
from core.environment import get_env_int
from core.exceptions import SandboxUnavailableError
from models.execution import Execution
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)

CONTAINER_PREFIX = "atoms-sandbox-"

# 容器标签：孤儿清理按 label 精确匹配，不再依赖名称子串
CONTAINER_LABEL = "atoms.sandbox"
CONTAINER_LABEL_VALUE = "1"
EXECUTION_LABEL = "atoms.execution_id"

# 孤儿工作区保护窗口：最近 N 秒内创建的目录不清理，避免误删正在启动的执行
ORPHAN_WORKSPACE_GRACE_SECONDS = 120.0

# 镜像可用性缓存：避免每次执行都尝试拉取镜像（网络不通时会反复超时）
_image_available: Optional[bool] = None
_image_checked_at: float = 0.0
_IMAGE_CACHE_TTL = 60.0  # 缓存 60 秒

# 沙箱内 nginx 配置：worker 以 root 运行，避免 --cap-drop=ALL 下
# nginx 对临时目录执行 chown（目标 uid 101）因缺少 CAP_CHOWN 而崩溃。
# pid 与临时目录都改写到 /tmp（tmpfs），根文件系统保持 --read-only。
NGINX_CONF = """user root;
worker_processes 1;
error_log /dev/stderr warn;
pid /tmp/nginx.pid;

events { worker_connections 32; }

http {
    include /etc/nginx/mime.types;
    default_type application/octet-stream;
    sendfile on;
    access_log /dev/stdout;
    client_body_temp_path /tmp/client_temp;
    proxy_temp_path /tmp/proxy_temp;
    fastcgi_temp_path /tmp/fastcgi_temp;
    uwsgi_temp_path /tmp/uwsgi_temp;
    scgi_temp_path /tmp/scgi_temp;

    server {
        listen 80;
        server_name _;
        location / {
            root /usr/share/nginx/html;
            index index.html;
        }
    }
}
"""


def _env_int(name: str, default: int) -> int:
    """读取整型环境变量，缓存到 settings 避免重复查。"""
    return get_env_int(name, default=default)


def _env_str(name: str, default: str) -> str:
    """读取字符串环境变量，未设置返回默认值。"""
    return os.environ.get(name, default)


class ExecutionService:
    """沙箱执行服务。每个实例绑定一个数据库会话。"""

    def __init__(self, db: AsyncSession):
        self.db = db

    # ── 配置 ──────────────────────────────────────────────
    @property
    def sandbox_root(self) -> Path:
        return Path(_env_str("SANDBOX_ROOT", str(Path(tempfile.gettempdir()) / "atoms_sandbox")))

    @property
    def sandbox_image(self) -> str:
        return _env_str("SANDBOX_IMAGE", "nginx:alpine")

    @property
    def idle_timeout(self) -> int:
        return _env_int("SANDBOX_IDLE_TIMEOUT", 600)

    @property
    def sandbox_host(self) -> str:
        return _env_str("SANDBOX_HOST", "127.0.0.1")

    @property
    def cpu_limit(self) -> float:
        raw = os.environ.get("SANDBOX_CPU", "0.5")
        try:
            return float(raw)
        except ValueError:
            return 0.5

    @property
    def memory_limit(self) -> str:
        return _env_str("SANDBOX_MEMORY", "128m")

    @property
    def pids_limit(self) -> int:
        return _env_int("SANDBOX_PIDS_LIMIT", 64)

    @property
    def max_containers(self) -> int:
        """同时存在的沙箱容器总量上限，<=0 表示不限制。"""
        return _env_int("SANDBOX_MAX_CONTAINERS", 4)

    # ── Docker 可用性 ─────────────────────────────────────
    @staticmethod
    def is_docker_available() -> bool:
        try:
            result = subprocess.run(
                ["docker", "info"],
                capture_output=True,
                text=True,
                timeout=10,
            )
            return result.returncode == 0
        except (FileNotFoundError, subprocess.TimeoutExpired):
            return False

    def ensure_image(self) -> None:
        """确保沙箱镜像存在，不存在则拉取。失败抛 SandboxUnavailableError。

        结果缓存 60 秒，避免网络不通时反复拉取超时。
        """
        global _image_available, _image_checked_at
        now = time.time()
        if _image_available is not None and (now - _image_checked_at) < _IMAGE_CACHE_TTL:
            if not _image_available:
                raise SandboxUnavailableError(
                    error_codes.SANDBOX_IMAGE_PULL_FAILED,
                    details={"image": self.sandbox_image, "reason": "cached_unavailable"},
                )
            return

        check = subprocess.run(
            ["docker", "image", "inspect", self.sandbox_image],
            capture_output=True,
            text=True,
            timeout=15,
        )
        if check.returncode == 0:
            _image_available = True
            _image_checked_at = now
            return

        logger.info("沙箱镜像 %s 不存在，开始拉取", self.sandbox_image)
        pull = subprocess.run(
            ["docker", "pull", self.sandbox_image],
            capture_output=True,
            text=True,
            timeout=120,
        )
        if pull.returncode != 0:
            _image_available = False
            _image_checked_at = now
            raise SandboxUnavailableError(
                error_codes.SANDBOX_IMAGE_PULL_FAILED,
                details={"image": self.sandbox_image, "reason": pull.stderr.strip()},
            )
        _image_available = True
        _image_checked_at = now

    # ── 端口分配 ──────────────────────────────────────────
    @staticmethod
    def _allocate_port() -> int:
        """绑定 127.0.0.1:0 取一个空闲端口后立即释放。"""
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind(("127.0.0.1", 0))
            return s.getsockname()[1]

    # ── 总量上限 ──────────────────────────────────────────
    @staticmethod
    def _count_sandbox_containers() -> int:
        """统计当前运行中的沙箱容器数（按 label 精确过滤）。"""
        try:
            ps = subprocess.run(
                ["docker", "ps", "-q", "--filter", f"label={CONTAINER_LABEL}={CONTAINER_LABEL_VALUE}"],
                capture_output=True,
                text=True,
                timeout=30,
            )
        except (OSError, subprocess.SubprocessError) as exc:
            logger.warning("统计沙箱容器失败：%s", exc)
            return 0
        if ps.returncode != 0:
            return 0
        return len([cid for cid in ps.stdout.split() if cid])

    async def _enforce_container_cap(self) -> None:
        """创建新容器前保证总量不超限：超限先回收最旧的执行，仍超限则拒绝。"""
        limit = self.max_containers
        if limit <= 0:
            return

        count = self._count_sandbox_containers()
        if count < limit:
            return

        excess = count - limit + 1
        result = await self.db.execute(
            select(Execution)
            .where(Execution.status == "running")
            .order_by(Execution.started_at.asc(), Execution.id.asc())
        )
        for execution in list(result.scalars().all())[:excess]:
            self._reap(execution, status="stopped")
        await self.db.commit()

        if self._count_sandbox_containers() >= limit:
            raise SandboxUnavailableError(
                error_codes.SANDBOX_START_FAILED,
                details={"reason": "container_limit_reached", "limit": limit},
                retryable=True,
            )

    # ── 工作区 ────────────────────────────────────────────
    def _create_workspace(self, execution_id: str, html: str) -> Path:
        workspace = self.sandbox_root / execution_id
        workspace.mkdir(parents=True, exist_ok=True)
        index = workspace / "index.html"
        index.write_text(html, encoding="utf-8")
        index.chmod(0o644)
        return workspace

    def _ensure_nginx_conf(self) -> Path:
        """生成共享的沙箱 nginx 配置（只读挂载进容器，覆盖官方默认）。"""
        root = self.sandbox_root
        root.mkdir(parents=True, exist_ok=True)
        conf = root / "nginx.conf"
        conf.write_text(NGINX_CONF, encoding="utf-8")
        return conf

    @staticmethod
    def _remove_workspace(workspace: Path) -> None:
        try:
            shutil.rmtree(workspace, ignore_errors=True)
        except OSError as exc:
            logger.warning("清理工作区失败 %s: %s", workspace, exc)

    # ── 核心：运行 HTML ───────────────────────────────────
    async def run_html(self, html: str, version_id: int, user_id: str) -> Execution:
        """把 HTML 放进沙箱运行，返回 Execution 记录。

        失败时抛 SandboxUnavailableError；调用方负责处理并记录 failed 状态。
        """
        if not self.is_docker_available():
            raise SandboxUnavailableError(error_codes.SANDBOX_DOCKER_UNAVAILABLE)

        self.ensure_image()
        await self._enforce_container_cap()

        last_error: Optional[Exception] = None
        for attempt in range(3):
            port = self._allocate_port()
            sandbox_id = uuid.uuid4().hex[:12]
            workspace = self._create_workspace(sandbox_id, html)
            nginx_conf = self._ensure_nginx_conf()
            container_name = f"{CONTAINER_PREFIX}{sandbox_id}"

            cmd = [
                "docker", "run", "-d",
                "--name", container_name,
                "--rm",
                "--label", f"{CONTAINER_LABEL}={CONTAINER_LABEL_VALUE}",
                "--label", f"{EXECUTION_LABEL}={sandbox_id}",
                "--read-only",
                "--cap-drop=ALL",
                "--security-opt=no-new-privileges",
                f"--cpus={self.cpu_limit}",
                f"--memory={self.memory_limit}",
                f"--pids-limit={self.pids_limit}",
                "--network=bridge",
                "-p", f"127.0.0.1:{port}:80",
                "-v", f"{workspace}:/usr/share/nginx/html:ro",
                "-v", f"{nginx_conf}:/etc/nginx/nginx.conf:ro",
                "--tmpfs", "/tmp:rw,noexec,size=16m",
                "--entrypoint", "nginx",
                self.sandbox_image,
                "-g", "daemon off;",
            ]

            try:
                result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            except subprocess.TimeoutExpired:
                # CLI 被杀时容器可能已经创建，按名称强制回收，避免留下无记录孤儿
                self._remove_container(container_name)
                self._remove_workspace(workspace)
                last_error = RuntimeError("docker run 超时")
                continue

            if result.returncode != 0:
                self._remove_workspace(workspace)
                stderr = result.stderr.strip()
                # 端口被抢占时重试
                if "port is already allocated" in stderr or "address already in use" in stderr:
                    last_error = RuntimeError(f"端口 {port} 被占用：{stderr}")
                    continue
                raise SandboxUnavailableError(
                    error_codes.SANDBOX_RUN_FAILED, details={"reason": stderr}
                )

            container_id = result.stdout.strip()
            preview_url = f"http://{self.sandbox_host}:{port}/"
            expires_at = datetime.now(timezone.utc) + timedelta(seconds=self.idle_timeout)

            execution = Execution(
                user_id=user_id,
                version_id=version_id,
                container_id=container_id,
                sandbox_id=sandbox_id,
                port=port,
                status="running",
                preview_url=preview_url,
                started_at=datetime.now(timezone.utc),
                expires_at=expires_at,
            )
            try:
                self.db.add(execution)
                await self.db.commit()
                await self.db.refresh(execution)
            except Exception:
                # 容器已启动但落库失败：立即回收，避免留下无 DB 记录的孤儿
                logger.warning("沙箱执行落库失败，回收容器 %s", container_name, exc_info=True)
                self._remove_container(container_name)
                self._remove_workspace(workspace)
                raise
            return execution

        # 三次重试都失败
        if last_error:
            raise SandboxUnavailableError(
                error_codes.SANDBOX_START_FAILED,
                details={"reason": str(last_error)},
                retryable=True,
            )
        raise SandboxUnavailableError(error_codes.SANDBOX_START_FAILED)

    # ── 回收单个执行 ──────────────────────────────────────
    def _resolve_sandbox_id(self, execution: Execution) -> Optional[str]:
        """解析沙箱 uuid。新记录直接取自 sandbox_id；旧记录在删容器前按 name 反查。"""
        if execution.sandbox_id:
            return execution.sandbox_id
        if not execution.container_id:
            return None
        try:
            inspect = subprocess.run(
                ["docker", "inspect", "--format", "{{.Name}}", execution.container_id],
                capture_output=True, text=True, timeout=10,
            )
        except (OSError, subprocess.SubprocessError):
            return None
        if inspect.returncode != 0:
            return None
        name = inspect.stdout.strip().lstrip("/")
        if not name.startswith(CONTAINER_PREFIX):
            return None
        return name[len(CONTAINER_PREFIX):] or None

    def _reap(self, execution: Execution, *, status: str) -> None:
        """停容器 + 删工作区 + 置状态（不提交事务，由调用方统一 commit）。

        必须先解析 sandbox_id 再删容器：容器带 --rm，一旦删除就无法从 name 反查。
        """
        sandbox_id = self._resolve_sandbox_id(execution)
        reference = execution.container_id or (
            f"{CONTAINER_PREFIX}{sandbox_id}" if sandbox_id else None
        )
        if reference:
            self._remove_container(reference)
        if sandbox_id:
            if execution.sandbox_id is None:
                execution.sandbox_id = sandbox_id
            self._remove_workspace(self.sandbox_root / sandbox_id)
        execution.status = status

    @staticmethod
    def _remove_container(reference: str) -> None:
        """按容器名或 ID 强制删除容器（幂等：容器不存在时忽略失败）。"""
        try:
            subprocess.run(
                ["docker", "rm", "-f", reference],
                capture_output=True, text=True, timeout=30,
            )
        except (OSError, subprocess.SubprocessError) as exc:
            logger.warning("删除沙箱容器 %s 失败：%s", reference, exc)

    # ── 停止单个执行 ──────────────────────────────────────
    async def stop(self, execution_id: int, user_id: Optional[str] = None) -> Optional[Execution]:
        conditions = [Execution.id == execution_id]
        if user_id is not None:
            conditions.append(Execution.user_id == user_id)
        result = await self.db.execute(select(Execution).where(*conditions))
        execution = result.scalar_one_or_none()
        if execution is None:
            return None

        if execution.status == "running":
            self._reap(execution, status="stopped")

        await self.db.commit()
        await self.db.refresh(execution)
        return execution

    # ── 回收过期执行 ──────────────────────────────────────
    async def cleanup_expired(self) -> int:
        """扫描过期的 running 执行，停止容器并清理。返回清理数量。"""
        now = datetime.now(timezone.utc)
        result = await self.db.execute(
            select(Execution).where(
                Execution.status == "running",
                Execution.expires_at < now,
            )
        )
        expired = result.scalars().all()
        count = 0
        for execution in expired:
            self._reap(execution, status="expired")
            count += 1
        if count:
            await self.db.commit()
        self._cleanup_orphan_workspaces(await self._running_sandbox_ids())
        return count

    async def _running_sandbox_ids(self) -> set[str]:
        result = await self.db.execute(
            select(Execution).where(Execution.status == "running")
        )
        return {
            execution.sandbox_id
            for execution in result.scalars().all()
            if execution.sandbox_id
        }

    def _cleanup_orphan_workspaces(self, known_ids: set[str]) -> int:
        """清理无 running 记录的工作区目录；保护最近创建的目录，避免误删正在启动的。"""
        root = self.sandbox_root
        if not root.is_dir():
            return 0
        cutoff = time.time() - ORPHAN_WORKSPACE_GRACE_SECONDS
        removed = 0
        for entry in root.iterdir():
            if not entry.is_dir() or entry.name in known_ids:
                continue
            try:
                if entry.stat().st_mtime >= cutoff:
                    continue
            except OSError:
                continue
            shutil.rmtree(entry, ignore_errors=True)
            removed += 1
        if removed:
            logger.info("清理了 %d 个孤儿沙箱工作区", removed)
        return removed

    # ── 启动时清理残留容器 ────────────────────────────────
    @staticmethod
    def cleanup_orphan_containers() -> None:
        """删除所有带 atoms.sandbox=1 标签的残留容器（不依赖名称子串）。"""
        if not ExecutionService.is_docker_available():
            return
        ps = subprocess.run(
            ["docker", "ps", "-aq", "--filter", f"label={CONTAINER_LABEL}={CONTAINER_LABEL_VALUE}"],
            capture_output=True, text=True, timeout=30,
        )
        if ps.returncode != 0:
            return
        container_ids = [cid for cid in ps.stdout.split() if cid]
        for cid in container_ids:
            ExecutionService._remove_container(cid)
        logger.info("清理了 %d 个残留沙箱容器", len(container_ids))
