/**
 * API client for NovelAgent frontend
 */

import { createSSEStream } from './sseParser'
import type {
  User,
  LoginRequest,
  LoginResponse,
  Project,
  ProjectDetail,
  ProjectListResponse,
  ProjectCreate,
  ProjectUpdate,
  Outline,
  OutlineUpdate,
  ChapterCountRequest,
  ChapterOutline,
  ChapterOutlineUpdate,
  Chapter,
  ChapterContentUpdate,
  ReviewRequest,
  ReviewResponse,
  UserSettings,
  SettingsUpdate,
  ChatMessage,
  ChatResponse,
  ApiError,
  AgentPrompt,
  AgentPromptListResponse,
  AgentPromptUpdate,
  ProjectAgentPromptItem,
  ProjectAgentPromptsResponse,
  ModelConfig,
  ModelConfigListResponse,
  ModelConfigCreate,
  ModelConfigUpdate,
  ProvidersListResponse,
  FetchModelsResponse,
} from "@/types";

// ==================== Configuration ====================

// Use empty string for relative path (proxied through nginx) or explicit URL
const API_BASE_URL = import.meta.env.VITE_API_URL || "";

// ==================== Session Token Management ====================

let sessionToken: string | null = null;

/**
 * 获取 session token - 优先从 Cookie 读取，其次从 localStorage 读取
 */
export function getSessionToken(): string | null {
  if (!sessionToken) {
    // 首先尝试从 Cookie 读取（HttpOnly 方式）
    const cookies = document.cookie.split(';');
    for (const cookie of cookies) {
      const [name, value] = cookie.trim().split('=');
      if (name === 'session_token') {
        sessionToken = decodeURIComponent(value);
        return sessionToken;
      }
    }
    // 兼容旧版 localStorage 方式
    sessionToken = localStorage.getItem("session_token");
  }
  return sessionToken;
}

/**
 * 设置 session token - 同时写入 Cookie 和 localStorage
 */
export function setSessionToken(token: string | null): void {
  sessionToken = token;
  if (token) {
    // 写入 localStorage（兼容旧版）
    localStorage.setItem("session_token", token);
    // 写入 Cookie（供后端 HttpOnly 模式使用）
    document.cookie = `session_token=${encodeURIComponent(token)}; path=/; max-age=${7 * 24 * 60 * 60}`;
  } else {
    localStorage.removeItem("session_token");
    // 清除 Cookie
    document.cookie = 'session_token=; path=/; expires=Thu, 01 Jan 1970 00:00:00 GMT';
  }
}

// ==================== Request Helper ====================

// 请求超时时间（毫秒）
const REQUEST_TIMEOUT = 30000;

interface RequestOptions {
  method?: "GET" | "POST" | "PUT" | "DELETE";
  body?: unknown;
  requireAuth?: boolean;
  timeout?: number;  // 自定义超时时间
}

/**
 * 发送 API 请求
 * @param endpoint - API 端点
 * @param options - 请求选项
 * @returns 响应数据
 */
async function request<T>(
  endpoint: string,
  options: RequestOptions = {}
): Promise<T> {
  const { method = "GET", body, requireAuth = true, timeout = REQUEST_TIMEOUT } = options;

  const headers: HeadersInit = {
    "Content-Type": "application/json",
  };

  // 使用 HTTP Basic 认证，将 session token 作为 username
  if (requireAuth) {
    const token = getSessionToken();
    if (token) {
      const credentials = btoa(`${token}:`);
      headers["Authorization"] = `Basic ${credentials}`;
    }
  }

  // 创建超时控制器
  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), timeout);

  try {
    const response = await fetch(`${API_BASE_URL}${endpoint}`, {
      method,
      headers,
      body: body ? JSON.stringify(body) : undefined,
      signal: controller.signal,
      credentials: 'include', // 发送和接收 cookies
    });

    if (!response.ok) {
      const error: ApiError = await response.json().catch(() => ({
        detail: `HTTP ${response.status}: ${response.statusText}`,
      }));
      throw new Error(error.detail);
    }

    // 处理 204 No Content
    if (response.status === 204) {
      return undefined as T;
    }

    return response.json();
  } catch (err) {
    // 处理超时错误
    if (err instanceof Error && err.name === 'AbortError') {
      throw new Error('请求超时，请稍后重试');
    }
    throw err;
  } finally {
    clearTimeout(timeoutId);
  }
}

