 # Atoms Studio 后续路线图

> 本路线图记录执行与隔离层（Phase 1）落地之后的分阶段方向。各阶段为用户认可的演进方向，未承诺排期；当前仅 Phase 1 进入实施（见 [execution_sandbox_plan](execution_sandbox_plan.md)）。
>
> 参考来源：Atoms 官网 atomsai.com 与帮助中心 help.atoms.dev 的 Agent 协作、集成、代码编辑、发布等文档。

## 阶段总览

> Point 估算采用 Fibonacci 敏捷故事点，基于 1 名开发者、无重大阻塞的假设。时间为粗略区间，仅供量级参考，不构成承诺。
> Point 对照：1(<1天) 2(1-2天) 3(2-3天) 5(约1周) 8(1-2周) 13(2-3周) 21(3-5周) 34(5周+)。

| Phase | 名称 | 核心目标（2-3 句） | Point | 粗略时间 | 依赖 | 状态 |
|---|---|---|---|---|---|---|
| 1 | 执行与隔离层 | 把 Provider 产出的 HTML 放进 Docker 沙箱实际运行，返回 `preview_url` 替代 iframe srcDoc。建立端口分配、容器生命周期、超时回收的执行服务。 | 13 | 2-3 周 | 无 | 计划已写，待批准 |
| 2 | 多轮迭代回路 | 让用户基于已有产物提修改意见，系统把当前 artifact_html 连同意见一起发给 Provider 生成新版本。建立"看产物→提意见→出新版本"的迭代闭环。 | 5 | 约 1 周 | Phase 1 | 方向已确认 |
| 3 | 代码编辑器 | 前端嵌入 Monaco/CodeMirror，允许直接编辑 artifact 源码，保存后重跑预览。支持文件树、编辑会话、Diff 对比。 | 8 | 1-2 周 | Phase 1 | 方向已确认 |
| 4 | 真实 AI Provider | 替换 MockOutputProvider，接入真实大模型生成 Plan/Outline/HTML。保持响应契约不变，确保上层流程不受影响。 | 8 | 1-2 周 | Phase 2 或 Phase 3 | 方向已确认 |
| 5 | 多 Agent 协作 | 引入角色体系（Team Leader/PM/Architect/Engineer 等）和 Team Mode，实现 Agent 间交接、提问卡、计划卡审批。把单轮生成升级为团队协作。 | 21 | 3-5 周 | Phase 4 | 方向已确认 |
| 6 | 工具与集成框架 | 建立工具注册表，支持内置工具、MCP、外部连接器三种来源，Agent 可发现并调用工具。定义统一的执行与权限模型。 | 21 | 3-5 周 | Phase 4（或 Phase 5） | 方向已确认 |
| 7 | 安全扫描与质量门禁 | 作为内置工具实现安全扫描，构建后/发布前自动检测密钥泄漏、XSS、权限风险，出报告并支持阻断或带风险发布。 | 8 | 1-2 周 | Phase 1, Phase 6 | 方向已确认 |
| 8 | 生产预览通道 | 通过反向代理/子域名把沙箱端口安全暴露给远程用户，解决 127.0.0.1 仅本机可访问的问题。 | 8 | 1-2 周 | Phase 1 | 方向已确认 |
| 9 | 发布与部署 | 一键发布到公开 URL，支持自定义域名、暂停/下线、版本回滚、自托管导出。把预览产物变成可对外的正式站点。 | 13 | 2-3 周 | Phase 8, Phase 7 | 方向已确认 |
| 10 | 构建终端与实时反馈 | 预览区旁实时展示构建 stdout/stderr、文件创建、错误日志，让用户看到 Agent 实际在做什么。 | 5 | 约 1 周 | Phase 1 | 方向已确认 |
| 11 | 知识库与工作区上下文 | 工作区级持久 system prompt + 知识库（RAG）+ 文件引用，所有对话继承上下文，提升生成质量与一致性。 | 13 | 2-3 周 | Phase 4 | 方向已确认 |
| 12 | 消息队列与任务编排 | Agent 工作中用户可排队后续指令，支持重排、编辑、暂停/恢复，不打断当前任务。 | 5 | 约 1 周 | Phase 5（或 Phase 4） | 方向已确认 |

