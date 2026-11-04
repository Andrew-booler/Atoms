import { act, render, renderHook, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import type { BuildEvent } from '../src/lib/build-stream';
import { BuildTerminal } from '../src/components/studio/BuildTerminal';
import { useBuildTerminal } from '../src/hooks/useBuildTerminal';
import { parseSSEFrame, parseSSEText, STREAM_INTERRUPTED_MESSAGE, streamBuildEvents } from '../src/lib/build-stream';

vi.mock('../src/lib/build-stream', async importOriginal => {
  const actual = await importOriginal<typeof import('../src/lib/build-stream')>();
  return { ...actual, streamBuildEvents: vi.fn() };
});

const realStreamBuildEvents = async () =>
  (
    await vi.importActual<typeof import('../src/lib/build-stream')>('../src/lib/build-stream')
  ).streamBuildEvents;

vi.mock('../src/lib/studio', async importOriginal => {
  const actual = await importOriginal<typeof import('../src/lib/studio')>();
  return {
    ...actual,
    studioApi: { ...actual.studioApi, startBuild: vi.fn(), latestBuild: vi.fn() },
  };
});

import { studioApi } from '../src/lib/studio';

const events: BuildEvent[] = [
  { seq: 1, type: 'stage_started', stage: 'plan', message: '开始生成计划', data: {} },
  {
    seq: 2,
    type: 'stage_finished',
    stage: 'plan',
    message: '计划已生成',
    data: { duration_ms: 120, usage: { total_tokens: 320 } },
  },
  { seq: 3, type: 'file_created', message: '已写入 index.html（2048 字节）', data: { name: 'index.html', bytes: 2048 } },
  {
    seq: 4,
    type: 'log',
    message: '沙箱预览已启动',
    data: { preview_url: 'http://127.0.0.1:49152/', port: 49152, files: [{ name: 'index.html', bytes: 2048 }] },
  },
  { seq: 5, type: 'done', message: '构建完成', data: {} },
];

describe('BuildTerminal', () => {
  it('默认折叠，点击后展示结构化日志', async () => {
    render(<BuildTerminal events={events} running={false} />);
    expect(screen.queryByText('开始生成计划', { exact: false })).not.toBeInTheDocument();

    await userEvent.click(screen.getByRole('button', { name: /构建终端/ }));

    expect(screen.getByText(/开始生成计划/)).toBeInTheDocument();
    expect(screen.getByText(/120 ms/)).toBeInTheDocument();
    expect(screen.getByText(/token 320/)).toBeInTheDocument();
    expect(screen.getByText(/index\.html · 2\.0 KB/)).toBeInTheDocument();
    expect(screen.getByText(/预览 http:\/\/127\.0\.0\.1:49152/)).toBeInTheDocument();
    expect(screen.getByText(/构建完成/)).toBeInTheDocument();
  });

  it('构建中自动展开并显示状态，完成后日志仍可回看', async () => {
    const { rerender } = render(<BuildTerminal events={[]} running />);
    expect(screen.getByText('构建中…')).toBeInTheDocument();
    expect(screen.getByText(/尚无构建事件/)).toBeInTheDocument();

    rerender(<BuildTerminal events={events} running={false} />);
    expect(screen.getByText('已完成')).toBeInTheDocument();
    expect(screen.getByText(/构建完成/)).toBeInTheDocument();

    await userEvent.click(screen.getByRole('button', { name: /构建终端/ }));
    expect(screen.queryByText(/构建完成/)).not.toBeInTheDocument();
    await userEvent.click(screen.getByRole('button', { name: /构建终端/ }));
    expect(screen.getByText(/构建完成/)).toBeInTheDocument();
  });

  it('错误事件红色展示可读中文而非仅错误码', async () => {
    render(
      <BuildTerminal
        events={[
          { seq: 1, type: 'error', stage: 'artifact', message: '生成的页面内容无效，请重新生成。', data: { code: 'STUDIO_ARTIFACT_INVALID' } },
        ]}
        running={false}
        error="生成的页面内容无效，请重新生成。"
      />
    );
    await userEvent.click(screen.getByRole('button', { name: /构建终端/ }));

    const line = screen.getByText(/生成的页面内容无效，请重新生成。/);
    expect(line.className).toContain('text-red-400');
    expect(screen.getByText('构建失败')).toBeInTheDocument();
  });

  it('连接中断时构建终端显示中文提示并标记失败', async () => {
    render(<BuildTerminal events={[]} running={false} error={STREAM_INTERRUPTED_MESSAGE} />);

    expect(screen.getByText('构建失败')).toBeInTheDocument();
    await userEvent.click(screen.getByRole('button', { name: /构建终端/ }));
    expect(screen.getByText(new RegExp(STREAM_INTERRUPTED_MESSAGE))).toBeInTheDocument();
    expect(screen.queryByText(/Network Error/)).not.toBeInTheDocument();
  });
});

describe('SSE 解析', () => {
  it('按空行切帧并忽略心跳注释', () => {
    const text =
      'id: 1\nevent: log\ndata: {"seq":1,"type":"log","message":"就绪","data":{}}\n\n' +
      ': keep-alive\n\n' +
      'id: 2\nevent: done\ndata: {"seq":2,"type":"done","message":"完成","data":{}}\n\n';
    const parsed = parseSSEText(text);
    expect(parsed.map(item => item.type)).toEqual(['log', 'done']);
    expect(parsed[0].message).toBe('就绪');
  });

  it('坏 JSON 与无 data 的帧返回 null', () => {
    expect(parseSSEFrame(': keep-alive')).toBeNull();
    expect(parseSSEFrame('data: not-json')).toBeNull();
  });
});

describe('streamBuildEvents（fetch 事件流）', () => {
  beforeEach(() => {
    vi.unstubAllGlobals();
  });

  it('解析事件并在 done 后停止', async () => {
    const body = new ReadableStream<Uint8Array>({
      start(controller) {
        controller.enqueue(
          new TextEncoder().encode(
            'event: stage_started\ndata: {"seq":1,"type":"stage_started","stage":"plan","message":"开始","data":{}}\n\n' +
              'event: done\ndata: {"seq":2,"type":"done","message":"完成","data":{}}\n\n'
          )
        );
        controller.close();
      },
    });
    vi.stubGlobal(
      'fetch',
      vi.fn(async () => new Response(body, { status: 200, headers: { 'Content-Type': 'text/event-stream' } }))
    );
    const onEvent = vi.fn();
    const stream = await realStreamBuildEvents();
    await stream(1, 'b1', { onEvent });

    expect(onEvent).toHaveBeenCalledTimes(2);
    expect(onEvent.mock.calls[1][0].type).toBe('done');
  });

  it('401 抛出带中文 message 的 BuildStreamError', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(async () =>
        new Response(JSON.stringify({ code: 'AUTH_REQUIRED', message: '请先登录后再操作。' }), { status: 401 })
      )
    );
    const stream = await realStreamBuildEvents();
    await expect(stream(1, 'b1', { onEvent: vi.fn() })).rejects.toMatchObject({
      name: 'BuildStreamError',
      status: 401,
      message: '请先登录后再操作。',
    });
  });

  it('SSE 提前关闭（未收到 done）提示中文连接中断，而非 Network Error', async () => {
    const body = new ReadableStream<Uint8Array>({
      start(controller) {
        controller.enqueue(
          new TextEncoder().encode(
            'event: stage_started\ndata: {"seq":1,"type":"stage_started","stage":"plan","message":"开始","data":{}}\n\n'
          )
        );
        controller.close();
      },
    });
    vi.stubGlobal(
      'fetch',
      vi.fn(async () => new Response(body, { status: 200, headers: { 'Content-Type': 'text/event-stream' } }))
    );

    const stream = await realStreamBuildEvents();
    const error = (await stream(1, 'b1', { onEvent: vi.fn() }).catch(item => item)) as Error;

    expect(error).toBeInstanceOf(Error);
    expect(error.message).toBe(STREAM_INTERRUPTED_MESSAGE);
    expect(error.message).not.toContain('Network Error');
  });

  it('fetch 抛 TypeError（Network Error）时转为中文连接中断提示', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(async () => {
        throw new TypeError('Network Error');
      })
    );

    const stream = await realStreamBuildEvents();
    const error = (await stream(1, 'b1', { onEvent: vi.fn() }).catch(item => item)) as Error;

    expect(error.message).toBe(STREAM_INTERRUPTED_MESSAGE);
    expect(error.message).not.toContain('Network Error');
  });
});

