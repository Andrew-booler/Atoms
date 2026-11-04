import { client } from './api';
import type { BuildEvent } from './build-stream';

export type Stage = 'plan' | 'outline' | 'artifact';

/** 构建终端：一次构建的事件集合（刷新后可回看）。 */
export interface BuildStartResponse {
  build_id: string;
}

export interface BuildEventsResponse {
  build_id?: string | null;
  events: BuildEvent[];
}

const withBuildId = (url: string, buildId?: string) =>
  buildId ? `${url}?build_id=${encodeURIComponent(buildId)}` : url;

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

export interface ApiErrorBody {
  code?: string;
  message?: string;
  details?: Record<string, unknown>;
}

const getErrorBody = (error: unknown): ApiErrorBody | undefined => {
  const err = error as {
    data?: ApiErrorBody;
    response?: { data?: ApiErrorBody & { detail?: string }; message?: string };
    message?: string;
  };
  return err?.data ?? err?.response?.data;
};

/** 统一错误展示：优先使用后端 ErrorResponse.message，兼容旧版 detail。 */
const getErrorDetail = (error: unknown): string => {
  const body = getErrorBody(error);
  const err = error as { message?: string };
  return body?.message || (body as { detail?: string } | undefined)?.detail || err?.message || '请求失败，请重试';
};

export const describeError = getErrorDetail;

/** 需要按错误码分支时使用（如权限、限流）。 */
export const describeErrorCode = (error: unknown): string | undefined => getErrorBody(error)?.code;

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
    profile?: string,
    buildId?: string
  ): Promise<PlanResponse> {
    const res = await client.apiCall.invoke({
      url: `${withBuildId(`/api/v1/studio/projects/${projectId}/plan`, buildId)}${buildId ? '&final=true' : ''}`,
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
    profile?: string,
    buildId?: string
  ): Promise<OutlineResponse> {
    const res = await client.apiCall.invoke({
      url: withBuildId(`/api/v1/studio/projects/${projectId}/outline`, buildId),
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
      base_version_id?: number;
      revision_note?: string;
    },
    buildId?: string
  ): Promise<BuildResponse> {
    const res = await client.apiCall.invoke({
      url: withBuildId(`/api/v1/studio/projects/${projectId}/artifact`, buildId),
      method: 'POST',
      data: payload,
      options: { timeout: 600_000 },
    });
    return res.data as BuildResponse;
  },

  async editArtifact(
    projectId: number,
    payload: { html: string; note?: string },
    buildId?: string
  ): Promise<BuildResponse> {
    const res = await client.apiCall.invoke({
      url: withBuildId(`/api/v1/studio/projects/${projectId}/artifact/edit`, buildId),
      method: 'POST',
      data: payload,
      options: { timeout: 600_000 },
    });
    return res.data as BuildResponse;
  },

  /** 为一次完整的 plan→outline→artifact 构建开启终端会话。 */
  async startBuild(projectId: number): Promise<BuildStartResponse> {
    const res = await client.apiCall.invoke({
      url: `/api/v1/studio/projects/${projectId}/builds`,
      method: 'POST',
      data: {},
    });
    return res.data as BuildStartResponse;
  },

  /** 刷新页面后回看最近一次构建记录（无记录时 events 为空）。 */
  async latestBuild(projectId: number): Promise<BuildEventsResponse> {
    const res = await client.apiCall.invoke({
      url: `/api/v1/studio/projects/${projectId}/builds/latest`,
      method: 'GET',
      data: {},
    });
    return res.data as BuildEventsResponse;
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