**合计：约 128 points，约 22-32 周（单人）。** 多人并行可压缩，核心链路（1→2→4→5→6）不可压缩。

## 非功能性需求（横切关注点）

以下 NFR 不单独成 Phase，而是嵌入到对应 Phase 中实施。按优先级排列，P0 必须在 Phase 1 前或同期落地。

### P0 — 基础安全与隔离（Phase 1 前/同期）

| 项 | 当前状态 | 目标 | 落地 Phase |
|---|---|---|---|
| CORS 收紧 | `allow_origin_regex=".*"` + 凭据 | 生产环境限制为前端域名，dev 放开 | Phase 1 同期 |
| 请求体大小限制 | artifact_html 无上限 | 限制 artifact 最大体积（如 5MB），超限 413 | Phase 1 同期 |
| 速率限制 | 无 | auth 接口防暴力破解；artifact/build 接口防 DoS；按 IP + 用户限流 | Phase 1 同期 |
| 沙箱资源隔离 | 未实施 | Docker `--read-only`、`--cap-drop=ALL`、CPU/内存/PID 限制、只读挂载 | Phase 1（已在计划中） |
| artifact HTML 安全 | 仅校验结构 | 沙箱内渲染（脱离主站同源）+ 发布前安全扫描 | Phase 1 + Phase 7 |

### P1 — 多用户与数据安全（随核心功能落地）

| 项 | 当前状态 | 目标 | 落地 Phase |
|---|---|---|---|
| 多用户数据隔离 | studio 路由共享 `studio-shared` 数据 | 按 user_id 隔离项目/消息/版本，查询带 user 过滤 | Phase 4 前后（真实用户接入时） |
| 服务端并发控制 | 仅前端 busy 状态 | 同项目构建加服务端锁（DB 行锁或 Redis），防止并发写冲突 | Phase 2（多轮迭代引入并发风险时） |
| 安全响应头 | 主应用缺失 | 加 CSP、HSTS、X-Content-Type-Options、Referrer-Policy | Phase 8（生产预览通道上线前） |
| 审计日志 | 仅有应用日志 | 记录关键操作（登录、构建、发布、配置变更）的 actor + 时间 + 对象 | Phase 5（多 Agent 引入更多操作时） |
| 密钥管理 | 仅 env 读取 | JWT/OIDC/AI key 不进日志、提供轮换机制 | Phase 4（接真实 AI 时） |

### P2 — 生产就绪（发布/部署阶段）

| 项 | 目标 | 落地 Phase |
|---|---|---|
| 成本控制 | 追踪每轮 AI token 用量与沙箱资源消耗，设用户/工作区配额 | Phase 9 |
| 可观测性 | 结构化日志 + 请求指标 + 链路追踪（现有 telemetry 模块扩展） | Phase 8 前 |
| 孤儿资源回收 | 沙箱容器/工作区/数据库连接泄漏兜底清理 | Phase 1（已含回收器）+ 持续 |
| 备份与恢复 | 数据库定期备份、项目版本可恢复 | Phase 9 |
| 优雅降级 | AI/沙箱不可用时返回明确错误，不崩溃；前端降级展示 | 贯穿各 Phase |

### NFR 与 Phase 的映射总览

```
Phase 1  ── 沙箱隔离 + CORS + 限流 + 请求体限制
Phase 2  ── 服务端并发锁
Phase 4  ── 密钥管理 + 多用户数据隔离
Phase 5  ── 审计日志
Phase 7  ── artifact 安全扫描
Phase 8  ── 安全响应头 + 可观测性
Phase 9  ── 成本控制 + 备份恢复
```

> **说明**：当前应用尚未跑过自动化安全扫描（SAST/DAST）。Phase 7 的安全扫描工具是面向"产物 HTML"的；对"平台自身代码"的安全扫描建议在 Phase 8/9 前引入 CI 级别的 SAST（如 Semgrep/Bandit）和依赖审计（pip-audit），作为质量门禁的一部分。

