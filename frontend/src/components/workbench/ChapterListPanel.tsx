// ChapterListPanel.tsx — 左栏章节列表（按情节块分组）

import { cn } from '@/lib/utils'
import { useWorkbenchStore } from '@/stores/workbenchStore'

interface ChapterItem {
  chapterNumber: number
  title: string
  status: 'written' | 'writing' | 'pending'
}

interface PlotBlockGroup {
  title: string
  chapters: ChapterItem[]
  isActive: boolean
}

interface ChapterListPanelProps {
  blocks: PlotBlockGroup[]
}

export function ChapterListPanel({ blocks }: ChapterListPanelProps)
{
  const { selectedChapterNumber, setSelectedChapterNumber } = useWorkbenchStore()

  return (
    <>
      {blocks.map((block) => (
        <div key={block.title}>
          {/* 情节块标题 */}
          <div
            className={cn(
              'px-3 py-1.5 text-[10px] font-medium uppercase tracking-wide',
              block.isActive ? 'text-primary' : 'text-muted-foreground'
            )}
          >
            {block.title} {block.isActive && '▶'}
          </div>

          {/* 章节列表 */}
          {block.chapters.map((ch) => (
            <button
              key={ch.chapterNumber}
              onClick={() => setSelectedChapterNumber(ch.chapterNumber)}
              className={cn(
                'w-full flex items-center gap-2 px-3 py-1.5 text-[11px] text-left',
                selectedChapterNumber === ch.chapterNumber
                  ? 'bg-primary/5 border-r-2 border-primary text-primary font-medium'
                  : 'text-muted-foreground hover:bg-muted/50'
              )}
            >
              <span
                className={cn(
                  'text-[8px]',
                  ch.status === 'written' && 'text-green-500',
                  ch.status === 'writing' && 'text-primary',
                  ch.status === 'pending' && 'text-gray-300'
                )}
              >
                {ch.status === 'written' ? '●' : ch.status === 'writing' ? '●' : '○'}
              </span>
              第{ch.chapterNumber}章 {ch.title}
              {ch.status === 'writing' && (
                <span className="ml-auto bg-primary/10 text-primary text-[9px] px-1 rounded">
                  写作中
                </span>
              )}
            </button>
          ))}
        </div>
      ))}
    </>
  )
}
