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
  limit?: number,
  beforeId?: number,
): Promise<ConversationResponse> {
  const { getSessionToken } = await import('./api')
  const API_BASE_URL = import.meta.env.VITE_API_URL || ''
  const token = getSessionToken()

  const params = new URLSearchParams()
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

/** 清空项目会话 */
export async function deleteConversation(projectId: number): Promise<void> {
  const { getSessionToken } = await import('./api')
  const API_BASE_URL = import.meta.env.VITE_API_URL || ''
  const token = getSessionToken()

  const headers: HeadersInit = {}
  if (token) {
    headers['Authorization'] = `Basic ${btoa(`${token}:`)}`
  }

  const res = await fetch(
    `${API_BASE_URL}/api/projects/${projectId}/agent/conversation`,
    { method: 'DELETE', headers, credentials: 'include' },
  )
  if (!res.ok) {
    throw new Error(`Failed to clear conversation: ${res.status}`)
  }
}
