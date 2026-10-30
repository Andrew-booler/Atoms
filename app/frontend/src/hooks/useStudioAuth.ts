import { useCallback, useEffect, useState } from 'react';
import { client } from '@/lib/api';

export type AuthState = 'loading' | 'authenticated' | 'anonymous';

export interface StudioUser {
  id?: string;
  email?: string;
  name?: string;
}

/**
 * 三段式鉴权状态：loading 期间既不当作已登录也不当作未登录，
 * 避免首屏把已登录用户误判为匿名。
 */
export function useStudioAuth() {
  const [state, setState] = useState<AuthState>('loading');
  const [user, setUser] = useState<StudioUser | null>(null);

  useEffect(() => {
    let alive = true;
    client.auth
      .me()
      .then((res) => {
        if (!alive) return;
        if (res?.data) {
          setUser(res.data as StudioUser);
          setState('authenticated');
        } else {
          setState('anonymous');
        }
      })
      .catch(() => {
        if (alive) setState('anonymous');
      });
    return () => {
      alive = false;
    };
  }, []);

  const login = useCallback(() => {
    client.auth.toLogin();
  }, []);

  const logout = useCallback(async () => {
    try {
      await client.auth.logout();
    } finally {
      setUser(null);
      setState('anonymous');
    }
  }, []);

  return { state, user, login, logout };
}
