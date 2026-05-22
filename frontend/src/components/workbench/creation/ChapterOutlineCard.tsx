// frontend/src/components/workbench/creation/ChapterOutlineCard.tsx

import type { ChapterOutline } from '@/types'

/** 获取章节状态图标 */
function getChapterStatusIcon(chapter: ChapterOutline): string
{
  if (chapter.has_content) return '📝'
  if (chapter.confirmed) return '✅'
  return ''
}

interface ChapterOutlineCardProps
{
  /** 章节大纲数据 */
  chapter: ChapterOutline
  /** 是否选中 */
  isActive: boolean
  /** 点击回调 */
  onClick: () => void
}

/**
 * 章节大纲卡片 — 侧边栏列表项
 * 显示章节序号、标题、状态图标
 */
export function ChapterOutlineCard({ chapter, isActive, onClick }: ChapterOutlineCardProps)
{
  const icon = getChapterStatusIcon(chapter)

  return (
    <button
      onClick={onClick}
      className={`w-full px-2.5 py-2 text-left text-xs border-b hover:bg-muted/50 transition-colors ${
        isActive ? 'bg-primary/10 border-l-2 border-l-primary' : ''
      }`}
    >
      <div className="flex items-center gap-1.5">
        <span className="text-muted-foreground text-[10px] min-w-[16px]">{chapter.chapter_number}.</span>
        <span className="truncate flex-1">{chapter.title || '未命名'}</span>
        {icon && <span className="text-[10px] flex-shrink-0">{icon}</span>}
      </div>
    </button>
  )
}
