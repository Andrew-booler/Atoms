import { ChevronDown, ChevronRight, TerminalSquare } from 'lucide-react';
import { useEffect, useRef, useState } from 'react';
import type { BuildEvent } from '@/lib/build-stream';
import { cn } from '@/lib/utils';

const STAGE_LABEL: Record<string, string> = {
  plan: '计划',
  outline: '结构',
  artifact: '页面',
};

const stageName = (stage?: string | null) => (stage ? STAGE_LABEL[stage] ?? stage : '构建');

const formatBytes = (value: unknown): string => {
  const bytes = typeof value === 'number' && Number.isFinite(value) ? value : null;
  if (bytes == null) return '';
  if (bytes < 1024) return `${bytes} B`;
  return `${(bytes / 1024).toFixed(1)} KB`;
};

const formatDuration = (value: unknown): string => {
  const ms = typeof value === 'number' && Number.isFinite(value) ? value : null;
  return ms == null ? '' : `${ms} ms`;
};

const formatUsage = (value: unknown): string => {
  if (!value || typeof value !== 'object') return 'token 用量未统计（模拟输出）';
  const total = (value as { total_tokens?: unknown }).total_tokens;
  return typeof total === 'number' ? `token ${total}` : 'token 用量未统计（模拟输出）';
};

function EventRow({ event }: { event: BuildEvent }) {
  const data = event.data ?? {};
  const stage = stageName(event.stage);
  const duration = formatDuration(data.duration_ms);

  switch (event.type) {
    case 'stage_started':
      return <p>▸ {stage}：{event.message}</p>;
    case 'stage_finished':
      return (
        <p>
          ✓ {stage}：{event.message}
          {duration ? ` · ${duration}` : ''} · {formatUsage(data.usage)}
        </p>
      );
    case 'file_created': {
      const name = typeof data.name === 'string' ? data.name : '产物';
      const size = formatBytes(data.bytes);
      return <p>＋ {name}{size ? ` · ${size}` : ''}</p>;
    }
    case 'log': {
      const files = Array.isArray(data.files) ? data.files : [];
      return (
        <div>
          <p>· {event.message}</p>
          {typeof data.preview_url === 'string' && data.preview_url && (
            <p className="pl-3 text-[#9BE0B0]">预览 {data.preview_url}</p>
          )}
          {typeof data.port === 'number' && <p className="pl-3 text-[#A9A196]">端口 {data.port}</p>}
          {files.length > 0 && (
            <p className="pl-3 text-[#A9A196]">
              工作区 {files.map(file => {
                const item = file as { name?: unknown; bytes?: unknown };
                return `${typeof item.name === 'string' ? item.name : '文件'} ${formatBytes(item.bytes)}`.trim();
              }).join('，')}
            </p>
          )}
        </div>
      );
    }
    case 'error': {
      const code = typeof data.code === 'string' ? data.code : undefined;
      return (
        <p className="text-red-400">
          ✕ {event.message}{code ? `（${code}）` : ''}
        </p>
      );
    }
    case 'done':
      return <p className="text-[#9BE0B0]">● {event.message}</p>;
    default:
      return <p>· {event.message}</p>;
  }
}

interface BuildTerminalProps {
  events: BuildEvent[];
  running: boolean;
  error?: string | null;
  defaultOpen?: boolean;
}

/** 可折叠构建终端：实时追加事件，错误红色展示可读中文，完成后保留日志可回看。 */
export function BuildTerminal({ events, running, error, defaultOpen = false }: BuildTerminalProps) {
  const [open, setOpen] = useState(defaultOpen || running);
  const logRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (running) setOpen(true);
  }, [running]);

  useEffect(() => {
    if (!open) return;
    const node = logRef.current;
    if (node) node.scrollTop = node.scrollHeight;
  }, [events.length, open]);

  const status = running ? '构建中…' : error ? '构建失败' : events.length ? '已完成' : '暂无记录';

  return (
    <section aria-label="构建终端" className="shrink-0 border-t border-line bg-paper">
      <button
        type="button"
        onClick={() => setOpen(value => !value)}
        aria-expanded={open}
        aria-controls="build-terminal-log"
        className="flex w-full items-center gap-2 px-4 py-2 text-left"
      >
        <TerminalSquare size={14} className="text-ink-soft" />
        <span className="text-[12.5px] font-medium text-ink">构建终端</span>
        <span
          className={cn(
            'mono text-[10.5px]',
            running ? 'text-brand-ink' : error ? 'text-red-600' : 'text-ink-faint'
          )}
        >
          {status}
        </span>
        <span className="mono ml-auto text-[10.5px] text-ink-faint">{events.length} 条</span>
        {open ? <ChevronDown size={14} className="text-ink-faint" /> : <ChevronRight size={14} className="text-ink-faint" />}
      </button>
      {open && (
        <div
          id="build-terminal-log"
          ref={logRef}
          role="log"
          aria-live="polite"
          className="studio-scroll max-h-56 overflow-y-auto border-t border-line bg-[#1F1D1A] px-3 py-2"
        >
          {events.length === 0 ? (
            <p className="mono text-[11px] leading-5 text-[#A9A196]">尚无构建事件。提交需求后这里会实时显示进度。</p>
          ) : (
            <div className="mono space-y-1 text-[11px] leading-5 text-[#E8E2D9]">
              {events.map(event => (
                <EventRow key={event.seq} event={event} />
              ))}
            </div>
          )}
        </div>
      )}
    </section>
  );
}
