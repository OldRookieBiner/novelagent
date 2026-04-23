/**
 * Workflow API Client - 工作流 API 客户端
 * 用于与 LangGraph 工作流后端交互
 */

import { getSessionToken, StreamOptions } from './api'
import type {
  WorkflowStateResponse,
  WorkflowMode,
  WorkflowSSEEvent,
  WrittenChapter,
} from '@/types'

// 使用空字符串作为相对路径（通过 nginx 代理）或显式 URL
const API_BASE_URL = import.meta.env.VITE_API_URL || ''

// ==================== Workflow API ====================

/**
 * SSE 流式回调
 */
export interface WorkflowStreamCallbacks {
  // 节点开始
  onNodeStart?: (nodeName: string) => void
  // 节点完成
  onNodeDone?: (nodeName: string, data: unknown) => void
  // 数据块
  onChunk?: (chunk: string) => void
  // 检查点保存
  onCheckpoint?: (state: WorkflowStateResponse) => void
  // 等待确认
  onWaiting?: (confirmationType: string) => void
  // 完成
  onDone?: (result: { stage: string; chapters: WrittenChapter[] }) => void
  // 错误
  onError?: (error: string) => void
}

export const workflowApi = {
  /**
   * 运行工作流（SSE 流式）
   * @param projectId - 项目 ID
   * @param callbacks - 回调函数
   * @param options - 流式请求选项（包括 AbortSignal 用于取消）
   */
  async runWorkflow(
    projectId: number,
    callbacks: WorkflowStreamCallbacks,
    options?: StreamOptions
  ): Promise<void>
  {
    const token = getSessionToken()
    const headers: HeadersInit = {}

    if (token)
    {
      const credentials = btoa(`${token}:`)
      headers['Authorization'] = `Basic ${credentials}`
    }

    const response = await fetch(`${API_BASE_URL}/api/projects/${projectId}/workflow/run`, {
      method: 'POST',
      headers,
      signal: options?.signal,
    })

    if (!response.ok)
    {
      const errorData = await response.json().catch(() => ({ detail: '运行工作流失败' }))
      callbacks.onError?.(errorData.detail || `HTTP ${response.status}`)
      return
    }

    const reader = response.body?.getReader()
    if (!reader)
    {
      callbacks.onError?.('无法获取数据流')
      return
    }

    const decoder = new TextDecoder()
    let buffer = ''

    /**
     * 处理缓冲区中的完整事件
     */
    const processBuffer = (buf: string): string =>
    {
      let remaining = buf

      // 处理所有完整的 SSE 事件（以 \n\n 结尾）
      while (true)
      {
        const eventEndIndex = remaining.indexOf('\n\n')
        if (eventEndIndex === -1)
        {
          // 没有完整事件，保留在缓冲区
          break
        }

        const eventBlock = remaining.slice(0, eventEndIndex)
        remaining = remaining.slice(eventEndIndex + 2)

        // 解析事件行
        const lines = eventBlock.split('\n')
        let eventType = 'message'
        let eventData = ''

        for (const line of lines)
        {
          if (line.startsWith('event:'))
          {
            eventType = line.slice(6).trim()
          }
          else if (line.startsWith('data:'))
          {
            eventData += line.slice(5)
          }
        }

        if (eventData)
        {
          try
          {
            const parsed = JSON.parse(eventData) as WorkflowSSEEvent

            switch (eventType)
            {
              case 'node_start':
                callbacks.onNodeStart?.(parsed.data as string)
                break

              case 'node_done':
                callbacks.onNodeDone?.(
                  (parsed.data as { node: string; data: unknown }).node,
                  (parsed.data as { node: string; data: unknown }).data
                )
                break

              case 'chunk':
                callbacks.onChunk?.(parsed.data as string)
                break

              case 'checkpoint':
                callbacks.onCheckpoint?.(parsed.data as WorkflowStateResponse)
                break

              case 'waiting':
                callbacks.onWaiting?.(parsed.data as string)
                break

              case 'done':
                callbacks.onDone?.(parsed.data as { stage: string; chapters: WrittenChapter[] })
                break

              case 'error':
                callbacks.onError?.(parsed.data as string)
                break

              default:
                // 忽略未知事件类型
                break
            }
          }
          catch
          {
            // 尝试直接解析字符串数据
            if (eventType === 'chunk')
            {
              callbacks.onChunk?.(eventData)
            }
            else if (eventType === 'error')
            {
              callbacks.onError?.(eventData)
            }
          }
        }
      }

      return remaining
    }

    try
    {
      while (true)
      {
        const { done, value } = await reader.read()

        if (done)
        {
          // 处理剩余的缓冲区
          if (buffer.trim())
          {
            processBuffer(buffer)
          }
          break
        }

        buffer += decoder.decode(value, { stream: true })
        buffer = processBuffer(buffer)
      }
    }
    catch (err)
    {
      // 用户主动取消，不触发错误回调
      if (err instanceof Error && err.name === 'AbortError')
      {
        return
      }
      callbacks.onError?.(err instanceof Error ? err.message : '未知错误')
    }
  },

  /**
   * 确认工作流当前节点
   * @param projectId - 项目 ID
   */
  async confirmWorkflow(projectId: number): Promise<void>
  {
    const token = getSessionToken()
    const headers: HeadersInit = {
      'Content-Type': 'application/json',
    }

    if (token)
    {
      const credentials = btoa(`${token}:`)
      headers['Authorization'] = `Basic ${credentials}`
    }

    const response = await fetch(`${API_BASE_URL}/api/projects/${projectId}/workflow/confirm`, {
      method: 'POST',
      headers,
    })

    if (!response.ok)
    {
      const errorData = await response.json().catch(() => ({ detail: '确认失败' }))
      throw new Error(errorData.detail || `HTTP ${response.status}`)
    }
  },

  /**
   * 获取工作流状态
   * @param projectId - 项目 ID
   * @returns 工作流状态
   */
  async getWorkflowState(projectId: number): Promise<WorkflowStateResponse>
  {
    const token = getSessionToken()
    const headers: HeadersInit = {}

    if (token)
    {
      const credentials = btoa(`${token}:`)
      headers['Authorization'] = `Basic ${credentials}`
    }

    const response = await fetch(`${API_BASE_URL}/api/projects/${projectId}/workflow/state`, {
      method: 'GET',
      headers,
    })

    if (!response.ok)
    {
      const errorData = await response.json().catch(() => ({ detail: '获取状态失败' }))
      throw new Error(errorData.detail || `HTTP ${response.status}`)
    }

    return response.json()
  },

  /**
   * 取消工作流
   * @param projectId - 项目 ID
   */
  async cancelWorkflow(projectId: number): Promise<void>
  {
    const token = getSessionToken()
    const headers: HeadersInit = {}

    if (token)
    {
      const credentials = btoa(`${token}:`)
      headers['Authorization'] = `Basic ${credentials}`
    }

    const response = await fetch(`${API_BASE_URL}/api/projects/${projectId}/workflow/cancel`, {
      method: 'POST',
      headers,
    })

    if (!response.ok)
    {
      const errorData = await response.json().catch(() => ({ detail: '取消失败' }))
      throw new Error(errorData.detail || `HTTP ${response.status}`)
    }
  },

  /**
   * 设置工作流模式
   * @param projectId - 项目 ID
   * @param mode - 工作流模式
   */
  async setWorkflowMode(projectId: number, mode: WorkflowMode): Promise<void>
  {
    const token = getSessionToken()
    const headers: HeadersInit = {
      'Content-Type': 'application/json',
    }

    if (token)
    {
      const credentials = btoa(`${token}:`)
      headers['Authorization'] = `Basic ${credentials}`
    }

    const response = await fetch(`${API_BASE_URL}/api/projects/${projectId}/workflow/mode`, {
      method: 'PUT',
      headers,
      body: JSON.stringify({ mode }),
    })

    if (!response.ok)
    {
      const errorData = await response.json().catch(() => ({ detail: '设置模式失败' }))
      throw new Error(errorData.detail || `HTTP ${response.status}`)
    }
  },
}
