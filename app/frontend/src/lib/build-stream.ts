import { getStoredToken } from './auth';
import { getAPIBaseURL } from './config';

/** 后端固定事件类型（见 backend/services/build_events.py）。 */
export const BUILD_EVENT_TYPES = [
  'stage_started',
  'stage_finished',
  'file_created',
  'log',
  'error',
  'done',
] as const;

export type BuildEventType = (typeof BUILD_EVENT_TYPES)[number];

export interface BuildEvent {
  seq: number;
  type: BuildEventType;
  stage?: string | null;
  message?: string | null;
  data: Record<string, unknown>;
  created_at?: string | null;
}

export class BuildStreamError extends Error {
  status?: number;

  constructor(message: string, status?: number) {
    super(message);
    this.name = 'BuildStreamError';
    this.status = status;
  }
}

/** 解析一个 SSE 帧；只取 data 行的 JSON，注释心跳返回 null。 */
export function parseSSEFrame(frame: string): BuildEvent | null {
  const dataLines: string[] = [];
  for (const raw of frame.replace(/\r\n/g, '\n').split('\n')) {
    if (raw.startsWith(':')) continue;
    if (raw.startsWith('data:')) dataLines.push(raw.slice(5).trimStart());
  }
  if (!dataLines.length) return null;
  try {
    const parsed = JSON.parse(dataLines.join('\n')) as BuildEvent;
    return parsed && typeof parsed.seq === 'number' ? parsed : null;
  } catch {
    return null;
  }
}

/** 把一段 SSE 文本切成事件；用于测试与缓冲收尾。 */
export function parseSSEText(text: string): BuildEvent[] {
  return text
    .replace(/\r\n/g, '\n')
    .split('\n\n')
    .map(parseSSEFrame)
    .filter((event): event is BuildEvent => event !== null);
}

interface StreamOptions {
  signal?: AbortSignal;
  onEvent: (event: BuildEvent) => void;
}

/**
 * 订阅构建事件流。
 *
 * 浏览器原生 EventSource 不能带自定义头，因此这里用 fetch + ReadableStream 解析；
 * 后端同时接受 Authorization 头与 ?access_token= 查询参数（文档见 roadmap Phase 10）。
 * 收到 done/error 或流结束时 resolve；HTTP 非 2xx 抛 BuildStreamError。
 */
export async function streamBuildEvents(
  projectId: number,
  buildId: string,
  { signal, onEvent }: StreamOptions
): Promise<void> {
  const token = getStoredToken();
  const response = await fetch(
    `${getAPIBaseURL()}/api/v1/studio/projects/${projectId}/builds/${encodeURIComponent(buildId)}/stream`,
    {
      method: 'GET',
      headers: {
        Accept: 'text/event-stream',
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
      },
      signal,
    }
  );

  if (!response.ok) {
    let message = `构建事件流连接失败（${response.status}）`;
    try {
      const body = (await response.json()) as { message?: string } | null;
      if (body?.message) message = body.message;
    } catch {
      // 非 JSON 响应保持状态码文案
    }
    throw new BuildStreamError(message, response.status);
  }
  if (!response.body) {
    throw new BuildStreamError('当前浏览器不支持构建事件流。');
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = '';

  const consume = (frames: string[]): boolean => {
    for (const frame of frames) {
      const event = parseSSEFrame(frame);
      if (!event) continue;
      onEvent(event);
      if (event.type === 'done' || event.type === 'error') return true;
    }
    return false;
  };

  try {
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      const frames = buffer.split('\n\n');
      buffer = frames.pop() ?? '';
      if (consume(frames)) return;
    }
    if (buffer.trim()) consume([buffer]);
  } finally {
    reader.releaseLock();
  }
}
