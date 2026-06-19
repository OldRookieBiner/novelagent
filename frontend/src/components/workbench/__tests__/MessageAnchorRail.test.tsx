// frontend/src/components/workbench/__tests__/MessageAnchorRail.test.tsx
import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent } from '@/test/utils'
import { MessageAnchorRail } from '../MessageAnchorRail'
import type { AiMessage } from '@/stores/workbenchStore'

const makeUserMsg = (id: string, content: string): AiMessage => ({
  id,
  role: 'user',
  content,
  segments: [],
  timestamp: Number(id) + 1000,
})

const makeMsgs = (n: number) =>
  Array.from({ length: n }, (_, i) => makeUserMsg(String(i), `第 ${i + 1} 条消息内容用于测试`))

describe('MessageAnchorRail', () => {
  it('少于 2 条消息不渲染', () => {
    const { container } = render(
      <MessageAnchorRail userMessages={makeMsgs(1)} activeId={null} onJump={vi.fn()} />
    )
    expect(container.firstChild).toBeNull()
  })

  it('零条消息不渲染', () => {
    const { container } = render(
      <MessageAnchorRail userMessages={[]} activeId={null} onJump={vi.fn()} />
    )
    expect(container.firstChild).toBeNull()
  })

  it('渲染锚点数量与 userMessages 一致', () => {
    render(
      <MessageAnchorRail userMessages={makeMsgs(5)} activeId={null} onJump={vi.fn()} />
    )
    const anchors = screen.getAllByLabelText(/^跳转到第 \d+ 条消息$/)
    expect(anchors).toHaveLength(5)
  })

  it('点击锚点触发 onJump 并传入正确 id', () => {
    const onJump = vi.fn()
    const msgs = makeMsgs(3)
    render(<MessageAnchorRail userMessages={msgs} activeId={null} onJump={onJump} />)
    const anchors = screen.getAllByLabelText(/^跳转到第 \d+ 条消息$/)
    fireEvent.click(anchors[1])
    expect(onJump).toHaveBeenCalledWith(msgs[1].id)
  })

  it('activeId 对应锚点有高亮 className', () => {
    const msgs = makeMsgs(3)
    render(<MessageAnchorRail userMessages={msgs} activeId={msgs[1].id} onJump={vi.fn()} />)
    const target = screen.getByLabelText('跳转到第 2 条消息')
    expect(target.className).toContain('w-[12px]')
    expect(target.className).toContain('bg-primary')
  })

  it('非 active 锚点是默认样式', () => {
    const msgs = makeMsgs(3)
    render(<MessageAnchorRail userMessages={msgs} activeId={msgs[1].id} onJump={vi.fn()} />)
    const other = screen.getByLabelText('跳转到第 1 条消息')
    expect(other.className).toContain('w-[8px]')
    expect(other.className).not.toContain('bg-primary')
  })

  it('mouseenter 容器后浮层显现', async () => {
    const msgs = makeMsgs(3)
    const { container } = render(
      <MessageAnchorRail userMessages={msgs} activeId={null} onJump={vi.fn()} />
    )
    const rail = container.firstChild as HTMLElement
    fireEvent.mouseEnter(rail)
    const tooltip = await screen.findByRole('tooltip')
    expect(tooltip).toBeInTheDocument()
    // 浮层中应包含每条消息的标题
    expect(tooltip.textContent).toContain('1.')
    expect(tooltip.textContent).toContain('2.')
    expect(tooltip.textContent).toContain('3.')
  })

  it('点击浮层中的标题项触发 onJump 并关闭浮层', async () => {
    const onJump = vi.fn()
    const msgs = makeMsgs(3)
    const { container } = render(
      <MessageAnchorRail userMessages={msgs} activeId={null} onJump={onJump} />
    )
    const rail = container.firstChild as HTMLElement
    fireEvent.mouseEnter(rail)
    const tooltip = await screen.findByRole('tooltip')
    const items = tooltip.querySelectorAll('button')
    fireEvent.click(items[2])
    expect(onJump).toHaveBeenCalledWith(msgs[2].id)
  })
})
