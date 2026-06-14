// frontend/src/lib/agentApi.ts

import { createSSEStream } from './sseParser'
import type { SSEData } from './sseParser'

/** Agent 聊天 SSE 回调 */
export interface AgentChatCallbacks {
  onAgentText?: (content: string) => void
  onToolStart?: (tool: string, args: Record<string, unknown>) => void
  onToolResult?: (tool: string, result: Record<string, unknown>) => void
  onImpactAssessment?: (data: Record<string, unknown>) => void
  onWarning?: (data: Record<string, unknown>) => void
  onAiUpdate?: (module: string, summary: string) => void
  onChapterPreview?: (data: Record<string, unknown>) => void
  onReview?: (data: Record<string, unknown>) => void
  onAgentDone?: () => void
  onAgentProgress?: (data: { progress_message: string; progress_percent: number }) => void
  onError?: (error: string) => void
}

/** Agent 聊天请求选项 */
export interface AgentChatOptions {
  modelConfigId?: number
  modelName?: string
  activeTab?: string
  activeMenuItem?: string
  currentChapterNumber?: number
  history?: Array<{ role: string; content: string }>
  signal?: AbortSignal
}

/**
 * 发送 Agent 聊天消息（SSE 流式）
 */
export async function sendAgentMessage(
  projectId: number,
  message: string,
  callbacks: AgentChatCallbacks,
  options?: AgentChatOptions
): Promise<void> {
  await createSSEStream(
    {
      url: `/api/projects/${projectId}/agent/chat`,
      method: 'POST',
      body: {
        message,
        model_config_id: options?.modelConfigId,
        model_name: options?.modelName,
        active_tab: options?.activeTab,
        active_menu_item: options?.activeMenuItem,
        current_chapter_number: options?.currentChapterNumber,
        history: options?.history,
      },
      signal: options?.signal,
    },
    (type: string, data: SSEData) => {
      const payload = (typeof data === 'object' && data !== null) ? data as Record<string, unknown> : {}

      switch (type) {
        case 'agent_text':
          callbacks.onAgentText?.(String(payload.content || ''))
          break
        case 'agent_tool_start':
          callbacks.onToolStart?.(String(payload.tool || ''), (payload.args as Record<string, unknown>) || {})
          break
        case 'agent_tool_result':
          callbacks.onToolResult?.(String(payload.tool || ''), (payload.result as Record<string, unknown>) || {})
          break
        case 'ai_update':
          callbacks.onAiUpdate?.(String(payload.module || ''), String(payload.summary || ''))
          break
        case 'agent_chapter_preview':
          callbacks.onChapterPreview?.(payload)
          break
        case 'agent_review':
          callbacks.onReview?.(payload)
          break
        case 'impact_assessment':
          callbacks.onImpactAssessment?.(payload)
          break
        case 'warning':
          callbacks.onWarning?.(payload)
          break
        case 'agent_progress':
          callbacks.onAgentProgress?.(payload as { progress_message: string; progress_percent: number })
          break
        case 'agent_done':
          callbacks.onAgentDone?.()
          break
        case 'error':
          callbacks.onError?.(String(payload.error || payload.message || '请求失败'))
          break
      }
    },
    (error: string) => {
      callbacks.onError?.(error)
    }
  )
}

/** 会话列表项 */
export interface ConversationItem {
  id: number
  title: string
  message_count: number
  is_active: boolean
  created_at: string | null
  updated_at: string | null
}

/** 会话及消息响应类型 */
export interface ConversationResponse {
  conversation_id: number
  title: string
  message_count: number
  messages: Array<{
    id: string
    role: 'user' | 'assistant'
    content: string
    segments: Array<{ type: string; content: string; data?: Record<string, unknown> }>
    actions?: Array<{
      tool: string
      status: 'running' | 'done' | 'error'
      description: string
      args?: Record<string, unknown>
      result?: Record<string, unknown>
    }>
    timestamp: number
  }>
}

/** 获取项目会话及消息 */
export async function fetchConversation(
  projectId: number,
  conversationId?: number,
  limit?: number,
  beforeId?: number,
): Promise<ConversationResponse> {
  const { getSessionToken } = await import('./api')
  const API_BASE_URL = import.meta.env.VITE_API_URL || ''
  const token = getSessionToken()

  const params = new URLSearchParams()
  if (conversationId) params.set('conversation_id', String(conversationId))
  if (limit) params.set('limit', String(limit))
  if (beforeId) params.set('before_id', String(beforeId))

  const query = params.toString()
  const url = `${API_BASE_URL}/api/projects/${projectId}/agent/conversation${query ? '?' + query : ''}`

  const headers: HeadersInit = {}
  if (token) {
    headers['Authorization'] = `Basic ${btoa(`${token}:`)}`
  }

  const res = await fetch(url, { headers, credentials: 'include' })
  if (!res.ok) {
    throw new Error(`Failed to fetch conversation: ${res.status}`)
  }
  return res.json()
}

