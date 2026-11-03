import { client } from './api';

/** 用户自选 AI 接入状态：密钥始终以掩码返回。 */
export interface AiConfigStatus {
  configured: boolean;
  base_url?: string | null;
  model?: string | null;
  api_key_masked?: string | null;
  updated_at?: string | null;
  message?: string | null;
}

export interface AiConfigInput {
  base_url: string;
  api_key: string;
  model: string;
}

export interface AiConfigDeleteResult {
  deleted: boolean;
  message: string;
}

export interface AiTestResult {
  ok: boolean;
  message: string;
  status_code?: number | null;
  latency_ms?: number | null;
}

export const userAiApi = {
  async get(): Promise<AiConfigStatus> {
    const res = await client.apiCall.invoke({
      url: '/api/v1/user/ai-config',
      method: 'GET',
      data: {},
    });
    return res.data as AiConfigStatus;
  },

  async save(input: AiConfigInput): Promise<AiConfigStatus> {
    const res = await client.apiCall.invoke({
      url: '/api/v1/user/ai-config',
      method: 'PUT',
      data: input,
    });
    return res.data as AiConfigStatus;
  },

  async remove(): Promise<AiConfigDeleteResult> {
    const res = await client.apiCall.invoke({
      url: '/api/v1/user/ai-config',
      method: 'DELETE',
      data: {},
    });
    return res.data as AiConfigDeleteResult;
  },

  async test(draft?: AiConfigInput): Promise<AiTestResult> {
    const res = await client.apiCall.invoke({
      url: '/api/v1/user/ai-config/test',
      method: 'POST',
      data: draft ?? {},
    });
    return res.data as AiTestResult;
  },
};
