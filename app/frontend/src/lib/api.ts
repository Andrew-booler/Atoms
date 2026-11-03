import { createClient } from '@metagptx/web-sdk';
import { redirectToLogin } from './auth';

// 401 统一跳转登录页；web-sdk 会自动从 localStorage.token 读取 Bearer 令牌。
export const client = createClient({ onUnauthorized: redirectToLogin });
