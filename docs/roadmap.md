 # Atoms Studio 后续路线图

> 本路线图记录执行与隔离层（Phase 1）落地之后的分阶段方向。各阶段为用户认可的演进方向，未承诺排期；当前 Phase 1–4、Phase 10、Phase 16、Phase 17 已完成（Phase 10/16/17 均为 2026-11-04，见「实现顺序与实施时点」）。Phase 10 是窗口内的临时提前项：按原顺序本应先做 Phase 5，但其体量远大于当前交付窗口，故先完整交付只依赖 Phase 1 的构建终端；**Phase 5 仍是下一轮首位**。Phase 17 仅完成本地验证与迁移，未部署生产。
>
> 参考来源：Atoms 官网 atomsai.com 与帮助中心 help.atoms.dev 的 Agent 协作、集成、代码编辑、发布等文档。

## 阶段总览

> Point 估算采用 Fibonacci 敏捷故事点，基于 1 名开发者、无重大阻塞的假设。时间为粗略区间，仅供量级参考，不构成承诺。
> Point 对照：1(<1天) 2(1-2天) 3(2-3天) 5(约1周) 8(1-2周) 13(2-3周) 21(3-5周) 34(5周+)。

| Phase | 名称 | 核心目标（2-3 句） | Point | 粗略时间 | 依赖 | 状态 |
|---|---|---|---|---|---|---|
| 1 | 执行与隔离层 | 把 Provider 产出的 HTML 放进 Docker 沙箱实际运行，返回 `preview_url` 替代 iframe srcDoc。建立端口分配、容器生命周期、超时回收的执行服务。 | 13 | 2-3 周 | 无 | ✅ 已完成 |
| 2 | 多轮迭代回路 | 让用户基于已有产物提修改意见，系统把当前 artifact_html 连同意见一起发给 Provider 生成新版本。建立"看产物→提意见→出新版本"的迭代闭环。 | 5 | 约 1 周 | Phase 1 | ✅ 已完成 |
| 3 | 代码编辑器 | 前端嵌入 Monaco/CodeMirror，允许直接编辑 artifact 源码，保存后重跑预览。支持文件树、编辑会话、Diff 对比。 | 8 | 1-2 周 | Phase 1 | ✅ 已完成 |
| 4 | 真实 AI Provider | 替换 MockOutputProvider，接入真实大模型生成 Plan/Outline/HTML。保持响应契约不变，确保上层流程不受影响。 | 8 | 1-2 周 | Phase 2 或 Phase 3 | ✅ 已完成 |
| 5 | 多 Agent 协作 | 引入角色体系（Team Leader/PM/Architect/Engineer 等）和 Team Mode，实现 Agent 间交接、提问卡、计划卡审批。把单轮生成升级为团队协作。 | 21 | 3-5 周 | Phase 4 | 方向已确认 |
| 6 | 工具与集成框架 | 建立工具注册表，支持内置工具、MCP、外部连接器三种来源，Agent 可发现并调用工具。定义统一的执行与权限模型。 | 21 | 3-5 周 | Phase 4（或 Phase 5） | 方向已确认 |
| 7 | 安全扫描与质量门禁 | 作为内置工具实现安全扫描，构建后/发布前自动检测密钥泄漏、XSS、权限风险，出报告并支持阻断或带风险发布。 | 8 | 1-2 周 | Phase 1, Phase 6 | 方向已确认 |
| 8 | 生产预览通道 | 通过反向代理/子域名把沙箱端口安全暴露给远程用户，解决 127.0.0.1 仅本机可访问的问题。 | 8 | 1-2 周 | Phase 1 | 暂缓（跳过，2026-11-04 决策：缺域名/DNS/反代外部资源） |
| 9 | 发布与部署 | 一键发布到公开 URL，支持自定义域名、暂停/下线、版本回滚、自托管导出。把预览产物变成可对外的正式站点。 | 13 | 2-3 周 | Phase 8, Phase 7 | 暂缓（连带于 Phase 8） |
| 10 | 构建终端与实时反馈 | 预览区旁实时展示构建 stdout/stderr、文件创建、错误日志，让用户看到 Agent 实际在做什么。 | 5 | 约 1 周 | Phase 1 | 已完成（2026-11-04，仅本地验证；临时提前于 Phase 5） |
| 11 | 知识库与工作区上下文 | 工作区级持久 system prompt + 知识库（RAG）+ 文件引用，所有对话继承上下文，提升生成质量与一致性。 | 13 | 2-3 周 | Phase 4 | 方向已确认 |
| 12 | 消息队列与任务编排 | Agent 工作中用户可排队后续指令，支持重排、编辑、暂停/恢复，不打断当前任务。 | 5 | 约 1 周 | Phase 5（或 Phase 4） | 方向已确认 |
| 13 | 用户自选 AI API（能力扩展） | 用户/工作区级配置自己的 base_url + key + model，预设主流 OpenAI 兼容厂商；密钥加密存储、不落日志。 | 8 | 1-2 周 | Phase 4 | 方向已确认 |
| 14 | 动态后端 / 前后端分离（能力扩展） | 支持生成带后端逻辑的应用（Node/FastAPI），产物有 API + 状态；沙箱扩展为可运行进程 + 出站隔离。 | 21 | 3-5 周 | Phase 1（沙箱扩展） | 方向已确认 |
| 15 | 多语言 / 多文件项目（能力扩展） | 单文件 HTML → 多文件项目 + 构建流水线（React/Vue 等），含文件树、依赖安装、构建、产物托管闭环。 | 34 | 5 周+ | Phase 1 + Phase 14 | 方向已确认 |
| 16 | 统一业务异常体系（横切加固） | 建立业务异常基类与分级、错误码-消息映射、全局异常处理器；对外统一返回 `ErrorResponse{code, message, details?}` 而非裸状态码；日志脱敏。牵动 API 错误响应契约与现有测试。 | 5 | 约 1 周 | 无（建议 P0 前置，可早于 Phase 5） | **已完成（2026-11-04）** |
| 17 | 认证与多用户数据隔离（横切加固） | 登录与会话、数据按 `user_id` 归属、查询强制过滤、历史 `studio-shared` 数据迁移回填、越权访问测试、前后端联调。解决共享账号与数据串用风险。 | 13 | 2-3 周 | 无；建议紧接 Phase 16、早于 Phase 5 | 已完成（2026-11-04，仅本地验证） |

**合计：约 209 points，约 36-49 周（单人）。** 其中主线 Phase 1-12 约 128 points、能力扩展 Phase 13-15 约 63 points、横切加固 Phase 16 约 5 points、认证与多用户隔离 Phase 17 约 13 points。多人并行可压缩，核心链路（1→2→4→5→6）不可压缩；能力扩展（13→14→15）相对独立、可与主线并行推进；Phase 16/17 编号追加在末尾，**建议实施时点前置到 Phase 5 之前**（见「实现顺序与实施时点」）。

## 项目痛点归并与落位（2026-11-03 并入）

> 来源：逐条提取 [项目说明](项目说明.md) §二「未完成 / 关键横切缺口」与 §三「后续扩展与优先级判断」，并对照 [需求说明](需求说明.md) §1/§2/§5/§6。归并去重后得 14 条待排期/待办项，另列 6 条已覆盖项。

