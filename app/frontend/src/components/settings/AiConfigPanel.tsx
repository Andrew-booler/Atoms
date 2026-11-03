import { FormEvent, useEffect, useState } from 'react';
import { describeError } from '@/lib/studio';
import {
  AiConfigInput,
  AiConfigStatus,
  AiTestResult,
  userAiApi,
} from '@/lib/user-ai';

const inputClass =
  'mt-1 w-full rounded-md border border-line bg-canvas px-3 py-2 text-[13px] text-ink outline-none transition-colors focus:border-brand';

/** 设置页「AI 接入」区块：配置自选 base_url / key / model，并测试连通性。 */
export function AiConfigPanel() {
  const [status, setStatus] = useState<AiConfigStatus>({ configured: false });
  const [form, setForm] = useState<AiConfigInput>({ base_url: '', api_key: '', model: '' });
  const [notice, setNotice] = useState('');
  const [error, setError] = useState('');
  const [testResult, setTestResult] = useState<AiTestResult | null>(null);
  const [pending, setPending] = useState<'save' | 'test' | 'clear' | 'load' | null>('load');

  useEffect(() => {
    let cancelled = false;
    userAiApi
      .get()
      .then((data) => {
        if (cancelled) return;
        setStatus(data);
        setForm((prev) => ({
          base_url: data.base_url ?? prev.base_url,
          api_key: '',
          model: data.model ?? prev.model,
        }));
      })
      .catch((err) => {
        if (!cancelled) setError(describeError(err));
      })
      .finally(() => {
        if (!cancelled) setPending(null);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const update = (key: keyof AiConfigInput, value: string) =>
    setForm((prev) => ({ ...prev, [key]: value }));

  async function handleSave(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError('');
    setNotice('');
    setTestResult(null);
    setPending('save');
    try {
      const saved = await userAiApi.save({
        base_url: form.base_url.trim(),
        api_key: form.api_key.trim(),
        model: form.model.trim(),
      });
      setStatus(saved);
      setForm((prev) => ({ ...prev, api_key: '' }));
      setNotice(saved.message || '已启用自选接入。');
    } catch (err) {
      setError(describeError(err));
    } finally {
      setPending(null);
    }
  }

  async function handleTest() {
    setError('');
    setNotice('');
    setPending('test');
    try {
      const draft =
        form.api_key.trim() && form.base_url.trim() && form.model.trim()
          ? {
              base_url: form.base_url.trim(),
              api_key: form.api_key.trim(),
              model: form.model.trim(),
            }
          : undefined;
      setTestResult(await userAiApi.test(draft));
    } catch (err) {
      setError(describeError(err));
    } finally {
      setPending(null);
    }
  }

  async function handleClear() {
    setError('');
    setNotice('');
    setTestResult(null);
    setPending('clear');
    try {
      const result = await userAiApi.remove();
      setStatus({ configured: false });
      setNotice(result.message);
    } catch (err) {
      setError(describeError(err));
    } finally {
      setPending(null);
    }
  }

  const busy = pending !== null;

  return (
    <section className="rounded-[10px] border border-line bg-paper" aria-label="AI 接入">
      <div className="flex items-center justify-between border-b border-line bg-canvas px-4 py-2.5">
        <span className="mono text-[10.5px] uppercase tracking-[0.09em] text-ink-faint">
          AI 接入
        </span>
        {status.configured ? (
          <span
            className="rounded-[3px] border border-brand/40 bg-brand-soft px-1.5 py-0.5 text-[10.5px] font-medium text-brand-ink"
            data-testid="ai-config-enabled"
          >
            已启用自选接入
          </span>
        ) : (
          <span className="mono text-[10.5px] text-ink-faint">使用系统默认供应商</span>
        )}
      </div>

      <form className="space-y-3 px-4 py-4" onSubmit={handleSave}>
        <p className="text-[12.5px] leading-[1.6] text-ink-soft">
          配置你自己的 OpenAI 兼容服务。保存后所有生成调用优先走此配置，失败时自动回退系统默认供应商。
        </p>

        {!status.configured && (
          <div className="rounded-md border border-line bg-canvas px-3 py-2 text-[12px] text-ink-faint">
            当前未配置自选接入。
          </div>
        )}

        {status.configured && (
          <div className="rounded-md border border-line bg-canvas px-3 py-2 text-[12px] text-ink-soft">
            当前密钥：<span className="mono text-ink">{status.api_key_masked || '****'}</span>
            <span className="ml-2 text-ink-faint">（密钥仅保存时可见，之后一律掩码）</span>
          </div>
        )}

        <label className="block text-[12.5px] text-ink-soft">
          Base URL
          <input
            className={inputClass}
            value={form.base_url}
            onChange={(event) => update('base_url', event.target.value)}
            placeholder="https://api.example.com/v1"
            required
            aria-label="Base URL"
          />
        </label>

        <label className="block text-[12.5px] text-ink-soft">
          API Key
          <input
            className={inputClass}
            value={form.api_key}
            onChange={(event) => update('api_key', event.target.value)}
            placeholder="sk-..."
            required={!status.configured}
            autoComplete="off"
            type="password"
            aria-label="API Key"
          />
          {status.configured && (
            <span className="mt-1 block text-[11.5px] text-ink-faint">
              留空则沿用当前密钥；填写则覆盖。
            </span>
          )}
        </label>

        <label className="block text-[12.5px] text-ink-soft">
          模型名称
          <input
            className={inputClass}
            value={form.model}
            onChange={(event) => update('model', event.target.value)}
            placeholder="qwen3.8-flash"
            required
            aria-label="模型名称"
          />
        </label>

        {notice && (
          <p className="rounded-md border border-brand/30 bg-brand-soft px-3 py-2 text-[12.5px] text-brand-ink" role="status">
            {notice}
          </p>
        )}
        {error && (
          <p className="rounded-md border border-err/30 bg-err/5 px-3 py-2 text-[12.5px] text-err" role="alert">
            {error}
          </p>
        )}
        {testResult && (
          <p
            className={
              testResult.ok
                ? 'rounded-md border border-brand/30 bg-brand-soft px-3 py-2 text-[12.5px] text-brand-ink'
                : 'rounded-md border border-err/30 bg-err/5 px-3 py-2 text-[12.5px] text-err'
            }
            role="status"
          >
            {testResult.message}
            {testResult.latency_ms != null && testResult.ok
              ? `（耗时 ${testResult.latency_ms} ms）`
              : ''}
          </p>
        )}

        <div className="flex flex-wrap items-center gap-2 pt-1">
          <button
            type="submit"
            disabled={busy}
            className="inline-flex h-8 items-center rounded-md bg-brand px-3 text-[12.5px] font-medium text-white transition-opacity disabled:opacity-60"
          >
            {pending === 'save' ? '保存中…' : '保存并启用'}
          </button>
          <button
            type="button"
            disabled={busy}
            onClick={handleTest}
            className="inline-flex h-8 items-center rounded-md border border-line-strong bg-transparent px-3 text-[12.5px] font-medium text-ink transition-colors hover:border-ink-faint disabled:opacity-60"
          >
            {pending === 'test' ? '测试中…' : '测试连通性'}
          </button>
          {status.configured && (
            <button
              type="button"
              disabled={busy}
              onClick={handleClear}
              className="inline-flex h-8 items-center rounded-md px-3 text-[12.5px] font-medium text-err transition-colors hover:bg-err/5 disabled:opacity-60"
            >
              {pending === 'clear' ? '清除中…' : '清除自选接入'}
            </button>
          )}
        </div>
      </form>
    </section>
  );
}