## 代码质量门禁（横切关注点）

命名规范、代码分层、测试分层已写入 [开发规范](../docs/开发规范.md) 与 [测试策略与规范](../docs/测试策略与规范.md)。以下是**可执行的质量门禁**，当前大部分缺失，需在 Phase 1 同期建立，贯穿后续所有 Phase。

### 当前状态

| 项 | 状态 |
|---|---|
| 命名规范 | ✅ 已写入开发规范 |
| 代码分层与依赖方向 | ✅ 已写入开发规范 |
| 前端 ESLint | ✅ 已有 `eslint.config.js` |
| 后端 lint/format | ❌ 无 ruff/flake8/black 配置 |
| 后端类型检查 | ❌ 无 mypy 配置 |
| 测试覆盖率阈值 | ❌ `.coveragerc` 无 `fail_under`，无最低覆盖率要求 |
| CI 流水线 | ❌ 无 `.github/workflows` |
| pre-commit hooks | ❌ 无配置 |
| 依赖审计 | ❌ 无 pip-audit / npm audit |
| SAST | ❌ 无 Semgrep / Bandit |

### P0 — Phase 1 同期必须建立

| 门禁 | 要求 | 落地方式 |
|---|---|---|
| 后端 lint + format | 统一代码风格，禁止未通过 lint 的代码合并 | 引入 `ruff`（替代 flake8+isort+black），配置 `ruff.toml`，CI 跑 `ruff check` + `ruff format --check` |
| 测试覆盖率阈值 | 新增业务代码必须有对应测试，核心模块覆盖率不低于阈值 | `.coveragerc` 加 `fail_under = 70`（整体），`core/`、`services/` 关键模块单独要求 ≥ 80%；CI 跑覆盖率不达标则失败 |
| 测试全绿准入 | 合并前单元+集成测试必须全绿 | CI 跑前端 `pnpm test` + 后端 `pytest`，失败则阻断合并 |
| 命名与分层合规 | 符合开发规范 §2-3 | CI 的 lint + 代码评审清单双重检查 |

### P1 — 随核心功能逐步加严

| 门禁 | 要求 | 落地 Phase |
|---|---|---|
| 后端类型检查 | 核心模块（`core/`、`services/`）通过 mypy | Phase 4（接真实 AI 前，类型边界更重要） |
| CI 流水线 | GitHub Actions：lint → test → coverage → build，PR 必过 | Phase 1 同期建立骨架，Phase 4 前完善 |
| pre-commit hooks | 提交前自动 ruff format + ruff check，防止未格式化代码入库 | Phase 1 同期 |
| 依赖审计 | 后端 `pip-audit`、前端 `npm audit`，高危依赖阻断合并 | Phase 4（接真实 AI/外部工具前） |

### P2 — 生产就绪

| 门禁 | 要求 | 落地 Phase |
|---|---|---|
| SAST | Semgrep / Bandit 扫描平台自身代码的安全漏洞 | Phase 8/9 前 |
| 覆盖率趋势 | 覆盖率不得随 PR 下降（diff-coverage） | Phase 8 前 |
| 构建产物检查 | 前端构建无 error、产物大小在阈值内 | Phase 9 |

### 与已有文档的关系

- 命名规范、代码分层、测试分层：继续沿用 [开发规范](../docs/开发规范.md) 与 [测试策略与规范](../docs/测试策略与规范.md)，不重复。
- 本节补充的是**可执行门禁**（工具+阈值+CI），是对现有规范的落地保障。
- 覆盖率阈值建议：先设整体 70%、核心模块 80%，随 Phase 推进逐步提高，避免一开始因阈值过高阻碍开发。

## Phase 2 与 Phase 3 的优先级调整

**结论：Phase 2（多轮迭代回路）优先于 Phase 3（代码编辑器）。**

