// frontend/src/components/writing/ChapterNav.tsx
import type { ChapterOutline } from '@/types'

interface ChapterNavProps
{
  chapterOutlines: ChapterOutline[]
  currentChapter: ChapterOutline | null
  isGenerating: boolean
  onSelectChapter: (chapter: ChapterOutline) => void
}

/**
 * 写作页面章节导航组件
 * 显示章节列表，支持切换章节和生成状态指示
 */
export default function ChapterNav({
  chapterOutlines,
  currentChapter,
  isGenerating,
  onSelectChapter,
}: ChapterNavProps)
{
  return (
    <div className="w-[200px] border-r bg-background shrink-0">
      <div className="p-4 border-b">
        <h2 className="font-semibold text-sm">章节列表</h2>
      </div>
      <div className="overflow-y-auto max-h-[calc(100vh-140px)]">
        {chapterOutlines.map((chapter) => (
          <div
            key={chapter.id}
            onClick={() => !isGenerating && onSelectChapter(chapter)}
            className={`px-4 py-3 text-sm cursor-pointer border-b ${
              currentChapter?.id === chapter.id
                ? 'bg-secondary font-medium'
                : 'hover:bg-muted'
            } ${isGenerating ? 'pointer-events-none opacity-60' : ''}`}
          >
            <div className="flex items-center justify-between">
              <span className="truncate">
                第{chapter.chapter_number}章：{chapter.title || '未命名'}
              </span>
              {chapter.has_content && (
                <span className="text-green-600 text-xs ml-1">✓</span>
              )}
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}