// ==================== Auth API ====================

export const authApi = {
  async login(credentials: LoginRequest): Promise<LoginResponse> {
    const response = await request<LoginResponse>("/api/auth/login", {
      method: "POST",
      body: credentials,
      requireAuth: false,
    });
    setSessionToken(response.session_token);
    return response;
  },

  async logout(): Promise<void> {
    try {
      await request("/api/auth/logout", { method: "POST" });
    } finally {
      setSessionToken(null);
    }
  },

  async me(): Promise<User> {
    return request<User>("/api/auth/me");
  },
};

// ==================== Projects API ====================

export const projectsApi = {
  async list(): Promise<ProjectListResponse> {
    return request<ProjectListResponse>("/api/projects/");
  },

  async get(projectId: number): Promise<ProjectDetail> {
    return request<ProjectDetail>(`/api/projects/${projectId}`);
  },

  async create(data: ProjectCreate): Promise<Project> {
    return request<Project>("/api/projects/", {
      method: "POST",
      body: data,
    });
  },

  async update(projectId: number, data: ProjectUpdate): Promise<Project> {
    return request<Project>(`/api/projects/${projectId}`, {
      method: "PUT",
      body: data,
    });
  },

  async delete(projectId: number): Promise<void> {
    return request(`/api/projects/${projectId}`, { method: "DELETE" });
  },
};

// ==================== Outline API ====================

// Streaming callback types
export interface OutlineStreamResult {
  outline: Partial<Outline>;
  stage: string;
}

export interface OutlineStreamCallbacks {
  onChunk: (chunk: string) => void;
  onDone: (result: OutlineStreamResult) => void;
  onError: (error: string) => void;
}

// 流式请求选项
export interface StreamOptions {
  signal?: AbortSignal;  // 用于取消请求
}

export const outlineApi = {
  async get(projectId: number): Promise<Outline> {
    return request<Outline>(`/api/projects/${projectId}/outline`);
  },

  async create(projectId: number): Promise<Outline> {
    return request<Outline>(`/api/projects/${projectId}/outline`, {
      method: "POST",
    });
  },

  /**
   * Generate outline with streaming - uses unified SSE handler
   * @param projectId - 项目 ID
   * @param callbacks - 回调函数
   * @param options - 流式请求选项（包括 AbortSignal 用于取消）
   * @param llmConfigId - 可选的模型配置 ID
   */
  async createStream(
    projectId: number,
    callbacks: OutlineStreamCallbacks,
    options?: StreamOptions,
    llmConfigId?: number
  ): Promise<void> {
    await createSSEStream(
      {
        url: `/api/projects/${projectId}/outline`,
        method: 'POST',
        body: llmConfigId ? { llm_config_id: llmConfigId } : {},
        signal: options?.signal,
      },
      (type, data) => {
        if (type === 'done') {
          callbacks.onDone(data as OutlineStreamResult)
        } else if (type !== 'error') {
          // chunk 事件
          callbacks.onChunk(typeof data === 'string' ? data : String(data))
        }
      },
      callbacks.onError
    )
  },

  async update(projectId: number, data: OutlineUpdate): Promise<Outline> {
    return request<Outline>(`/api/projects/${projectId}/outline`, {
      method: "PUT",
      body: data,
    });
  },

  async confirm(projectId: number): Promise<void> {
    return request(`/api/projects/${projectId}/outline/confirm`, {
      method: "POST",
    });
  },

  async setChapterCount(
    projectId: number,
    data: ChapterCountRequest
  ): Promise<void> {
    return request(`/api/projects/${projectId}/outline/chapter-count`, {
      method: "POST",
      body: data,
    });
  },
};

