/**
 * ChapterNav 组件测试
 * 测试章节导航列表的渲染和交互
 */

import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent } from '@/test/utils'
import ChapterNav from '../ChapterNav'
import type { ChapterOutline } from '@/types'

// 模拟章节大纲数据
const mockChapterOutlines: ChapterOutline[] = [
  {
    id: 1,
    project_id: 1,
    chapter_number: 1,
    title: '初入江湖',
    target_words: 3000,
    confirmed: true,
    created_at: '2026-01-01',
    has_content: true,
  },
  {
    id: 2,
    project_id: 1,
    chapter_number: 2,
    title: '拜师学艺',
    target_words: 3000,
    confirmed: true,
    created_at: '2026-01-01',
    has_content: false,
  },
  {
    id: 3,
    project_id: 1,
    chapter_number: 3,
    title: '',
    target_words: 3000,
    confirmed: false,
    created_at: '2026-01-01',
    has_content: false,
  },
]

describe('ChapterNav', () => {
  it('渲染章节列表并显示章节号和标题', () => {
    render(
      <ChapterNav
        chapterOutlines={mockChapterOutlines}
        currentChapter={null}
        isGenerating={false}
        onSelectChapter={vi.fn()}
      />
    )

    // 验证章节列表标题
    expect(screen.getByText('章节列表')).toBeInTheDocument()
    // 验证章节号和标题显示
    expect(screen.getByText(/第1章：初入江湖/)).toBeInTheDocument()
    expect(screen.getByText(/第2章：拜师学艺/)).toBeInTheDocument()
    // 无标题时显示"未命名"
    expect(screen.getByText(/第3章：未命名/)).toBeInTheDocument()
    // 有内容的章节显示 ✓
    expect(screen.getByText('✓')).toBeInTheDocument()
  })

  it('高亮选中章节，点击时调用 onSelectChapter', () => {
    const onSelectChapter = vi.fn()
    const { container } = render(
      <ChapterNav
        chapterOutlines={mockChapterOutlines}
        currentChapter={mockChapterOutlines[0]}
        isGenerating={false}
        onSelectChapter={onSelectChapter}
      />
    )

    // 选中章节有高亮样式
    const selectedItems = container.querySelectorAll('.bg-secondary')
    expect(selectedItems.length).toBeGreaterThan(0)

    // 点击未选中的章节
    fireEvent.click(screen.getByText(/第2章：拜师学艺/))
    expect(onSelectChapter).toHaveBeenCalledWith(mockChapterOutlines[1])
  })
})
