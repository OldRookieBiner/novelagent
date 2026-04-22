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
  HealthCheckResponse,
} from "@/types";

// ==================== Configuration ====================

// Use empty string for relative path (proxied through nginx) or explicit URL
const API_BASE_URL = import.meta.env.VITE_API_URL || "";

// ==================== Session Token Management ====================

let sessionToken: string | null = null;

export function setSessionToken(token: string | null): void {
  sessionToken = token;
  if (token) {
    localStorage.setItem("session_token", token);
  } else {
    localStorage.removeItem("session_token");
  }
}

export function getSessionToken(): string | null {
  if (!sessionToken) {
    sessionToken = localStorage.getItem("session_token");
  }
  return sessionToken;
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
   * Generate outline with streaming - calls callbacks for each chunk
   * @param projectId - 项目 ID
   * @param callbacks - 回调函数
   * @param options - 流式请求选项（包括 AbortSignal 用于取消）
   */
  async createStream(
    projectId: number,
    callbacks: OutlineStreamCallbacks,
    options?: StreamOptions
  ): Promise<void> {
    const token = getSessionToken();
    const headers: HeadersInit = {};

    if (token) {
      const credentials = btoa(`${token}:`);
      headers["Authorization"] = `Basic ${credentials}`;
    }

    const response = await fetch(`${API_BASE_URL}/api/projects/${projectId}/outline`, {
      method: "POST",
      headers,
      signal: options?.signal,  // 传递 AbortSignal
    });

    if (!response.ok) {
      const errorData = await response.json().catch(() => ({ detail: '生成失败' }));
      callbacks.onError(errorData.detail || `HTTP ${response.status}`);
      return;
    }

    const reader = response.body?.getReader();
    if (!reader) {
      callbacks.onError('无法获取数据流');
      return;
    }

    const decoder = new TextDecoder();
    let buffer = '';

    // Process SSE buffer - returns remaining unprocessed buffer
    const processBuffer = (buf: string): string => {
      let remaining = buf;

      // Process all complete SSE events (ending with \n\n)
      while (true) {
        const eventEndIndex = remaining.indexOf('\n\n');
        if (eventEndIndex === -1) {
          // No complete event, keep in buffer
          break;
        }

        const eventBlock = remaining.slice(0, eventEndIndex);
        remaining = remaining.slice(eventEndIndex + 2);

        // Parse event lines
        const lines = eventBlock.split('\n');
        let eventType = 'message';
        let eventData = '';

        for (const line of lines) {
          if (line.startsWith('event:')) {
            eventType = line.slice(6).trim();
          } else if (line.startsWith('data:')) {
            eventData += line.slice(5);
          }
        }

        if (eventData) {
          if (eventType === 'done') {
            // Completion event - parse JSON
            try {
              const result = JSON.parse(eventData) as OutlineStreamResult;
              callbacks.onDone(result);
            } catch (e) {
              callbacks.onError(`解析完成数据失败: ${eventData.slice(0, 100)}...`);
            }
          } else if (eventType === 'error') {
            callbacks.onError(eventData);
          } else {
            // Regular chunk - decode and forward
            try {
              const chunk = JSON.parse(eventData);
              callbacks.onChunk(chunk);
            } catch {
              // If not valid JSON, treat as raw text
              callbacks.onChunk(eventData);
            }
          }
        }
      }

      return remaining;
    };

    try {
      while (true) {
        const { done, value } = await reader.read();

        if (done) {
          // Process any remaining buffer
          if (buffer.trim()) {
            processBuffer(buffer);
          }
          break;
        }

        buffer += decoder.decode(value, { stream: true });
        buffer = processBuffer(buffer);
      }
    } catch (err) {
      // 用户主动取消，不触发错误回调
      if (err instanceof Error && err.name === 'AbortError') {
        return;
      }
      callbacks.onError(err instanceof Error ? err.message : '未知错误');
    }
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
   * Generate chapter outlines with SSE streaming - one by one
   * @param projectId - 项目 ID
   * @param callbacks - 回调函数
   * @param options - 流式请求选项（包括 AbortSignal 用于取消）
   */
  async createStream(
    projectId: number,
    callbacks: ChapterOutlineStreamCallbacks,
    options?: StreamOptions
  ): Promise<void> {
    const token = getSessionToken();
    const headers: HeadersInit = {};

    if (token) {
      const credentials = btoa(`${token}:`);
      headers["Authorization"] = `Basic ${credentials}`;
    }

    const response = await fetch(`${API_BASE_URL}/api/projects/${projectId}/chapter-outlines`, {
      method: "POST",
      headers,
      signal: options?.signal,  // 传递 AbortSignal
    });

    if (!response.ok) {
      const errorData = await response.json().catch(() => ({ detail: '生成失败' }));
      callbacks.onError(errorData.detail || `HTTP ${response.status}`);
      return;
    }

    const reader = response.body?.getReader();
    if (!reader) {
      callbacks.onError('无法获取数据流');
      return;
    }

    const decoder = new TextDecoder();
    let buffer = '';

    // Process SSE buffer - returns remaining unprocessed buffer
    const processBuffer = (buf: string): string => {
      let remaining = buf;

      // Process all complete SSE events (ending with \n\n)
      while (true) {
        const eventEndIndex = remaining.indexOf('\n\n');
        if (eventEndIndex === -1) {
          // No complete event, keep in buffer
          break;
        }

        const eventBlock = remaining.slice(0, eventEndIndex);
        remaining = remaining.slice(eventEndIndex + 2);

        // Parse event lines
        const lines = eventBlock.split('\n');
        let eventType = 'message';
        let eventData = '';

        for (const line of lines) {
          if (line.startsWith('event:')) {
            eventType = line.slice(6).trim();
          } else if (line.startsWith('data:')) {
            eventData += line.slice(5);
          }
        }

        if (eventData) {
          if (eventType === 'progress') {
            // Progress event
            try {
              const result = JSON.parse(eventData);
              callbacks.onProgress(result.chapter_number, result.total, result.chapter);
            } catch {
              console.error('Failed to parse progress event');
            }
          } else if (eventType === 'done') {
            // Completion event
            try {
              const result = JSON.parse(eventData);
              callbacks.onDone(result.total, result.stage);
            } catch {
              callbacks.onError('解析完成数据失败');
            }
          } else if (eventType === 'error') {
            callbacks.onError(eventData);
          }
        }
      }

      return remaining;
    };

    try {
      while (true) {
        const { done, value } = await reader.read();

        if (done) {
          // Process any remaining buffer
          if (buffer.trim()) {
            processBuffer(buffer);
          }
          break;
        }

        buffer += decoder.decode(value, { stream: true });
        buffer = processBuffer(buffer);
      }
    } catch (err) {
      // 用户主动取消，不触发错误回调
      if (err instanceof Error && err.name === 'AbortError') {
        return;
      }
      callbacks.onError(err instanceof Error ? err.message : '未知错误');
    }
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
  async list(): Promise<ModelConfigListResponse> {
    return request<ModelConfigListResponse>("/api/model-configs/");
  },

  /**
   * 测试模型连接（不创建配置）
   */
  async testConnection(data: ModelConfigCreate): Promise<HealthCheckResponse> {
    return request<HealthCheckResponse>("/api/model-configs/test", {
      method: "POST",
      body: data,
    });
  },

  async create(data: ModelConfigCreate): Promise<ModelConfig> {
    return request<ModelConfig>("/api/model-configs/", {
      method: "POST",
      body: data,
    });
  },

  async update(configId: number, data: ModelConfigUpdate): Promise<ModelConfig> {
    return request<ModelConfig>(`/api/model-configs/${configId}`, {
      method: "PUT",
      body: data,
    });
  },

  async delete(configId: number): Promise<{ success: boolean }> {
    return request<{ success: boolean }>(`/api/model-configs/${configId}`, {
      method: "DELETE",
    });
  },

  async checkHealth(configId: number): Promise<HealthCheckResponse> {
    return request<HealthCheckResponse>(`/api/model-configs/${configId}/health`, {
      method: "POST",
    });
  },

  async setDefault(configId: number): Promise<ModelConfig> {
    return request<ModelConfig>(`/api/model-configs/${configId}/default`, {
      method: "PUT",
    });
  },
};