// ==================== Chapter Outlines API ====================

// Streaming callback types for chapter outlines
export interface ChapterOutlineStreamCallbacks {
  onProgress: (chapterNumber: number, total: number, chapter: { id: number; chapter_number: number; title: string }) => void;
  onDone: (total: number, stage: string) => void;
  onError: (error: string) => void;
}

export const chapterOutlinesApi = {
  async list(projectId: number): Promise<ChapterOutline[]> {
    return request<ChapterOutline[]>(`/api/projects/${projectId}/chapter-outlines`);
  },

  /**
   * Generate chapter outlines with SSE streaming - uses unified SSE handler
   * @param projectId - 项目 ID
   * @param callbacks - 回调函数
   * @param options - 流式请求选项（包括 AbortSignal 用于取消）
   * @param llmConfigId - 可选的模型配置 ID
   */
  async createStream(
    projectId: number,
    callbacks: ChapterOutlineStreamCallbacks,
    options?: StreamOptions,
    llmConfigId?: number
  ): Promise<void> {
    await createSSEStream(
      {
        url: `/api/projects/${projectId}/chapter-outlines`,
        method: 'POST',
        body: llmConfigId ? { llm_config_id: llmConfigId } : {},
        signal: options?.signal,
      },
      (type, data) => {
        if (type === 'progress') {
          const progress = data as { chapter_number: number; total: number; chapter: { id: number; chapter_number: number; title: string } }
          callbacks.onProgress(progress.chapter_number, progress.total, progress.chapter)
        } else if (type === 'done') {
          const done = data as { total: number; stage: string }
          callbacks.onDone(done.total, done.stage)
        }
        // error 类型由 onError 回调处理
      },
      callbacks.onError
    )
  },

  async update(
    projectId: number,
    chapterNum: number,
    data: ChapterOutlineUpdate
  ): Promise<ChapterOutline> {
    return request<ChapterOutline>(
      `/api/projects/${projectId}/chapter-outlines/${chapterNum}`,
      {
        method: "PUT",
        body: data,
      }
    );
  },

  async confirm(projectId: number, chapterNum: number): Promise<void> {
    return request(
      `/api/projects/${projectId}/chapter-outlines/${chapterNum}/confirm`,
      { method: "POST" }
    );
  },
};

// ==================== Chapters API ====================

export const chaptersApi = {
  async get(projectId: number, chapterNum: number): Promise<Chapter> {
    return request<Chapter>(`/api/projects/${projectId}/chapters/${chapterNum}`);
  },

  async create(projectId: number, chapterNum: number): Promise<Chapter> {
    return request<Chapter>(`/api/projects/${projectId}/chapters/${chapterNum}`, {
      method: "POST",
    });
  },

  async update(
    projectId: number,
    chapterNum: number,
    data: ChapterContentUpdate
  ): Promise<Chapter> {
    return request<Chapter>(`/api/projects/${projectId}/chapters/${chapterNum}`, {
      method: "PUT",
      body: data,
    });
  },

  async review(
    projectId: number,
    chapterNum: number,
    data?: ReviewRequest
  ): Promise<ReviewResponse> {
    return request<ReviewResponse>(
      `/api/projects/${projectId}/chapters/${chapterNum}/review`,
      {
        method: "POST",
        body: data,
      }
    );
  },
};

// ==================== Settings API ====================

export const settingsApi = {
  async get(): Promise<UserSettings> {
    return request<UserSettings>("/api/settings/");
  },

  async update(data: SettingsUpdate): Promise<UserSettings> {
    return request<UserSettings>("/api/settings/", {
      method: "PUT",
      body: data,
    });
  },
};

// ==================== Chat API (for info collection) ====================

export const chatApi = {
  async sendMessage(projectId: number, message: ChatMessage): Promise<ChatResponse> {
    return request<ChatResponse>(`/api/projects/${projectId}/outline/chat`, {
      method: "POST",
      body: message,
    });
  },
};

// ==================== Collected Info API ====================

