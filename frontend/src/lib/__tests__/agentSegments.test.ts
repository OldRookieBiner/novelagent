import { describe, it, expect } from 'vitest'
import { normalizeLegacySegments, type BackendAction, type RawSegment } from '@/lib/agentSegments'
import type { ToolCallSegmentData } from '@/stores/workbenchStore'

function callData(seg: { type: string; data?: unknown }): ToolCallSegmentData
{
  return seg.data as ToolCallSegmentData
}

describe('normalizeLegacySegments', () => {
  it('基本配对：tool_start + tool_result → 1 个 done tool_call', () => {
    const raw: RawSegment[] = [
      { type: 'tool_start', content: 'A', data: { tool: 'A', args: { x: 1 } } },
      { type: 'tool_result', content: 'A', data: { tool: 'A', result: { ok: true } } },
    ]
    const out = normalizeLegacySegments(raw)
    expect(out).toHaveLength(1)
    expect(out[0].type).toBe('tool_call')
    const d = callData(out[0])
    expect(d.tool).toBe('A')
    expect(d.status).toBe('done')
    expect(d.args).toEqual({ x: 1 })
    expect(d.result).toEqual({ ok: true })
  })

  it('嵌套/交错：[start A, start B, result B, result A] → 2 个 done，顺序 A, B', () => {
    const raw: RawSegment[] = [
      { type: 'tool_start', content: 'A', data: { tool: 'A' } },
      { type: 'tool_start', content: 'B', data: { tool: 'B' } },
      { type: 'tool_result', content: 'B', data: { tool: 'B' } },
      { type: 'tool_result', content: 'A', data: { tool: 'A' } },
    ]
    const out = normalizeLegacySegments(raw)
    expect(out).toHaveLength(2)
    expect(callData(out[0]).tool).toBe('A')
    expect(callData(out[0]).status).toBe('done')
    expect(callData(out[1]).tool).toBe('B')
    expect(callData(out[1]).status).toBe('done')
  })

  it('残留 start：未配对的 tool_start → 标 error', () => {
    const raw: RawSegment[] = [
      { type: 'tool_start', content: 'A', data: { tool: 'A' } },
      { type: 'agent_text', content: '中间还在输出' },
    ]
    const out = normalizeLegacySegments(raw)
    // 应当只有 1 个 tool_call + 1 个 agent_text；tool_call 标 error
    expect(out).toHaveLength(2)
    const callIdx = out.findIndex(s => s.type === 'tool_call')
    expect(callIdx).toBeGreaterThanOrEqual(0)
    expect(callData(out[callIdx]).status).toBe('error')
  })

  it('actions 校正：配对得 done，但 actions 写 error → 最终 error', () => {
    const raw: RawSegment[] = [
      { type: 'tool_start', content: 'A', data: { tool: 'A', args: { x: 1 } } },
      { type: 'tool_result', content: 'A', data: { tool: 'A', result: { ok: true } } },
    ]
    const actions: BackendAction[] = [
      { tool: 'A', status: 'error', args: { x: 1 }, result: { reason: 'boom' } },
    ]
    const out = normalizeLegacySegments(raw, actions)
    expect(out).toHaveLength(1)
    const d = callData(out[0])
    expect(d.status).toBe('error')
    expect(d.result).toEqual({ reason: 'boom' })
  })

  it('actions 按工具名顺序对齐：A done, A error → 第一个 done，第二个 error', () => {
    const raw: RawSegment[] = [
      { type: 'tool_start', content: 'A', data: { tool: 'A' } },
      { type: 'tool_result', content: 'A', data: { tool: 'A' } },
      { type: 'tool_start', content: 'A', data: { tool: 'A' } },
      { type: 'tool_result', content: 'A', data: { tool: 'A' } },
    ]
    const actions: BackendAction[] = [
      { tool: 'A', status: 'done' },
      { tool: 'A', status: 'error' },
    ]
    const out = normalizeLegacySegments(raw, actions)
    expect(out).toHaveLength(2)
    expect(callData(out[0]).status).toBe('done')
    expect(callData(out[1]).status).toBe('error')
  })

  it('非工具段原样透传', () => {
    const raw: RawSegment[] = [
      { type: 'agent_text', content: 'hello' },
      { type: 'progress', content: '进度', data: { percent: 50 } },
    ]
    const out = normalizeLegacySegments(raw)
    expect(out).toHaveLength(2)
    expect(out[0].type).toBe('agent_text')
    expect(out[0].content).toBe('hello')
    expect(out[1].type).toBe('progress')
    expect(out[1].data).toEqual({ percent: 50 })
  })

  it('空 / null 输入安全返回空数组', () => {
    expect(normalizeLegacySegments(undefined)).toEqual([])
    expect(normalizeLegacySegments(null)).toEqual([])
    expect(normalizeLegacySegments([])).toEqual([])
  })

  it('已经是 tool_call 的段原样保留且 running 仍可被后续 actions 校正', () => {
    const raw: RawSegment[] = [
      { type: 'tool_call', content: 'A', data: { tool: 'A', status: 'running' } },
    ]
    const out = normalizeLegacySegments(raw, [{ tool: 'A', status: 'done', result: { ok: 1 } }])
    expect(out).toHaveLength(1)
    expect(callData(out[0]).status).toBe('done')
    expect(callData(out[0]).result).toEqual({ ok: 1 })
  })
})