| # | 痛点（归并去重） | 出处（文件·章节） | 现状判定 | 落位（Phase / 横切） |
|---|---|---|---|---|
| P1 | 多用户数据隔离缺失：studio 路由共享 `studio-shared` 数据，未按 `user_id` 过滤 | 项目说明 §二「关键横切缺口」；需求说明 §1 | **已解决**（2026-11-04） | Phase 17（与登录/会话合并实施） |
| P2 | 服务端速率限制缺失（auth 防暴力破解、artifact/build 防 DoS） | 项目说明 §二；本文件 NFR P0 | 待解决（原定 Phase 1 同期未落地） | 横切 P0，与 Phase 16 同期补 |
| P3 | 请求体大小限制缺失（`artifact_html` 无上限） | 项目说明 §二；本文件 NFR P0 | 待解决（原定 Phase 1 同期未落地） | 横切 P0，与 Phase 16 同期补 |
| P4 | CORS 未收紧（`allow_origin_regex=".*"` + 凭据） | 项目说明 §二；本文件 NFR P0 | 待解决（原定 Phase 1 同期未落地） | 横切 P0，与 Phase 16 同期补 |
| P5 | AI 密钥轮换缺失 | 项目说明 §二；本文件 NFR P1「密钥管理」 | 待解决 | 横切 P1，Phase 16 或 Phase 5 前 |
| P6 | AI token 用量与成本追踪缺失 | 项目说明 §二 | 待解决 | Phase 9「成本控制」 |
| P7 | CI 流水线缺失（无 `.github/workflows`） | 项目说明 §二；本文件「代码质量门禁」P1 | 待解决 | 横切 P0/P1，先建骨架 |
| P8 | 后端 lint/format 缺失（无 ruff/black 配置） | 项目说明 §二；门禁 P0 | 待解决 | 横切 P0，与 Phase 16 同期 |
| P9 | 后端类型检查缺失（无 mypy 配置） | 项目说明 §二；门禁 P1 | 待解决 | 横切 P1，Phase 5 前 |
| P10 | 覆盖率阈值门禁缺失（`.coveragerc` 无 `fail_under`） | 项目说明 §二；门禁 P0 | 待解决 | 横切 P0，与 Phase 16 同期 |
| P11 | Phase 5–12 未实施（多 Agent/工具框架/安全扫描/生产预览/发布/终端/知识库/队列） | 项目说明 §二「未完成」 | 待排期（方向已确认） | 既有 Phase 5–12 |
| P12 | 无登录/认证/租户体系（共享账号、无登录入口） | 需求说明 §1「产品目标和边界」、阅读背景 | **已解决**（2026-11-04） | Phase 17（与 P1 多用户隔离合并实施；不含角色/租户后台） |
| P13 | 错误协议只回 HTTP 状态码 + 固定文案（422/404/502/500），用户看不懂 | 需求说明 §5「当前规则与限制·错误协议」 | 待解决（2026-11-03 新需求） | **Phase 16** 统一业务异常体系 |
| P14 | 后端无自动化测试入口（文档记 18 条设计用例未建立） | 需求说明 §6「验证与追溯」；后端测试计划 §5-P3 | **已解决**：`app/backend/tests/` 已建立，2026-11-04 Phase 17 后收集 172 条（单元 113、接口集成 59），本轮全绿 | 已覆盖；相关文档已于 2026-11-04 同步 |

### 已覆盖 / 已完成的痛点（不重复排期）

| 痛点 | 出处 | 结论 |
|---|---|---|
| 沙箱资源隔离（只读挂载、`--cap-drop=ALL`、CPU/内存/PID 限额） | 项目说明 §一、§二；本文件 NFR P0 | ✅ 已完成（Phase 1） |
| 产物脱离主站同源渲染（iframe `srcDoc` → 沙箱 `preview_url`） | 项目说明 §一 | ✅ 已完成（Phase 1） |
| 孤儿沙箱容器 / 工作区回收 | 本文件 NFR P2「孤儿资源回收」 | ✅ 已覆盖（Phase 1 回收器 + 兜底守卫） |
| 三阶段编排 + 产物校验（错误可独立定位） | 项目说明 §一「关键取舍」 | ✅ 已完成（Phase 1–4） |
| 真实 AI 接入 + 限流指数退避 | 项目说明 §一、§二 | ✅ 已完成（Phase 4） |
| 单镜像部署（Fly.io + Docker DinD） | 项目说明 §二/§三；需求说明 §2「部署仍为占位」 | ✅ 已落地：`Dockerfile` + `fly.toml`（app `atoms-services`、区域 `sin`）+ `.github/workflows/fly-deploy.yml`；产品内 `/deploy` 页面仍是占位（发布能力未实现） |

## Phase 顺序评估与调整说明（2026-11-04 更新）

**结论**：
1. **现有 Phase 1–16 一律不重排（有意保持不动）**。多篇文档按数字引用 Phase（项目说明「Phase 1–4 / Phase 5–12」、[执行与隔离层设计](执行与隔离层设计.md) Phase 1、后端测试计划等），重排会造成大量悬空引用与文档漂移。
2. **新增 Phase 17（认证与多用户数据隔离）**，编号追加在末尾；按 2026-11-04 决策，登录/认证与多用户数据隔离合并为同一件事，不再作为两个独立事项。
3. **Phase 16 与 Phase 17 均建议实施时点前置到 Phase 5 之前**——编号顺序与实施时点解耦，从根本上规避重编号冲突。具体落地顺序见「实现顺序与实施时点」。
4. 其余痛点全部落入既有 Phase 或横切 NFR 表，不新增其它 Phase 编号。

**紧迫度与用户体验影响评估**：

| 候选项 | 紧迫度 | 用户体验影响 | 结论 |
|---|---|---|---|
| 统一业务异常体系（Phase 16） | 高（对外前必须，错误不可读直接损可用性） | 高（用户只看到裸错误码） | 前置，P0，最先做 |
| 认证与多用户数据隔离（Phase 17） | 高（对外/多用户前必须，数据串用属事故级风险） | 高（实施前无登录入口，任何人可见全部数据） | 已完成（2026-11-04），仅本地验证 |
| P0 横切（限流/请求体/CORS/lint/覆盖率门禁） | 高（原定 Phase 1 同期，已逾期） | 中（安全与稳定性，非直接可见） | 与 Phase 16 同期补 |
| Phase 5 多 Agent、Phase 6 工具框架 | 中（依赖已满足） | 高（产品差异化） | 保持原序 |
| Phase 13–15 能力扩展 | 中低（相对独立） | 高（长期价值） | 保持原序，可并行 |

**有意保持不动的顺序**：Phase 2 优先于 Phase 3（既有理由不变）；Phase 10 可纳入 Phase 1 一并做的提示不变；Phase 6 可从 Phase 5 提前到 Phase 4 的弹性不变。

### 文档同步结果（2026-11-04 已完成）

上一版本本节登记为「待跟进」，2026-11-04 已按下表完成同步（只改 docs 下 Markdown，未动代码、未提交 git）：