export interface CollectedInfoUpdate {
  genre?: string;
  theme?: string;
  main_characters?: string;
  world_setting?: string;
  style_preference?: string;
}

export const collectedInfoApi = {
  async update(projectId: number, data: CollectedInfoUpdate): Promise<Outline> {
    return request<Outline>(`/api/projects/${projectId}/outline/collected-info`, {
      method: "PUT",
      body: data,
    });
  },
};

// ==================== Agent Prompts API ====================

export const agentPromptsApi = {
  async getGlobal(): Promise<AgentPromptListResponse> {
    return request<AgentPromptListResponse>("/api/agent-prompts");
  },

  async updateGlobal(
    agentType: string,
    data: AgentPromptUpdate
  ): Promise<AgentPrompt> {
    return request<AgentPrompt>(`/api/agent-prompts/${agentType}`, {
      method: "PUT",
      body: data,
    });
  },

  async resetGlobal(agentType: string): Promise<AgentPrompt> {
    return request<AgentPrompt>(`/api/agent-prompts/${agentType}/reset`, {
      method: "POST",
    });
  },

  async getProject(projectId: number): Promise<ProjectAgentPromptsResponse> {
    return request<ProjectAgentPromptsResponse>(
      `/api/projects/${projectId}/agent-prompts`
    );
  },

  async setProjectCustom(
    projectId: number,
    agentType: string,
    data: AgentPromptUpdate
  ): Promise<ProjectAgentPromptItem> {
    return request<ProjectAgentPromptItem>(
      `/api/projects/${projectId}/agent-prompts/${agentType}`,
      {
        method: "PUT",
        body: data,
      }
    );
  },

  async deleteProjectCustom(
    projectId: number,
    agentType: string
  ): Promise<{ success: boolean }> {
    return request<{ success: boolean }>(
      `/api/projects/${projectId}/agent-prompts/${agentType}`,
      { method: "DELETE" }
    );
  },
};

// ==================== Model Configs API ====================

export const modelConfigsApi = {
  /**
   * 获取模型配置列表
   */
  async list(): Promise<ModelConfigListResponse> {
    return request<ModelConfigListResponse>("/api/model_configs/");
  },

  /**
   * 获取提供商列表
   */
  async getProviders(): Promise<ProvidersListResponse> {
    return request<ProvidersListResponse>("/api/model_configs/providers");
  },

  /**
   * 从提供商获取可用模型列表
   */
  async fetchModels(data: {
    provider: string
    base_url: string
    api_key: string
  }): Promise<FetchModelsResponse> {
    return request<FetchModelsResponse>("/api/model_configs/fetch-models", {
      method: "POST",
      body: data,
    });
  },

  /**
   * 创建模型配置
   */
  async create(data: ModelConfigCreate): Promise<ModelConfig> {
    return request<ModelConfig>("/api/model_configs/", {
      method: "POST",
      body: data,
    });
  },

  /**
   * 更新模型配置
   */
  async update(configId: number, data: ModelConfigUpdate): Promise<ModelConfig> {
    return request<ModelConfig>(`/api/model_configs/${configId}`, {
      method: "PUT",
      body: data,
    });
  },

  /**
   * 删除模型配置
   */
  async delete(configId: number): Promise<void> {
    return request(`/api/model_configs/${configId}`, { method: "DELETE" });
  },

  /**
   * 设置默认模型配置
   */
  async setDefault(configId: number): Promise<ModelConfig> {
    return request<ModelConfig>(`/api/model_configs/${configId}/default`, {
      method: "PUT",
    });
  },

  /**
   * 健康检查
   */
  async checkHealth(configId: number): Promise<{ status: string; latency?: number; error?: string }> {
    return request(`/api/model_configs/${configId}/health`, {
      method: "POST",
    });
  },
};

// ==================== Workflow API ====================

// 重新导出 workflowApi（定义在 workflowApi.ts）
export { workflowApi } from './workflowApi'
export type { WorkflowStreamCallbacks } from './workflowApi'