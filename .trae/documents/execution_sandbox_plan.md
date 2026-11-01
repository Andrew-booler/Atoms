# 执行与隔离层（HTML 沙箱运行）实现计划

> 决策：1A（隔离静态服务）+ 2A（Docker 容器）+ 3A（临时服务，超时回收）。
> Output provider 本轮不变，产物仍为单文件 HTML；执行层把 HTML 放进只读工作区，由 Docker 容器起静态服务，返回 `http://127.0.0.1:<port>/` 供前端预览。

## 仓库调研结论

- **产物流向**：`routers/studio.py::artifact` 调用 `studio_ai.get_provider().artifact()` 拿到 HTML → `validate_artifact_html` 校验 `<body`/`</html>` → 存入 `studio_versions.artifact_html` → 返回 `BuildResponse.artifact_html`。
- **前端渲染**：`ArtifactPreview.tsx` 用 `<iframe srcDoc={artifact_html}>` 直接注入，没有任何执行/隔离环节。
- **数据模型**：`models/studio_versions.py` 已有 `artifact_html`，无运行态表。
- **环境**：Docker Desktop 已在运行；后端 Python 3.15，FastAPI + asyncpg。
- **配置入口**：`core/config.py::Settings` 支持动态环境变量；`core/environment.py` 提供 `get_env_bool/int`。

## 目标行为

1. 构建产物时，把 HTML 写入隔离工作区并启动一个 Docker 容器，以只读方式挂载工作区、仅对 `127.0.0.1` 暴露端口。
2. 响应里返回 `preview_url`（如 `http://127.0.0.1:52341/`），前端改用 `iframe src` 加载。
3. 容器有空闲超时，到时自动停止并删除；后端有回收器兜底清理残留容器与工作区。
4. 可对已保存版本重新运行预览；可手动停止。
5. Docker 不可用时，`/artifact` 返回明确的 503（不崩溃），测试自动 skip。

## 文件与模块

| 路径 | 变更 |
|---|---|
| `services/execution.py` | 新增。`ExecutionService`：分配端口、写工作区、`docker run`、登记运行表、停止、列出、回收 |
| `models/execution.py` | 新增。`Execution` ORM（id/version_id/container_id/port/status/preview_url/started_at/expires_at） |
| `alembic/versions/..._add_executions.py` | 新增迁移建表 |
| `routers/studio.py` | `artifact` 路由在存库后调用执行层；新增 `GET /versions/{id}/run`、`DELETE /executions/{id}` |
| `schemas/studio.py` | `BuildResponse` 增加 `preview_url`；新增执行相关响应模型 |
| `frontend/src/components/studio/ArtifactPreview.tsx` | `srcDoc` → `src`（有 `preview_url` 时） |
| `core/config.py` | 新增沙箱相关 env 读取（沿用动态 `__getattr__`，无需改字段） |
| `tests/unit/test_execution.py` | 单元测试（mock docker CLI） |
| `tests/integration/test_execution_api.py` | 真实 Docker 集成测试（不可用 skip） |
| `docs/执行与隔离层设计.md` | 设计与运维说明 |

## 实现步骤（依赖顺序）

1. **数据模型与迁移**：定义 `Execution` 模型并生成 Alembic 迁移；`main.py` 已自动发现 models 包。
2. **执行服务骨架**：`services/execution.py`
   - 端口分配：`socket.socket` 绑定 `("127.0.0.1", 0)` 取端口后关闭，传给容器。
   - 工作区：`Path(settings.sandbox_root) / execution_id`，写入 `index.html`，权限 `0o644`。
   - 起容器（subprocess 调 `docker run`，避免引入 `docker` Python 包）：
     ```
     docker run -d --name atoms-sandbox-<id> \
       --rm --read-only \
       --cap-drop=ALL --security-opt=no-new-privileges \
       --cpus=0.5 --memory=128m --pids-limit=64 \
       --network=bridge -p 127.0.0.1:<port>:80 \
       -v <workspace>:/usr/share/nginx/html:ro \
       --tmpfs /var/cache/nginx:rw,noexec,size=16m \
       --tmpfs /var/run:rw,noexec,size=8m \
       nginx:alpine
     ```
   - `nginx:alpine` 默认配置即服务 `/usr/share/nginx/html`，无需自定义配置文件。
   - 容器名加 `atoms-sandbox-` 前缀，便于识别与批量清理。
