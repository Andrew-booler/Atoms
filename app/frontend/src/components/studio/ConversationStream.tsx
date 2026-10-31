import { AlertCircle, Check, FileCode2, Layers, RotateCcw } from 'lucide-react';
import { useEffect, useRef } from 'react';
import { cn } from '@/lib/utils';
import { PlanCard } from './PlanCard';
import type { StudioMessage } from '@/lib/studio';

interface ConversationStreamProps {
  messages: StudioMessage[];
  planState: 'pending' | 'running' | 'done';
  onApprove: (message: StudioMessage) => void;
  onRevise: (message: StudioMessage) => void;
  runningPlanId?: number | null;
  onCopy: (action: () => Promise<void>) => Promise<void>;
  onRetry?: () => void;
  busy: boolean;
  error?: string | null;
  buildStage?: string | null;
}

function formatTime(raw?: string | null) {
  if (!raw) return '';
  const date = new Date(raw);
  if (Number.isNaN(date.getTime())) return '';
  return date.toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' });
}

export function ConversationStream({
  messages,
  runningPlanId,
  onCopy,
  onApprove,
  onRevise,
  onRetry,
  busy,
  error,
  buildStage,
}: ConversationStreamProps) {
  const endRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    endRef.current?.scrollIntoView({ block: 'end', behavior: 'smooth' });
  }, [messages.length, busy, error]);

  return (
    <div className="studio-scroll min-h-0 flex-1 overflow-y-auto" role="log" aria-live="polite">
      <div className="mx-auto w-full max-w-[720px] space-y-4 px-4 py-5">
        {messages.map((message) => {
          if (message.role === 'user') {
            return (
              <div key={message.id} className="flex justify-end">
                <div className="rise-in max-w-[85%] rounded-[8px] bg-canvas px-3 py-2 text-[13.5px] leading-[1.65] text-ink">
                  <p className="whitespace-pre-wrap break-words">{message.content}</p>
                </div>
              </div>
            );
          }

          if (message.kind === 'plan' && message.meta.plan) {
            const approved = message.meta.approved === true;
            return (
              <PlanCard
                key={message.id}
                plan={message.meta.plan}
                model={message.meta.model}
                state={approved ? 'done' : runningPlanId === message.id ? 'running' : 'pending'}
                onApprove={() => onApprove(message)}
                onRevise={() => onRevise(message)}
                onCopy={onCopy}
                approveDisabled={busy}
              />
            );
          }

          if (message.kind === 'note') {
            return (
              <div key={message.id} className="flex items-center gap-2 py-0.5">
                <RotateCcw className="h-3 w-3 text-ink-faint" strokeWidth={2} />
                <p className="mono text-[11.5px] text-ink-faint">{message.content}</p>
              </div>
            );
          }

          if (message.kind === 'build') {
            const interactions = message.meta.interactions ?? [];
            return (
              <div key={message.id} className="rise-in">
                <div className="flex items-start gap-2">
                  <Check className="mt-0.5 h-3.5 w-3.5 shrink-0 text-ok" strokeWidth={2.6} />
                  <div className="min-w-0">
                    <p className="text-[13.5px] leading-[1.65] text-ink">{message.content}</p>
                    <p className="mono mt-1 text-[10.5px] text-ink-faint">
                      {formatTime(message.created_at)}
                      {message.meta.model ? ` · ${message.meta.model}` : ''}
                    </p>
                  </div>
                </div>

                {(message.meta.sections?.length ?? 0) > 0 && (
                  <div className="mt-2 flex flex-wrap gap-1.5 pl-[22px]">
                    {message.meta.sections?.map((section) => (
                      <span
                        key={section}
                        className="inline-flex items-center gap-1 rounded border border-line px-1.5 py-0.5 text-[11px] text-ink-soft"
                      >
                        <Layers className="h-2.5 w-2.5" strokeWidth={2} />
                        {section}
                      </span>
                    ))}
                  </div>
                )}

                {interactions.length > 0 && (
                  <ul className="mt-2 space-y-1 pl-[22px]">
                    {interactions.slice(0, 4).map((item) => (
                      <li
                        key={item}
                        className="flex items-start gap-1.5 text-[12px] leading-[1.55] text-ink-soft"
                      >
                        <FileCode2 className="mt-[2px] h-3 w-3 shrink-0 text-ink-faint" strokeWidth={1.9} />
                        {item}
                      </li>
                    ))}
                  </ul>
                )}
              </div>
            );
          }

          return (
            <div key={message.id} className="rise-in">
              <p className="whitespace-pre-wrap break-words text-[13.5px] leading-[1.7] text-ink-soft">
                {message.content}
              </p>
              <p className="mono mt-1 text-[10.5px] text-ink-faint">{formatTime(message.created_at)}</p>
            </div>
          );
        })}

        {busy && (
          <div className="flex items-center gap-2 rounded-md border border-line bg-canvas px-3 py-2">
            <span className="stage-dot-active h-1.5 w-1.5 rounded-full bg-brand" />
            <span className="text-[12.5px] text-ink-soft">{buildStage || '正在处理…'}</span>
          </div>
        )}

        {error && (
          <div
            role="alert"
            className="flex flex-wrap items-center gap-2 rounded-md border border-[#F2D5D5] bg-[#FDF3F3] px-3 py-2"
          >
            <AlertCircle className="h-3.5 w-3.5 shrink-0 text-err" strokeWidth={2} />
            <span className="min-w-0 flex-1 text-[12.5px] leading-[1.55] text-err">{error}</span>
            {onRetry && (
              <button
                type="button"
                onClick={onRetry}
                disabled={busy}
                className="inline-flex h-7 items-center gap-1 rounded border border-[#E8BFBF] !bg-transparent px-2 text-[12px] font-medium text-err transition-colors hover:!bg-transparent"
              >
                <RotateCcw className="h-3 w-3" strokeWidth={2} />
                重试
              </button>
            )}
          </div>
        )}

        <div ref={endRef} className={cn('h-px w-full')} />
      </div>
    </div>
  );
}