理由：
- 多轮迭代是对话式工作台的核心闭环：用户看了产物后提修改意见，系统基于已有 artifact 重新生成新版本。没有这个回路，工作台只能"一次性出活"，无法迭代。
- 代码编辑器是高级能力，依赖用户能看懂并修改 HTML/JS/CSS；在多轮回路跑通之前，编辑器的使用场景有限。
- 依赖关系上，两者都只依赖 Phase 1（执行与隔离层），互不依赖，因此可以按用户价值排序，多轮回路的用户价值更高。

排序后的实施顺序：Phase 1 → Phase 2 → Phase 3 → Phase 4 → Phase 5 → Phase 6 → Phase 7 / Phase 8 → Phase 9 → Phase 10 / Phase 11 / Phase 12。

## 依赖关系验证

逐一确认每个 Phase 在其依赖 Phase 完成后是否获得足够支持，并标注风险与可调整空间。

### Phase 1 → Phase 2（多轮迭代回路）
- Phase 1 提供：沙箱执行 + `preview_url` + 版本存库。
- Phase 2 需要：能取到当前版本的 `artifact_html` 作为上下文、能存新版本、能预览新版本。
- **结论：支持充分。** Phase 2 的核心改动是 artifact 路由增加 `base_version_id` 参数，把上版 HTML 传给 Provider；存库和预览复用 Phase 1 能力。
- 风险：Provider 契约需支持"基于已有 HTML 修改"，若真实模型（Phase 4）未到位，用 Mock 验证流程即可。

### Phase 1 → Phase 3（代码编辑器）
- Phase 1 提供：沙箱预览能力。
- Phase 3 需要：保存编辑后的 HTML、触发沙箱重跑、展示预览。
- **结论：支持充分。** 编辑器只需把修改后的 HTML 走一遍 Phase 1 的执行服务即可。
- 可调整：Phase 3 与 Phase 2 互不依赖，可并行；若人力有限，按已定优先级先做 Phase 2。

### Phase 2/3 → Phase 4（真实 AI Provider）
- Phase 2/3 提供：完整的调用链路（需求→Plan→Outline→HTML→存库→预览）。
- Phase 4 需要：一个可替换的 Provider 注入点。
- **结论：支持充分。** `RealOutputProvider` 契约已存在，只需实现并替换默认注入。Phase 2/3 的链路是验证真实输出效果的最佳场景。
- 前置条件：需确认目标模型是否支持 function-calling（影响 Phase 5/6）、是否需要 embedding 模型（影响 Phase 11）。建议在 Phase 4 选型时一并考虑。

### Phase 4 → Phase 5（多 Agent 协作）
- Phase 4 提供：真实模型调用能力。
- Phase 5 需要：多次模型调用、角色 prompt、任务编排、状态持久化、人机交互卡（提问/计划审批）。
- **结论：基本支持，但需补充编排层。** Phase 4 只提供单次生成，Phase 5 需要在其上构建编排器（顺序/条件分支、checkpoint、human-in-the-loop）。技术选型（LangGraph 或自研）需在 Phase 5 启动时定。
- 风险：若 Phase 4 选的模型不支持稳定的多轮 tool/function calling，Phase 5 的交接质量会受影响。

### Phase 4/5 → Phase 6（工具与集成框架）
- 原依赖写的是 Phase 5，**实际可放宽到 Phase 4**。
- Phase 4 提供：模型调用（若支持 function-calling）。
- Phase 6 需要：工具注册表、MCP client、OAuth 连接器、权限模型、沙箱内执行。
- **结论：Phase 4 即可启动，Phase 5 让工具更强大。** 单 Agent 也能调用工具（如 Engineer 自己跑覆盖率）；多 Agent 时不同角色可使用不同工具集。
- 建议：若想提前验证工具机制，可在 Phase 4 完成后先做内置工具（覆盖率、Lint），MCP 和外部连接器后置。
- 风险：工具执行的沙箱隔离需复用 Phase 1 的隔离思路，但工具可能需要写操作（如 GitHub 提交），隔离模型要区分"只读工具"和"需确认的写工具"。

