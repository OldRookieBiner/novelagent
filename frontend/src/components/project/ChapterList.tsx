// frontend/src/components/project/ChapterList.tsx
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import type { ChapterOutline } from '@/types'

interface ChapterListProps
{
  chapters: ChapterOutline[]
  selectedChapter: ChapterOutline | null
  onSelectChapter: (chapter: ChapterOutline) => void
}

/**
 * 章节列表组件
 * 显示所有章节大纲，支持选中章节查看详情
 */
export default function ChapterList({
  chapters,
  selectedChapter,
  onSelectChapter,
}: ChapterListProps)
{
  return (
    <Card className="w-64 shrink-0">
      <CardHeader>
        <CardTitle className="text-lg">章节列表</CardTitle>
      </CardHeader>
      <CardContent className="p-0">
        <div className="max-h-96 overflow-y-auto">
          {chapters.length === 0 ? (
            <div className="p-4 text-center text-muted-foreground text-sm">
              暂无章节
            </div>
          ) : (
            chapters.map((chapter) => (
              <div
                key={chapter.id}
                className={`px-4 py-2 border-b cursor-pointer hover:bg-muted ${
                  selectedChapter?.id === chapter.id ? 'bg-muted' : ''
                }`}
                onClick={() => onSelectChapter(chapter)}
              >
                <div className="flex items-center gap-2">
                  <span className="text-sm">
                    {chapter.chapter_number}. {chapter.title || '未命名'}
                  </span>
                  {chapter.has_content && (
                    <span className="text-xs text-green-600">✓</span>
                  )}
                </div>
              </div>
            ))
          )}
        </div>
      </CardContent>
    </Card>
  )
}
