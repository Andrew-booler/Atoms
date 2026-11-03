import axios, { AxiosInstance } from 'axios';
import { getAPIBaseURL } from './config';

// web-sdk 的请求拦截器会读取 localStorage.token 并附加 Bearer 头，
// 因此这里必须使用同一个键名，登录态才能被工作台接口复用。
export const AUTH_TOKEN_KEY = 'token';

const LOGIN_PATH = '/login';

export interface AuthUser {
  id: string;
  email: string;
  name?: string | null;
  role?: string;
}

export interface AuthSession {
  token: string;
  token_type: string;
  expires_at: string;
  user: AuthUser;
}

export function getStoredToken(): string | null {
  return typeof window === 'undefined' ? null : window.localStorage.getItem(AUTH_TOKEN_KEY);
}

export function storeToken(token: string): void {
  window.localStorage.setItem(AUTH_TOKEN_KEY, token);
}

export function clearToken(): void {
  window.localStorage.removeItem(AUTH_TOKEN_KEY);
}

/** 401 时统一跳转登录页，避免接口失败被静默吞掉。 */
export function redirectToLogin(): void {
  if (typeof window === 'undefined') return;
  if (window.location.pathname === LOGIN_PATH) return;
  const from = `${window.location.pathname}${window.location.search}`;
  window.location.assign(`${LOGIN_PATH}?from=${encodeURIComponent(from)}`);
}

function errorMessage(error: unknown, fallback: string): string {
  if (axios.isAxiosError(error)) {
    const body = error.response?.data as { message?: string } | undefined;
    if (body?.message) return body.message;
  }
  return fallback;
}

class AuthApi {
  private client: AxiosInstance;

  constructor() {
    this.client = axios.create({
      headers: { 'Content-Type': 'application/json' },
    });
    this.client.interceptors.request.use((config) => {
      const token = getStoredToken();
      if (token) {
        config.headers.Authorization = `Bearer ${token}`;
      }
      return config;
    });
  }

  private baseURL() {
    return `${getAPIBaseURL()}/api/v1/auth`;
  }

  async register(email: string, password: string, name?: string): Promise<AuthSession> {
    try {
      const response = await this.client.post(`${this.baseURL()}/register`, {
        email,
        password,
        name: name || undefined,
      });
      storeToken(response.data.token);
      return response.data;
    } catch (error) {
      throw new Error(errorMessage(error, '注册失败，请稍后重试。'));
    }
  }

  async login(email: string, password: string): Promise<AuthSession> {
    try {
      const response = await this.client.post(`${this.baseURL()}/login`, { email, password });
      storeToken(response.data.token);
      return response.data;
    } catch (error) {
      throw new Error(errorMessage(error, '登录失败，请检查邮箱或密码。'));
    }
  }

  async getCurrentUser(): Promise<AuthUser | null> {
    if (!getStoredToken()) return null;
    try {
      const response = await this.client.get(`${this.baseURL()}/me`);
      return response.data as AuthUser;
    } catch (error) {
      if (axios.isAxiosError(error) && error.response?.status === 401) {
        clearToken();
        return null;
      }
      throw new Error(errorMessage(error, '获取用户信息失败。'));
    }
  }

  async logout(): Promise<void> {
    try {
      await this.client.post(`${this.baseURL()}/logout`);
    } catch {
      // 登出是无状态的，网络异常也要清理本地令牌。
    } finally {
      clearToken();
    }
  }
}

export const authApi = new AuthApi();
