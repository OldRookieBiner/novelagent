/**
 * agentApi.sendAgentMessage —— 验证请求 body 字段构造
 *
 * 重点回归：currentChapterNumber 必须按 phase==writing && != null 才传，
 * 否则字段缺省（不能被 JSON.stringify 序列化为 null/undefined 占位）。
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { sendAgentMessage } from './agentApi'

// mock createSSEStream，捕获第一个参数中的 body
const capturedBodies: unknown[] = []
vi.mock('./sseParser', () => ({
  createSSEStream: vi.fn(async (req: { body: unknown }) => {
    capturedBodies.push(req.body)
  }),
}))

beforeEach(() => {
  capturedBodies.length = 0
})

describe('sendAgentMessage 请求 body', () => {
  it('传入 currentChapterNumber=5 时，body 含 current_chapter_number=5', async () => {
    await sendAgentMessage(1, 'hi', {}, { currentChapterNumber: 5 })
    const body = capturedBodies[0] as Record<string, unknown>
    expect(body.current_chapter_number).toBe(5)
  })

  it('未传 currentChapterNumber 时，current_chapter_number 字段为 undefined（不会被发到后端）', async () => {
    await sendAgentMessage(1, 'hi', {}, {})
    const body = capturedBodies[0] as Record<string, unknown>
    // JSON.stringify 会丢弃 undefined 字段；后端 pydantic Optional[int] = None 也能正确处理
    expect(body.current_chapter_number).toBeUndefined()
  })

  it('options 完全省略时，current_chapter_number 同样不出现', async () => {
    await sendAgentMessage(1, 'hi', {})
    const body = capturedBodies[0] as Record<string, unknown>
    expect(body.current_chapter_number).toBeUndefined()
  })

  it('其他 options 字段（modelConfigId / modelName）正确透传', async () => {
    await sendAgentMessage(1, 'hi', {}, {
      modelConfigId: 7,
      modelName: 'deepseek-v3',
      currentChapterNumber: 3,
    })
    const body = capturedBodies[0] as Record<string, unknown>
    expect(body.model_config_id).toBe(7)
    expect(body.model_name).toBe('deepseek-v3')
    expect(body.current_chapter_number).toBe(3)
  })
})
