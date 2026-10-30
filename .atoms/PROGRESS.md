---
last_updated: 2026-10-29T10:06:00Z
---

# Requirements & Progress

## Requirements Overview

构建对标 Atoms 的 AI 应用生成工作台（浅色极简），采用原型化开发、持续迭代。首版必须跑通一条真实主流程：输入需求 → AI 真实生成（非 mock）→ 在 App Viewer 中立刻操作成品；计划模式需在执行前输出结构化计划并由用户确认。六大核心模块需覆盖导航与信息架构。

## User Stories

1. 作为创作者，我描述一句需求后能看到 AI 拆出的执行计划，并决定是否执行。
2. 作为创作者，我确认计划后能在右侧直接操作真实可运行的成品，而不是看截图。
3. 作为创作者，我能回到历史版本，并随时切换查看。
4. 作为创作者，我能看到我的项目列表，并新建/删除项目。
5. 作为访问者，我能先浏览工作台，只有在需要保存时才被要求登录。

## Task Breakdown
| ID | Task | Assignee | Status | Deps |
|----|------|----------|--------|------|
| T1 | 激活 Atoms Cloud 后端（Auth/DB/Storage/Functions/AI） | Alex | done | - |
| T2 | 建表：projects / studio_messages / studio_versions | Alex | done | T1 |
| T3 | AI 适配层：3 段式生成 + JSON 校验修复 + HTML 净化 | Alex | done | T1 |
| T4 | Studio 业务路由：项目/消息/plan/outline/artifact/restore | Alex | done | T2,T3 |
| T5 | 设计令牌与全局样式（浅色纸感极简） | Alex | done | T1 |
| T6 | 工作台外壳：侧栏 + 对话 + App Viewer 三栏 | Alex | done | T5 |
| T7 | 主流程串联：计划卡确认 → 构建 → 沙箱预览 | Alex | done | T4,T6 |
| T8 | 版本切换与回滚 | Alex | done | T7 |
| T9 | 部署分享 / Cloud 后端占位页 + 路由 | Alex | done | T6 |
| T10 | 验证：lint + build + 界面检查 | Alex | done | T7,T9 |
| T11 | 上下文文档：架构摘要与进度 | Alex | done | T10 |

## Progress Log

- 2026-10-29 激活 Atoms Cloud 后端，确认 Auth/Database/Edge Functions/AI 全可用。
- 2026-10-29 建表三张（需显式声明整型自增 id 才能生成主键，首轮建表失败后修正）。
- 2026-10-29 完成 AI 适配层 `services/studio_ai.py`，三 profile 可切换。
- 2026-10-29 完成 `routers/studio.py`，生成拆为 plan/outline/artifact 三段，各自独立重试。
- 2026-10-29 完成浅色极简工作台与 App Viewer（iframe srcDoc + sandbox）。
- 2026-10-29 占位页（部署分享、Cloud 后端）与路由接入完成。
- 2026-10-29 `pnpm run lint` 与 `pnpm run build` 通过，界面检查渲染质量 4 分。
- 2026-10-29 架构摘要与项目上下文写入完成。
