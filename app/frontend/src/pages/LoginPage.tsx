import { FormEvent, useState } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import { authApi } from '@/lib/auth';

type Mode = 'login' | 'register';

function safeRedirect(from: string | null): string {
  if (from && from.startsWith('/') && !from.startsWith('//')) return from;
  return '/';
}

export default function LoginPage() {
  const navigate = useNavigate();
  const location = useLocation();
  const [mode, setMode] = useState<Mode>('login');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [name, setName] = useState('');
  const [error, setError] = useState('');
  const [pending, setPending] = useState(false);

  const from = new URLSearchParams(location.search).get('from');

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError('');
    setPending(true);
    try {
      if (mode === 'register') {
        await authApi.register(email.trim(), password, name.trim());
      } else {
        await authApi.login(email.trim(), password);
      }
      navigate(safeRedirect(from), { replace: true });
    } catch (err) {
      setError(err instanceof Error ? err.message : '操作失败，请稍后重试。');
    } finally {
      setPending(false);
    }
  }

  return (
    <main className="min-h-screen bg-background text-foreground flex items-center justify-center px-6">
      <div className="w-full max-w-sm rounded-lg border border-border bg-card p-8 shadow-sm">
        <p className="font-mono text-xs uppercase tracking-widest text-muted-foreground">
          Atoms Studio
        </p>
        <h1 className="mt-3 text-2xl font-semibold">
          {mode === 'login' ? '登录工作台' : '创建账号'}
        </h1>
        <p className="mt-2 text-sm text-muted-foreground">
          {mode === 'login'
            ? '使用邮箱和密码登录，查看属于你的项目。'
            : '注册后即可创建项目并保存历史版本。'}
        </p>

        <form className="mt-6 space-y-4" onSubmit={handleSubmit}>
          {mode === 'register' && (
            <label className="block text-sm">
              <span className="text-muted-foreground">昵称（可选）</span>
              <input
                className="mt-1 w-full rounded-md border border-input bg-background px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-ring"
                value={name}
                onChange={(event) => setName(event.target.value)}
                autoComplete="nickname"
              />
            </label>
          )}
          <label className="block text-sm">
            <span className="text-muted-foreground">邮箱</span>
            <input
              className="mt-1 w-full rounded-md border border-input bg-background px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-ring"
              type="email"
              required
              value={email}
              onChange={(event) => setEmail(event.target.value)}
              autoComplete="email"
            />
          </label>
          <label className="block text-sm">
            <span className="text-muted-foreground">密码</span>
            <input
              className="mt-1 w-full rounded-md border border-input bg-background px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-ring"
              type="password"
              required
              minLength={8}
              value={password}
              onChange={(event) => setPassword(event.target.value)}
              autoComplete={mode === 'login' ? 'current-password' : 'new-password'}
            />
          </label>

          {error && <p className="text-sm text-destructive">{error}</p>}

          <button
            type="submit"
            disabled={pending}
            className="w-full rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground disabled:opacity-60"
          >
            {pending ? '请稍候…' : mode === 'login' ? '登录' : '注册并登录'}
          </button>
        </form>

        <button
          type="button"
          className="mt-6 text-sm text-muted-foreground underline-offset-4 hover:underline"
          onClick={() => {
            setMode(mode === 'login' ? 'register' : 'login');
            setError('');
          }}
        >
          {mode === 'login' ? '还没有账号？注册' : '已有账号？登录'}
        </button>
      </div>
    </main>
  );
}
