# 架构设计

## 1. 总览

Atoms Studio 是一个「对话式应用生成工作台」：用户用自然语言描述需求 → AI 给出可确认的结构化计划 → 确认后真实生成一个可运行的前端应用 → 在 App Viewer 沙箱内即时交互 → 每次构建落库为可回滚版本。

前后端分离部署：

- `app/frontend`：Vite + React + TypeScript + shadcn/ui + Tailwind
- `app/backend`：FastAPI（Atoms Cloud / FuncSea），异步 SQLAlchemy 2.0
- 前端通过 `@metagptx/web-sdk` 访问后端，不直连模型、不持有密钥

## 2. 分层结构

```
前端
├── pages/Index.tsx              工作台编排（三栏 + 主流程状态机）
├── pages/DeployPage.tsx         部署与分享（占位）
├── pages/CloudPage.tsx          Cloud 后端（占位）
├── components/studio/
│   ├── ProjectRail.tsx          项目列表 + 主导航 + 登录态入口
│   ├── ConversationStream.tsx   对话流（用户气泡 / 助手通栏 / 计划卡 / 构建结果）
│   ├── PlanCard.tsx             结构化计划卡（确认执行 / 调整需求 / 复制）
│   ├── ArtifactPreview.tsx      App Viewer：srcDoc iframe + 桌面/移动 + 版本切换
│   ├── RequirementComposer.tsx  输入区 + 模型选择
│   └── PlaceholderPanel.tsx     未构建模块的统一占位页
├── hooks/useStudioAuth.ts       三态鉴权（loading / authenticated / anonymous）
└── lib/studio.ts                类型契约 + API 封装（唯一数据入口）

后端
├── routers/studio.py            /api/v1/studio/* 业务接口
├── services/studio_ai.py        AI 适配层（提示词 + 解析 + 校验 + 修复）
├── routers/projects.py 等       实体 CRUD（自动生成）
└── models/{projects,studio_messages,studio_versions}.py
```

## 3. AI 适配层

模型调用全部收敛在 `services/studio_ai.py`，切换模型只改 `MODEL_PROFILES`：

| profile | 模型 | 用途 |
|---|---|---|
| balanced（默认） | gpt-5.5 | 通用高质量 |
| fast | deepseek-v4-flash | 快速小步迭代 |
| quality | claude-opus-5 | 复杂界面还原 |

三段式生成，每段一次独立模型调用，前端据此呈现真实阶段进度而非假进度条：

1. **generate_plan** → 结构化 JSON（summary / stack / steps / files），要求 3–5 个实现步骤
2. **generate_outline** → 界面结构 JSON（title / sections / interactions / seed_data）
3. **generate_artifact** → 单文件 HTML 产物

结构化输出不依赖裸 `json.loads`：先抽取 JSON 块 → 校验必填字段 → 失败一次修复重试 → 仍失败返回 502 明确错误。产物 HTML 经 `sanitize_html` 裁剪为完整文档（`<!DOCTYPE>` 起、`</html>` 止、必含 body），失败重建一次。

产物约束（写进系统提示）：禁止外链 CDN/字体/图片、样式与脚本内联、必须实现真实交互、≤400 行、响应式、浅色克制视觉。

## 4. 数据模型

三张表，均按 `user_id` 隔离（系统托管字段，前端不可写）：

**projects** — `id, user_id, name, description(text), status, current_version, preview_ready`
项目当前指针指向 `current_version`，回滚只改指针，不复制产物。

**studio_messages** — `id, user_id, project_id, role, kind, content(text), meta(text JSON)`
`kind` 区分 requirement / plan / build / note；`meta` 承载计划对象、模型名、版本引用等结构化附加信息。

**studio_versions** — `id, user_id, project_id, version_no, label, plan_summary(text), artifact_html(text)`
版本号在项目内自增（`max(version_no)+1`），每次构建追加一条，产物完整快照保存在 `artifact_html`。

## 5. 主流程与接口

```
POST /api/v1/studio/projects                 建项目
POST /api/v1/studio/projects/{id}/messages   落用户消息
POST /api/v1/studio/projects/{id}/plan       阶段一 → 计划
POST /api/v1/studio/projects/{id}/outline    阶段二 → 界面结构
POST /api/v1/studio/projects/{id}/artifact   阶段三 → 产物 + 新版本
GET  /api/v1/studio/projects/{id}            载入项目（含当前产物）
POST /api/v1/studio/projects/{id}/restore    回滚版本指针
GET  /api/v1/studio/versions/{id}            读取指定版本产物
GET  /api/v1/studio/models                   可选模型清单
```

会话边界：每个涉及 AI 的接口都先 `commit()` 收尾读阶段，再调用模型，模型返回后开启新的写阶段并 `commit()`。绝不在慢速 AI/HTTP 调用期间持有 SQLAlchemy 事务。

## 6. 预览沙箱方案

产物是一个**自包含 HTML 文档**，前端用 `<iframe srcDoc sandbox="allow-scripts allow-forms allow-modals allow-popups">` 渲染：

- `allow-scripts` 让产物里的交互真正可用；不授予 `allow-same-origin`，产物无法访问宿主页面存储与 Cookie
- 无需构建产物服务器或对象存储，天然支持离线与版本切换
- 换版本 / 手动刷新通过 `key` 变更重挂载 iframe；桌面/移动视图通过 `max-width` 收敛
- 「在新标签页打开」用 Blob URL 生成临时可访问页面，60s 后回收

## 7. 登录与访问控制

复用 Atoms Cloud 内置鉴权：`client.auth.me()` 三态判定、`client.auth.toLogin()` 跳转、`/auth/callback` 由模板只读页处理。后端所有业务接口依赖 `get_current_user`，按 `user_id` 过滤，未登录返回 401。前端未登录时仍可浏览工作台与示例需求，点击生成才引导登录。

## 8. 已知限制与后续方向

- 生成产物为单文件 HTML 原型，尚未输出多文件 React 工程或真实文件树（`files` 目前是计划描述）
- 部署与分享、Cloud 后端数据表/存储/函数目前是占位页，保留真实信息架构
- 未做团队协作与多人共享项目
- 后续建议顺序：多文件工程产物 → 部署分享（稳定 URL + 权限）→ 预览内元素级点选修改 → 项目协作者
