/**
 * workflowApi 测试
 * 测试工作流 API 客户端，包括 SSE 流式处理
 */

import { describe, it, expect, vi, beforeEach } from 'vitest'

// Mock fetch
const mockFetch = vi.fn()
;(globalThis as any).fetch = mockFetch

// Mock localStorage
const localStorageStore: Record<string, string> = {}
vi.stubGlobal('localStorage', {
  getItem: (key: string) => localStorageStore[key] ?? null,
  setItem: (key: string, value: string) => { localStorageStore[key] = value },
  removeItem: (key: string) => { delete localStorageStore[key] },
  clear: () => { Object.keys(localStorageStore).forEach(k => delete localStorageStore[k]) },
})

/**
 * 创建模拟的 SSE ReadableStream
 * @param events - SSE 事件数组 [{ type, data }]
 */
function createMockSSEStream(events: Array<{ type: string; data: unknown }>): ReadableStream<Uint8Array>
{
  const encoder = new TextEncoder()
  let index = 0

  return new ReadableStream<Uint8Array>({
    pull(controller)
    {
      if (index < events.length)
      {
        const event = events[index]
        const eventStr = `event: ${event.type}\ndata: ${JSON.stringify(event.data)}\n\n`
        controller.enqueue(encoder.encode(eventStr))
        index++
      }
      else
      {
        controller.close()
      }
    },
  })
}

