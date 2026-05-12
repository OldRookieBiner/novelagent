/**
 * Workflow API Client - 工作流 API 客户端
 * 用于与 LangGraph 工作流后端交互
 */

import { getSessionToken, StreamOptions } from './api'
import { createSSEStream, type SSEData } from './sseParser'
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
   * @param options - 流式请求选项（包括 AbortSignal 用于取消，llmConfigId 指定模型配置，modelName 指定模型名）
   */
  async runWorkflow(
    projectId: number,
    callbacks: WorkflowStreamCallbacks,
    options?: StreamOptions & { llmConfigId?: number; modelName?: string }
  ): Promise<void>
  {
    // 事件处理函数
    const handleEvent = (eventType: string, data: SSEData) =>
    {
      switch (eventType)
      {
        case 'node_start':
          {
            const nodeData = data as unknown as { node: string; message?: string }
            callbacks.onNodeStart?.(nodeData.node)
          }
          break

        case 'node_done':
          {
            const nodeData = data as unknown as { node: string; state: unknown }
            callbacks.onNodeDone?.(nodeData.node, nodeData.state)
          }
          break

        case 'chunk':
          {
            // 后端发送 {"content": "文本"} 格式，提取 content 字段
            const chunkData = data as unknown as { content: string } | string
            const chunkText = typeof chunkData === 'string' ? chunkData : chunkData.content
            if (chunkText)
            {
              callbacks.onChunk?.(chunkText)
            }
          }
          break

        case 'checkpoint':
          callbacks.onCheckpoint?.(data as unknown as WorkflowStateResponse)
          break

        case 'waiting':
          {
            const waitingData = data as unknown as { node: string; confirmation_type: string }
            callbacks.onWaiting?.(waitingData.confirmation_type)
          }
          break

        case 'done':
          callbacks.onDone?.(data as unknown as { stage: string; chapters: WrittenChapter[] })
          break

        case 'error':
          {
            // 兼容后端两种 error data 格式：
            // 1. 对象：{"error": "大纲生成失败，请重试"}
            // 2. 字符串：直接的消息文本
            const errorData = data as unknown as { error?: string } | string
            const errorMsg = typeof errorData === 'object' && errorData !== null
              ? (errorData.error || JSON.stringify(errorData))
              : String(errorData)
            callbacks.onError?.(errorMsg)
          }
          break

        default:
          // 忽略未知事件类型
          break
      }
    }

    // 使用统一的 SSE 流处理器
    const requestBody: Record<string, unknown> = {}
    if (options?.llmConfigId)
    {
      requestBody.llm_config_id = options.llmConfigId
    }
    if (options?.modelName)
    {
      requestBody.llm_model_name = options.modelName
    }
    await createSSEStream(
      {
        url: `/api/projects/${projectId}/workflow/run`,
        method: 'POST',
        body: Object.keys(requestBody).length > 0 ? requestBody : undefined,
        signal: options?.signal,
      },
      handleEvent,
      (error) => callbacks.onError?.(error)
    )
  },

  /**
   * 重新规划工作流（SSE 流式）
   * 清理旧的大纲/人物/关系数据，重新生成规划
   * @param projectId - 项目 ID
   * @param callbacks - 回调函数
   * @param options - 流式请求选项
   */
  async replanWorkflow(
    projectId: number,
    callbacks: WorkflowStreamCallbacks,
    options?: StreamOptions & { llmConfigId?: number; modelName?: string }
  ): Promise<void>
  {
    // 事件处理函数
    const handleEvent = (eventType: string, data: SSEData) =>
    {
      switch (eventType)
      {
        case 'node_start':
        {
          const nodeData = data as unknown as { node: string; message?: string }
          callbacks.onNodeStart?.(nodeData.node)
        }
        break

        case 'node_done':
        {
          const nodeData = data as unknown as { node: string; state: unknown }
          callbacks.onNodeDone?.(nodeData.node, nodeData.state)
        }
        break

        case 'chunk':
        {
          const chunkData = data as unknown as { content: string } | string
          const chunkText = typeof chunkData === 'string' ? chunkData : chunkData.content
          if (chunkText)
          {
            callbacks.onChunk?.(chunkText)
          }
        }
        break

        case 'checkpoint':
          callbacks.onCheckpoint?.(data as unknown as WorkflowStateResponse)
          break

        case 'waiting':
        {
          const waitingData = data as unknown as { node: string; confirmation_type: string }
          callbacks.onWaiting?.(waitingData.confirmation_type)
        }
        break

        case 'done':
          callbacks.onDone?.(data as unknown as { stage: string; chapters: WrittenChapter[] })
          break

        case 'error':
        {
          const errorData = data as unknown as { error?: string } | string
          const errorMsg = typeof errorData === 'object' && errorData !== null
            ? (errorData.error || JSON.stringify(errorData))
            : String(errorData)
          callbacks.onError?.(errorMsg)
        }
        break

        default:
          break
      }
    }

    const requestBody: Record<string, unknown> = {}
    if (options?.llmConfigId)
    {
      requestBody.llm_config_id = options.llmConfigId
    }
    if (options?.modelName)
    {
      requestBody.llm_model_name = options.modelName
    }

    await createSSEStream(
      {
        url: `/api/projects/${projectId}/workflow/replan`,
        method: 'POST',
        body: Object.keys(requestBody).length > 0 ? requestBody : undefined,
        signal: options?.signal,
      },
      handleEvent,
      (error) => callbacks.onError?.(error)
    )
  },

  /**
   * 重新生成章节大纲（SSE 流式）
   * 保留大纲/人物/关系，仅重新生成章节大纲
   * @param projectId - 项目 ID
   * @param callbacks - 回调函数
   * @param options - 流式请求选项
   */
  async replanChapterOutlines(
    projectId: number,
    callbacks: {
      onProgress?: (data: { chapter_number: number; total: number; chapter: { chapter_number: number; title: string; scene: string; characters: string; plot: string; conflict: string; ending: string; target_words: number } }) => void
      onDone?: (data: { total: number; stage: string }) => void
      onError?: (error: string) => void
    },
    options?: StreamOptions & { llmConfigId?: number; modelName?: string }
  ): Promise<void>
  {
    const handleEvent = (eventType: string, data: SSEData) =>
    {
      switch (eventType)
      {
        case 'progress':
        {
          const progressData = data as unknown as {
            chapter_number: number
            total: number
            chapter: {
              chapter_number: number
              title: string
              scene: string
              characters: string
              plot: string
              conflict: string
              ending: string
              target_words: number
            }
          }
          callbacks.onProgress?.(progressData)
        }
        break

        case 'done':
          callbacks.onDone?.(data as unknown as { total: number; stage: string })
          break

        case 'error':
        {
          const errorData = data as unknown as { error?: string } | string
          const errorMsg = typeof errorData === 'object' && errorData !== null
            ? (errorData.error || JSON.stringify(errorData))
            : String(errorData)
          callbacks.onError?.(errorMsg)
        }
        break

        default:
          break
      }
    }

    const requestBody: Record<string, unknown> = {}
    if (options?.llmConfigId)
    {
      requestBody.llm_config_id = options.llmConfigId
    }
    if (options?.modelName)
    {
      requestBody.llm_model_name = options.modelName
    }

    await createSSEStream(
      {
        url: `/api/projects/${projectId}/workflow/replan-chapter-outlines`,
        method: 'POST',
        body: Object.keys(requestBody).length > 0 ? requestBody : undefined,
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
