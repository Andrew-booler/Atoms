import '@testing-library/jest-dom/vitest';
import { cleanup } from '@testing-library/react';
import { TextDecoder, TextEncoder } from 'node:util';
import { afterEach, vi } from 'vitest';

// jsdom 不实现滚动定位，ConversationStream 挂载时会调用
Object.defineProperty(Element.prototype, 'scrollIntoView', {
  configurable: true,
  writable: true,
  value: vi.fn(),
});

// ArtifactPreview 用 TextEncoder 计算产物体积；jsdom 环境缺失时回退到 Node 实现
if (typeof globalThis.TextEncoder === 'undefined') {
  globalThis.TextEncoder = TextEncoder;
}
if (typeof globalThis.TextDecoder === 'undefined') {
  globalThis.TextDecoder = TextDecoder;
}

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});
