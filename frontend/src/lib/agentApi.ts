// frontend/src/lib/agentApi.ts

import { createSSEStream } from './sseParser'
import type { SSEData } from './sseParser'

/** Agent 聊天 SSE 回调 */
export interface AgentChatCallbacks {
  onAgentText?: (content: string) => void
  onToolStart?: (tool: string, args: Record<string, unknown>) => void
  onToolResult?: (tool: string, result: Record<string, unknown>) => void
  onAiUpdate?: (module: string, summary: string) => void
  onChapterPreview?: (data: Record<string, unknown>) => void
  onReview?: (data: Record<string, unknown>) => void
  onAgentDone?: () => void
  onError?: (error: string) => void
}

/** Agent 聊天请求选项 */
export interface AgentChatOptions {
  modelConfigId?: number
  activeTab?: string
  activeMenuItem?: string
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
        active_tab: options?.activeTab,
        active_menu_item: options?.activeMenuItem,
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
