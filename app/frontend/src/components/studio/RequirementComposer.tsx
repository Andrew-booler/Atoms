import { ArrowUp, CornerDownLeft, Loader2, Sparkles } from 'lucide-react';
import { useEffect, useRef } from 'react';
import { cn } from '@/lib/utils';
import type { ModelOption } from '@/lib/studio';

interface RequirementComposerProps {
  value: string;
  onChange: (value: string) => void;
  onSubmit: () => void;
  busy: boolean;
  disabled?: boolean;
  placeholder: string;
  models: ModelOption[];
  profile: string;
  onProfileChange: (profile: string) => void;
  suggestions?: string[];
  hint?: string;
}

export function RequirementComposer({
  value,
  onChange,
  onSubmit,
  busy,
  disabled,
  placeholder,
  models,
  profile,
  onProfileChange,
  suggestions = [],
  hint,
}: RequirementComposerProps) {
  const areaRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    const el = areaRef.current;
    if (!el) return;
    el.style.height = 'auto';
    el.style.height = `${Math.min(el.scrollHeight, 168)}px`;
  }, [value]);

  const canSubmit = value.trim().length > 0 && !busy && !disabled;

  return (
    <div className="border-t border-line bg-paper px-4 py-3">
      <div className="mx-auto w-full max-w-[720px]">
        {suggestions.length > 0 && (
          <div className="mb-2 flex flex-wrap gap-1.5">
            {suggestions.map((item) => (
              <button
                key={item}
                type="button"
                onClick={() => {
                  onChange(item);
                  areaRef.current?.focus();
                }}
                className="max-w-full truncate rounded-full border border-line px-2.5 py-1 text-[11.5px] text-ink-soft transition-colors hover:border-ink-faint hover:text-ink"
              >
                {item}
              </button>
            ))}
          </div>
        )}

        <div
          className={cn(
            'rounded-[10px] border bg-paper transition-colors',
            disabled ? 'border-line opacity-60' : 'border-line-strong focus-within:border-ink-faint'
          )}
        >
          <textarea
            ref={areaRef}
            value={value}
            onChange={(event) => onChange(event.target.value)}
            onKeyDown={(event) => {
              if (event.key === 'Enter' && (event.metaKey || event.ctrlKey)) {
                event.preventDefault();
                if (canSubmit) onSubmit();
              }
            }}
            rows={2}
            disabled={disabled}
            placeholder={placeholder}
            aria-label="描述你想要的应用"
            className="studio-scroll block max-h-[168px] w-full resize-none bg-transparent px-3 pt-2.5 text-[13.5px] leading-[1.6] text-ink placeholder:text-ink-faint focus:outline-none disabled:cursor-not-allowed"
          />

          <div className="flex items-center gap-2 px-2 pb-2 pt-1">
            <label className="sr-only" htmlFor="model-profile">
              生成模型
            </label>
            <select
              id="model-profile"
              value={profile}
              onChange={(event) => onProfileChange(event.target.value)}
              disabled={busy || models.length === 0}
              className="mono h-7 rounded-md border border-line bg-canvas px-1.5 text-[10.5px] uppercase tracking-[0.04em] text-ink-soft outline-none transition-colors hover:border-ink-faint disabled:opacity-50"
            >
              {models.map((model) => (
                <option key={model.key} value={model.key}>
                  {model.label} · {model.model}
                </option>
              ))}
            </select>

            <span className="mono hidden items-center gap-1 text-[10.5px] text-ink-faint sm:flex">
              <CornerDownLeft className="h-3 w-3" strokeWidth={2} />
              ⌘ / Ctrl + Enter
            </span>

            <button
              type="button"
              onClick={onSubmit}
              disabled={!canSubmit}
              className="ml-auto inline-flex h-8 items-center gap-1.5 rounded-md bg-brand px-3 text-[12.5px] font-medium text-white transition-colors hover:bg-[#A93A0A] disabled:cursor-not-allowed disabled:opacity-50"
            >
              {busy ? (
                <Loader2 className="h-3.5 w-3.5 animate-spin" />
              ) : (
                <ArrowUp className="h-3.5 w-3.5" strokeWidth={2.4} />
              )}
              {busy ? '生成中' : '生成计划'}
            </button>
          </div>
        </div>

        <p className="mt-1.5 flex items-center gap-1.5 text-[11px] text-ink-faint">
          <Sparkles className="h-3 w-3" strokeWidth={1.9} />
          {hint || '先生成计划，确认后才会真正构建成品。'}
        </p>
      </div>
    </div>
  );
}
