import { client } from './api';

export type Stage = 'plan' | 'outline' | 'artifact';

export interface ModelOption {
  key: string;
  model: string;
  label: string;
  hint: string;
}

export interface ModelsResponse {
  profiles: ModelOption[];
  default_profile: string;
}

export interface ProjectSummary {
  id: number;
  name: string;
  description?: string | null;
  status?: string | null;
  current_version?: number | null;
  preview_ready?: boolean | null;
  version_count: number;
  updated_at?: string | null;
}

export interface PlanStep {
  title: string;
  detail: string;
}

export interface PlanFile {
  path: string;
  purpose: string;
}

export interface PlanPayload {
  summary: string;
  stack: string[];
  steps: PlanStep[];
  files: PlanFile[];
}

export interface MessageMeta {
  plan?: PlanPayload;
  model?: string;
  requirement?: string;
  approved?: boolean;
  version_id?: number;
  version_no?: number;
  title?: string;
  sections?: string[];
  interactions?: string[];
}

export interface StudioMessage {
  id: number;
  role: 'user' | 'assistant' | 'system';
  kind?: string | null;
  content: string;
  meta: MessageMeta;
  created_at?: string | null;
}

export interface VersionSummary {
  id: number;
  version_no: number;
  label?: string | null;
  created_at?: string | null;
}

export interface VersionDetail extends VersionSummary {
  project_id: number;
  plan_summary?: string | null;
  artifact_html: string;
}

export interface ProjectDetail {
  project: ProjectSummary;
  messages: StudioMessage[];
  versions: VersionSummary[];
  current_artifact?: string | null;
}

export interface OutlinePayload {
  title: string;
  sections: { name: string; blocks: string[] }[];
  interactions: string[];
  seed_data: string[];
}

export interface PlanResponse {
  plan: PlanPayload;
  message: StudioMessage;
  model: string;
}

export interface OutlineResponse {
  outline: OutlinePayload;
  model: string;
}

export interface BuildResponse {
  project: ProjectSummary;
  version: VersionSummary;
  message: StudioMessage;
  outline_title: string;
  artifact_html: string;
  preview_url?: string | null;
}

const getErrorDetail = (error: unknown): string => {
  const err = error as {
    data?: { detail?: string };
    response?: { data?: { detail?: string } };
    message?: string;
  };
  return (
    err?.data?.detail || err?.response?.data?.detail || err?.message || '请求失败，请重试'
  );
};

export const describeError = getErrorDetail;

export const studioApi = {
  async models(): Promise<ModelsResponse> {
    const res = await client.apiCall.invoke({
      url: '/api/v1/studio/models',
      method: 'GET',
      data: {},
    });
    return res.data as ModelsResponse;
  },

  async listProjects(): Promise<ProjectSummary[]> {
    const res = await client.apiCall.invoke({
      url: '/api/v1/studio/projects',
      method: 'GET',
      data: {},
    });
    return res.data as ProjectSummary[];
  },

  async createProject(name: string, description = ''): Promise<ProjectSummary> {
    const res = await client.apiCall.invoke({
      url: '/api/v1/studio/projects',
      method: 'POST',
      data: { name, description },
    });
    return res.data as ProjectSummary;
  },

  async deleteProject(projectId: number): Promise<void> {
    await client.apiCall.invoke({
      url: `/api/v1/studio/projects/${projectId}`,
      method: 'DELETE',
      data: {},
    });
  },

  async getProject(projectId: number): Promise<ProjectDetail> {
    const res = await client.apiCall.invoke({
      url: `/api/v1/studio/projects/${projectId}`,
      method: 'GET',
      data: {},
    });
    return res.data as ProjectDetail;
  },

  async appendMessage(
    projectId: number,
    payload: { role: string; kind?: string; content: string }
  ): Promise<StudioMessage> {
    const res = await client.apiCall.invoke({
      url: `/api/v1/studio/projects/${projectId}/messages`,
      method: 'POST',
      data: payload,
    });
    return res.data as StudioMessage;
  },

  async plan(
    projectId: number,
    requirement: string,
    profile?: string
  ): Promise<PlanResponse> {
    const res = await client.apiCall.invoke({
      url: `/api/v1/studio/projects/${projectId}/plan`,
      method: 'POST',
      data: { requirement, profile },
      options: { timeout: 600_000 },
    });
    return res.data as PlanResponse;
  },

  async outline(
    projectId: number,
    requirement: string,
    planSummary: string,
    profile?: string
  ): Promise<OutlineResponse> {
    const res = await client.apiCall.invoke({
      url: `/api/v1/studio/projects/${projectId}/outline`,
      method: 'POST',
      data: { requirement, plan_summary: planSummary, profile },
      options: { timeout: 600_000 },
    });
    return res.data as OutlineResponse;
  },

  async artifact(
    projectId: number,
    payload: {
      requirement: string;
      plan_summary: string;
      outline: OutlinePayload;
      profile?: string;
    }
  ): Promise<BuildResponse> {
    const res = await client.apiCall.invoke({
      url: `/api/v1/studio/projects/${projectId}/artifact`,
      method: 'POST',
      data: payload,
      options: { timeout: 600_000 },
    });
    return res.data as BuildResponse;
  },

  async getVersion(versionId: number): Promise<VersionDetail> {
    const res = await client.apiCall.invoke({
      url: `/api/v1/studio/versions/${versionId}`,
      method: 'GET',
      data: {},
    });
    return res.data as VersionDetail;
  },

  async restore(projectId: number, versionId: number): Promise<ProjectSummary> {
    const res = await client.apiCall.invoke({
      url: `/api/v1/studio/projects/${projectId}/restore`,
      method: 'POST',
      data: { version_id: versionId },
    });
    return res.data as ProjectSummary;
  },
};