### Phase 1 + Phase 6 → Phase 7（安全扫描）
- Phase 1 提供：沙箱执行环境。
- Phase 6 提供：工具注册与执行框架。
- Phase 7 需要：把安全扫描作为内置工具注册，在构建后/发布前触发。
- **结论：支持充分。** 安全扫描本质是对 `artifact_html` 做静态分析，Phase 6 的工具框架足以承载。
- 可简化：首期可不依赖 Phase 6，直接在 artifact 路由后硬编码调用扫描函数；但为了统一工具管理，建议走 Phase 6。

### Phase 1 → Phase 8（生产预览通道）
- Phase 1 提供：绑定 127.0.0.1 的沙箱端口。
- Phase 8 需要：把端口通过反向代理/子域名暴露给远程用户，保持隔离。
- **结论：支持充分。** Phase 8 是网络层叠加，不改沙箱本身。
- 风险：安全边界复杂（防止用户通过预览端口访问宿主内网），需专门的安全设计与评审。

### Phase 8 + Phase 7 → Phase 9（发布与部署）
- Phase 8 提供：远程可访问的预览 URL。
- Phase 7 提供：发布前安全门禁。
- Phase 9 需要：托管平台、域名管理、暂停/下线、回滚、导出。
- **结论：支持充分。** 发布 = 把某个版本的沙箱产物固化为静态站点并托管；安全扫描在发布前阻断。
- 前置：需决定托管方案（自建 nginx/对象存储 CDN / 第三方如 Vercel/Netlify）。

### Phase 1 → Phase 10（构建终端）
- Phase 1 提供：沙箱进程。
- Phase 10 需要：捕获沙箱 stdout/stderr，实时推送到前端。
- **结论：支持充分，且可提前。** Phase 10 只依赖 Phase 1 的执行服务，甚至可以在 Phase 1 实施时一并做（把日志流作为执行服务的一部分）。
- 建议：若 Phase 1 实施时有余力，把终端输出纳入 Phase 1；否则单独立 Phase 10。

### Phase 4 → Phase 11（知识库与上下文）
- Phase 4 提供：模型调用。
- Phase 11 需要：embedding 模型、向量存储、文件解析、RAG 检索、上下文注入。
- **结论：基本支持，但需额外组件。** Phase 4 的 chat 模型不提供 embedding，需单独接入 embedding 模型（可用开源如 bge-m3 或模型厂商的 embedding API）和向量数据库（pgvector / Chroma / Qdrant）。
- 建议：Phase 4 选型时确认是否同时提供 embedding API，否则 Phase 11 需额外集成。

### Phase 5/4 → Phase 12（消息队列）
- 原依赖写的是 Phase 5，**可放宽到 Phase 4**。
- Phase 4/5 提供：任务执行模型。
- Phase 12 需要：任务队列状态、排队/重排/暂停 UI、任务调度。
- **结论：Phase 4 即可做简化版，Phase 5 让队列更有意义。** 单 Agent 时队列只排队"下一条指令"；多 Agent 时可排队给不同角色的指令。
- 建议：若 Phase 5 编排器已实现任务状态机，Phase 12 复用即可；否则单独立实现。

### 依赖关系小结

| 可提前/并行的 Phase | 说明 |
|---|---|
| Phase 3 | 与 Phase 2 并行，都只依赖 Phase 1 |
| Phase 8 | Phase 1 完成后即可做，不必等 Phase 5/6 |
| Phase 10 | 可纳入 Phase 1 一起做 |
| Phase 6 | 可从 Phase 5 提前到 Phase 4（先做内置工具） |
| Phase 12 | 可从 Phase 5 提前到 Phase 4（简化版队列） |

**关键链路上的硬依赖**：Phase 1 → Phase 4 → Phase 5 → Phase 6（多 Agent 用工具）→ Phase 7/9。这条链不可压缩，是产品从"单轮 mock 生成"到"多 Agent 带工具真实开发"的核心路径。

## 各阶段概要

### Phase 1：执行与隔离层
- 方案：1A（隔离静态服务）+ 2A（Docker 容器）+ 3A（临时服务超时回收）。
- HTML 写入隔离工作区 → `docker run` 起 `nginx:alpine`（只读挂载、`--cap-drop=ALL`、`--read-only`、`-p 127.0.0.1:<port>:80`、CPU/内存/PID 限制）→ 返回 `http://127.0.0.1:<port>/` → 超时回收。
- 详细计划见 [execution_sandbox_plan](execution_sandbox_plan.md)。

