/**
 * Workflow API Client - 工作流 API 客户端
 * 用于与 LangGraph 工作流后端交互
 */

import { getSessionToken, StreamOptions } from './api'
import { createSSEStream } from './sseParser'
import type {
  WorkflowStateResponse,
  WorkflowMode,
  WrittenChapter,
} from '@/types'

// 使用空字符串作为相对路径（通过 nginx 代理）或显式 URL
const API_BASE_URL = import.meta.env.VITE_API_URL || ''

// ==================== Helper Functions ====================

/**
 * 构建认证请求头
 */
function buildAuthHeaders(includeContentType = false): HeadersInit
{
  const headers: HeadersInit = {}

  if (includeContentType)
  {
    headers['Content-Type'] = 'application/json'
  }

  const token = getSessionToken()
  if (token)
  {
    const credentials = btoa(`${token}:`)
    headers['Authorization'] = `Basic ${credentials}`
  }

  return headers
}

/**
 * 发送请求并处理错误
 */
async function makeRequest<T = void>(
  url: string,
  method: 'GET' | 'POST' | 'PUT' | 'DELETE',
  defaultErrorMsg: string,
  body?: unknown
): Promise<T>
{
  const headers = buildAuthHeaders(!!body)

  const response = await fetch(`${API_BASE_URL}${url}`, {
    method,
    headers,
    body: body ? JSON.stringify(body) : undefined,
  })

  if (!response.ok)
  {
    const errorData = await response.json().catch(() => ({ detail: defaultErrorMsg }))
    throw new Error(errorData.detail || `HTTP ${response.status}`)
  }

  // 对于 POST/PUT/DELETE 返回 void，对于 GET 返回 JSON
  if (method === 'GET')
  {
    return response.json()
  }

  return undefined as T
}

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
   * 运行工作流（SSE 流式）- 使用统一的 SSE 处理器
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
    // 事件处理函数
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

    // 使用统一的 SSE 流处理器
    await createSSEStream(
      {
        url: `/api/projects/${projectId}/workflow/run`,
        method: 'POST',
        signal: options?.signal,
      },
      handleEvent,
      (error) => callbacks.onError?.(error)
    )
  },

  /**
   * 确认工作流当前节点
   * @param projectId - 项目 ID
   */
  async confirmWorkflow(projectId: number): Promise<void>
  {
    await makeRequest<void>(
      `/api/projects/${projectId}/workflow/confirm`,
      'POST',
      '确认失败'
    )
  },

  /**
   * 获取工作流状态
   * @param projectId - 项目 ID
   * @returns 工作流状态
   */
  async getWorkflowState(projectId: number): Promise<WorkflowStateResponse>
  {
    return makeRequest<WorkflowStateResponse>(
      `/api/projects/${projectId}/workflow/state`,
      'GET',
      '获取状态失败'
    )
  },

  /**
   * 取消工作流
   * @param projectId - 项目 ID
   */
  async cancelWorkflow(projectId: number): Promise<void>
  {
    await makeRequest<void>(
      `/api/projects/${projectId}/workflow/cancel`,
      'POST',
      '取消失败'
    )
  },

  /**
   * 设置工作流模式
   * @param projectId - 项目 ID
   * @param mode - 工作流模式
   */
  async setWorkflowMode(projectId: number, mode: WorkflowMode): Promise<void>
  {
    await makeRequest<void>(
      `/api/projects/${projectId}/workflow/mode`,
      'PUT',
      '设置模式失败',
      { mode }
    )
  },

  /**
   * 更新工作流阶段
   * @param projectId - 项目 ID
   * @param stage - 新阶段
   */
  async updateStage(projectId: number, stage: string): Promise<void>
  {
    await makeRequest<void>(
      `/api/projects/${projectId}/workflow/stage`,
      'PUT',
      '更新阶段失败',
      { stage }
    )
  },
}
