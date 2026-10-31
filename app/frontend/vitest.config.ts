import { fileURLToPath } from 'node:url';
import react from '@vitejs/plugin-react-swc';
import { defineConfig } from 'vitest/config';

// 单元测试运行器：Vitest + jsdom。
// Playwright 会把 TSX 里的 JSX 编译成它自己的组件描述对象（__pw_type），
// React 无法渲染，因此页面/组件单元不能复用 Playwright 运行入口。
export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url)),
    },
  },
  test: {
    environment: 'jsdom',
    setupFiles: ['./tests/setup.ts'],
    include: ['tests/**/*.test.{ts,tsx}'],
    // Playwright 用例由 tests/studio.config.ts 运行，避免被 Vitest 重复采集
    exclude: ['tests/**/*.spec.ts', 'node_modules/**'],
    restoreMocks: true,
    coverage: {
      provider: 'v8',
      reporter: ['text', 'html', 'json-summary'],
      reportsDirectory: './coverage',
      include: ['src/**/*.{ts,tsx}'],
      exclude: ['src/components/ui/**', 'src/vite-env.d.ts'],
    },
  },
});