| 文件 | 位置 | 已更新内容 |
|---|---|---|
| docs/项目说明.md | §二「当前完成程度」、§三「建议优先级」 | 「Phase 5–12」扩为「Phase 5–12、16、17」；补 Phase 16/17 建议 P0 前置；把已完成的 Fly.io 部署与后端测试移出「未完成」 |
| docs/需求说明.md | §1、§2、§5、§6、§7 | 认证边界更新为 Phase 17 已实施的公开/受保护路由与 404 越权语义；部署占位区分为「产品页面占位 / 平台自身已部署」；错误协议登记 Phase 16 契约；后端测试计数按实际更新为 113 + 59 |
| docs/测试用例与覆盖矩阵.md | §2.3、§2.4、§4、§6 | 后端测试计数按实际更新；新增「错误契约」用例类别与计数（规划中，未建立） |
| docs/执行与隔离层设计.md | §3、§8、§10 | 沙箱错误改为统一 code（`SANDBOX_DOCKER_UNAVAILABLE`、`SANDBOX_IMAGE_PULL_FAILED`），并标注 Phase 16 实施前仍为现状行为；测试计数按实际更新 |
| docs/后端测试覆盖与大厂规范落地计划.md | 文首、§1、§5-P3 | 增加 2026-11-04 现状更新；P3 已落地；异常体系测试纳入后端测试落地清单 |
| docs/开发规范.md | §3、§4、§5 | 命名规则改为摘要 + 指向《命名规范》；错误契约与错误码规范更新；后端测试现状更新 |
| docs/命名规范.md | 新建 | 迁入散落在开发规范/总架构中的命名规则，新增 `DOMAIN_REASON` 错误码规范 |
| docs/总架构设计.md | §4、目录树、§12 | 命名章节改为摘要 + 链接；后端测试目录与接口集成状态改为实际 |
| docs/README.md | 查阅建议、模块索引、交付边界 | 登记《命名规范》；更新计数与状态 |

## 实现顺序与实施时点

**建议落地顺序（按紧迫度与用户影响，而非 Phase 编号）**：

| 顺序 | 内容 | 对应 Phase | 建议时点 | 前置依赖 | 理由 / 状态 |
|---|---|---|---|---|---|
| 1 | 执行与隔离层（Docker 沙箱 + `preview_url`） | Phase 1 | 已完成 | 无 | 所有预览、构建终端与动态后端能力的底座，已落地 |
| 2 | 多轮迭代回路（按修改意见生成新版本） | Phase 2 | 已完成 | Phase 1 | 已落地；真实模式下的上下文改稿在 Phase 4 后生效 |
| 3 | 代码编辑器（CodeMirror，源码编辑保存为新版本） | Phase 3 | 已完成 | Phase 1 | 已落地；文件树/Diff/编辑会话留待后续扩展 |
| 4 | 真实 AI Provider（多供应商主备 + 示例短路） | Phase 4 | 已完成（2026-11-04 实测可用） | Phase 2 或 Phase 3 | 已落地；百炼与方舟均已实测返回非空正文 |
| 5 | 统一业务异常体系（`ErrorResponse{code,message,details?}`） | Phase 16 | 立即（P0） | 无 | 已完成（2026-11-04）；错误可读性直接决定可用性 |
| 6 | 认证与多用户数据隔离（登录/会话 + `user_id` 过滤） | Phase 17 | 紧接 Phase 16，Phase 5 之前 | 无（依赖 Phase 16 的错误契约） | 已完成（2026-11-04，仅本地验证）；共享账号与数据串用属事故级风险 |
| 7 | P0 横切补强（限流、请求体上限、CORS 收紧、lint/覆盖率门禁） | 横切 NFR（非 Phase） | 与 Phase 16/17 同期 | Phase 16（共用异常与路由改造面） | 安全稳定底线，原定 Phase 1 同期、已逾期 |
| 8 | 多 Agent 协作（角色体系 + 编排器 + 交接/审批） | Phase 5 | Phase 17 之后 | Phase 4 | 核心差异化能力，但先保证可安全对外 |
| 9 | 工具与集成框架（内置工具、MCP、外部连接器） | Phase 6 | Phase 5 之后（可提前做内置工具） | Phase 4（或 Phase 5） | 多 Agent 需要工具才能落地；先内置后扩展 |
| 10 | 安全扫描与质量门禁（密钥泄漏、XSS、权限风险） | Phase 7 | Phase 6 之后、发布前 | Phase 1、Phase 6 | 作为内置工具实现；为 Phase 9 发布提供门禁 |
| 11 | 生产预览通道（子域名/反代暴露沙箱） | Phase 8 | **跳过 / 暂缓** | Phase 1 | 需域名 + DNS/反向代理等外部资源，当前不具备；见下方恢复条件 |
| 12 | 发布与部署（公开 URL、自定义域名、回滚、自托管导出） | Phase 9 | **暂缓（连带于 Phase 8）** | Phase 8、Phase 7 | 依赖生产预览通道；Phase 8 暂缓则本项无法独立开工 |
| 13 | 构建终端与实时反馈（stdout/stderr、文件创建、错误日志） | Phase 10 | 已完成（2026-11-04，临时提前） | Phase 1 | 只依赖沙箱与任务执行；已完成 SSE 事件流、构建终端面板与刷新回看，Phase 5 仍为下一轮首位 |
| 14 | 知识库与工作区上下文（持久 prompt + RAG + 文件引用） | Phase 11 | Phase 4 之后，可与 Phase 5/6 并行 | Phase 4 | 依赖真实 AI；提升生成质量与跨对话一致性 |
| 15 | 消息队列与任务编排（排队、重排、暂停/恢复） | Phase 12 | Phase 5 稳定后 | Phase 5（或 Phase 4） | 需多 Agent/长任务才有排队价值；过早做缺少真实队列场景 |
| 16 | 用户自选 AI API（工作区级 base_url + key + model） | Phase 13 | 可与主线并行 | Phase 4 | 相对独立，不阻塞对外关键路径；可在 Phase 16/17 后随时插入 |
| 17 | 动态后端 / 前后端分离（Node/FastAPI 产物 + 出站隔离） | Phase 14 | Phase 7 之后或与能力扩展并行 | Phase 1（沙箱扩展） | 高风险高成本，需先有安全扫描与沙箱扩展基础 |
| 18 | 多语言 / 多文件项目（多文件 + 构建流水线） | Phase 15 | Phase 14 之后 | Phase 1 + Phase 14 | 依赖动态后端与多文件沙箱，属长期能力 |

**该表覆盖 Phase 1–17 全部，无遗漏项**（Phase 8、9 以「跳过/暂缓」保留在表中，不从表中消失）。

**临时顺序调整（2026-11-04，仅影响实施时点）**：本轮跳过 Phase 5、先完整交付 Phase 10。理由：Phase 5（多 Agent 协作，21 points）体量远大于当前交付窗口，半途停下会再次留下半成品；Phase 10 只依赖 Phase 1 的沙箱能力，可在窗口内完整实现、测试与验证。该调整不改变 Phase 编号、依赖关系与文档引用，**Phase 5 仍是下一轮首位**。

**Phase 10 SSE 约定（2026-11-04）**：事件类型固定为 `stage_started` / `stage_finished` / `file_created` / `log` / `error` / `done`；一次构建以 `(user_id, project_id, build_id)` 定位，`seq` 在构建内递增；`done` 与 `error` 为终止事件，服务端发送后主动关闭连接；鉴权沿用 Phase 17 的 JWT，SSE 端点优先读 `Authorization: Bearer`，浏览器原生 `EventSource` 可用 `?access_token=` 兜底。事件只含文件名与字节数，不落页面正文。

**Phase 8 跳过 / 暂缓说明（用户决策）**：

- **跳过原因**：生产预览通道需要可用域名、DNS 解析与反向代理/子域名路由等外部资源，当前不具备；继续实施会产生外部依赖与环境不确定性，投入产出比低。
- **恢复条件**：具备可解析域名与反向代理（或云厂商子域名/路由能力）、明确对外访问范围与安全边界后，再重新评估；Phase 1 的沙箱能力已就绪，恢复时无需重做底座。
- **连带影响**：Phase 9（发布与部署）依赖 Phase 8，**随之暂缓**；Phase 7 安全扫描仍可先做（作为内置工具），不必等待 8/9。用户自选 API、动态后端等能力（Phase 13/14）不依赖 8/9，可照常并行。