### Phase 2：多轮迭代回路
- 用户在预览旁输入修改意见（如"把标题改成红色"），后端把当前 `artifact_html` + 修改意见传给 Output provider，生成新 HTML，存为新版本（`version_no + 1`），更新项目 `current_version`。
- 保持 Output provider 契约不变，仅在请求中携带上一版 artifact_html 作为上下文。
- 需要前端新增"修改意见"输入区，后端 artifact 路由支持传入 `base_version_id`。
- **决策点（Phase 2 启动时定）**：
  - 传给 Provider 的上下文是完整 `artifact_html` 还是 diff（首期建议传完整 HTML，简单可靠）。
  - 新版本的 `version_no` 策略：当前最大序号 +1，恢复历史版本后再构建取历史最大 +1。

### Phase 3：代码编辑器
- 前端嵌入 Monaco 或 CodeMirror，直接展示/编辑当前版本的 `artifact_html`。
- 编辑后保存为新版本（或覆盖当前版本，待定），并重新启动沙箱预览。
- 与 Phase 2 的关系：多轮回路是"用自然语言改"，编辑器是"用代码改"，两者可并存。
- 参考 Atoms：编辑器支持文件树、Diff 对比、编辑会话（Submit all / Discard all）、把文件作为上下文加入对话（`#` 引用）、下载项目为 ZIP。
- **决策点（Phase 3 启动时定）**：
  - 编辑器选型：Monaco（VS Code 内核，功能全但体积大）vs CodeMirror（轻量、可定制）。
  - 编辑保存语义：保存为新版本（保留历史）vs 覆盖当前版本（Atoms 是编辑会话 Submit all 后应用）。

### Phase 4：真实 AI Provider
- `services/studio_output.py` 中 `RealOutputProvider` 契约已存在，默认不创建不调用。
- 替换 `MockOutputProvider`，接入真实大模型，保持 Plan/Outline/HTML 响应形状不变。
- 建议在 Phase 2 或 Phase 3 跑通后再接入，以便用真实生成内容验证迭代回路与编辑器。
- **决策点（Phase 4 启动时定）**：
  - 模型选型：需确认是否支持 **function-calling / tool use**（直接影响 Phase 5 多 Agent 交接和 Phase 6 工具调用）。
  - 是否同时提供 **embedding API**（影响 Phase 11 知识库，若无则需单独接入 embedding 模型）。
  - API key 的存储与轮换方案（不写死在代码里）。

### Phase 5：多 Agent 协作
参考 Atoms 的 Team Mode 设计：
- **角色体系**：Team Leader（协调分派）、Product Manager（需求/范围/优先级）、Architect（系统结构/数据模型/集成）、Engineer（编码/测试）、Data Analyst（数据分析）、Deep Researcher（市场/竞品/技术调研）。当前可先实现核心 3-4 个角色。
- **Team Mode 开关**：关闭时单 Agent（Engineer）处理；开启时 Team Leader 协调多个 specialist。
- **@mention 直接指派**：用户可 `@某角色` 直接分派聚焦任务。
- **Agent 间交接**：工作可从一个 Agent 流转到另一个，用户在 Chat 中跟随 Working Process。
- **交互卡片**：
  - 问题卡（Question Card）：Agent 向用户追问信息，用户回答后继续。
  - 计划卡（Plan Card）：Agent 提出计划，用户 Approve / Decline 后才执行。
  - 版本卡（Version Card）：产出新版本时出现，可 Preview。
- **依赖**：需要真实 AI Provider（Phase 4），因为多 Agent 本质是多次模型调用 + 角色 prompt。
- **技术选型**：可用 LangGraph（状态图 + checkpoint + human-in-the-loop）或自研轻量编排层；先做角色 prompt + 顺序交接，再上图编排。
- **决策点（Phase 5 启动时定）**：
  - 编排框架：LangGraph / AutoGen / 自研轻量编排器（需评估对 human-in-the-loop 和 checkpoint 的支持）。
  - 首批角色集合：建议先实现 Team Leader + Engineer 两个角色跑通交接，再逐步扩展 PM / Architect。

