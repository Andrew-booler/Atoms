import { defineConfig } from '@playwright/test';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const testsDir = path.dirname(fileURLToPath(import.meta.url));
const frontendDir = path.resolve(testsDir, '..');
const backendDir = path.resolve(frontendDir, '../backend');
const python = process.env.ATOMS_BACKEND_PYTHON ?? 'E:\\Dependencies\\Atoms\\backend-venv\\Scripts\\python.exe';
const databaseUrl =
  process.env.DATABASE_URL ?? 'postgresql+asyncpg://postgres:postgres@127.0.0.1:5432/postgres';

export default defineConfig({
  tsconfig: '../tsconfig.app.json',
  testDir: '.', testMatch: 'studio.integration.spec.ts', workers: 1, fullyParallel: false,
  timeout: 240000, expect: { timeout: 10000 },
  reporter: [['list'], ['json', { outputFile: path.join(testsDir, 'results.json') }]],
  use: { baseURL: 'http://127.0.0.1:3101', headless: true, trace: 'retain-on-failure' },
  webServer: [
    {
      cwd: backendDir,
      command: `"${python}" -m uvicorn testing.studio_app:app --host 127.0.0.1 --port 8101`,
      url: 'http://127.0.0.1:8101/docs',
      reuseExistingServer: false,
      timeout: 60000,
      env: { DATABASE_URL: databaseUrl, PYTHONPATH: backendDir },
    },
    {
      cwd: frontendDir,
      command: `node "${path.join(frontendDir, 'node_modules', 'vite', 'bin', 'vite.js')}"`,
      url: 'http://127.0.0.1:3101',
      reuseExistingServer: false,
      timeout: 60000,
      env: { VITE_PORT: '3101', BACKEND_PORT: '8101' },
    },
  ],
});