/** 获取项目所有会话列表 */
export async function fetchConversations(projectId: number): Promise<ConversationItem[]> {
  const { getSessionToken } = await import('./api')
  const API_BASE_URL = import.meta.env.VITE_API_URL || ''
  const token = getSessionToken()

  const headers: HeadersInit = {}
  if (token) {
    headers['Authorization'] = `Basic ${btoa(`${token}:`)}`
  }

  const res = await fetch(
    `${API_BASE_URL}/api/projects/${projectId}/agent/conversations`,
    { headers, credentials: 'include' },
  )
  if (!res.ok) {
    throw new Error(`Failed to fetch conversations: ${res.status}`)
  }
  return res.json()
}

/** 新建会话 */
export async function createConversation(projectId: number): Promise<ConversationItem> {
  const { getSessionToken } = await import('./api')
  const API_BASE_URL = import.meta.env.VITE_API_URL || ''
  const token = getSessionToken()

  const headers: HeadersInit = { 'Content-Type': 'application/json' }
  if (token) {
    headers['Authorization'] = `Basic ${btoa(`${token}:`)}`
  }

  const res = await fetch(
    `${API_BASE_URL}/api/projects/${projectId}/agent/conversations`,
    { method: 'POST', headers, credentials: 'include' },
  )
  if (!res.ok) {
    const data = await res.json().catch(() => ({}))
    throw new Error(data.detail || `Failed to create conversation: ${res.status}`)
  }
  return res.json()
}

/** 切换到指定会话 */
export async function activateConversation(projectId: number, conversationId: number): Promise<ConversationItem> {
  const { getSessionToken } = await import('./api')
  const API_BASE_URL = import.meta.env.VITE_API_URL || ''
  const token = getSessionToken()

  const headers: HeadersInit = { 'Content-Type': 'application/json' }
  if (token) {
    headers['Authorization'] = `Basic ${btoa(`${token}:`)}`
  }

  const res = await fetch(
    `${API_BASE_URL}/api/projects/${projectId}/agent/conversations/${conversationId}/activate`,
    { method: 'POST', headers, credentials: 'include' },
  )
  if (!res.ok) {
    const data = await res.json().catch(() => ({}))
    throw new Error(data.detail || `Failed to activate conversation: ${res.status}`)
  }
  return res.json()
}

/** 重命名会话 */
export async function renameConversation(projectId: number, conversationId: number, title: string): Promise<ConversationItem> {
  const { getSessionToken } = await import('./api')
  const API_BASE_URL = import.meta.env.VITE_API_URL || ''
  const token = getSessionToken()

  const headers: HeadersInit = { 'Content-Type': 'application/json' }
  if (token) {
    headers['Authorization'] = `Basic ${btoa(`${token}:`)}`
  }

  const res = await fetch(
    `${API_BASE_URL}/api/projects/${projectId}/agent/conversations/${conversationId}`,
    {
      method: 'PUT',
      headers,
      credentials: 'include',
      body: JSON.stringify({ title }),
    },
  )
  if (!res.ok) {
    const data = await res.json().catch(() => ({}))
    throw new Error(data.detail || `Failed to rename conversation: ${res.status}`)
  }
  return res.json()
}

/** 删除指定会话 */
export async function deleteConversation(projectId: number, conversationId: number): Promise<void> {
  const { getSessionToken } = await import('./api')
  const API_BASE_URL = import.meta.env.VITE_API_URL || ''
  const token = getSessionToken()

  const headers: HeadersInit = {}
  if (token) {
    headers['Authorization'] = `Basic ${btoa(`${token}:`)}`
  }

  const res = await fetch(
    `${API_BASE_URL}/api/projects/${projectId}/agent/conversations/${conversationId}`,
    { method: 'DELETE', headers, credentials: 'include' },
  )
  if (!res.ok) {
    const data = await res.json().catch(() => ({}))
    throw new Error(data.detail || `Failed to delete conversation: ${res.status}`)
  }
}
