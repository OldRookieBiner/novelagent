/**
 * ChapterEditor 组件测试
 * 测试章节编辑器的标题显示、错误提示和按钮状态
 */

import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@/test/utils'
import ChapterEditor from '../ChapterEditor'

// 默认 props
const defaultProps = {
  projectId: '1',
  chapterNumber: 3,
  chapterTitle: '风云再起',
  chapterOutline: {
    scene: '山顶',
    characters: '李明、王芳',
    plot: '决战巅峰',
    conflict: '正邪对立',
    ending: '和平归来',
  },
  content: '',
  wordCount: 0,
  mode: 'preview' as const,
  isGenerating: false,
  isSaving: false,
  error: null as string | null,
  onGenerate: vi.fn(),
  onStop: vi.fn(),
  onSave: vi.fn(),
  onContentChange: vi.fn(),
  onModeChange: vi.fn(),
  onClearError: vi.fn(),
}

describe('ChapterEditor', () => {
  it('显示章节标题和大纲信息', () => {
    render(<ChapterEditor {...defaultProps} />)

    // 验证章节标题
    expect(screen.getByText('第3章：风云再起')).toBeInTheDocument()
    // 验证大纲信息显示
    expect(screen.getByText('山顶')).toBeInTheDocument()
    expect(screen.getByText('李明、王芳')).toBeInTheDocument()
    expect(screen.getByText('决战巅峰')).toBeInTheDocument()
    expect(screen.getByText('正邪对立')).toBeInTheDocument()
    expect(screen.getByText('和平归来')).toBeInTheDocument()
  })

  it('根据生成状态显示不同按钮', () => {
    // 未生成时显示"AI 生成"按钮
    const { rerender } = render(<ChapterEditor {...defaultProps} />)
    expect(screen.getByText('AI 生成')).toBeInTheDocument()

    // 生成中显示"停止生成"按钮和状态文字
    rerender(
      <ChapterEditor {...defaultProps} isGenerating={true} />
    )
    expect(screen.getByText('停止生成')).toBeInTheDocument()
    expect(screen.getByText('正在生成...')).toBeInTheDocument()

    // 已有内容时显示"重新生成"按钮
    rerender(
      <ChapterEditor {...defaultProps} wordCount={2000} />
    )
    expect(screen.getByText('重新生成')).toBeInTheDocument()
  })

  it('有错误时显示错误信息', () => {
    render(
      <ChapterEditor {...defaultProps} error="生成失败，请重试" />
    )
    expect(screen.getByText('生成失败，请重试')).toBeInTheDocument()
  })
})