**为什么编号与实施时点解耦**：Phase 编号已被多篇文档按数字引用（项目说明、执行与隔离层设计、后端测试计划等）。若把 Phase 16/17 插到中间重排 1–16，会产生大量悬空引用与文档漂移。因此新增能力一律追加编号（16、17），只在本文登记「建议实施时点」，编号保持历史稳定、时点随紧迫度调整。读者只需记住：**16 → 17 → 5 → 6 → 7 → 10/11/12 → 13/14 → 15** 是实际落地主线，**8/9 暂缓**。

**这样排的理由（按紧迫度与用户影响）**：

1. **错误可读性直接决定产品可用性**：用户看到 422/502 裸状态码无法自助处理，客服与重试成本高，且属于对外第一印象问题，故最先做。
2. **认证与数据隔离是事故级风险**：Phase 17 实施前所有使用者共享 `studio-shared` 数据，任何人可读写他人项目；一旦对外，数据串用不可接受，故紧随其后。2026-11-04 已实施。
3. **先错误体系、后认证**：401/403/429 等分支需要统一错误契约承载；顺序颠倒会导致认证接口先写一套 `detail`、再返工。
4. **横切 P0 可并行**：限流、请求体上限、CORS、lint/覆盖率门禁与 Phase 16/17 改动面重叠（同批路由与异常处理），同批做最省成本。
5. **主线与能力扩展不抢占对外关键路径**：Phase 5 多 Agent 价值高但不解决安全问题，排在其后；Phase 13–15 可与主线并行，不阻塞。

## 非功能性需求（横切关注点）

以下 NFR 不单独成 Phase，而是嵌入到对应 Phase 中实施。按优先级排列，**P0 必须在对外使用前落地**；其中多项原定 Phase 1 前/同期，已逾期，2026-11-04 调整为与 Phase 16 同期补。

### P0 — 基础安全与隔离（原定 Phase 1 前/同期，已逾期）

| 项 | 当前状态 | 目标 | 落地 Phase |
|---|---|---|---|
| CORS 收紧 | `allow_origin_regex=".*"` + 凭据 | 生产环境限制为前端域名，dev 放开 | 与 Phase 16 同期（已逾期） |
| 请求体大小限制 | artifact_html 无上限 | 限制 artifact 最大体积（如 5MB），超限 413 `ARTIFACT_TOO_LARGE` | 与 Phase 16 同期（已逾期） |
| 速率限制 | 无 | auth 接口防暴力破解；artifact/build 接口防 DoS；按 IP + 用户限流 | 与 Phase 16 同期（已逾期） |
| 沙箱资源隔离 | ✅ 已实施 | Docker `--read-only`、`--cap-drop=ALL`、CPU/内存/PID 限制、只读挂载 | Phase 1（已完成） |
| artifact HTML 安全 | 沙箱内渲染已实施；发布前扫描未实施 | 沙箱内渲染（脱离主站同源）+ 发布前安全扫描 | Phase 1（已完成）+ Phase 7（待排期） |

### P1 — 多用户与数据安全（随核心功能落地）

| 项 | 当前状态 | 目标 | 落地 Phase |
|---|---|---|---|
| 多用户数据隔离 | **已完成**：按登录用户 `user_id` 隔离项目/消息/版本/执行记录，越权返回 404 | 保持查询强制过滤，新增接口不得绕过 | Phase 17（2026-11-04 完成） |
| 服务端并发控制 | 仅前端 busy 状态 | 同项目构建加服务端锁（DB 行锁或 Redis），防止并发写冲突 | Phase 2 已过（未实施），待排期，建议 Phase 5 前 |
| 安全响应头 | 主应用缺失 | 加 CSP、HSTS、X-Content-Type-Options、Referrer-Policy | Phase 8（生产预览通道上线前） |
| 审计日志 | 仅有应用日志 | 记录关键操作（登录、构建、发布、配置变更）的 actor + 时间 + 对象 | Phase 5（多 Agent 引入更多操作时） |
| 密钥管理 | ✅ env 隔离已实施（`app/.env`）；轮换机制缺失 | JWT/OIDC/AI key 不进日志、提供轮换机制 | Phase 4（env 隔离已完成）；轮换待排期 |

### P2 — 生产就绪（发布/部署阶段）

| 项 | 目标 | 落地 Phase |
|---|---|---|
| 成本控制 | 追踪每轮 AI token 用量与沙箱资源消耗，设用户/工作区配额；台账见 [AI 额度使用记录](AI额度使用记录.md) | Phase 9 |
| 可观测性 | 结构化日志 + 请求指标 + 链路追踪（现有 telemetry 模块扩展） | Phase 8 前 |
| 孤儿资源回收 | 沙箱容器/工作区/数据库连接泄漏兜底清理 | Phase 1（已含回收器）+ 持续 |
| 备份与恢复 | 数据库定期备份、项目版本可恢复 | Phase 9 |
| 优雅降级 | AI/沙箱不可用时返回明确错误，不崩溃；前端降级展示 | 贯穿各 Phase |

### NFR 与 Phase 的映射总览

```
Phase 1  ── 沙箱隔离 + CORS + 限流 + 请求体限制
Phase 2  ── 服务端并发锁
Phase 4  ── 密钥管理
Phase 5  ── 审计日志
Phase 7  ── artifact 安全扫描
Phase 8  ── 安全响应头 + 可观测性
Phase 9  ── 成本控制 + 备份恢复
Phase 16 ── 统一错误响应契约 + 前端可读错误 + 日志脱敏
Phase 17 ── 登录/会话 + 多用户数据隔离 + 越权访问控制
```

> **说明**：当前应用尚未跑过自动化安全扫描（SAST/DAST）。Phase 7 的安全扫描工具是面向"产物 HTML"的；对"平台自身代码"的安全扫描建议在 Phase 8/9 前引入 CI 级别的 SAST（如 Semgrep/Bandit）和依赖审计（pip-audit），作为质量门禁的一部分。

## 代码质量门禁（横切关注点）

命名规范、代码分层、测试分层已写入 [命名规范](命名规范.md)、[开发规范](开发规范.md) 与 [测试策略与规范](测试策略与规范.md)。以下是**可执行的质量门禁**，当前大部分缺失，需在 Phase 16 同期建立，贯穿后续所有 Phase。

### 当前状态

| 项 | 状态 |
|---|---|
| 命名规范 | ✅ 已独立维护于 [命名规范](命名规范.md) |
| 代码分层与依赖方向 | ✅ 已写入开发规范 |
| 前端 ESLint | ✅ 已有 `eslint.config.js` |
| 后端 lint/format | ❌ 无 ruff/flake8/black 配置 |
| 后端类型检查 | ❌ 无 mypy 配置 |
| 测试覆盖率阈值 | ❌ `.coveragerc` 无 `fail_under`，无最低覆盖率要求 |
| CI 流水线 | ⚠️ 仅有 `.github/workflows/fly-deploy.yml`（push 即部署，无 lint/test/coverage/build 阶段） |
| pre-commit hooks | ❌ 无配置 |
| 依赖审计 | ❌ 无 pip-audit / npm audit |
| SAST | ❌ 无 Semgrep / Bandit |

> 2026-11-04 核实：`app/backend/tests/`、`pytest.ini`、`.coveragerc` 已存在；`pytest.ini` 默认带 `--cov` 但无阈值；CI 只有一个 Fly.io 部署工作流。