describe('WorkflowApi', () =>
{
  beforeEach(() =>
  {
    mockFetch.mockReset()
    Object.keys(localStorageStore).forEach(k => delete localStorageStore[k])
  })

  describe('getWorkflowState', () =>
  {
    it('获取工作流状态成功', async () =>
    {
      const mockState = {
        project_id: 1,
        stage: 'outline',
        has_checkpoint: true,
        current_chapter: 0,
        total_chapters: 10,
        written_chapters_count: 0,
        waiting_for_confirmation: true,
        confirmation_type: 'outline',
        updated_at: '2026-04-23T10:00:00Z',
      }

      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve(mockState),
      })

      const { workflowApi } = await import('@/lib/workflowApi')
      const result = await workflowApi.getWorkflowState(1)

      expect(result.project_id).toBe(1)
      expect(result.stage).toBe('outline')
      expect(result.has_checkpoint).toBe(true)
      expect(result.waiting_for_confirmation).toBe(true)
    })

    it('无检查点时返回正确状态', async () =>
    {
      const mockState = {
        project_id: 1,
        stage: 'inspiration',
        has_checkpoint: false,
        current_chapter: 0,
        total_chapters: 0,
        written_chapters_count: 0,
        waiting_for_confirmation: false,
        confirmation_type: null,
        updated_at: null,
      }

      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve(mockState),
      })

      const { workflowApi } = await import('@/lib/workflowApi')
      const result = await workflowApi.getWorkflowState(1)

      expect(result.has_checkpoint).toBe(false)
      expect(result.waiting_for_confirmation).toBe(false)
    })

    it('请求失败时抛出错误', async () =>
    {
      mockFetch.mockResolvedValueOnce({
        ok: false,
        status: 404,
        json: () => Promise.resolve({ detail: '项目不存在' }),
      })

      const { workflowApi } = await import('@/lib/workflowApi')

      await expect(workflowApi.getWorkflowState(999)).rejects.toThrow('项目不存在')
    })
  })

  describe('confirmWorkflow', () =>
  {
    it('确认工作流成功', async () =>
    {
      mockFetch.mockResolvedValueOnce({
        ok: true,
      })

      const { workflowApi } = await import('@/lib/workflowApi')

      // 不应抛出错误
      await expect(workflowApi.confirmWorkflow(1)).resolves.toBeUndefined()
    })

    it('确认失败时抛出错误', async () =>
    {
      mockFetch.mockResolvedValueOnce({
        ok: false,
        status: 400,
        json: () => Promise.resolve({ detail: '无法确认' }),
      })

      const { workflowApi } = await import('@/lib/workflowApi')

      await expect(workflowApi.confirmWorkflow(1)).rejects.toThrow('无法确认')
    })
  })

  describe('cancelWorkflow', () =>
  {
    it('取消工作流成功', async () =>
    {
      mockFetch.mockResolvedValueOnce({
        ok: true,
      })

      const { workflowApi } = await import('@/lib/workflowApi')

      await expect(workflowApi.cancelWorkflow(1)).resolves.toBeUndefined()
    })
  })

  describe('setWorkflowMode', () =>
  {
    it('设置工作流模式成功', async () =>
    {
      mockFetch.mockResolvedValueOnce({
        ok: true,
      })

      const { workflowApi } = await import('@/lib/workflowApi')

      await expect(workflowApi.setWorkflowMode(1, 'hybrid')).resolves.toBeUndefined()

      // 验证请求体
      expect(mockFetch).toHaveBeenCalledWith(
        expect.stringContaining('/workflow/mode'),
        expect.objectContaining({
          method: 'PUT',
          body: JSON.stringify({ mode: 'hybrid' }),
        })
      )
    })
  })

  describe('runWorkflow SSE 流式处理', () =>
  {
    it('处理 node_start 事件', async () =>
    {
      const events = [
        { type: 'node_start', data: 'generate_outline' },
        { type: 'done', data: { stage: 'outline', chapters: [] } },
      ]

      mockFetch.mockResolvedValueOnce({
        ok: true,
        body: createMockSSEStream(events),
      })

      const { workflowApi } = await import('@/lib/workflowApi')
      const onNodeStart = vi.fn()

      await workflowApi.runWorkflow(1, { onNodeStart })

      expect(onNodeStart).toHaveBeenCalledWith('generate_outline')
    })

    it('处理 node_done 事件', async () =>
    {
      const events = [
        {
          type: 'node_done',
          data: { node: 'generate_outline', data: { title: '测试小说' } },
        },
        { type: 'done', data: { stage: 'outline', chapters: [] } },
      ]

      mockFetch.mockResolvedValueOnce({
        ok: true,
        body: createMockSSEStream(events),
      })

      const { workflowApi } = await import('@/lib/workflowApi')
      const onNodeDone = vi.fn()

      await workflowApi.runWorkflow(1, { onNodeDone })

      expect(onNodeDone).toHaveBeenCalledWith('generate_outline', { title: '测试小说' })
    })

    it('处理 chunk 事件', async () =>
    {
      const events = [
        { type: 'chunk', data: '这是生成的文本...' },
        { type: 'done', data: { stage: 'writing', chapters: [] } },
      ]

      mockFetch.mockResolvedValueOnce({
        ok: true,
        body: createMockSSEStream(events),
      })

      const { workflowApi } = await import('@/lib/workflowApi')
      const onChunk = vi.fn()

      await workflowApi.runWorkflow(1, { onChunk })

      expect(onChunk).toHaveBeenCalledWith('这是生成的文本...')
    })

    it('处理 waiting 事件', async () =>
    {
      const events = [
        { type: 'waiting', data: 'outline' },
      ]

      mockFetch.mockResolvedValueOnce({
        ok: true,
        body: createMockSSEStream(events),
      })

      const { workflowApi } = await import('@/lib/workflowApi')
      const onWaiting = vi.fn()

      await workflowApi.runWorkflow(1, { onWaiting })

      expect(onWaiting).toHaveBeenCalledWith('outline')
    })

    it('处理 checkpoint 事件', async () =>
    {
      const checkpointData = {
        project_id: 1,
        stage: 'outline',
        has_checkpoint: true,
        current_chapter: 0,
        total_chapters: 10,
        written_chapters_count: 0,
        waiting_for_confirmation: true,
        confirmation_type: 'outline',
        updated_at: '2026-04-23T10:00:00Z',
      }

      const events = [
        { type: 'checkpoint', data: checkpointData },
        { type: 'done', data: { stage: 'outline', chapters: [] } },
      ]

      mockFetch.mockResolvedValueOnce({
        ok: true,
        body: createMockSSEStream(events),
      })

      const { workflowApi } = await import('@/lib/workflowApi')
      const onCheckpoint = vi.fn()

      await workflowApi.runWorkflow(1, { onCheckpoint })

      expect(onCheckpoint).toHaveBeenCalledWith(expect.objectContaining({
        stage: 'outline',
        has_checkpoint: true,
      }))
    })

    it('处理 done 事件', async () =>
    {
      const events = [
        {
          type: 'done',
          data: {
            stage: 'complete',
            chapters: [
              { chapter_number: 1, content: '内容...', word_count: 1000 },
            ],
          },
        },
      ]

      mockFetch.mockResolvedValueOnce({
        ok: true,
        body: createMockSSEStream(events),
      })

      const { workflowApi } = await import('@/lib/workflowApi')
      const onDone = vi.fn()

      await workflowApi.runWorkflow(1, { onDone })

      expect(onDone).toHaveBeenCalledWith({
        stage: 'complete',
        chapters: [
          { chapter_number: 1, content: '内容...', word_count: 1000 },
        ],
      })
    })

    it('处理 error 事件', async () =>
    {
      const events = [
        { type: 'error', data: 'API 调用失败' },
      ]

      mockFetch.mockResolvedValueOnce({
        ok: true,
        body: createMockSSEStream(events),
      })

      const { workflowApi } = await import('@/lib/workflowApi')
      const onError = vi.fn()

      await workflowApi.runWorkflow(1, { onError })

      expect(onError).toHaveBeenCalledWith('API 调用失败')
    })

    it('处理请求失败', async () =>
    {
      mockFetch.mockResolvedValueOnce({
        ok: false,
        status: 500,
        json: () => Promise.resolve({ detail: '服务器错误' }),
      })

      const { workflowApi } = await import('@/lib/workflowApi')
      const onError = vi.fn()

      await workflowApi.runWorkflow(1, { onError })

      // 错误消息优先使用 detail 字段
      expect(onError).toHaveBeenCalledWith('服务器错误')
    })

    it('处理请求失败无 detail 时使用状态码', async () =>
    {
      mockFetch.mockResolvedValueOnce({
        ok: false,
        status: 500,
        json: () => Promise.resolve({}),
      })

      const { workflowApi } = await import('@/lib/workflowApi')
      const onError = vi.fn()

      await workflowApi.runWorkflow(1, { onError })

      // 无 detail 时使用 HTTP 状态码
      expect(onError).toHaveBeenCalledWith(expect.stringContaining('500'))
    })

    it('支持 AbortSignal 取消', async () =>
    {
      const controller = new AbortController()

      mockFetch.mockResolvedValueOnce({
        ok: true,
        body: createMockSSEStream([]),
      })

      const { workflowApi } = await import('@/lib/workflowApi')

      // 传递 signal
      await workflowApi.runWorkflow(1, {}, { signal: controller.signal })

      // 验证 fetch 被调用并传递了 signal
      expect(mockFetch).toHaveBeenCalledWith(
        expect.any(String),
        expect.objectContaining({
          signal: controller.signal,
        })
      )
    })
  })

  describe('认证头', () =>
  {
    it('带有 token 时发送认证头', async () =>
    {
      localStorageStore['session_token'] = 'test-token-123'

      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve({ project_id: 1, stage: 'inspiration', has_checkpoint: false }),
      })

      const { workflowApi } = await import('@/lib/workflowApi')
      await workflowApi.getWorkflowState(1)

      // 验证 Authorization 头
      expect(mockFetch).toHaveBeenCalledWith(
        expect.any(String),
        expect.objectContaining({
          headers: expect.objectContaining({
            Authorization: expect.stringContaining('Basic'),
          }),
        })
      )
    })
  })
})
