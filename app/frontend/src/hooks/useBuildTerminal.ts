import { useCallback, useEffect, useRef, useState } from 'react';
import { describeStreamError, streamBuildEvents, type BuildEvent } from '@/lib/build-stream';
import { studioApi } from '@/lib/studio';

export interface BuildTerminal {
  events: BuildEvent[];
  running: boolean;
  error: string | null;
  buildId: string | null;
  begin: (projectId: number) => Promise<string>;
  watch: (projectId: number, buildId: string) => void;
  loadLatest: (projectId: number) => Promise<void>;
  reset: () => void;
  cancel: () => void;
}

/** 构建终端状态：创建构建会话、订阅 SSE、保留历史事件供刷新回看。 */
export function useBuildTerminal(): BuildTerminal {
  const [events, setEvents] = useState<BuildEvent[]>([]);
  const [running, setRunning] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [buildId, setBuildId] = useState<string | null>(null);
  const abortRef = useRef<AbortController | null>(null);

  const cancel = useCallback(() => {
    abortRef.current?.abort();
    abortRef.current = null;
    setRunning(false);
  }, []);

  const append = useCallback((event: BuildEvent) => {
    setEvents(previous => {
      if (previous.some(item => item.seq === event.seq)) return previous;
      return [...previous, event];
    });
    if (event.type === 'error') {
      setError(event.message || '构建失败，请重试。');
      setRunning(false);
    } else if (event.type === 'done') {
      setError(null);
      setRunning(false);
    }
  }, []);

  const watch = useCallback(
    (projectId: number, id: string) => {
      abortRef.current?.abort();
      const controller = new AbortController();
      abortRef.current = controller;
      setRunning(true);
      void streamBuildEvents(projectId, id, { signal: controller.signal, onEvent: append })
        .catch(failure => {
          if (controller.signal.aborted) return;
          setRunning(false);
          // HTTP 错误展示后端 message；连接层失败统一中文兜底，不抛出 Network Error。
          setError(describeStreamError(failure));
        })
        .finally(() => {
          if (!controller.signal.aborted) setRunning(false);
        });
    },
    [append]
  );

  const begin = useCallback(async (projectId: number) => {
    abortRef.current?.abort();
    abortRef.current = null;
    setRunning(false);
    setError(null);
    const started = await studioApi.startBuild(projectId);
    setEvents([]);
    setBuildId(started.build_id);
    return started.build_id;
  }, []);

  const loadLatest = useCallback(async (projectId: number) => {
    abortRef.current?.abort();
    abortRef.current = null;
    setRunning(false);
    try {
      const latest = await studioApi.latestBuild(projectId);
      setBuildId(latest.build_id ?? null);
      setEvents(latest.events ?? []);
      const lastError = (latest.events ?? []).filter(item => item.type === 'error').pop();
      setError(lastError?.message ?? null);
    } catch {
      setEvents([]);
      setBuildId(null);
      setError(null);
    }
  }, []);

  const reset = useCallback(() => {
    abortRef.current?.abort();
    abortRef.current = null;
    setEvents([]);
    setBuildId(null);
    setError(null);
    setRunning(false);
  }, []);

  useEffect(() => () => abortRef.current?.abort(), []);

  return { events, running, error, buildId, begin, watch, loadLatest, reset, cancel };
}