### P0 — 与 Phase 16 同期必须建立（原定 Phase 1 同期，已逾期）

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
| CI 流水线 | GitHub Actions：lint → test → coverage → build，PR 必过 | Phase 16 同期建立骨架，Phase 5 前完善 |
| pre-commit hooks | 提交前自动 ruff format + ruff check，防止未格式化代码入库 | Phase 16 同期 |
| 依赖审计 | 后端 `pip-audit`、前端 `npm audit`，高危依赖阻断合并 | Phase 4（接真实 AI/外部工具前） |

### P2 — 生产就绪

| 门禁 | 要求 | 落地 Phase |
|---|---|---|
| SAST | Semgrep / Bandit 扫描平台自身代码的安全漏洞 | Phase 8/9 前 |
| 覆盖率趋势 | 覆盖率不得随 PR 下降（diff-coverage） | Phase 8 前 |
| 构建产物检查 | 前端构建无 error、产物大小在阈值内 | Phase 9 |

### 与已有文档的关系

- 命名规范、代码分层、测试分层：命名沿用 [命名规范](命名规范.md)，分层沿用 [开发规范](开发规范.md) 与 [测试策略与规范](测试策略与规范.md)，不重复。
- 本节补充的是**可执行门禁**（工具+阈值+CI），是对现有规范的落地保障。
- 覆盖率阈值建议：先设整体 70%、核心模块 80%，随 Phase 推进逐步提高，避免一开始因阈值过高阻碍开发。

## Phase 2 与 Phase 3 的优先级调整

**结论：Phase 2（多轮迭代回路）优先于 Phase 3（代码编辑器）。**

理由：
- 多轮迭代是对话式工作台的核心闭环：用户看了产物后提修改意见，系统基于已有 artifact 重新生成新版本。没有这个回路，工作台只能"一次性出活"，无法迭代。
- 代码编辑器是高级能力，依赖用户能看懂并修改 HTML/JS/CSS；在多轮回路跑通之前，编辑器的使用场景有限。
- 依赖关系上，两者都只依赖 Phase 1（执行与隔离层），互不依赖，因此可以按用户价值排序，多轮回路的用户价值更高。

排序后的实施顺序：Phase 1 → Phase 2 → Phase 3 → Phase 4 → Phase 5 → Phase 6 → Phase 7 / Phase 8 → Phase 9 → Phase 10 / Phase 11 / Phase 12。

> Phase 16（统一业务异常体系）与 Phase 17（认证与多用户数据隔离）为横切加固，均已于 2026-11-04 完成；其编号追加在末尾仅为稳定引用，不参与上述主线排序（见「实现顺序与实施时点」）。

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
- **状态：已完成。** `services/execution.py` 已实现 `ExecutionService.run_html()`，端口分配、容器生命周期与超时回收均已落地，并有单元测试覆盖。

### Phase 2：多轮迭代回路
- 用户在预览旁输入修改意见（如"把标题改成红色"），后端把当前 `artifact_html` + 修改意见传给 Output provider，生成新 HTML，存为新版本（`version_no + 1`），更新项目 `current_version`。
- 保持 Output provider 契约不变，仅在请求中携带上一版 artifact_html 作为上下文。
- 需要前端新增"修改意见"输入区，后端 artifact 路由支持传入 `base_version_id`。
- **状态：已完成。** `ArtifactRequest` 新增 `base_version_id` / `revision_note`；artifact 路由按 `base_version_id` 加载基线版本并把其 `artifact_html` 作为 `context` 透传给 Provider，落库时 label 追加"（迭代自 vX）"、`plan_summary` 兜底为基线值。前端在预览区显示"修改意见"输入框，提交后走 outline + artifact 生成新版本。Mock 阶段仅验证"提意见 → 新版本号递增 → 旧版本保留"的闭环，真实按上下文智能修改在 Phase 4 接入后生效。
- **决策点（Phase 2 启动时定）**：
  - 传给 Provider 的上下文是完整 `artifact_html` 还是 diff（首期建议传完整 HTML，简单可靠）。
  - 新版本的 `version_no` 策略：当前最大序号 +1，恢复历史版本后再构建取历史最大 +1。

### Phase 3：代码编辑器
- 前端嵌入 Monaco 或 CodeMirror，直接展示/编辑当前版本的 `artifact_html`。
- 编辑后保存为新版本（或覆盖当前版本，待定），并重新启动沙箱预览。
- 与 Phase 2 的关系：多轮回路是"用自然语言改"，编辑器是"用代码改"，两者可并存。
- 参考 Atoms：编辑器支持文件树、Diff 对比、编辑会话（Submit all / Discard all）、把文件作为上下文加入对话（`#` 引用）、下载项目为 ZIP。
- **状态：已完成。** 选型 **CodeMirror 6**（`@uiw/react-codemirror` + `@codemirror/lang-html`，轻量可定制）。语义采用"保存为新版本"：在预览区头部新增"编辑源码"入口，切换到内嵌 CodeMirror 编辑器，修改后可附备注，"保存并预览"调用新增路由 `POST /projects/{project_id}/artifact/edit`（`EditArtifactRequest { html, note }`），后端 `validate_artifact_html` 校验后以"当前最大 version_no +1"落库为新版本，label 沿用当前版本标题并可追加备注，随后复用沙箱执行服务重跑预览并更新 `current_version`。文件树 / Diff / 编辑会话等进阶能力留待后续 Phase 扩展。
- **决策点（Phase 3 启动时定）**：
  - 编辑器选型：Monaco（VS Code 内核，功能全但体积大）vs CodeMirror（轻量、可定制）——已定 **CodeMirror**。
  - 编辑保存语义：保存为新版本（保留历史）vs 覆盖当前版本（Atoms 是编辑会话 Submit all 后应用）——已定 **保存为新版本**。

