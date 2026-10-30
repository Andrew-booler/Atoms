import { Check, Copy, Loader2, PencilLine } from 'lucide-react';
import { useState } from 'react';
import { cn } from '@/lib/utils';
import type { PlanPayload } from '@/lib/studio';

interface PlanCardProps {
  plan: PlanPayload;
  model?: string;
  /** pending: 等待用户确认；running: 正在执行；done: 已产出产物 */
  state: 'pending' | 'running' | 'done';
  onApprove?: () => void;
  onRevise?: () => void;
  approveDisabled?: boolean;
}

const stateLabel: Record<PlanCardProps['state'], string> = {
  pending: '待确认',
  running: '执行中',
  done: '已执行',
};

export function PlanCard({
  plan,
  model,
  state,
  onApprove,
  onRevise,
  approveDisabled,
}: PlanCardProps) {
  const [copied, setCopied] = useState(false);

  const copyPlan = async () => {
    const text = [
      plan.summary,
      '',
      ...plan.steps.map((step, index) => `${index + 1}. ${step.title} — ${step.detail}`),
      '',
      ...plan.files.map((file) => `${file.path} — ${file.purpose}`),
    ].join('\n');
    try {
      await navigator.clipboard.writeText(text);
      setCopied(true);
      window.setTimeout(() => setCopied(false), 1600);
    } catch {
      setCopied(false);
    }
  };

  return (
    <div className="rise-in overflow-hidden rounded-[10px] border border-line bg-paper">
      <div className="flex flex-wrap items-center gap-x-2 gap-y-1.5 border-b border-line px-4 py-2.5">
        <span className="text-[12.5px] font-semibold tracking-[-0.01em] text-ink">执行计划</span>
        <span
          className={cn(
            'mono rounded-[3px] px-1.5 py-0.5 text-[10px] uppercase tracking-[0.04em]',
            state === 'pending' && 'bg-brand-soft text-brand-ink',
            state === 'running' && 'bg-[#FEF6E7] text-warn',
            state === 'done' && 'bg-[#EFF7F0] text-ok'
          )}
        >
          {stateLabel[state]}
        </span>
        {model && <span className="mono ml-auto text-[10.5px] text-ink-faint">{model}</span>}
      </div>

      <div className="px-4 py-3.5">
        <p className="text-[14px] leading-[1.6] text-ink">{plan.summary}</p>

        {plan.stack.length > 0 && (
          <div className="mt-2.5 flex flex-wrap gap-1.5">
            {plan.stack.map((tag) => (
              <span
                key={tag}
                className="rounded border border-line px-1.5 py-0.5 text-[11px] text-ink-soft"
              >
                {tag}
              </span>
            ))}
          </div>
        )}

        <ol className="mt-3.5 space-y-2">
          {plan.steps.map((step, index) => (
            <li key={`${step.title}-${index}`} className="flex gap-2.5">
              <span className="mono mt-[1px] flex h-[18px] w-[18px] shrink-0 items-center justify-center rounded-[4px] border border-line text-[10.5px] text-ink-soft">
                {index + 1}
              </span>
              <span className="min-w-0">
                <span className="block text-[13.5px] font-medium leading-[1.5] text-ink">
                  {step.title}
                </span>
                {step.detail && (
                  <span className="mt-0.5 block text-[12.5px] leading-[1.55] text-ink-soft">
                    {step.detail}
                  </span>
                )}
              </span>
            </li>
          ))}
        </ol>

        {plan.files.length > 0 && (
          <div className="mt-3.5 rounded-md bg-canvas px-3 py-2.5">
            <span className="mono block text-[10px] uppercase tracking-[0.09em] text-ink-faint">
              产出文件
            </span>
            <ul className="mt-1.5 space-y-1">
              {plan.files.map((file) => (
                <li key={file.path} className="flex flex-wrap items-baseline gap-x-2">
                  <span className="mono text-[11.5px] text-ink">{file.path}</span>
                  {file.purpose && (
                    <span className="text-[11.5px] text-ink-faint">{file.purpose}</span>
                  )}
                </li>
              ))}
            </ul>
          </div>
        )}
      </div>

      {state === 'pending' && (
        <div className="flex flex-wrap items-center gap-2 border-t border-line bg-canvas px-4 py-2.5">
          <button
            type="button"
            onClick={onApprove}
            disabled={approveDisabled}
            className="inline-flex h-8 items-center gap-1.5 rounded-md bg-brand px-3 text-[12.5px] font-medium text-white transition-colors hover:bg-[#A93A0A] disabled:cursor-not-allowed disabled:opacity-50"
          >
            <Check className="h-3.5 w-3.5" strokeWidth={2.4} />
            确认执行
          </button>
          <button
            type="button"
            onClick={onRevise}
            disabled={approveDisabled}
            className="inline-flex h-8 items-center gap-1.5 rounded-md border border-line-strong !bg-transparent px-3 text-[12.5px] font-medium text-ink transition-colors hover:!bg-transparent hover:border-ink-faint disabled:cursor-not-allowed disabled:opacity-50"
          >
            <PencilLine className="h-3.5 w-3.5" strokeWidth={1.9} />
            调整需求
          </button>
          <button
            type="button"
            onClick={copyPlan}
            className="ml-auto inline-flex h-8 items-center gap-1.5 rounded-md px-2 text-[12px] text-ink-faint transition-colors hover:text-ink"
          >
            {copied ? <Check className="h-3.5 w-3.5" /> : <Copy className="h-3.5 w-3.5" />}
            {copied ? '已复制' : '复制计划'}
          </button>
        </div>
      )}

      {state === 'running' && (
        <div className="flex items-center gap-2 border-t border-line bg-canvas px-4 py-2.5">
          <Loader2 className="h-3.5 w-3.5 animate-spin text-warn" />
          <span className="text-[12.5px] text-ink-soft">正在按计划构建，请稍候…</span>
        </div>
      )}
    </div>
  );
}
