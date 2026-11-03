import { getAPIBaseURL } from '../lib/config';

// Don't cache the getAPIBase() URL, get it dynamically
const getAPIBase = () => `${getAPIBaseURL()}/api/v1`;

/** 读取统一错误契约中的 message，失败时回退到调用方文案。 */
async function errorMessage(response: Response, fallback: string): Promise<string> {
  try {
    const body = await response.json();
    return body?.message || body?.detail || fallback;
  } catch {
    return fallback;
  }
}

export interface EnvVariable {
  key: string;
  value: string;
  description: string;
}

export interface EnvConfig {
  backend_vars: Record<string, EnvVariable>;
  frontend_vars: Record<string, EnvVariable>;
}

export interface EnvVariableUpdate {
  value: string;
}

export const settingsApi = {
  // Fetch all configurations
  async getConfig(): Promise<EnvConfig> {
    const response = await fetch(`${getAPIBase()}/admin/settings/`, {
      credentials: 'include',
    });

    if (!response.ok) {
      throw new Error(await errorMessage(response, 'Failed to fetch configuration'));
    }

    return response.json();
  },

  // Update backend configuration
  async updateBackendConfig(
    key: string,
    value: string
  ): Promise<{ message: string }> {
    const response = await fetch(
      `${getAPIBase()}/admin/settings/backend/${key}`,
      {
        method: 'PUT',
        headers: {
          'Content-Type': 'application/json',
        },
        credentials: 'include',
        body: JSON.stringify({ value }),
      }
    );

    if (!response.ok) {
      throw new Error(await errorMessage(response, 'Failed to update backend configuration'));
    }

    return response.json();
  },

  // Update frontend configuration
  async updateFrontendConfig(
    key: string,
    value: string
  ): Promise<{ message: string }> {
    const response = await fetch(
      `${getAPIBase()}/admin/settings/frontend/${key}`,
      {
        method: 'PUT',
        headers: {
          'Content-Type': 'application/json',
        },
        credentials: 'include',
        body: JSON.stringify({ value }),
      }
    );

    if (!response.ok) {
      throw new Error(await errorMessage(response, 'Failed to update frontend configuration'));
    }

    return response.json();
  },

  // Add backend configuration
  async addBackendConfig(
    key: string,
    value: string
  ): Promise<{ message: string }> {
    const response = await fetch(
      `${getAPIBase()}/admin/settings/backend/${key}`,
      {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        credentials: 'include',
        body: JSON.stringify({ value }),
      }
    );

    if (!response.ok) {
      throw new Error(await errorMessage(response, 'Failed to add backend configuration'));
    }

    return response.json();
  },

  // Add frontend configuration
  async addFrontendConfig(
    key: string,
    value: string
  ): Promise<{ message: string }> {
    const response = await fetch(
      `${getAPIBase()}/admin/settings/frontend/${key}`,
      {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        credentials: 'include',
        body: JSON.stringify({ value }),
      }
    );

    if (!response.ok) {
      throw new Error(await errorMessage(response, 'Failed to add frontend configuration'));
    }

    return response.json();
  },

  // Delete backend configuration
  async deleteBackendConfig(key: string): Promise<{ message: string }> {
    const response = await fetch(
      `${getAPIBase()}/admin/settings/backend/${key}`,
      {
        method: 'DELETE',
        credentials: 'include',
      }
    );

    if (!response.ok) {
      throw new Error(await errorMessage(response, 'Failed to delete backend configuration'));
    }

    return response.json();
  },

  // Delete frontend configuration
  async deleteFrontendConfig(key: string): Promise<{ message: string }> {
    const response = await fetch(
      `${getAPIBase()}/admin/settings/frontend/${key}`,
      {
        method: 'DELETE',
        credentials: 'include',
      }
    );

    if (!response.ok) {
      throw new Error(await errorMessage(response, 'Failed to delete frontend configuration'));
    }

    return response.json();
  },
};