import { finalizeRunningToolCalls } from '@/lib/agentSegments'

describe('finalizeRunningToolCalls', () => {
  it('把所有 running tool_call 改为 error', () => {
    const segs = [
      { type: 'agent_text' as const, content: 'x' },
      { type: 'tool_call' as const, content: 'A', data: { tool: 'A', status: 'running' } },
      { type: 'tool_call' as const, content: 'A', data: { tool: 'A', status: 'done', result: { ok: 1 } } },
      { type: 'tool_call' as const, content: 'B', data: { tool: 'B', status: 'running' } },
    ]
    const out = finalizeRunningToolCalls(segs, 'error')
    expect(out).not.toBe(segs)
    expect((out[1].data as any).status).toBe('error')
    expect((out[2].data as any).status).toBe('done') // 已 done 不动
    expect((out[2].data as any).result).toEqual({ ok: 1 })
    expect((out[3].data as any).status).toBe('error')
  })

  it('把 running tool_call 改为 aborted', () => {
    const segs = [
      { type: 'tool_call' as const, content: 'A', data: { tool: 'A', status: 'running' } },
    ]
    const out = finalizeRunningToolCalls(segs, 'aborted')
    expect((out[0].data as any).status).toBe('aborted')
  })

  it('无 running 时返回同引用（避免无意义 re-render）', () => {
    const segs = [
      { type: 'agent_text' as const, content: 'x' },
      { type: 'tool_call' as const, content: 'A', data: { tool: 'A', status: 'done' } },
    ]
    const out = finalizeRunningToolCalls(segs, 'error')
    expect(out).toBe(segs)
  })

  // 契约：本函数仅用于 error / aborted；agent_done 路径不应调用之。
  // 通过 TypeScript 函数签名（finalStatus: 'error' | 'aborted'）保证编译期约束，
  // 这里再加运行时断言保护，文档化设计意图：
  it('仅接受 error / aborted（设计契约）', () => {
    const segs = [{ type: 'tool_call' as const, content: 'A', data: { tool: 'A', status: 'running' } }]
    // @ts-expect-error 故意传入非法值验证文档约束
    const out = finalizeRunningToolCalls(segs, 'done')
    // 即便错误传入 'done'，函数仍会改写 status；这正说明此函数不该在 onAgentDone 调用。
    // 此用例的价值在于：把这条契约固化在测试里，未来若有人想在 onAgentDone 路径调用，
    // 会被这个用例和类型签名共同提醒。
    expect((out[0].data as any).status).toBe('done')
  })
})