3. **运行登记表**：`ExecutionService` 启动成功后写 `Execution` 行，`status=running`、`expires_at=now+idle_timeout`。
4. **接线 artifact 路由**：存库后调用 `run_html(html, version_id)`；把 `preview_url` 填进 `BuildResponse`。失败则记录 `status=failed` 并返回 503（不影响版本已存库）。
5. **预览与停止接口**：
   - `GET /api/v1/studio/versions/{id}/run`：读 `artifact_html` → `run_html` → 返回 `preview_url`。
   - `DELETE /api/v1/studio/executions/{id}`：停止容器、删工作区、标 `stopped`。
6. **回收器**：`ExecutionService.cleanup_expired()` 扫描 `expires_at < now` 的 `running` 行，`docker stop` + 删工作区 + 标 `stopped`。挂到 FastAPI lifespan（启动时注册后台 task，关闭时停止）。
7. **前端适配**：`ArtifactPreview` 有 `preview_url` 用 `src`，否则降级 `srcDoc`（兼容旧版本数据）。
8. **测试**：单元测试 mock `subprocess.run` 校验命令参数与端口回写；集成测试用真实 Docker 跑一段含 `<h1>ok</h1>` 的 HTML，`httpx.get(preview_url)` 断言包含 `ok`，再 `DELETE` 后断言容器已移除。
9. **文档**：`docs/执行与隔离层设计.md` 记录架构、安全边界、env 配置、排障命令。

## 依赖与考量

- **不新增 Python 依赖**：用 `subprocess` 调 `docker` CLI；`nginx:alpine` 镜像需首次 `docker pull`（在执行服务首次运行前确保拉取，或启动时检查并拉取）。
- **配置项**（动态 env，默认值写在 `ExecutionService` 里）：
  - `SANDBOX_ROOT`：默认 `tempfile.gettempdir() / "atoms_sandbox"`
  - `SANDBOX_IMAGE`：默认 `nginx:alpine`
  - `SANDBOX_IDLE_TIMEOUT`：默认 `600`（秒）
  - `SANDBOX_HOST`：默认 `127.0.0.1`
  - `SANDBOX_CPU`/`SANDBOX_MEMORY`/`SANDBOX_PIDS_LIMIT`：资源上限
- **安全边界**：工作区 `:ro`、容器根文件系统 `--read-only`、`--cap-drop=ALL`、`no-new-privileges`、端口只绑 `127.0.0.1`、CPU/内存/PID 限制、`--tmpfs` 给 nginx 必要可写目录。
- **失败处理**：`docker run` 非 0 退出 → 标 failed，清理工作区，返回 503；不影响 `artifact_html` 已落库。
- **并发**：每次执行独立容器与端口，天然隔离；`/run` 重复调用会起新容器（旧的由回收器清理）。
- **Windows 兼容**：工作区路径用 `pathlib`，`-v` 挂载时 Docker Desktop 会处理 Windows 路径；容器内路径固定 `/usr/share/nginx/html`。

## 验证

- 单元：`tests/unit/test_execution.py` mock subprocess，断言 `docker run` 参数含 `--read-only`、`:ro`、`127.0.0.1:`、`--cap-drop=ALL`；断言端口从 socket 取得；断言超时行写入。
- 集成：`tests/integration/test_execution_api.py` 真实 Docker 起容器 → `httpx.get(url)` 命中 HTML → 停止后 `docker inspect` 返回非 0。
- 回归：现有 87 个测试全绿；`/artifact` 返回体新增 `preview_url` 字段不破坏前端已有逻辑。
- 手动：浏览器打开预览 URL，确认页面渲染；等超时后容器消失。

## 风险

- **Docker 未安装/未启动**：执行层返回 503，artifact 仍保存；前端降级到 `srcDoc`。
- **端口被占用**：socket 分配后到 `docker run` 之间端口可能被抢占 → 捕获失败后重试最多 3 次换端口。
- **镜像拉取慢/失败**：首次启动前 `docker image inspect nginx:alpine`，不存在则 `docker pull`；失败返回 503 并提示。
- **残留容器**：后台回收器 + 启动时扫一遍带 `atoms-sandbox-` 前缀的容器清理掉。
- **工作区清理失败**：记录日志，不阻塞下次执行（目录名用 uuid，不会冲突）。