### Phase 6：工具与集成框架
这是用户特别关注的"平台加载多种工具"的能力。参考 Atoms 的 Connector 机制和 MCP：

**工具的三种来源**：
1. **内置工具**：平台自带，不需要用户配置，如测试覆盖率计算、安全扫描、Lint、格式化。
2. **MCP 工具**：遵循 MCP（Model Context Protocol）协议的外部工具服务器，用户在配置中填入 MCP server 地址，平台启动 stdio 进程或连接远程 endpoint。
3. **外部连接器**：第三方服务集成（GitHub、Supabase、Stripe 等），通过 OAuth 授权，平台提供 Connector catalog 供用户浏览连接。

**工具如何接入、AI 如何发现和装载**：
- **工具注册表（Tool Registry）**：后端维护一个工具注册表，每条记录包含工具名、描述、参数 schema、执行方式（内置函数 / MCP / REST）、权限范围、是否需要用户确认。
- **发现**：AI 不"自动下载"工具，而是由用户在工作区/对话级别启用工具；启用的工具列表注入到 Agent 的 system prompt 或通过 function-calling 暴露给模型。模型根据描述决定调用哪个工具。
- **装载与执行**：
  - 内置工具：直接调用平台内函数（如 `compute_coverage(html)`）。
  - MCP 工具：后端启动 MCP client，按 MCP 协议调用工具，结果返回给 Agent。
  - 外部连接器：通过已授权的 OAuth token 调用第三方 API。
- **安全边界**：
  - 最小权限：连接时只申请必要 scope，用户可审阅。
  - 写操作确认：涉及创建/更新外部数据时，弹出确认卡，用户同意后才执行。
  - 沙箱执行：工具在隔离环境运行，不直接访问宿主。
- **首批内置工具**：测试覆盖率计算、安全扫描（Phase 7）、HTML Lint、依赖审计。
- **决策点（Phase 6 启动时定）**：
  - **工具执行的隔离模型**：与 Phase 1 的静态服务沙箱**分离**，单独设计"工具沙箱"。Phase 1 沙箱是只读静态服务（无代码执行、无网络出站）；工具沙箱需要执行代码、可能需要网络出站、可能写临时文件，安全策略不同。两者共享 Docker 基础设施但独立配置。
    - **是否需要现在改造 Phase 1：不需要。** Phase 1 无需为 Phase 6 预留，保持 `ExecutionService` 模块化、便于新增沙箱类型即可。工具若需读取 artifact，复用 Phase 1 工作区的只读挂载。
  - MCP 客户端库选型（Python 生态的 MCP SDK）。
  - 外部连接器的 OAuth 授权流程与 token 存储方案。
  - 工具权限分级：只读工具自动放行；写操作工具需用户确认卡。

### Phase 7：安全扫描与质量门禁
参考 Atoms 发布面板的 Security scan：
- 在构建完成后、发布前自动运行安全扫描。
- 检查项：硬编码密钥/API key、不安全的外链、XSS 风险、缺失的 CSP、权限配置、用户数据暴露。
- 输出：扫描状态（进行中 / 已通过 / 有发现），发现项列表，"一键修复"建议。
- 发布策略：有高危发现时阻断发布；中低危可"Publish Anyway"但需确认风险。
- 依赖：Phase 1（沙箱）和 Phase 6（工具框架）——安全扫描本身作为一个内置工具接入。
- **决策点（Phase 7 启动时定）**：
  - 扫描规则集与覆盖范围（密钥正则、CSP、XSS、外链白名单等）。
  - 严重等级阈值与发布门禁策略（哪些级别阻断、哪些允许带风险发布）。
  - 首期可简化为不依赖 Phase 6、直接在 artifact 路由后调用扫描函数。

