# DESIGN.md

## Direction & Layout

**产品定义**：一个像 Atoms 一样的 AI 应用生成工作台。用户用一句话描述需求，AI 先给出可确认的计划，再产出可立即在沙箱里操作的前端成品。核心情绪是「冷静、可信、专注」——工具感强，但界面不喧哗。

**视觉主张**：把界面做成一张**纸**。纯白工作区、几乎无阴影、只有极细的分隔线，让对话文本与 App Viewer 里的成品成为唯一的高视觉重量。定义性视觉记忆点是「三段式工作台」：左侧 248px 索引栏（项目列表）→ 中间对话流 → 右侧 App Viewer，用一条 1px 竖线分隔，像 Notion 的多栏文档而不是 SaaS 仪表盘。

参考基调：Notion 的编辑区呼吸感 + Linear 的分隔线精度。**不**是 Glassmorphism、**不**是深色渐变科技风、**不**是圆形彩色图标网格。

**布局网格**：
- 桌面 ≥1280px：`248px 侧栏 | minmax(420px,1fr) 对话 | minmax(480px,1.1fr) 预览`，两栏之间 1px 边线，无间隙无阴影。
- 平板 820–1279px：侧栏收成 56px 图标轨；对话与预览 50/50 分栏。
- 移动 <820px：单列，顶部 Tab 切换「对话 / 预览」，侧栏变为抽屉。
- 最大内容宽度：对话区 720px 居中，预览区铺满可用宽度。
- 纵向节奏：8px 基准，区块间距 24px/32px，卡片间距 12px。

**Do / Don't**：
- Do：用 1px `#E7E5E0` 边线建立层级；主色只出现在主按钮、当前选中项和进度点。
- Do：对话中的计划用「编号步骤 + 文件清单」排版，像工程文档。
- Don't：不用彩色左边框卡片、不用发光/玻璃拟态、不用紫蓝渐变大面积铺底。
- Don't：预览区不要套卡片外壳，让成品直接占满该面板（沙箱浏览器感）。

## Tokens

**色彩**（浅色单主题）：
- `--paper: #FFFFFF` 主背景
- `--canvas: #FAFAF8` 次级背景（侧栏、预览外框）
- `--ink: #1A1A18` 主文本
- `--ink-soft: #55534E` 次文本
- `--ink-faint: #8C8981` 辅助/时间戳
- `--line: #E7E5E0` 边框
- `--line-strong: #D6D3CC` 输入框/悬停边框
- `--brand: #C2410C` 主色（暖赤陶，克制使用；替代泛用的蓝紫）
- `--brand-soft: #FDF2EC` 主色底纹
- `--ok: #15803D` / `--warn: #B45309` / `--err: #B91C1C`

**字体**：
- 界面与正文：`"Inter Tight", "Inter", system-ui, -apple-system, "Segoe UI", sans-serif`，正文 14px/1.65，字重 400。
- 标题：同族，字重 600，字距 `-0.015em`，H1 22px，H2 17px，H3 15px。
- 等宽（文件路径、模型名、代码）：`"JetBrains Mono", ui-monospace, "SF Mono", monospace`，12px/1.5。
- 中文回退：`"PingFang SC", "Microsoft YaHei"`。

**间距与形状**：
- 间距刻度 4/8/12/16/24/32/48。
- 圆角：输入框与按钮 8px，面板 10px，抽屉 14px，头像与状态点为全圆。
- 图标按钮 32×32，点击目标 ≥40px（移动端 ≥44px）。

**层级与深度**：
- 默认零阴影，仅用 1px 边线；浮层（Popover / Dialog / Toast）用 `0 8px 28px -12px rgba(26,26,24,0.18)` + 1px 边线。
- 粘性区（顶栏、输入区）用背景色 + 顶部 1px 线，不用模糊毛玻璃。

## Shared Patterns & States

- **ProjectListItem**：名称 14px/500 + 版本徽标（等宽 11px）；选中态 `bg-brand-soft` + 左侧 2px `--brand` 竖条；悬停 `bg-canvas`。
- **MessageBubble**：用户消息靠右、`bg-canvas` + 8px 圆角 + 无边框；助手消息通栏左对齐、无气泡底色，只靠排版区分（Notion 式）。计划消息用编号列表 + 文件清单等宽块。
- **PrimaryButton**：`bg-brand` / 白字，8px 圆角，高 36px，字重 500；悬停加深 6%；`disabled` 用 `opacity-50` 且 `cursor-not-allowed`。焦点 `ring-2 ring-brand/30 ring-offset-1`。
- **SecondaryButton**：白底 + `--line-strong` 边框 + `--ink` 文字，**必须**保持 `!bg-transparent` 悬停不反色。
- **PlanCard**：`--paper` 底 + 1px 边线 + 10px 圆角；标题行含状态徽标（待确认 / 已执行 / 已回滚）；底部动作区：确认执行、调整需求、复制计划。
- **ProgressRail**：三个等宽阶段「计划 → 结构 → 产物」，当前阶段有 `--brand` 实心点 + 呼吸动画（1.6s ease-in-out），已完成用 `--ok` 勾。
- **EmptyState**：居中、最大 360px、图标 20px 线条风 + 一行说明 + 一个建议需求芯片（点击填入输入框）。
- **占位页 Placeholder**：保留真实产品标签（部署与分享、版本历史、Cloud 后端），内容区显示 `尚未构建` + 该模块计划做的能力清单，并提供返回工作台的主按钮。

**状态**：所有异步动作必须有 loading（按钮内联 spinner + 文案改为动词进行时）、error（红色行内提示 + 重试按钮）、empty（引导文案）。生成阶段失败必须能回到可重试状态，不能卡死。

**动效**：仅 120–200ms，`cubic-bezier(0.2, 0, 0.2, 1)`；用于抽屉、Tab、消息进场（4px 上浮 + 淡入）。禁止无限循环的装饰动画（阶段进度点除外）。主内容首屏直接可见，不依赖滚动或 IntersectionObserver 触发显示。

**可访问性**：正文对比度 ≥ 7:1（`--ink` on `--paper`），次文本 ≥ 4.5:1；所有图标按钮带 `aria-label`；预览 iframe 带 `title`；Tab 切换用 `role="tablist"`；表单错误用 `role="alert"` 行内提示。

## Media

本产品是操作型工具界面，**不使用装饰性摄影或插画**——留白和生成的成品本身就是视觉焦点。

必需的视觉资产只有一个：**品牌标记**。用内联 SVG 实现（两个叠置的方框，象征「外壳 + 生成物」），`--brand` 描边 + 4px 圆角，出现在侧栏顶部与占位页，不生成额外图片文件。

空状态与占位页用线性图标（lucide）表达，禁止抽象渐变块替代。App Viewer 内展示的是用户/模型生成的真实 HTML，不做截图占位。
