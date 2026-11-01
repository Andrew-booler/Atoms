import { html } from '@codemirror/lang-html';
import CodeMirror from '@uiw/react-codemirror';
import { Save, X } from 'lucide-react';
import { useState } from 'react';

interface ArtifactEditorProps {
  initialHtml: string;
  busy: boolean;
  onSave: (html: string, note: string) => void;
  onCancel: () => void;
}

export function ArtifactEditor({ initialHtml, busy, onSave, onCancel }: ArtifactEditorProps) {
  const [value, setValue] = useState(initialHtml);
  const [note, setNote] = useState('');
  const changed = value !== initialHtml;
  const canSave = value.trim().length > 0 && !busy;

  return (
    <section className="flex h-full min-h-0 flex-col bg-canvas" aria-label="代码编辑器">
      <header className="flex h-14 shrink-0 items-center gap-2 border-b border-line bg-canvas px-3">
        <span className="mono truncate text-[11.5px] text-ink-faint">/edit · 源码编辑</span>
        <input
          value={note}
          onChange={(event) => { if (!busy) setNote(event.target.value); }}
          placeholder="备注（可选）"
          aria-label="编辑备注"
          disabled={busy}
          className="mono ml-2 h-7 min-w-0 flex-1 rounded-md border border-line-strong bg-paper px-2 text-[11px] text-ink-soft outline-none transition-colors focus:border-ink-faint disabled:opacity-50"
        />
        <button
          type="button"
          onClick={onCancel}
          disabled={busy}
          className="inline-flex h-8 shrink-0 items-center gap-1 rounded-md border border-line-strong bg-paper px-2.5 text-[12px] text-ink-soft transition-colors hover:text-ink disabled:opacity-50"
        >
          <X className="h-3.5 w-3.5" strokeWidth={1.9} />
          取消
        </button>
        <button
          type="button"
          onClick={() => onSave(value, note)}
          disabled={!canSave}
          className="inline-flex h-8 shrink-0 items-center gap-1 rounded-md bg-brand px-2.5 text-[12px] font-medium text-white transition-colors hover:bg-[#A93A0A] disabled:cursor-not-allowed disabled:opacity-50"
        >
          <Save className="h-3.5 w-3.5" strokeWidth={1.9} />
          保存并预览
        </button>
      </header>

      <div className="studio-scroll min-h-0 flex-1 overflow-hidden">
        <CodeMirror
          value={value}
          onChange={(val) => setValue(val)}
          height="100%"
          theme="light"
          extensions={[html()]}
          basicSetup={{
            lineNumbers: true,
            foldGutter: true,
            autocompletion: true,
            highlightActiveLine: true,
          }}
        />
      </div>

      <footer className="flex h-9 shrink-0 items-center border-t border-line px-3">
        <span className="mono text-[10.5px] text-ink-faint">
          {changed ? '有未保存修改' : '无改动'} · {Math.round(new TextEncoder().encode(value).length / 1024)} KB
        </span>
      </footer>
    </section>
  );
}