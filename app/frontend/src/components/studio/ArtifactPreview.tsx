import { ExternalLink, Loader2, Monitor, RotateCw, Smartphone } from 'lucide-react';
import { useMemo, useRef, useState } from 'react';
import { cn } from '@/lib/utils';
import type { VersionSummary } from '@/lib/studio';

interface ArtifactPreviewProps {
  html: string | null;
  previewUrl?: string | null;
  title: string;
  busy: boolean;
  stageLabel: string;
  versions: VersionSummary[];
  activeVersion?: number | null;
  onRestore: (version: VersionSummary) => void;
  restoring: boolean;
  onAction: (action: () => Promise<void>) => Promise<void>;
}

type Viewport = 'desktop' | 'mobile';

export function ArtifactPreview({
  html,
  previewUrl,
  title,
  busy,
  stageLabel,
  versions,
  activeVersion,
  onRestore,
  restoring,
  onAction,
}: ArtifactPreviewProps) {
  const [viewport, setViewport] = useState<Viewport>('desktop');
  const [reloadKey, setReloadKey] = useState(0);
  const frameRef = useRef<HTMLIFrameElement>(null);

  const document_ = useMemo(() => {
    if (!html) return '';
    // 同一个 key 内不重排 DOM，换版本时由 key 触发重新挂载
    return html;
  }, [html]);

  const openInNewTab = () => onAction(async () => {
    if (previewUrl) {
      const opened = window.open(previewUrl, '_blank');
      if (!opened) throw new Error("外开页面被浏览器阻止，请允许弹窗后重试。");
      return;
    }
    if (!document_) return;
    const blob = new Blob([document_], { type: 'text/html;charset=utf-8' });
    const url = URL.createObjectURL(blob);
    const opened = window.open(url, '_blank');
    if (opened) opened.opener = null;
    window.setTimeout(() => URL.revokeObjectURL(url), 60_000);
    if (!opened) throw new Error("外开页面被浏览器阻止，请允许弹窗后重试。");
  });

  return (
    <section className="flex h-full min-h-0 flex-col bg-canvas" aria-label="应用预览">
      <header className="flex h-14 shrink-0 items-center gap-2 border-b border-line bg-canvas px-3">
        <span className="mono truncate text-[11.5px] text-ink-faint">
          {html ? `/preview · ${title}` : '/preview'}
        </span>

        <div className="ml-auto flex items-center gap-1">
          {versions.length > 0 && (
            <select
              aria-label="选择版本"
              value={activeVersion ?? ''}
              onChange={(event) => {
                const picked = versions.find(
                  (item) => String(item.version_no) === event.target.value
                );
                if (picked) onRestore(picked);
              }}
              disabled={restoring || busy}
              className="mono h-7 max-w-[150px] rounded-md border border-line-strong bg-paper px-1.5 text-[11px] text-ink-soft outline-none transition-colors hover:border-ink-faint disabled:opacity-50"
            >
              {versions.map((version) => (
                <option key={version.id} value={version.version_no}>
                  v{version.version_no}
                  {version.version_no === activeVersion ? ' · 当前' : ''}
                </option>
              ))}
            </select>
          )}

          <div
            role="group"
            aria-label="预览宽度"
            className="flex items-center rounded-md border border-line-strong bg-paper p-0.5"
          >
            <button
              type="button"
              disabled={busy}
              onClick={() => { if (!busy) setViewport('desktop'); }}
              aria-label="桌面视图"
              aria-pressed={viewport === 'desktop'}
              className={cn(
                'flex h-6 w-6 items-center justify-center rounded transition-colors',
                viewport === 'desktop' ? 'bg-brand-soft text-brand-ink' : 'text-ink-faint hover:text-ink'
              )}
            >
              <Monitor className="h-3.5 w-3.5" strokeWidth={1.9} />
            </button>
            <button
              type="button"
              disabled={busy}
              onClick={() => { if (!busy) setViewport('mobile'); }}
              aria-label="移动视图"
              aria-pressed={viewport === 'mobile'}
              className={cn(
                'flex h-6 w-6 items-center justify-center rounded transition-colors',
                viewport === 'mobile' ? 'bg-brand-soft text-brand-ink' : 'text-ink-faint hover:text-ink'
              )}
            >
              <Smartphone className="h-3.5 w-3.5" strokeWidth={1.9} />
            </button>
          </div>

          <button
            type="button"
            onClick={() => { if (!busy) setReloadKey((key) => key + 1); }}
            aria-label="重新加载预览"
            disabled={!html || busy}
            className="flex h-7 w-7 items-center justify-center rounded-md text-ink-faint transition-colors hover:bg-paper hover:text-ink disabled:opacity-40"
          >
            <RotateCw className="h-3.5 w-3.5" strokeWidth={1.9} />
          </button>
          <button
            type="button"
            onClick={openInNewTab}
            aria-label="在新标签页打开"
            disabled={!html || busy}
            className="flex h-7 w-7 items-center justify-center rounded-md text-ink-faint transition-colors hover:bg-paper hover:text-ink disabled:opacity-40"
          >
            <ExternalLink className="h-3.5 w-3.5" strokeWidth={1.9} />
          </button>
        </div>
      </header>

      <div className="studio-scroll flex min-h-0 flex-1 justify-center overflow-auto p-3">
        {html ? (
          <div
            className={cn(
              'h-full w-full overflow-hidden rounded-[10px] border border-line bg-paper transition-[max-width] duration-200',
              viewport === 'mobile' && 'max-w-[390px]'
            )}
          >
            <iframe
              key={`${activeVersion ?? 0}-${reloadKey}`}
              ref={frameRef}
              title={`${title} 预览`}
              src={previewUrl ?? undefined}
              srcDoc={previewUrl ? undefined : document_}
              sandbox="allow-scripts allow-forms allow-modals allow-popups"
              className={cn("h-full w-full border-0 bg-white", busy && "pointer-events-none")}
              tabIndex={busy ? -1 : 0}
            />
          </div>
        ) : (
          <div className="flex w-full max-w-[340px] flex-col items-center justify-center py-10 text-center">
            <div className="flex h-9 w-9 items-center justify-center rounded-md border border-line bg-paper">
              <Monitor className="h-4 w-4 text-ink-faint" strokeWidth={1.6} />
            </div>
            <p className="mt-3 text-[13px] font-medium text-ink">预览区还是空的</p>
            <p className="mt-1 text-[12.5px] leading-[1.6] text-ink-faint">
              在左侧描述你想要的应用，确认计划后即可在这里直接操作成品。
            </p>
          </div>
        )}
      </div>

      <footer className="flex h-9 shrink-0 items-center gap-2 border-t border-line px-3">
        {busy ? (
          <>
            <Loader2 className="h-3 w-3 animate-spin text-brand" />
            <span className="text-[11.5px] text-ink-soft">{stageLabel}</span>
          </>
        ) : (
          <span className="text-[11.5px] text-ink-faint">
            {html ? (previewUrl ? '沙箱隔离运行 · 交互可用' : '本地预览 · 沙箱未启动') : '等待生成产物'}
          </span>
        )}
        {html && (
          <span className="mono ml-auto text-[10.5px] text-ink-faint">
            {Math.round(new TextEncoder().encode(document_).length / 1024)} KB
          </span>
        )}
      </footer>
    </section>
  );
}
