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
} from "@/types";

// ==================== Configuration ====================

const API_BASE_URL = import.meta.env.VITE_API_URL || "http://localhost:8000";

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

interface RequestOptions {
  method?: "GET" | "POST" | "PUT" | "DELETE";
  body?: unknown;
  requireAuth?: boolean;
}

async function request<T>(
  endpoint: string,
  options: RequestOptions = {}
): Promise<T> {
  const { method = "GET", body, requireAuth = true } = options;

  const headers: HeadersInit = {
    "Content-Type": "application/json",
  };

  // Use HTTP Basic auth with session token as username
  if (requireAuth) {
    const token = getSessionToken();
    if (token) {
      // HTTP Basic: base64(username:password) - we use token as username with empty password
      const credentials = btoa(`${token}:`);
      headers["Authorization"] = `Basic ${credentials}`;
    }
  }

  const response = await fetch(`${API_BASE_URL}${endpoint}`, {
    method,
    headers,
    body: body ? JSON.stringify(body) : undefined,
  });

  if (!response.ok) {
    const error: ApiError = await response.json().catch(() => ({
      detail: `HTTP ${response.status}: ${response.statusText}`,
    }));
    throw new Error(error.detail);
  }

  // Handle 204 No Content
  if (response.status === 204) {
    return undefined as T;
  }

  return response.json();
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

export const chapterOutlinesApi = {
  async list(projectId: number): Promise<ChapterOutline[]> {
    return request<ChapterOutline[]>(`/api/projects/${projectId}/chapter-outlines`);
  },

  async create(projectId: number): Promise<ChapterOutline[]> {
    return request<ChapterOutline[]>(`/api/projects/${projectId}/chapter-outlines`, {
      method: "POST",
    });
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
    return request<ChatResponse>(`/api/projects/${projectId}/chat`, {
      method: "POST",
      body: message,
    });
  },
};