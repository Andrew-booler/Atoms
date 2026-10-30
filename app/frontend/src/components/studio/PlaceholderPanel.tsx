import { ArrowLeft } from 'lucide-react';
import { useNavigate } from 'react-router-dom';

interface PlaceholderPanelProps {
  eyebrow: string;
  title: string;
  description: string;
  planned: { title: string; detail: string }[];
}

/**
 * 尚未构建的模块统一使用这个页面：
 * 保留真实产品标签，明确写出计划交付的能力，并提供回到工作台的唯一主路径。
 */
export function PlaceholderPanel({ eyebrow, title, description, planned }: PlaceholderPanelProps) {
  const navigate = useNavigate();

  return (
    <div className="flex h-screen flex-col bg-paper">
      <header className="flex h-14 shrink-0 items-center gap-3 border-b border-line px-4">
        <button
          type="button"
          onClick={() => navigate('/')}
          className="inline-flex h-8 items-center gap-1.5 rounded-md border border-line-strong !bg-transparent px-2.5 text-[12.5px] font-medium text-ink transition-colors hover:!bg-transparent hover:border-ink-faint"
        >
          <ArrowLeft className="h-3.5 w-3.5" strokeWidth={2} />
          返回工作台
        </button>
        <span className="h-4 w-px bg-line" />
        <span className="mono text-[11.5px] text-ink-faint">{title}</span>
        <span className="mono ml-auto rounded-[3px] border border-line px-1.5 py-0.5 text-[10px] uppercase tracking-[0.05em] text-ink-faint">
          尚未构建
        </span>
      </header>

      <main className="studio-scroll flex min-h-0 flex-1 justify-center overflow-y-auto px-6 py-10">
        <div className="w-full max-w-[720px]">
          <span className="mono text-[10.5px] uppercase tracking-[0.12em] text-brand">{eyebrow}</span>
          <h1 className="mt-2 text-[24px] font-semibold leading-[1.25] tracking-[-0.02em] text-ink">
            {title}
          </h1>
          <p className="mt-2.5 max-w-[560px] text-[13.5px] leading-[1.7] text-ink-soft">
            {description}
          </p>

          <div className="mt-6 rounded-[10px] border border-line">
            <div className="border-b border-line bg-canvas px-4 py-2.5">
              <span className="mono text-[10.5px] uppercase tracking-[0.09em] text-ink-faint">
                计划中的能力
              </span>
            </div>
            <ul className="divide-y divide-line">
              {planned.map((item) => (
                <li key={item.title} className="px-4 py-3">
                  <p className="text-[13.5px] font-medium leading-[1.5] text-ink">{item.title}</p>
                  <p className="mt-0.5 text-[12.5px] leading-[1.6] text-ink-soft">{item.detail}</p>
                </li>
              ))}
            </ul>
          </div>

          <p className="mt-4 text-[12px] leading-[1.6] text-ink-faint">
            当前版本聚焦「需求 → 计划 → 可操作成品」这条主流程，其余模块已完成导航与信息架构，接入后端能力后即可逐个补齐。
          </p>
        </div>
      </main>
    </div>
  );
}
