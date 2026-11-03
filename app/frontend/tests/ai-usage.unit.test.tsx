import { render, screen } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { AiUsagePanel } from '../src/components/settings/AiUsagePanel';
import { aiUsageApi, type AiUsage } from '../src/lib/ai-usage';

vi.mock('../src/lib/ai-usage', () => ({
  aiUsageApi: { get: vi.fn() },
}));

vi.mock('../src/lib/studio', () => ({
  describeError: (error: unknown) =>
    (error as { message?: string })?.message || '请求失败，请重试',
}));

const api = vi.mocked(aiUsageApi);

const emptyTotals = {
  calls: 0,
  prompt_tokens: null,
  completion_tokens: null,
  reasoning_tokens: null,
  total_tokens: null,
  has_data: false,
};

function usageFixture(): AiUsage {
  return {
    today: {
      totals: {
        calls: 2,
        prompt_tokens: 30,
        completion_tokens: 70,
        reasoning_tokens: 5,
        total_tokens: 100,
        has_data: true,
      },
      providers: [
        {
          provider: 'openai',
          calls: 2,
          prompt_tokens: 30,
          completion_tokens: 70,
          reasoning_tokens: 5,
          total_tokens: 100,
          has_data: true,
        },
      ],
    },
    last_7_days: {
      totals: {
        calls: 3,
        prompt_tokens: 40,
        completion_tokens: 90,
        reasoning_tokens: null,
        total_tokens: 130,
        has_data: true,
      },
      providers: [
        {
          provider: 'openai',
          calls: 2,
          prompt_tokens: 30,
          completion_tokens: 70,
          reasoning_tokens: null,
          total_tokens: 100,
          has_data: true,
        },
        { ...emptyTotals, provider: 'mock', calls: 1, has_data: true },
      ],
    },
    total: {
      totals: {
        calls: 5,
        prompt_tokens: 60,
        completion_tokens: 140,
        reasoning_tokens: null,
        total_tokens: 200,
        has_data: true,
      },
      providers: [],
    },
    latest_build: {
      build_id: 'build-1234567890',
      recorded_at: '2026-11-04T05:00:00+08:00',
      totals: {
        calls: 1,
        prompt_tokens: 10,
        completion_tokens: 20,
        reasoning_tokens: null,
        total_tokens: 30,
        has_data: true,
      },
      providers: [
        {
          provider: 'aliyun',
          calls: 1,
          prompt_tokens: 10,
          completion_tokens: 20,
          reasoning_tokens: null,
          total_tokens: 30,
          has_data: true,
        },
      ],
    },
    generated_at: '2026-11-04T05:00:00+08:00',
  };
}

describe('AiUsagePanel', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('无数据显示暂无数据而不是 0', async () => {
    api.get.mockResolvedValue({
      today: { totals: emptyTotals, providers: [] },
      last_7_days: { totals: emptyTotals, providers: [] },
      total: { totals: emptyTotals, providers: [] },
      latest_build: null,
      generated_at: '2026-11-04T05:00:00+08:00',
    });

    render(<AiUsagePanel />);
    expect(await screen.findAllByText('暂无数据')).not.toHaveLength(0);
    expect(screen.getAllByText('暂无数据').length).toBeGreaterThanOrEqual(4);
    expect(screen.queryByText('0 tokens · 0 次调用')).toBeNull();
  });

  it('展示今日/7 天/累计与 provider 分布和最近构建用量', async () => {
    api.get.mockResolvedValue(usageFixture());

    render(<AiUsagePanel />);
    expect(await screen.findByText('100 tokens · 2 次调用')).toBeInTheDocument();
    expect(screen.getByText('130 tokens · 3 次调用')).toBeInTheDocument();
    expect(screen.getByText('200 tokens · 5 次调用')).toBeInTheDocument();
    expect(screen.getByText('模拟输出')).toBeInTheDocument();
    expect(screen.getByText('aliyun')).toBeInTheDocument();
    expect(screen.getByText('build-12')).toBeInTheDocument();
    expect(screen.getByText('30 tokens · 1 次调用')).toBeInTheDocument();
    expect(screen.getByText(/docs\/AI额度使用记录\.md/)).toBeInTheDocument();
  });

  it('有调用但 token 未统计时明确提示', async () => {
    const usage = usageFixture();
    usage.today = {
      totals: { ...emptyTotals, calls: 1, has_data: true },
      providers: [],
    };
    api.get.mockResolvedValue(usage);

    render(<AiUsagePanel />);
    expect(await screen.findByText('调用 1 次 · token 未统计')).toBeInTheDocument();
  });

  it('读取失败时展示后端 message', async () => {
    api.get.mockRejectedValue(new Error('登录已过期，请重新登录'));

    render(<AiUsagePanel />);
    expect(await screen.findByRole('alert')).toHaveTextContent('登录已过期，请重新登录');
  });
});
