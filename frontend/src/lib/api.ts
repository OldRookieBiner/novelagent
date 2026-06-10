/**
 * API client for NovelAgent frontend
 */

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
  UserSettings,
  SettingsUpdate,
  ChatMessage,
  ChatResponse,
  ApiError,
  ModelConfig,
  ModelConfigListResponse,
  ModelConfigCreate,
  ModelConfigUpdate,
  HealthCheckResponse,
  ProvidersListResponse,
  FetchModelsResponse,
  Volume,
  Arc,
  ArcUpdate,
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


/**
 * Clear stale token and redirect to login
 */
function clearAuthAndRedirect(): void {
  setSessionToken(null);
  localStorage.removeItem('auth-storage');
  window.location.href = '/login';
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
export async function request<T>(
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

    if (response.status === 401) {
      clearAuthAndRedirect();
    }

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
  async list(params?: { limit?: number; offset?: number }): Promise<ProjectListResponse> {
    const searchParams = new URLSearchParams()
    if (params?.limit) searchParams.set('limit', params.limit.toString())
    if (params?.offset) searchParams.set('offset', params.offset.toString())
    const query = searchParams.toString()
    return request<ProjectListResponse>(`/api/projects/${query ? '?' + query : ''}`);
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

  /**
   * 初始化项目（SSE 流式请求）
   * 后端返回 SSE 事件流，前端实时展示初始化进度
   */
  async initialize(
    concept: string,
    options: {
      onEvent: (type: string, data: Record<string, unknown>) => void;
      onError?: (error: string) => void;
    },
    targetWords: number = 100000,
    modelConfigId?: number,
    modelId?: string,
    signal?: AbortSignal,
  ): Promise<{ project_id: number; name: string; status: string; cancelled?: boolean }> {
    const { createSSEStream } = await import('./sseParser');

    let result: { project_id: number; name: string; status: string; cancelled?: boolean } = {
      project_id: 0,
      name: '',
      status: '',
    };

    await createSSEStream(
      {
        url: '/api/projects/initialize',
        method: 'POST',
        body: {
          concept,
          target_words: targetWords,
          model_config_id: modelConfigId,
          model_id: modelId,
        },
        signal,
      },
      (type, data) => {
        // 解析 init:done 事件中的 project_id
        if (type === 'init:done' && data && typeof data === 'object') {
          const d = data as Record<string, unknown>;
          if (d.project_id) {
            result.project_id = d.project_id as number;
          }
          if (d.status) {
            result.status = d.status as string;
          }
        }
        if (type === 'init:cancelled') {
          result.cancelled = true;
        }
        if (type === 'init:complete' && data && typeof data === 'object') {
          const d = data as Record<string, unknown>;
          if (d.project_id) {
            result.project_id = d.project_id as number;
          }
          if (d.name) {
            result.name = d.name as string;
          }
        }
        // 传递给上层回调
        options.onEvent(type, data as Record<string, unknown>);
      },
      (error) => options.onError?.(error),
    );

    return result;
  },
};

// ==================== Outline API ====================

export const outlineApi = {
  async get(projectId: number): Promise<Outline> {
    return request<Outline>(`/api/projects/${projectId}/outline`);
  },

  async create(projectId: number): Promise<Outline> {
    return request<Outline>(`/api/projects/${projectId}/outline`, {
      method: "POST",
    });
  },
  async update(projectId: number, data: OutlineUpdate): Promise<Outline> {
    return request<Outline>(`/api/projects/${projectId}/outline`, {
      method: "PUT",
      body: data,
    });
  },

  async confirm(projectId: number): Promise<void> {
    return request(`/api/projects/${projectId}/outline/confirm`, {
      method: "PUT",
    });
  },

  async setChapterCount(
    projectId: number,
    data: ChapterCountRequest
  ): Promise<void> {
    return request(`/api/projects/${projectId}/outline/chapter-count`, {
      method: "PUT",
      body: data,
    });
  },
};

// ==================== Chapter Outlines API ====================


export const chapterOutlinesApi = {
  async list(projectId: number): Promise<ChapterOutline[]> {
    return request<ChapterOutline[]>(`/api/projects/${projectId}/chapter-outlines`);
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
      { method: "PUT" }
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
};

// ==================== Quality Trend API ====================

export const qualityTrendApi = {
  /**
   * 获取项目所有章节的质量分数趋势
   */
  async get(projectId: number): Promise<{
    chapters: Array<{ chapter_number: number; scores: Record<string, number> }>;
    averages: Record<string, number>;
    alerts: string[];
  }> {
    return request(`/api/projects/${projectId}/chapters/quality-trend`);
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
  /** 自定义字段，用于灵感采集面板保存更多数据 */
  [key: string]: unknown;
}

export const collectedInfoApi = {
  async update(projectId: number, data: CollectedInfoUpdate): Promise<Outline> {
    return request<Outline>(`/api/projects/${projectId}/outline/collected-info`, {
      method: "PUT",
      body: data,
    });
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
    api_key?: string
    config_id?: number
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
  async checkHealth(configId: number): Promise<HealthCheckResponse> {
    return request(`/api/model_configs/${configId}/health`, {
      method: "POST",
    });
  },
};

// ==================== Volumes/Arcs API ====================

export const volumesApi = {
  /**
   * 获取项目的卷/弧结构
   */
  async list(projectId: number): Promise<Volume[]>
  {
    return request<Volume[]>(`/api/projects/${projectId}/volumes`)
  },

  /**
   * 更新卷信息
   */
  async updateVolume(projectId: number, volumeId: number, data: { title?: string; summary?: string }): Promise<Volume>
  {
    return request<Volume>(`/api/projects/${projectId}/volumes/${volumeId}`, {
      method: 'PUT',
      body: data,
    })
  },

  /**
   * 更新弧信息（含弧纲编辑）
   */
  async updateArc(projectId: number, arcId: number, data: ArcUpdate): Promise<Arc>
  {
    return request<Arc>(`/api/projects/${projectId}/arcs/${arcId}`, {
      method: 'PUT',
      body: data,
    })
  },

  /**
   * 确认弧纲（可同时编辑弧纲内容）
   */
  async confirmArcOutline(projectId: number, arcId: number, data?: ArcUpdate): Promise<Arc>
  {
    return request<Arc>(
      `/api/projects/${projectId}/arcs/${arcId}/confirm-outline`,
      { method: 'PUT', body: data || {} }
    )
  },

  /**
   * 更新章节摘要
   */
  async updateChapterSummary(projectId: number, chapterId: number, summary: string): Promise<void>
  {
    return request<void>(`/api/projects/${projectId}/chapters/${chapterId}/summary`, {
      method: 'PUT',
      body: { summary },
    })
  },
}
// ==================== Knowledge API ====================

// 扩展知识库 API 类型
declare module '@/lib/api' {
  interface KnowledgeApi {
    getTimeline(projectId: number, chapterStart?: number, chapterEnd?: number): Promise<any[]>;
  }
}

export const knowledgeApi = {
  /**
   * 获取故事种子
   */
  async getStorySeed(projectId: number): Promise<{ story_seed: string }> {
    return request<{ story_seed: string }>(`/api/projects/${projectId}/story-seed`)
  },

  /**
   * 更新故事种子
   */
  async updateStorySeed(projectId: number, storySeed: string): Promise<{ story_seed: string }> {
    return request<{ story_seed: string }>(`/api/projects/${projectId}/story-seed`, {
      method: 'PUT',
      body: { story_seed: storySeed },
    })
  },

  /**
   * 获取大纲摘要
   */
  async getOutlineSummary(projectId: number): Promise<{ outline: Record<string, unknown> }> {
    return request<{ outline: Record<string, unknown> }>(`/api/projects/${projectId}/outline-summary`)
  },

  /**
   * 获取世界观
   */
  async getWorldSetting(projectId: number): Promise<any>
  {
    return request<any>(`/api/projects/${projectId}/world-setting`)
  },

  /**
   * 更新世界观
   */
  async updateWorldSetting(projectId: number, data: Record<string, unknown>): Promise<Record<string, unknown>>
  {
    return request<any>(`/api/projects/${projectId}/world-setting`, {
      method: 'PUT',
      body: data,
    })
  },

  /**
   * 获取风格约束
   */
  async getStyleConstraints(projectId: number): Promise<any>
  {
    return request<any>(`/api/projects/${projectId}/style-constraints`)
  },

  /**
   * 获取项目角色列表
   */
  async getCharacters(projectId: number): Promise<any[]> {
    return request<any[]>(`/api/projects/${projectId}/characters`)
  },

  /**
   * 获取项目角色关系列表
   */
  async getRelations(projectId: number): Promise<any[]> {
    return request<any[]>(`/api/projects/${projectId}/relations`)
  },

  /**
   * 更新风格约束
   */
  async updateStyleConstraints(projectId: number, data: Record<string, unknown>): Promise<Record<string, unknown>>
  {
    return request<any>(`/api/projects/${projectId}/style-constraints`, {
      method: 'PUT',
      body: data,
    })
  },

  /**
   * 获取情节块列表
   */
  async getPlotBlocks(projectId: number): Promise<any[]>
  {
    return request<any[]>(`/api/projects/${projectId}/plot-blocks`)
  },

  /**
   * 获取支线列表
   */
  async getSubplots(projectId: number): Promise<any[]>
  {
    return request<any[]>(`/api/projects/${projectId}/subplots`)
  },

  /**
   * 获取伏笔列表
   */
  async getForeshadowings(projectId: number, status?: string): Promise<any[]>
  {
    const query = status ? `?status=${status}` : ''
    return request<any[]>(`/api/projects/${projectId}/foreshadowings${query}`)
  },

  /**
   * 获取时间线
   */
  async getTimeline(projectId: number): Promise<any[]>
  {
    return request<any[]>(`/api/projects/${projectId}/timeline`)
  },

  /**
   * 获取风格统计快照
   */
  async getStyleSnapshots(projectId: number, lastN?: number): Promise<any[]>
  {
    const query = lastN ? `?last_n=${lastN}` : ''
    return request<any[]>(`/api/projects/${projectId}/style-snapshots${query}`)
  },

  // ========== 情节块 CRUD ==========

  /**
   * 更新情节块
   */
  async updatePlotBlock(projectId: number, blockId: number, data: Record<string, unknown>): Promise<any>
  {
    return request<any>(`/api/projects/${projectId}/plot-blocks/${blockId}`, {
      method: 'PUT',
      body: data,
    })
  },

  /**
   * 删除情节块
   */
  async deletePlotBlock(projectId: number, blockId: number): Promise<void>
  {
    return request<void>(`/api/projects/${projectId}/plot-blocks/${blockId}`, {
      method: 'DELETE',
    })
  },

  // ========== 支线 CRUD ==========

  /**
   * 创建支线
   */
  async createSubplot(projectId: number, data: Record<string, unknown>): Promise<any>
  {
    return request<any>(`/api/projects/${projectId}/subplots`, {
      method: 'POST',
      body: data,
    })
  },

  /**
   * 更新支线
   */
  async updateSubplot(projectId: number, subplotId: number, data: Record<string, unknown>): Promise<any>
  {
    return request<any>(`/api/projects/${projectId}/subplots/${subplotId}`, {
      method: 'PUT',
      body: data,
    })
  },

  /**
   * 删除支线
   */
  async deleteSubplot(projectId: number, subplotId: number): Promise<void>
  {
    return request<void>(`/api/projects/${projectId}/subplots/${subplotId}`, {
      method: 'DELETE',
    })
  },

  // ========== 伏笔 CRUD ==========

  /**
   * 更新伏笔（内容+状态流转）
   */
  async updateForeshadowing(projectId: number, foreshadowingId: number, data: Record<string, unknown>): Promise<any>
  {
    return request<any>(`/api/projects/${projectId}/foreshadowings/${foreshadowingId}`, {
      method: 'PUT',
      body: data,
    })
  },
}
