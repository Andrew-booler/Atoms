import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { AiConfigPanel } from '../src/components/settings/AiConfigPanel';
import { userAiApi } from '../src/lib/user-ai';

vi.mock('../src/lib/user-ai', () => ({
  userAiApi: {
    get: vi.fn(),
    save: vi.fn(),
    remove: vi.fn(),
    test: vi.fn(),
  },
}));

vi.mock('../src/lib/studio', () => ({
  describeError: (error: unknown) =>
    (error as { message?: string })?.message || '请求失败，请重试',
}));

const api = vi.mocked(userAiApi);

async function fillDraft() {
  await userEvent.type(screen.getByLabelText('Base URL'), 'https://api.example/v1');
  await userEvent.type(screen.getByLabelText('API Key'), 'sk-1234567890abcd');
  await userEvent.type(screen.getByLabelText('模型名称'), 'demo-model');
}

describe('AiConfigPanel', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    api.get.mockResolvedValue({ configured: false });
  });

  it('保存后显示已启用自选接入与掩码密钥', async () => {
    api.save.mockResolvedValue({
      configured: true,
      base_url: 'https://api.example/v1',
      model: 'demo-model',
      api_key_masked: 'sk-****abcd',
      message: '已启用自选接入。',
    });

    render(<AiConfigPanel />);
    await screen.findByText('当前未配置自选接入。');
    await fillDraft();
    await userEvent.click(screen.getByRole('button', { name: '保存并启用' }));

    await waitFor(() =>
      expect(screen.getByTestId('ai-config-enabled')).toHaveTextContent('已启用自选接入')
    );
    expect(screen.getByText('已启用自选接入。')).toBeInTheDocument();
    expect(screen.getByText('sk-****abcd')).toBeInTheDocument();
    expect(api.save).toHaveBeenCalledWith({
      base_url: 'https://api.example/v1',
      api_key: 'sk-1234567890abcd',
      model: 'demo-model',
    });
  });

  it('连通性失败时展示可定位的中文提示', async () => {
    api.test.mockResolvedValue({
      ok: false,
      message: 'API Key 无效或已过期（401），请重新填写。',
      status_code: 401,
    });

    render(<AiConfigPanel />);
    await screen.findByText('当前未配置自选接入。');
    await fillDraft();
    await userEvent.click(screen.getByRole('button', { name: '测试连通性' }));

    expect(
      await screen.findByText('API Key 无效或已过期（401），请重新填写。')
    ).toBeInTheDocument();
    expect(api.test).toHaveBeenCalledWith({
      base_url: 'https://api.example/v1',
      api_key: 'sk-1234567890abcd',
      model: 'demo-model',
    });
  });

  it('清除配置后回退系统默认', async () => {
    api.get.mockResolvedValue({
      configured: true,
      base_url: 'https://api.example/v1',
      model: 'demo-model',
      api_key_masked: 'sk-****abcd',
    });
    api.remove.mockResolvedValue({
      deleted: true,
      message: '已清除自选接入，后续将使用系统默认供应商。',
    });

    render(<AiConfigPanel />);
    await screen.findByText('sk-****abcd');
    await userEvent.click(screen.getByRole('button', { name: '清除自选接入' }));

    await waitFor(() => expect(screen.queryByTestId('ai-config-enabled')).toBeNull());
    expect(screen.getByText('已清除自选接入，后续将使用系统默认供应商。')).toBeInTheDocument();
    expect(screen.getByText('当前未配置自选接入。')).toBeInTheDocument();
  });

  it('保存失败时提示后端 message', async () => {
    api.save.mockRejectedValue(new Error('Base URL 必须以 http:// 或 https:// 开头'));

    render(<AiConfigPanel />);
    await screen.findByText('当前未配置自选接入。');
    await fillDraft();
    await userEvent.click(screen.getByRole('button', { name: '保存并启用' }));

    expect(
      await screen.findByText('Base URL 必须以 http:// 或 https:// 开头')
    ).toBeInTheDocument();
  });
});
