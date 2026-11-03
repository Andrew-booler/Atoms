import { client } from './api';

/** token 字段为 null 表示供应商/模拟输出未返回用量，不是 0。 */
export interface UsageTotals {
  calls: number;
  prompt_tokens: number | null;
  completion_tokens: number | null;
  reasoning_tokens: number | null;
  total_tokens: number | null;
  has_data: boolean;
}

export interface ProviderUsage extends UsageTotals {
  provider: string;
}

export interface UsageWindow {
  totals: UsageTotals;
  providers: ProviderUsage[];
}

export interface BuildUsage {
  build_id: string;
  recorded_at: string | null;
  totals: UsageTotals;
  providers: ProviderUsage[];
}

export interface AiUsage {
  today: UsageWindow;
  last_7_days: UsageWindow;
  total: UsageWindow;
  latest_build: BuildUsage | null;
  generated_at: string;
}

export const aiUsageApi = {
  async get(): Promise<AiUsage> {
    const res = await client.apiCall.invoke({
      url: '/api/v1/user/ai-usage',
      method: 'GET',
      data: {},
    });
    return res.data as AiUsage;
  },
};