### Phase 4：真实 AI Provider
- **当前 mock 已增强为示例驱动：** `services/studio_examples.py` 提供 4 个完整可交互示范网页（饮水追踪器 / 任务看板 / 记账本 / 读书笔记库）与一个通用演示页；`MockOutputProvider` 按需求命中示例返回对应三件套（plan / outline / html），未命中返回通用页。接真实 Provider 后，若用户输入与示例文本相同，应**短路返回对应示范网页**，不调用真实模型，保证首体验稳定。
- **状态：已完成。** `services/studio_output.py` 中 `RealOutputProvider` 实现为真实调用 `services/studio_ai.py` 的编排层（`generate_plan` / `generate_outline` / `generate_artifact`），并保留示例短路：任一方法先 `match_example(requirement)`，命中即返回对应示范网页（`deepcopy` 隔离 plan/outline，html 原样返回），不调用真实模型。启用方式为「任一 AI 供应商（aliyun / ark / zhipu）配置完整即启用」（见 `services/aihub._build_providers`），`get_provider()` 据此惰性返回 `RealOutputProvider` 或回退 `MockOutputProvider`；`resolve_model()` / `available_models()` 按同样开关分派到 `studio_ai` 或返回 mock 模型（`mock-fixed-v1`）。真实档位由 `studio_ai.MODEL_PROFILES` 维护（balanced / fast / quality 三档，主选模型 `qwen3.8-flash`），密钥只经环境变量注入、各家独立，不写死在代码里。`generate_artifact` 支持 `context`（基线 HTML）参数，使 Phase 2 的"按上下文智能修改"在真实模式下生效。
- `services/studio_ai.py` 通过 `AIHubService` 完成三次模型调用，并对产物做 `sanitize_html()` 清洗（带一次失败重试）。**调用层已升级为多供应商主备降级**：`aliyun`（阿里百炼 Qwen3.8-Flash，主选）→ `ark`（火山方舟 doubao，备选）→ `zhipu`（智谱 GLM-4.7-Flash，兜底），任一家缺失 `base_url`/`api_key`/`model` 自动跳过。触发降级的条件：429、5xx、超时、连接错误、空响应；**401/403 认证类错误立即降级、不重试**；逐级落到下一家，全部失败抛 `AllProvidersFailedError`（携带逐家供应商与失败原因，不含密钥）。每家独立 `base_url`/`api_key`/`model`/`max_tokens`/并发上限/超时、独立重试计数与独立并发信号量。环境变量见 `app/.env.example`：
  - 阿里百炼：`APP_AI_ALIYUN_BASE_URL` 使用**工作区专属 MaaS 域名** `https://ws-8mf1tjg3auks3710.cn-beijing.maas.aliyuncs.com/compatible-mode/v1`（不是公共 `dashscope.aliyuncs.com`；`app/.env.example` 里的公共域名只是示例默认值，实际以 `app/.env` 配置为准）、`APP_AI_ALIYUN_API_KEY`、`APP_AI_ALIYUN_MODEL`（`qwen3.8-flash`）。**已验证（2026-11-04 实测）**：该域名 + 模型返回正文非空，耗时 7.63s。注意两种域名权限不通用：同一模型在公共域名 `dashscope.aliyuncs.com` 返回 403 `AccessDenied.Unpurchased`（账号未在公共域名开通），不能把公共域名当作可用的等价配置。
  - 火山方舟：`APP_AI_ARK_BASE_URL`（默认 `https://ark.cn-beijing.volces.com/api/v3`）、`APP_AI_ARK_API_KEY`、`APP_AI_ARK_MODEL`（填推理接入点 ID `ep-xxx` 或模型 ID，无默认值，必须显式配置）。**已验证（2026-11-04 实测）**：`deepseek-v4-1-flash-economy-261017` 返回 200、耗时 2.08s、正文非空、`finish_reason=stop`。该模型默认开启 thinking，**`max_tokens` 过小（如 32）会被 reasoning 全部吃光，导致 `content` 为空**；配置 `max_tokens` 时必须为推理留出余量，或在需要正文时避免过小上限。
  - 智谱兜底：`APP_AI_ZHIPU_*`；未配置时回退读取历史 `APP_AI_BASE_URL` / `APP_AI_KEY`。
  - 全局：`APP_AI_PROVIDER_ORDER`（默认 `aliyun,ark,zhipu`）、`APP_AI_MAX_RETRIES`、`APP_AI_RETRY_BASE`、`APP_AI_RETRY_MAX`、`APP_AI_MAX_CONCURRENCY`。
  - 安全：密钥仅经环境变量注入，日志只记录供应商名、模型与错误类型，不打印密钥。
- **实测记录（2026-11-04，已验证）**：
  1. 阿里百炼：工作区 MaaS 域名 + `qwen3.8-flash` → 可用，正文非空，耗时 7.63s。
  2. 公共域名 `dashscope.aliyuncs.com` + 同一模型 → 403 `AccessDenied.Unpurchased`（账号未在公共域名开通）；**两种域名权限不通用**，配置必须用工作区 MaaS 域名。
  3. 火山方舟：`deepseek-v4-1-flash-economy-261017` → 200、2.08s、正文非空、`finish_reason=stop`；该模型默认开启 thinking，`max_tokens` 过小（如 32）会被 reasoning 全部占用，导致 `content` 为空。
  4. 降级语义：401/403 立即降级且不重试；全部供应商失败时抛 `AllProvidersFailedError`。
- **thinking 与预算（2026-11-04 更新，按官方文档核实）**：调用层新增 `APP_AI_ENABLE_THINKING`（默认 `false`）。**关闭时**百炼传 `extra_body={"enable_thinking": false}`、方舟传 `extra_body={"reasoning_effort": "none"}`（不再传 `thinking.type`），其它供应商不传；**开启时**百炼传 `enable_thinking=true` + `thinking_budget`（默认 2048，可用 `APP_STUDIO_THINKING_BUDGET` 覆盖）、方舟传 `reasoning_effort=high`。请求体统一改用 `max_completion_tokens`（百炼/方舟语义均为“思考+回答”总量），移除 `max_tokens`；百炼不再同传 `max_tokens`/`reasoning_effort`，方舟不再同传 `max_tokens`/`thinking`，避免互斥 400。Studio 三阶段可见正文预算仍由 `APP_STUDIO_PLAN_MAX_TOKENS`（1600）、`APP_STUDIO_OUTLINE_MAX_TOKENS`（2200）、`APP_STUDIO_ARTIFACT_MAX_TOKENS`（6144）控制，请求总量自动换算：开启思考 = 正文 + thinking_budget + 1024；关闭思考 = 正文 + 1024（artifact 默认分别为 9216 / 7168）。`app/.env.example` 已同步说明。
- 替换 `MockOutputProvider` 已完成，Plan/Outline/HTML 响应形状不变，上层流程无感知。
- **决策点（Phase 4 启动时定，已收敛）**：
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

### Phase 16：统一业务异常体系（横切加固，建议 P0 前置）

> 新增于 2026-11-03；**已完成于 2026-11-04**。编号追加在末尾以避免改动现有 Phase 1–15 的大量引用；实际建议实施时点早于 Phase 5（多用户 / 对外），见「实现顺序与实施时点」。

**此前现状（本阶段已解决）**：报错只返回 HTTP 状态码 + 固定 detail 文案（需求说明 §5：字段无效 422、不存在 404、阶段/结构无效 502、DB 提交失败 500），前端只能展示裸错误，用户看不懂。

**目标**：建立完整业务异常体系——遇到错误 `throw` 对应异常，异常 message 简洁但说清问题相关信息；API 统一返回 `ErrorResponse{code, message, details?}`，而非裸错误码。错误码采用 `DOMAIN_REASON`（如 `STUDIO_BUILD_FAILED`），message 为中文可读句子，不引入 i18n key、不做中英双语；**契约一次到位直接切换，不做 `detail` 双写过渡**。

**可执行条目**：

