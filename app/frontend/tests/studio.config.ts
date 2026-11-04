import { defineConfig } from '@playwright/test';
import crypto from 'node:crypto';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const testsDir = path.dirname(fileURLToPath(import.meta.url));
const frontendDir = path.resolve(testsDir, '..');
const backendDir = path.resolve(frontendDir, '../backend');
const python = process.env.ATOMS_BACKEND_PYTHON ?? 'E:\\Dependencies\\Atoms\\backend-venv\\Scripts\\python.exe';
const databaseUrl =
  process.env.DATABASE_URL ?? 'postgresql+asyncpg://postgres:postgres@127.0.0.1:5432/postgres';
const authSecret = process.env.APP_AUTH_SECRET ?? 'test-auth-secret';

/** 生成与后端同一密钥的 HS256 访问令牌，作为全部界面/接口用例的登录前置。 */
function signTestToken(): string {
  const now = Math.floor(Date.now() / 1000);
  const header = Buffer.from(JSON.stringify({ alg: 'HS256', typ: 'JWT' })).toString('base64url');
  const payload = Buffer.from(
    JSON.stringify({ sub: 'studio-test-user', iat: now, nbf: now - 1, exp: now + 3600 }),
  ).toString('base64url');
  const signature = crypto.createHmac('sha256', authSecret).update(`${header}.${payload}`).digest('base64url');
  return `${header}.${payload}.${signature}`;
}

export const testAuthToken = signTestToken();

export default defineConfig({
  tsconfig: '../tsconfig.app.json',
  testDir: '.', testMatch: 'studio.integration.spec.ts', workers: 1, fullyParallel: false,
  timeout: 240000, expect: { timeout: 10000 },
  reporter: [['list'], ['json', { outputFile: path.join(testsDir, 'results.json') }]],
  use: {
    baseURL: 'http://127.0.0.1:3101',
    headless: true,
    trace: 'retain-on-failure',
    extraHTTPHeaders: { Authorization: `Bearer ${testAuthToken}` },
  },
  webServer: [
    {
      cwd: backendDir,
      command: `"${python}" -m uvicorn testing.studio_app:app --host 127.0.0.1 --port 8101`,
      url: 'http://127.0.0.1:8101/docs',
      reuseExistingServer: false,
      timeout: 60000,
      env: { DATABASE_URL: databaseUrl, PYTHONPATH: backendDir, APP_AUTH_SECRET: authSecret },
    },
    {
      cwd: frontendDir,
      command: `node "${path.join(frontendDir, 'node_modules', 'vite', 'bin', 'vite.js')}"`,
      url: 'http://127.0.0.1:3101',
      reuseExistingServer: false,
      env: { VITE_PORT: '3101', BACKEND_PORT: '8101' },
      // Vite 冷启动（首次依赖预打包）可能超过默认 60 秒，留足余量避免误判为启动失败。
      timeout: 180000,
    },
  ],
});
