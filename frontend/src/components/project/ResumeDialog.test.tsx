/**
 * ResumeDialog 测试
 * 测试恢复创作弹窗组件
 */

import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import ResumeDialog from './ResumeDialog'

describe('ResumeDialog', () =>
{
  const defaultProps = {
    open: true,
    onOpenChange: vi.fn(),
    projectName: '测试小说',
    currentStage: 'outline' as const,
    currentChapter: 0,
    writtenChaptersCount: 0,
    waitingForConfirmation: false,
    confirmationType: null,
    hasChapters: false,
    onResume: vi.fn(),
  }

  it('显示项目名称', () =>
  {
    render(<ResumeDialog {...defaultProps} />)
    expect(screen.getByText('测试小说')).toBeInTheDocument()
  })

  it('显示当前阶段', () =>
  {
    render(<ResumeDialog {...defaultProps} currentStage="outline" />)
    expect(screen.getByText('大纲生成')).toBeInTheDocument()
  })

  it('写作阶段显示当前章节', () =>
  {
    render(
      <ResumeDialog
        {...defaultProps}
        currentStage="writing"
        currentChapter={5}
      />
    )
    expect(screen.getByText('第 5 章')).toBeInTheDocument()
  })

  it('有已写章节时显示数量', () =>
  {
    render(
      <ResumeDialog
        {...defaultProps}
        writtenChaptersCount={3}
      />
    )
    expect(screen.getByText('3 章')).toBeInTheDocument()
  })

  it('等待确认时显示提示', () =>
  {
    render(
      <ResumeDialog
        {...defaultProps}
        waitingForConfirmation={true}
        confirmationType="outline"
      />
    )
    expect(screen.getByText(/等待大纲确认/)).toBeInTheDocument()
  })

  it('点击恢复按钮触发 onResume', () =>
  {
    const onResume = vi.fn()
    render(<ResumeDialog {...defaultProps} onResume={onResume} />)

    fireEvent.click(screen.getByText('恢复创作'))
    expect(onResume).toHaveBeenCalled()
  })

  it('点击取消按钮关闭弹窗', () =>
  {
    const onOpenChange = vi.fn()
    render(<ResumeDialog {...defaultProps} onOpenChange={onOpenChange} />)

    fireEvent.click(screen.getByText('取消'))
    expect(onOpenChange).toHaveBeenCalledWith(false)
  })

  it('有章节时显示查看章节按钮', () =>
  {
    render(
      <ResumeDialog
        {...defaultProps}
        hasChapters={true}
      />
    )
    expect(screen.getByText('查看章节')).toBeInTheDocument()
  })

  it('无章节时不显示查看章节按钮', () =>
  {
    render(
      <ResumeDialog
        {...defaultProps}
        hasChapters={false}
      />
    )
    expect(screen.queryByText('查看章节')).not.toBeInTheDocument()
  })

  it('点击查看章节触发 onViewChapters', () =>
  {
    const onViewChapters = vi.fn()
    render(
      <ResumeDialog
        {...defaultProps}
        hasChapters={true}
        onViewChapters={onViewChapters}
      />
    )

    fireEvent.click(screen.getByText('查看章节'))
    expect(onViewChapters).toHaveBeenCalled()
  })

  it('弹窗关闭时不显示内容', () =>
  {
    render(<ResumeDialog {...defaultProps} open={false} />)
    expect(screen.queryByText('发现未完成的创作')).not.toBeInTheDocument()
  })
})
