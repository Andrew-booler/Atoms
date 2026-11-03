import { ArrowLeft } from 'lucide-react';
import { useNavigate } from 'react-router-dom';
import { AiConfigPanel } from '@/components/settings/AiConfigPanel';
import { AiUsagePanel } from '@/components/settings/AiUsagePanel';

export default function SettingsPage() {
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
        <span className="mono text-[11.5px] text-ink-faint">设置</span>
      </header>

      <main className="studio-scroll flex min-h-0 flex-1 justify-center overflow-y-auto px-6 py-10">
        <div className="w-full max-w-[720px]">
          <span className="mono text-[10.5px] uppercase tracking-[0.12em] text-brand">偏好设置</span>
          <h1 className="mt-2 text-[24px] font-semibold leading-[1.25] tracking-[-0.02em] text-ink">
            AI 接入
          </h1>
          <p className="mt-2.5 max-w-[560px] text-[13.5px] leading-[1.7] text-ink-soft">
            默认使用系统内置的多供应商降级链。你也可以配置自己的 OpenAI 兼容服务，
            保存后生成调用会优先使用你的配置。
          </p>

          <div className="mt-6">
            <AiConfigPanel />
          </div>

          <p className="mt-4 text-[12px] leading-[1.6] text-ink-faint">
            密钥在服务端加密保存，界面只展示掩码；清除配置后立即回退系统默认供应商。
          </p>

          <div className="mt-10">
            <AiUsagePanel />
          </div>
        </div>
      </main>
    </div>
  );
}
