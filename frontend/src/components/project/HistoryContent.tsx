// frontend/src/components/project/HistoryContent.tsx
import { Link } from 'react-router-dom'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import InspirationForm from '@/components/project/InspirationForm'
import InspirationDisplay from '@/components/project/InspirationDisplay'
import ChapterList from '@/components/project/ChapterList'
import ChapterOutlineDetail from '@/components/project/ChapterOutlineDetail'
import type { Outline, ChapterOutline, CollectedInfo } from '@/types'
import type { InspirationData } from '@/lib/inspiration'

interface HistoryContentProps
{
  stepIndex: number
  outline: Outline | null
  chapterOutlines: ChapterOutline[]
  selectedChapter: ChapterOutline | null
  projectId: number
  onSelectChapter: (chapter: ChapterOutline) => void
  onConfirmChapter: (chapterNum: number) => void
  onInspirationUpdate: (data: InspirationData) => void
}

/**
 * 历史步骤内容组件
 * 根据步骤索引显示对应的历史内容
 */
export default function HistoryContent({
  stepIndex,
  outline,
  chapterOutlines,
  selectedChapter,
  projectId,
  onSelectChapter,
  onConfirmChapter,
  onInspirationUpdate,
}: HistoryContentProps)
{
  switch (stepIndex)
  {
    case 0: // 灵感采集
      const info = outline?.collected_info
      // 如果大纲未确认，允许修改灵感采集
      if (outline && !outline.confirmed)
      {
        return (
          <Card className="flex-1">
            <CardHeader>
              <CardTitle>修改灵感采集</CardTitle>
            </CardHeader>
            <CardContent>
              <InspirationForm
                initialData={info as Partial<InspirationData>}
                onSubmit={(data) =>
                {
                  onInspirationUpdate(data)
                }}
              />
            </CardContent>
          </Card>
        )
      }
      return (
        <Card className="flex-1">
          <CardHeader>
            <CardTitle>灵感采集记录</CardTitle>
          </CardHeader>
          <CardContent>
            {info && Object.keys(info).length > 0 ? (
              <InspirationDisplay data={info} />
            ) : (
              <div className="text-muted-foreground">暂无灵感采集记录</div>
            )}
          </CardContent>
        </Card>
      )

    case 1: // 大纲生成
      return (
        <Card className="flex-1">
          <CardHeader>
            <CardTitle>大纲信息</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            {outline ? (
              <>
                <div>
                  <div className="text-sm font-medium text-muted-foreground">标题</div>
                  <div className="text-lg font-bold">{outline.title || '未设置'}</div>
                </div>
                <div>
                  <div className="text-sm font-medium text-muted-foreground">简介</div>
                  <div>{outline.summary || '未设置'}</div>
                </div>
                {outline.plot_points && outline.plot_points.length > 0 && (
                  <div>
                    <div className="text-sm font-medium text-muted-foreground">主要情节节点</div>
                    <ul className="list-disc list-inside text-sm mt-1">
                      {outline.plot_points.map((point, idx) =>
                      {
                        const eventText = typeof point === 'string' ? point : point.event
                        return <li key={idx} className="mb-1">{eventText}</li>
                      })}
                    </ul>
                  </div>
                )}
                <div>
                  <div className="text-sm font-medium text-muted-foreground">章节数</div>
                  <div>{outline.chapter_count_suggested || 0} 章</div>
                </div>
              </>
            ) : (
              <div className="text-muted-foreground">暂无大纲信息</div>
            )}
          </CardContent>
        </Card>
      )

    case 2: // 章节大纲
    case 3: // 写作
    case 4: // 审核
      return (
        <div className="flex gap-6 flex-1">
          <ChapterList
            chapters={chapterOutlines}
            selectedChapter={selectedChapter}
            onSelectChapter={onSelectChapter}
          />
          <ChapterOutlineDetail
            chapter={selectedChapter}
            projectId={projectId}
            onConfirm={onConfirmChapter}
          />
        </div>
      )

    default:
      return null
  }
}