### Phase 8：生产预览通道
- 当前 `preview_url` 绑定 `127.0.0.1`，仅本机可访问。
- 生产环境需要通过反向代理或子域名把沙箱端口暴露给远程用户，同时保持隔离边界。
- 涉及网络与安全配置，需单独设计。
- **决策点（Phase 8 启动时定，无需现在决定）**：
  - 远程暴露方案：反向代理按路径分发 vs 子域名通配符（`*.preview.example.com`）。
  - 网络隔离策略：防止用户通过预览端口访问宿主内网（网络命名空间 / 防火墙规则）。
  - **是否需要现在决定：不需要。** Phase 1 的端口分配（socket 取随机端口 + `docker -p 127.0.0.1:port:80`）天然兼容后续任何反向代理方案，不锁定具体选型。等到 Phase 8 启动时再根据部署环境决定。

### Phase 9：发布与部署
参考 Atoms 的 Publish 流程：
- 一键发布到平台托管的公开 URL（如 `[name].pub.atoms.world`）。
- 支持自定义域名。
- 更新已发布站点（编辑后不自动上线，需点 Update）。
- 暂停/下线（App Status: Live / Paused / Unpublished）。
- 发布前强制过安全扫描（Phase 7）。
- 导出自托管包（ZIP + Dockerfile）。
- 依赖：Phase 8（生产预览通道）。
- **决策点（Phase 9 启动时定，无需现在决定）**：
  - 托管方案：自建 nginx + 对象存储 CDN vs 第三方（Vercel / Netlify / Cloudflare Pages）。
  - 自定义域名与证书管理（自动续期）。
  - 版本回滚与数据迁移策略（数据库是否同步回滚）。
  - **是否需要现在决定：不需要。** 托管方案强依赖部署环境、预算和运维能力，Phase 1-7 不涉及。到 Phase 9 启动时再评估。

### Phase 10：构建终端与实时反馈
参考 Atoms App Viewer 旁的 Terminal 面板：
- 在预览区旁实时展示 Agent 的构建活动：文件创建、代码生成、命令执行、错误日志。
- 支持刷新、清屏、复制。
- 依赖：Phase 1（沙箱执行层，终端展示沙箱内的 stdout/stderr）。

### Phase 11：知识库与工作区上下文
参考 AtomsAI 的 Workspace 概念：
- 工作区 = 持久 system prompt + 知识库 +（可选）工具 + 自定义 UI。
- 用户可上传文档/文件到知识库，Agent 在对话中通过 RAG 检索引用。
- 支持把项目文件作为上下文加入对话（`#` 引用文件）。
- 依赖：Phase 4（真实 AI Provider，需要 RAG 能力）。
- **决策点（Phase 11 启动时定）**：
  - embedding 模型选型：开源（bge-m3 等本地部署）vs 模型厂商 embedding API。
  - 向量数据库：pgvector（复用现有 PostgreSQL）/ Chroma / Qdrant。
  - 文件解析与分块策略（PDF/DOCX/代码的 chunk 大小与重叠）。

### Phase 12：消息队列与任务编排
参考 Atoms 的 Queue 功能：
- Agent 工作中，用户可输入后续指令并排队，不打断当前任务。
- 队列支持：重排、编辑、删除、暂停处理、恢复处理、立即发送。
- 依赖：Phase 5（多 Agent 协作，队列主要在多任务场景有价值）。

## Atoms 已实现但我们尚未规划的产品点（备忘）

以下是 Atoms 官网/帮助中心体现、但未排入上述 Phase 的能力，留作后续讨论：

- **SEO 优化（Sarah 角色）**：针对 Web 项目的 SEO 内容规划与改进。
- **广告投放（Adrian 角色）**：Google Ads 准备与分析。
- **积分/用量计费**：每轮对话显示 Credits used，工作区余额管理。
- **密钥与密钥管理**：独立于源码的 secrets 管理，不在对话中粘贴密钥。
- **分享与导出**：Share（打开 Atoms 项目本身）vs Publish（打开成品网站），导出项目 ZIP。
- **磁盘空间管理**：查看存储用量、清理大文件。
- **多模型选择**：用户可在消息中用 `#` 指定模型（Anthropic / Gemini / Open models）。
