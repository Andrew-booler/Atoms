---
last_updated: 2026-10-29T10:05:00Z
status: active
---

# Project Context

## Project Overview

Atoms Studio —— 一个对标 Atoms 的 AI 应用生成工作台。用户用一句话描述需求，AI 先输出可确认的结构化计划，确认后真实生成可运行的前端应用，并在 App Viewer 沙箱内即时交互；每次构建保存为可回滚版本。首版聚焦「需求 → 计划 → 可操作成品」这条完整主流程。

## Key Decisions
| Date | Decision | By | Rationale |
|------|----------|-----|-----------|
| 2026-10-29 | 后端使用 Atoms Cloud（Auth/Database/Edge Functions/AI），AI 全部走服务端 | Alex | 向终端用户暴露 AI 能力，密钥不能放前端 |
| 2026-10-29 | AI 调用拆成 plan / outline / artifact 三次独立模型调用 | Alex | 每个阶段可单独重试，前端能展示真实阶段进度而非假进度条 |
| 2026-10-29 | 产物为自包含单文件 HTML，用 iframe srcDoc + sandbox 渲染 | Alex | 无需构建服务器即可真正可交互，且天然隔离宿主环境 |
| 2026-10-29 | 模型通过 profile 抽象（balanced/fast/quality），前端只传 key | Alex | 可替换适配，避免模型名与密钥泄漏到前端 |
| 2026-10-29 | 版本回滚只移动 project.current_version 指针 | Alex | 产物快照不可变，回滚是 O(1) 且不产生冗余数据 |
| 2026-10-29 | 视觉采用纯白「纸感」+ 1px 分隔线 + 暖赤陶主色 #C2410C | Alex | 让对话与预览成为视觉焦点，区别于蓝紫渐变 AI 风 |
| 2026-10-29 | 部署分享 / Cloud 后端 / 版本历史用占位页保留真实信息架构 | Alex | 首版聚焦主流程，同时让用户看清产品方向 |

## Constraints

- 前端统一走 `@metagptx/web-sdk`，禁止 fetch/axios 直连 `/api/v1/*`
- 后端路由前缀必须 `/api/v1/`，routers 自动发现
- 禁止修改 `app/backend/core/**`、`models/**`、`main.py`、`lambda_handler.py`
- 慢速 AI 调用前后必须收尾 DB 事务（短 DB 阶段 → commit → AI → 新 DB 阶段）
- 所有业务数据按 `user_id` 隔离，`user_id` 由系统托管，前端不可写
- 用户无法执行终端命令，平台预览自动重载