| 序号 | 条目 | 落地内容 | 交付物 |
|---|---|---|---|
| 16-1 | 异常基类与分级 | `AppError(code, message, http_status, details?, retryable=False)`；子类：`ValidationError(422)`、`NotFoundError(404)`、`ConflictError(409)`、`RateLimitError(429)`、`PayloadTooLargeError(413)`、`AuthError(401/403)`、`ProviderError(502)`、`SandboxUnavailableError(503)`、`InternalError(500)`。现有 `ValueError` / `DockerNotAvailableError` / `HTTPException` 逐点迁移 | `app/backend/core/exceptions.py` |
| 16-2 | 错误码与 message 映射 | 集中错误码常量（如 `STUDIO_PLAN_INVALID`、`STUDIO_OUTLINE_INVALID`、`STUDIO_ARTIFACT_INVALID`、`STUDIO_DB_COMMIT_FAILED`、`SANDBOX_DOCKER_UNAVAILABLE`、`SANDBOX_IMAGE_PULL_FAILED`、`ARTIFACT_TOO_LARGE`、`RATE_LIMITED`、`AUTH_INVALID_CREDENTIALS`、`AUTH_REQUIRED`、`AUTH_FORBIDDEN`、`INTERNAL_ERROR`）；每码对应中文可读 message，占位参数受控（禁止拼接堆栈 / SQL / 绝对路径）。命名规则见[命名规范](命名规范.md) §6 | `app/backend/core/error_codes.py` |
| 16-3 | 全局异常处理器 | 注册 `AppError` / `AllProvidersFailedError` / `RequestValidationError` / `HTTPException` / 兜底 `Exception` 处理器，统一输出契约；未知异常对外回 `INTERNAL_ERROR` 通用文案、对内留脱敏堆栈 | `app/backend/core/exception_handlers.py`（main 与测试宿主共用） |
| 16-4 | 对外响应契约与前端展示 | 定义 `ErrorResponse{code, message, details?}`；前端 `src/lib/api.ts` 与 `StudioOperation` 按 `code` 展示可读文案，未知码兜底 `INTERNAL_ERROR` | `app/backend/schemas/errors.py`、`src/lib/api.ts`、前端错误展示组件 |
| 16-5 | 日志与敏感信息脱敏 | 日志只记 `code` / 端点 / 摘要；不打印 `DATABASE_URL`、AI key、Authorization、artifact 全文；`details` 过滤 password / token / api_key | `app/backend/core/log_redaction.py`、异常处理器 |
| 16-6 | 测试覆盖 | 单元：异常基类 / 映射 / 处理器；集成：各状态码分支返回 `{code,message}`；前端：错误展示改为 `message` 优先 | `app/backend/tests/unit/test_exceptions.py`、`tests/integration/test_error_contract.py`、前端错误解析工具 |

**实施结果（2026-11-04）**：

- 新增 `core/error_codes.py`（31 个 DOMAIN_REASON 码 + 中文 message 唯一来源）、`core/exceptions.py`（分级与 details 脱敏）、`core/exception_handlers.py`（统一注册）、`core/log_redaction.py`、`schemas/errors.py`。
- `main.py` 与接口测试宿主统一调用 `register_exception_handlers`，避免线上与测试契约漂移。
- studio / studio_ai / execution / auth / 依赖注入的错误分支迁移为 `AppError`；`AllProvidersFailedError` 保留逐家 provider/model/reason（脱敏）。
- 前端 `studio.ts` / `auth.ts` / `settings.ts` 改为 `message` 优先，并提供 `describeErrorCode`。
- 单测 112 条通过；新增错误契约集成用例 4 条通过；接口集成共 54 条，其余因本机 PostgreSQL/Docker 不可用未完整执行（见测试执行记录）。

**影响面（已完成同步）**：

- **API 响应契约变更**：所有错误响应从 `{"detail": ...}` 直接切换为 `ErrorResponse{code, message, details?}`，**未做双写过渡**。
- **现有测试**：后端错误断言已改为断言 `code` / `message`；未迁移的模板路由由全局 `HTTPException` 处理器映射为中文通用文案。
- **前端**：`StudioOperation` 的错误捕获与展示、表单与预览的错误提示改为读取 `message`。
- **文档**：需求说明 §5 错误协议、测试矩阵、开发规范、命名规范已同步。

**决策已收敛（2026-11-04 用户拍板）**：

| 决策点 | 结论 |
|---|---|
| 是否保留 `detail` 兼容字段 | **不保留，直接切换**，一次到位为 `ErrorResponse{code, message, details?}` |
| message 语言策略 | **仅中文**，写成用户能直接看懂的句子；不用 i18n key、不做中英双语 |
| 错误码命名规范 | **`DOMAIN_REASON`**（如 `STUDIO_BUILD_FAILED`），详见[命名规范](命名规范.md) §6 |
| 是否引入 `request_id` | **已决策暂缓**（见下方暂缓条目） |

**已决策暂缓：`request_id`（2026-11-04）**

- 决策：本轮**不引入** `request_id`，响应结构固定为 `ErrorResponse{code, message, details?}`。
- 暂缓理由：引入 `request_id` 需要新增一层中间件贯穿请求生命周期、注入日志上下文并同步改造日志格式与测试断言；当前优先级是「让错误先可读」，少这一层中间件可以更快落地，也避免错误契约一次改动面过大。
- 保留与不删除：本条不因暂缓而删除；后续引入时的落位为：新增请求 ID 中间件 → 异常处理器写入 `request_id` → `ErrorResponse` 增加 `request_id` 字段 → 日志与前端错误提示展示该 ID。届时需重新评估对 11 个接口与前端错误展示的改动面。

**建议时点**：P0 前置，早于 Phase 5（多用户 / 对外），且早于 Phase 17（认证与多用户隔离）。越晚改，错误契约被越多代码与测试依赖，回归成本越高。

### Phase 17：认证与多用户数据隔离（已完成，2026-11-04）

> 新增于 2026-11-04。按用户决策，登录/认证与多用户数据隔离**合并为同一件事实施**，不再作为两个独立事项；编号追加在末尾，建议实施时点紧随 Phase 16、早于 Phase 5（见「实现顺序与实施时点」）。

**状态**：已实施并完成本地验证。后端迁移 `c2d3e4f5a6b7`（接在 `b7c8d9e0f1a2` 之后，`alembic heads` 唯一）；后端单元 113 条、接口集成 59 条全绿；前端 21 条单元测试通过，`tsc --noEmit` 通过。**仅本地验证，未部署生产**。

**现状（实施前）**：产品不提供登录入口；Studio 业务路由统一使用 `SHARED_CONTEXT = "studio-shared"` 读写 `projects` / `studio_messages` / `studio_versions`，不按 `user_id` 过滤。模板侧的认证路由与 `AuthContext` 仍存在，但不构成产品登录入口，Studio 数据也不归属任何真实用户。

**目标**：引入登录与会话，使 Studio 数据按登录用户归属并在所有查询上强制过滤；历史共享数据完成迁移与回填；补齐越权测试与前后端联调。所有认证失败分支沿用 Phase 16 的 `ErrorResponse` 契约（`AUTH_REQUIRED` 401、`AUTH_INVALID_CREDENTIALS` 401、`AUTH_TOKEN_EXPIRED` 401、`AUTH_EMAIL_TAKEN` 409、`AUTH_FORBIDDEN` 403）。

**实施结论（决策已定，不再变更）**：

1. **会话**：JWT 访问令牌，有效期 7 天，无 refresh token；`APP_AUTH_SECRET` 缺失时应用启动直接失败，禁止随机兜底密钥。
2. **登录方式**：仅邮箱/密码，不做 OAuth；模板 OIDC 路由已替换，前端 `AuthCallback`、`AuthContext`、`ProtectedAdminRoute` 一并移除。
3. **历史数据**：存量 `studio-shared` 数据与 `executions` 回填到幂等创建的 `legacy` 用户（`legacy@atoms.local`，无密码、不可登录），不删除、不置空。
4. **越权语义**：跨用户访问统一返回 **404 `RESOURCE_NOT_FOUND`**，不使用 403。理由：403 会暴露“资源存在但无权访问”，攻击者可据此枚举他人项目/版本 id；404 与“资源确实不存在”不可区分，牺牲少量可观测性换取不泄露存在性。
5. **公开边界**：`/auth/*` 与 `/health` 公开；`/studio/*` 全部要求登录，查询按 `user_id` 过滤，客户端不能通过请求体覆盖归属。

**可执行条目**：

