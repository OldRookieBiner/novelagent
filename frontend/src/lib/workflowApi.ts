/**
 * Workflow API Client - 工作流 API 客户端
 * 用于与 LangGraph 工作流后端交互
 */

import { getSessionToken, StreamOptions } from './api'
import { parseSSEEventBlock, parseSSEData } from './sseParser'
import type {
  WorkflowStateResponse,
  WorkflowMode,
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
     * 处理单个 SSE 事件
     */
    const handleEvent = (eventType: string, data: unknown) =>
    {
      switch (eventType)
      {
        case 'node_start':
          callbacks.onNodeStart?.(data as string)
          break

        case 'node_done':
          {
            const nodeData = data as { node: string; data: unknown }
            callbacks.onNodeDone?.(nodeData.node, nodeData.data)
          }
          break

        case 'chunk':
          callbacks.onChunk?.(data as string)
          break

        case 'checkpoint':
          callbacks.onCheckpoint?.(data as WorkflowStateResponse)
          break

        case 'waiting':
          callbacks.onWaiting?.(data as string)
          break

        case 'done':
          callbacks.onDone?.(data as { stage: string; chapters: WrittenChapter[] })
          break

        case 'error':
          callbacks.onError?.(data as string)
          break

        default:
          // 忽略未知事件类型
          break
      }
    }

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

        // 使用共享解析器解析事件
        const event = parseSSEEventBlock(eventBlock)
        if (event.data)
        {
          // 解析数据（支持 JSON 或纯字符串）
          const parsedData = parseSSEData(event.data)
          handleEvent(event.type, parsedData)
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

  /**
   * 更新工作流阶段
   * @param projectId - 项目 ID
   * @param stage - 新阶段
   */
  async updateStage(projectId: number, stage: string): Promise<void>
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

    const response = await fetch(`${API_BASE_URL}/api/projects/${projectId}/workflow/stage`, {
      method: 'PUT',
      headers,
      body: JSON.stringify({ stage }),
    })

    if (!response.ok)
    {
      const errorData = await response.json().catch(() => ({ detail: '更新阶段失败' }))
      throw new Error(errorData.detail || `HTTP ${response.status}`)
    }
  },
}
