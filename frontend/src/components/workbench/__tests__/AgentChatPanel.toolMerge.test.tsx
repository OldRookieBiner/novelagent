import { describe, it, expect } from 'vitest'
import { render, screen, fireEvent, within } from '@testing-library/react'
import { AssistantMessageContentInner } from '@/components/workbench/AgentChatPanel'
import type { AiMessage, AiMessageSegment, ToolCallSegmentData } from '@/stores/workbenchStore'

function msg(segments: AiMessageSegment[], content = ''): AiMessage
{
  return {
    id: 'm1',
    role: 'assistant',
    content,
    segments,
    timestamp: Date.now(),
  }
}

function tc(tool: string, status: ToolCallSegmentData['status'], extra?: Partial<ToolCallSegmentData>): AiMessageSegment
{
  const data: ToolCallSegmentData = { tool, status, ...extra }
  return {
    type: 'tool_call',
    content: tool,
    data: data as unknown as Record<string, unknown>,
  }
}

describe('AssistantMessageContentInner — tool_call 渲染', () => {
  it('done tool_call：渲染对勾、不带状态后缀', () => {
    const m = msg([
      { type: 'agent_text', content: 'hi' },
      tc('advance_phase', 'done', { result: { advanced: true } }),
    ])
    const { container } = render(<AssistantMessageContentInner msg={m} isStreaming={false} />)
    const node = container.querySelector('[data-tool-status="done"]')
    expect(node).toBeTruthy()
    expect(node!.textContent || '').toContain('推进阶段')
    expect(node!.textContent || '').not.toContain('...')
    expect(node!.textContent || '').not.toContain('失败')
    expect(node!.textContent || '').not.toContain('已取消')
  })

  it('running tool_call：渲染 ... 后缀和 spinner', () => {
    const m = msg([
      { type: 'agent_text', content: 'hi' },
      tc('advance_phase', 'running'),
    ])
    const { container } = render(<AssistantMessageContentInner msg={m} isStreaming={true} />)
    const node = container.querySelector('[data-tool-status="running"]')
    expect(node).toBeTruthy()
    expect(node!.textContent || '').toContain('推进阶段')
    expect(node!.textContent || '').toContain('...')
  })

  it('error tool_call：渲染"失败"后缀', () => {
    const m = msg([
      { type: 'agent_text', content: 'hi' },
      tc('advance_phase', 'error'),
    ])
    const { container } = render(<AssistantMessageContentInner msg={m} isStreaming={false} />)
    const node = container.querySelector('[data-tool-status="error"]')
    expect(node).toBeTruthy()
    expect(node!.textContent || '').toContain('失败')
  })

  it('aborted tool_call：渲染"已取消"后缀', () => {
    const m = msg([
      { type: 'agent_text', content: 'hi' },
      tc('advance_phase', 'aborted'),
    ])
    const { container } = render(<AssistantMessageContentInner msg={m} isStreaming={false} />)
    const node = container.querySelector('[data-tool-status="aborted"]')
    expect(node).toBeTruthy()
    expect(node!.textContent || '').toContain('已取消')
  })

  it('点击单条 tool_call 展开 args / result，再次点击折叠', () => {
    const m = msg([
      { type: 'agent_text', content: 'hi' },
      tc('advance_phase', 'done', {
        args: { phase: 'structure' },
        result: { advanced: true, suggested_phase: 'writing' },
      }),
    ])
    const { container } = render(<AssistantMessageContentInner msg={m} isStreaming={false} />)
    const node = container.querySelector('[data-tool-status="done"]') as HTMLElement
    expect(node).toBeTruthy()
    // 默认折叠
    expect(node.textContent || '').not.toContain('suggested_phase')
    // 展开
    fireEvent.click(within(node).getByRole('button'))
    expect(node.textContent || '').toContain('suggested_phase')
    expect(node.textContent || '').toContain('phase')
    // 再次点击 → 折叠
    fireEvent.click(within(node).getByRole('button'))
    expect(node.textContent || '').not.toContain('suggested_phase')
  })

  it('连续 3 个同名 tool_call 折叠为 group，count=3 且各 item 状态独立', () => {
    const m = msg([
      { type: 'agent_text', content: 'go' },
      tc('create_character', 'done', { result: {} }),
      tc('create_character', 'done', { result: {} }),
      tc('create_character', 'running'),
    ])
    const { container } = render(<AssistantMessageContentInner msg={m} isStreaming={true} />)
    const group = container.querySelector('[data-testid^="tool-group-"]') as HTMLElement
    expect(group).toBeTruthy()
    // 标题含 ×3
    expect(group.textContent || '').toContain('×3')
    // 头部状态：有 running → running 后缀 ...
    expect(group.textContent || '').toContain('...')
    // 展开 group：3 条 item
    fireEvent.click(within(group).getByRole('button'))
    const items = group.querySelectorAll('div.ml-4 > div')
    expect(items.length).toBe(3)
  })

  it('group 不同状态混合：done+error → 头部 error（非 running）', () => {
    const m = msg([
      { type: 'agent_text', content: 'x' },
      tc('create_character', 'done', { result: {} }),
      tc('create_character', 'error'),
    ])
    const { container } = render(<AssistantMessageContentInner msg={m} isStreaming={false} />)
    const group = container.querySelector('[data-testid^="tool-group-"]') as HTMLElement
    expect(group).toBeTruthy()
    expect(group.textContent || '').toContain('失败')
  })

  it('旧格式（无 agent_text，content 含正文）也按 tool_call 渲染状态', () => {
    const m = msg(
      [tc('advance_phase', 'error')],
      '历史正文'
    )
    const { container } = render(<AssistantMessageContentInner msg={m} isStreaming={false} />)
    expect(screen.getByText('历史正文')).toBeTruthy()
    // 旧格式 fallback 中也渲染 tool_call 行
    expect(container.textContent || '').toContain('推进阶段')
    expect(container.textContent || '').toContain('失败')
  })
})