describe('useBuildTerminal', () => {
  beforeEach(() => {
    vi.mocked(studioApi.startBuild).mockReset();
    vi.mocked(studioApi.latestBuild).mockReset();
    vi.mocked(streamBuildEvents).mockReset();
  });

  it('begin 创建构建会话，watch 追加事件并在 done 后结束', async () => {
    vi.mocked(studioApi.startBuild).mockResolvedValue({ build_id: 'build-1' });
    vi.mocked(streamBuildEvents).mockImplementation(async (_projectId, _buildId, { onEvent }) => {
      onEvent({ seq: 1, type: 'stage_started', stage: 'plan', message: '开始', data: {} });
      onEvent({ seq: 2, type: 'done', message: '完成', data: {} });
    });

    const { result } = renderHook(() => useBuildTerminal());
    let buildId = '';
    await act(async () => {
      buildId = await result.current.begin(1);
    });
    expect(buildId).toBe('build-1');
    expect(result.current.buildId).toBe('build-1');

    act(() => result.current.watch(1, buildId));
    await waitFor(() => expect(result.current.events).toHaveLength(2));
    expect(result.current.running).toBe(false);
    expect(result.current.error).toBeNull();
  });

  it('error 事件保存可读 message 并停止运行', async () => {
    vi.mocked(studioApi.startBuild).mockResolvedValue({ build_id: 'build-2' });
    vi.mocked(streamBuildEvents).mockImplementation(async (_projectId, _buildId, { onEvent }) => {
      onEvent({ seq: 1, type: 'error', stage: 'artifact', message: '生成的页面内容无效，请重新生成。', data: {} });
    });

    const { result } = renderHook(() => useBuildTerminal());
    await act(async () => {
      await result.current.begin(1);
    });
    act(() => result.current.watch(1, 'build-2'));

    await waitFor(() => expect(result.current.error).toBe('生成的页面内容无效，请重新生成。'));
    expect(result.current.running).toBe(false);
  });

  it('连接层失败（network error）显示中文兜底提示并标记失败', async () => {
    vi.mocked(streamBuildEvents).mockRejectedValue(new TypeError('Network Error'));

    const { result } = renderHook(() => useBuildTerminal());
    act(() => result.current.watch(1, 'build-network'));

    await waitFor(() => expect(result.current.error).toBe(STREAM_INTERRUPTED_MESSAGE));
    expect(result.current.error).not.toContain('Network Error');
    expect(result.current.running).toBe(false);
  });

  it('loadLatest 刷新后回看最近一次构建', async () => {
    vi.mocked(studioApi.latestBuild).mockResolvedValue({ build_id: 'build-3', events });

    const { result } = renderHook(() => useBuildTerminal());
    await act(async () => {
      await result.current.loadLatest(1);
    });

    expect(result.current.buildId).toBe('build-3');
    expect(result.current.events).toHaveLength(events.length);
    expect(result.current.error).toBeNull();
  });
});
