import { useEffect, useState } from 'react';
import { describeError } from '@/lib/studio';
import { aiUsageApi, type AiUsage, type ProviderUsage, type UsageTotals, type UsageWindow } from '@/lib/ai-usage';

const numberFormat = new Intl.NumberFormat('zh-CN');

const providerLabel = (provider: string) => {
  if (provider === 'mock') return '模拟输出';
  if (provider === 'unknown') return '未标注';
  return provider;
};

/** 有调用但供应商未返回 usage 时，明确说“未统计”，不显示 0。 */
export function describeTotals(totals: UsageTotals): string {
  if (!totals.has_data) return '暂无数据';
  if (totals.total_tokens == null) return `调用 ${totals.calls} 次 · token 未统计`;
  return `${numberFormat.format(totals.total_tokens)} tokens · ${totals.calls} 次调用`;
}

function UsageCard({ label, window }: { label: string; window: UsageWindow }) {
  return (
    <div className="rounded-md border border-line bg-canvas px-3 py-2.5" data-testid={`usage-${label}`}>
      <p className="mono text-[10.5px] uppercase tracking-[0.09em] text-ink-faint">{label}</p>
      <p className="mt-1 text-[14px] font-medium text-ink">{describeTotals(window.totals)}</p>
      {window.totals.total_tokens != null && (
        <p className="mono mt-0.5 text-[11px] text-ink-faint">
          输入 {window.totals.prompt_tokens ?? '—'} · 输出 {window.totals.completion_tokens ?? '—'}
          {window.totals.reasoning_tokens != null ? ` · 思考 ${window.totals.reasoning_tokens}` : ''}
        </p>
      )}
    </div>
  );
}

function ProviderRows({ providers }: { providers: ProviderUsage[] }) {
  if (!providers.length) {
    return <p className="text-[12px] text-ink-faint">暂无数据</p>;
  }
  return (
    <ul className="space-y-1.5">
      {providers.map(provider => (
        <li key={provider.provider} className="flex items-center justify-between gap-3 text-[12.5px]">
          <span className="text-ink-soft">{providerLabel(provider.provider)}</span>
          <span className="mono text-ink">
            {provider.total_tokens == null ? 'token 未统计' : `${numberFormat.format(provider.total_tokens)} tokens`}
            <span className="ml-2 text-ink-faint">{provider.calls} 次</span>
          </span>
        </li>
      ))}
    </ul>
  );
}

/** 设置页「AI 用量」区块：今日 / 近 7 天 / 累计 + provider 分布 + 最近一次构建。 */
export function AiUsagePanel() {
  const [usage, setUsage] = useState<AiUsage | null>(null);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    aiUsageApi
      .get()
      .then(data => {
        if (!cancelled) setUsage(data);
      })
      .catch(err => {
        if (!cancelled) setError(describeError(err));
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  return (
    <section className="rounded-[10px] border border-line bg-paper" aria-label="AI 用量">
      <div className="flex items-center justify-between border-b border-line bg-canvas px-4 py-2.5">
        <span className="mono text-[10.5px] uppercase tracking-[0.09em] text-ink-faint">AI 用量</span>
        <span className="mono text-[10.5px] text-ink-faint">仅本人可见</span>
      </div>

      <div className="space-y-4 px-4 py-4">
        {loading && <p className="text-[12.5px] text-ink-faint">正在读取用量…</p>}
        {error && (
          <p className="rounded-md border border-err/30 bg-err/5 px-3 py-2 text-[12.5px] text-err" role="alert">
            {error}
          </p>
        )}
        {usage && (
          <>
            <div className="grid gap-2 sm:grid-cols-3">
              <UsageCard label="今日" window={usage.today} />
              <UsageCard label="近 7 天" window={usage.last_7_days} />
              <UsageCard label="累计" window={usage.total} />
            </div>

            <div>
              <p className="text-[12px] font-medium text-ink">近 7 天 provider 分布</p>
              <div className="mt-1.5">
                <ProviderRows providers={usage.last_7_days.providers} />
              </div>
            </div>

            <div>
              <p className="text-[12px] font-medium text-ink">最近一次构建用量</p>
              {usage.latest_build ? (
                <div className="mt-1.5 rounded-md border border-line bg-canvas px-3 py-2 text-[12.5px] text-ink-soft">
                  <p>
                    构建 <span className="mono text-ink">{usage.latest_build.build_id.slice(0, 8)}</span>
                    <span className="ml-2 text-ink-faint">{describeTotals(usage.latest_build.totals)}</span>
                  </p>
                  <div className="mt-1.5">
                    <ProviderRows providers={usage.latest_build.providers} />
                  </div>
                </div>
              ) : (
                <p className="mt-1.5 text-[12px] text-ink-faint">暂无数据</p>
              )}
            </div>

            <p className="text-[11.5px] leading-[1.6] text-ink-faint">
              产品内统计累计应用真实调用返回的 token；供应商侧免费额度余量是另一本台账
              （docs/AI额度使用记录.md），两者口径不同，数字不一致属正常。
            </p>
          </>
        )}
      </div>
    </section>
  );
}