| 序号 | 条目 | 落地内容 | 交付物 |
|---|---|---|---|
| 17-1 | 登录与会话 | 邮箱/密码注册、登录、`/me`、登出；JWT 7 天、无 refresh；未登录访问 Studio 接口返回 401 `AUTH_REQUIRED`。模板 OIDC 路由与前端认证回调已移除 | `app/frontend/src/pages/LoginPage.tsx`、`lib/auth.ts`、`routers/auth.py`、`services/auth.py` |
| 17-2 | 数据按 `user_id` 归属 | `projects` / `studio_messages` / `studio_versions` / `executions` 明确归属；新记录写入当前登录用户 `user_id`，`SHARED_CONTEXT` 常量已移除 | `models/*`、`routers/studio.py`、`services/execution.py` |
| 17-3 | 查询强制过滤 | 所有 Studio 读写查询按当前 `user_id` 过滤；跨用户访问统一 404 `RESOURCE_NOT_FOUND`；客户端请求体无法覆盖 `user_id` | `routers/studio.py` |
| 17-4 | 历史数据迁移与回填 | Alembic `c2d3e4f5a6b7`：users 增加 `password_hash` / `is_legacy` 与邮箱唯一索引；executions 增加非空 `user_id`；存量共享数据回填到幂等 `legacy` 用户；迁移可重复执行，附回滚说明 | `app/backend/alembic/versions/c2d3e4f5a6b7_add_multiuser_auth.py` |
| 17-5 | 越权访问测试 | 集成测试：A 用户不能读/写/删/恢复 B 用户的项目与版本、不能停止 B 的执行；未登录 401；伪造 `user_id` 无效；列表只返回本人项目 | `app/backend/tests/integration/test_studio_authz.py` |
| 17-6 | 前后端联调 | 登录页（注册/登录切换）、令牌写入 `localStorage.token`、401 统一跳转 `/login`；错误按中文 message 展示。界面集成链路用例本轮未补，见遗留风险 | `app/frontend/src/pages/LoginPage.tsx`、`lib/api.ts` |

**影响面（排期必须评估）**：

- **数据库结构变更**：`users` / `executions` 新增认证与归属字段属于生产表结构变更，必须先做迁移评审与回填演练；存量 `projects` / `studio_messages` / `studio_versions` 的 `studio-shared` 归属同时回填为 `legacy`。
- **现有接口与测试**：11 个 Studio 接口全部要求登录态；后端接口集成 59 条已改为由测试宿主注入固定用户并按 `user_id` 隔离；前端集成 35 条尚未登录前置改造（见遗留风险）。
- **前端**：新增登录页与令牌持久化（`localStorage.token`）；web-sdk 请求附带 Bearer 头，401 由 `onUnauthorized` 统一跳转 `/login`。
- **越权语义**：已确定为 404 + `RESOURCE_NOT_FOUND`（见「实施结论」）。前端只展示“资源不存在或已被删除”，不再出现“无权限”与“不存在”两套文案。
- **模板代码取舍**：Phase 17 只保留邮箱/密码会话与凭据校验所需部分；OIDC 路由、前端认证回调、AuthContext、ProtectedAdminRoute 均已移除，不引入租户、角色、用户管理后台。

**依赖与决策点（已全部关闭）**：

1. 会话方案：JWT 无状态，TTL 7 天；不做服务端会话表。
2. 登录方式：仅邮箱/密码；不做邮箱验证码、不做 OAuth。
3. 历史数据回填：幂等 `legacy` 用户，保留“历史共享数据”归属，不删除、不置空。
4. 跨用户访问：统一 404 `RESOURCE_NOT_FOUND`，不用 403。
5. 过期与刷新：不引入 refresh token；过期后返回 `AUTH_TOKEN_EXPIRED`，前端跳转登录重新登录。

**建议时点**：Phase 16 完成之后、Phase 5 之前（对外/多用户前必须）。越晚做，数据归属字段与查询过滤需要覆盖的代码路径越多，回填风险越大。

## Atoms 已实现但我们尚未规划的产品点（备忘）

以下是 Atoms 官网/帮助中心体现、但未排入上述 Phase 的能力，留作后续讨论：

- **SEO 优化（Sarah 角色）**：针对 Web 项目的 SEO 内容规划与改进。
- **广告投放（Adrian 角色）**：Google Ads 准备与分析。
- **积分/用量计费**：每轮对话显示 Credits used，工作区余额管理。
- **密钥与密钥管理**：独立于源码的 secrets 管理，不在对话中粘贴密钥。
- **分享与导出**：Share（打开 Atoms 项目本身）vs Publish（打开成品网站），导出项目 ZIP。
- **磁盘空间管理**：查看存储用量、清理大文件。
- **多模型选择**：用户可在消息中用 `#` 指定模型（Anthropic / Gemini / Open models）。

## 能力扩展规划：Phase 13–15（多语言 / 动态后端 / 自选 AI API）

> 以下三项已并入阶段总览表，作为 Phase 13（用户自选 AI API）、Phase 14（动态后端 / 前后端分离）、Phase 15（多语言 / 多文件项目）与其他 Phase 并列。此节保留现状、排序理由与决策点。

### 现状答复（均为「不支持」）

| 问题 | 现状 | 关键约束 |
|---|---|---|
| 除 HTML 外的其他语言 | ❌ 仅支持单文件 HTML | `sanitize_html` 强约束 `<!DOCTYPE html>…</html>`，`validate_artifact_html` 要求 `<body`/`</html>` |
| 动态逻辑 / 前后端分离 | ❌ 无后端运行时 | 沙箱为 `nginx:alpine` 只读静态托管，产物只有内联 JS，无 API 层、无持久化、无出站 |
| 用户自选 AI API | ❌ 仅平台侧 env 配置 | 模型硬编码于 `MODEL_PROFILES`（glm-4.7-flash），key 由 `APP_AI_BASE_URL`/`APP_AI_KEY` 环境变量注入，终端用户不可自选 |

### 排序理由

1. **用户自选 AI API**：改动最小（把模型配置从「平台环境变量」下沉为「用户级配置」）、价值最直接（用户用自己的 key 免去平台成本与限流、可换更强模型），且是后两项的「质量杠杆」——更好的模型才能稳定产出复杂后端代码。故最优先。
2. **动态后端 / 前后端分离**：产品形态从「静态原型」跃迁到「可运行 Web 应用」，价值高，但需先扩展沙箱运行时（Node/Python 进程 + 网络/密钥/持久化策略），代价大，故次之。
3. **多语言 / 多文件项目**：复杂度最高（依赖安装 + 构建流水线 + 供应链安全），且依赖「动态后端」运行时打底，故最后。

### 与既有 Phase 的关系

- 「用户自选 AI API」是对 Phase 4 的增强，可与 Phase 5/6 并行启动，并应处理「用户 key 的加密存储与轮换」（对应 P1 密钥管理）。
- 「动态后端」的产物运行时沙箱，应与 Phase 6 已规划的「工具沙箱（需执行代码、可能出站/写文件）」统一设计，共享 Docker 基础设施但独立隔离策略。
- 「多语言/多文件」可复用 Phase 3 编辑器已预留的「文件树 / 编辑会话」方向，以及 Phase 9 发布的产物托管。

### 各规划项的关键决策点（启动时定）

- 自选 AI API：支持哪些厂商预设；用户 key 的加密与用量统计归属；模型参数（max_tokens/温度）是否让用户可调。
- 动态后端：运行时选型（优先 Node.js 还是 Python，或两者）；出站网络白名单；持久化（临时卷 vs 数据库服务）；密钥如何注入产物。
- 多语言/多文件：构建环境（Docker 多阶段 vs DevContainer）；依赖供应链审计（npm audit / pip-audit）；构建超时与资源配额；产物缓存与增量构建。
