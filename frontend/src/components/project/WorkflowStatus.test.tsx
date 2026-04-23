/**
 * WorkflowStatus 测试
 * 测试工作流状态显示组件
 */

import { describe, it, expect, beforeEach, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import WorkflowStatus from './WorkflowStatus'
import type { WorkflowStage, ConfirmationType } from '@/types'

// 创建 mock 状态
interface MockStoreState {
  stage: WorkflowStage
  currentNode: string | null
  currentChapter: number
  writtenChapters: Array<{ chapter_number: number; content: string; word_count: number }>
  isRunning: boolean
  waitingForConfirmation: boolean
  confirmationType: ConfirmationType | null
}

let mockStoreState: MockStoreState = {
  stage: 'inspiration',
  currentNode: null,
  currentChapter: 0,
  writtenChapters: [],
  isRunning: false,
  waitingForConfirmation: false,
  confirmationType: null,
}

// Mock useWorkflowStore
vi.mock('@/stores/workflowStore', () => ({
  useWorkflowStore: vi.fn((selector?: (state: MockStoreState) => unknown) =>
  {
    if (selector)
    {
      return selector(mockStoreState)
    }
    return mockStoreState
  }),
}))

describe('WorkflowStatus', () =>
{
  beforeEach(() =>
  {
    vi.clearAllMocks()
    // 重置状态
    mockStoreState = {
      stage: 'inspiration',
      currentNode: null,
      currentChapter: 0,
      writtenChapters: [],
      isRunning: false,
      waitingForConfirmation: false,
      confirmationType: null,
    }
  })

  it('显示灵感阶段', () =>
  {
    mockStoreState.stage = 'inspiration'
    render(<WorkflowStatus />)
    expect(screen.getByText('灵感收集')).toBeInTheDocument()
  })

  it('显示大纲阶段', () =>
  {
    mockStoreState.stage = 'outline'
    render(<WorkflowStatus />)
    expect(screen.getByText('大纲生成')).toBeInTheDocument()
  })

  it('显示章节大纲阶段', () =>
  {
    mockStoreState.stage = 'chapter_outlines'
    render(<WorkflowStatus />)
    expect(screen.getByText('章节大纲')).toBeInTheDocument()
  })

  it('显示写作阶段及进度', () =>
  {
    mockStoreState.stage = 'writing'
    mockStoreState.currentChapter = 5
    mockStoreState.writtenChapters = [
      { chapter_number: 1, content: '', word_count: 1000 },
      { chapter_number: 2, content: '', word_count: 1000 },
    ]
    render(<WorkflowStatus />)
    expect(screen.getByText('章节写作')).toBeInTheDocument()
    // 使用正则匹配，因为文本可能被拆分
    expect(screen.getByText(/2\s*章/)).toBeInTheDocument()
  })

  it('显示审核阶段', () =>
  {
    mockStoreState.stage = 'review'
    render(<WorkflowStatus />)
    expect(screen.getByText('审核')).toBeInTheDocument()
  })

  it('显示完成阶段', () =>
  {
    mockStoreState.stage = 'complete'
    mockStoreState.writtenChapters = Array(10).fill({ chapter_number: 1, content: '', word_count: 1000 })
    render(<WorkflowStatus />)
    expect(screen.getByText('已完成')).toBeInTheDocument()
  })

  it('运行中显示加载动画', () =>
  {
    mockStoreState.isRunning = true
    const { container } = render(<WorkflowStatus />)
    const spinner = container.querySelector('.animate-spin')
    expect(spinner).toBeInTheDocument()
  })

  it('等待确认时显示提示', () =>
  {
    mockStoreState.waitingForConfirmation = true
    mockStoreState.confirmationType = 'outline'
    render(<WorkflowStatus />)
    expect(screen.getByText(/等待确认/)).toBeInTheDocument()
  })

  it('等待大纲确认显示正确文字', () =>
  {
    mockStoreState.waitingForConfirmation = true
    mockStoreState.confirmationType = 'outline'
    render(<WorkflowStatus />)
    expect(screen.getByText('大纲已生成，请确认后继续')).toBeInTheDocument()
  })

  it('等待章节大纲确认显示正确文字', () =>
  {
    mockStoreState.waitingForConfirmation = true
    mockStoreState.confirmationType = 'chapter_outlines'
    render(<WorkflowStatus />)
    expect(screen.getByText('章节大纲已生成，请确认后继续')).toBeInTheDocument()
  })

  it('等待审核修改显示正确文字', () =>
  {
    mockStoreState.waitingForConfirmation = true
    mockStoreState.confirmationType = 'review_failed'
    render(<WorkflowStatus />)
    expect(screen.getByText('审核未通过，请修改后重试')).toBeInTheDocument()
  })
})
