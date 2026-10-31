---
last_updated: 2026-10-31
status: active
---

# Project Context

## Project Overview

Atoms Studio是共享对话式工作台：输入→保存需求→mock计划→确认→mock结构/HTML→真实保存/预览→第二轮→恢复历史。所有使用者共享数据，不提供产品登录、用户管理、权限或租户隔离。操作及子请求串行，成功/失败均释放busy；不做跨标签锁、队列或并发协调。AI默认预置输出，不真实调用，不收密钥，不评估质量。

## Key Decisions

| Date | Decision | By | Rationale |
|---|---|---|---|
| 2026-10-31 | 用户授权剩余三项实施并取消强制Mike审阅 | 用户，Alex记录 | 不等待意见、不增加审阅门禁；保留可读性、自检和验证 |
| 2026-10-31 | Studio业务路由共享读取，新记录user_id=studio-shared | Alex | 固定非凭据标识，不暴露服务端凭据，不改生产表结构 |
| 2026-10-31 | 默认MockOutputProvider，真实提供者只显式适配边界 | Alex | Plan/Outline/HTML形状兼容，无真实模型请求 |
| 2026-10-31 | StudioOperation集中busy/错误/重试，Index组合实际业务步骤 | Alex | 只抽取实际职责，不为形式建控制器/仓储全集 |
| 2026-10-31 | 批准状态与版本同事务，恢复摘要立即同步 | Alex | 防重复保存与误成功；恢复读取失败只读重试 |
| 2026-10-31 | 保留60项目/最早400消息，手机最小抽屉 | Alex | 不扩展分页，超容量核对及草稿刷新不保证 |
| 2026-10-31 | Playwright仅单元21/集成35，隔离studio_test_t1 | Alex | 单元静态页面/类替身，集成真实路由与PostgreSQL，仅AI受控；全部设计子情景不由56标题推导 |

## Constraints

- 现有React/Vite与Atoms Cloud FastAPI，不重新初始化或激活后端。
- 前端产品API经SDK；11个Studio路径保持不变，不新增幂等字段或计划id。
- 不修改backend core/models/main/lambda等受保护模块、生产表结构和系统预览配置。
- 测试宿主只建立/重置studio_test_命名空间三表，不清空public生产数据。
- 部署与Cloud只占位，不实际发布或管理数据。
- 已取消外部架构模板及通用规范待办；第三方原文不修改，不恢复arc42。
- 正式需求、架构、规范、模块测试与执行证据唯一维护于docs。

## 术语表

- mock：预置结果或受控失败替代外部调用。
- version_no/current_version：项目内序号；不是版本记录id。
- 串行：前项及子请求结束后再开始下一项。
