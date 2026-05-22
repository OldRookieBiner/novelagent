// frontend/src/components/workbench/creation/ArcOutlineSection.tsx

import type { ChapterOutline } from '@/types'

/** 弧线大纲数据（占位接口，后续长篇小说支持时扩展） */
export interface ArcOutline
{
  id: number
  title: string
  summary?: string
  chapters: ChapterOutline[]
}

interface ArcOutlineSectionProps
{
  /** 弧线数据 */
  arc: ArcOutline
  /** 选中章节 ID */
  selectedChapterId: number | null
  /** 选中章节回调 */
  onSelectChapter: (chapter: ChapterOutline) => void
}

/**
 * 弧线大纲区段 — 长篇小说弧线分组显示
 * 当前为占位组件，后续长篇小说支持时完善
 */
export function ArcOutlineSection({ arc, selectedChapterId, onSelectChapter }: ArcOutlineSectionProps)
{
  return (
    <div className="mb-4">
      <div className="px-2 py-1.5 text-xs font-semibold text-muted-foreground bg-muted/30 rounded-t-md">
        {arc.title}
      </div>
      <div className="border border-t-0 rounded-b-md">
        {arc.chapters.map((chapter) =>
        {
          const isActive = selectedChapterId === chapter.id
          return (
            <button
              key={chapter.id}
              onClick={() => onSelectChapter(chapter)}
              className={`w-full px-2.5 py-2 text-left text-xs border-b last:border-b-0 hover:bg-muted/50 transition-colors ${
                isActive ? 'bg-primary/10 border-l-2 border-l-primary' : ''
              }`}
            >
              <span className="truncate">{chapter.chapter_number}. {chapter.title || '未命名'}</span>
            </button>
          )
        })}
      </div>
    </div>
  )
}
