// frontend/src/components/project/ChapterOutlineDetail.tsx
import { Link } from 'react-router-dom'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import type { ChapterOutline } from '@/types'

interface ChapterOutlineDetailProps
{
  chapter: ChapterOutline | null
  projectId: number
  onConfirm: (chapterNum: number) => void
}

/**
 * 章节大纲详情组件
 * 显示选中章节的详细信息，包括场景、人物、情节等
 */
export default function ChapterOutlineDetail({
  chapter,
  projectId,
  onConfirm,
}: ChapterOutlineDetailProps)
{
  return (
    <Card className="flex-1">
      <CardHeader>
        <CardTitle className="text-lg">
          {chapter
            ? `第 ${chapter.chapter_number} 章：${chapter.title || '未命名'}`
            : '章节详情'}
        </CardTitle>
      </CardHeader>
      <CardContent>
        {chapter ? (
          <div className="space-y-4">
            <div>
              <div className="text-sm font-medium text-muted-foreground">场景</div>
              <div>{chapter.scene || '-'}</div>
            </div>
            <div>
              <div className="text-sm font-medium text-muted-foreground">人物</div>
              <div>{chapter.characters || '-'}</div>
            </div>
            <div>
              <div className="text-sm font-medium text-muted-foreground">情节</div>
              <div>{chapter.plot || '-'}</div>
            </div>
            <div>
              <div className="text-sm font-medium text-muted-foreground">冲突</div>
              <div>{chapter.conflict || '-'}</div>
            </div>
            <div>
              <div className="text-sm font-medium text-muted-foreground">结局</div>
              <div>{chapter.ending || '-'}</div>
            </div>
            <div>
              <div className="text-sm font-medium text-muted-foreground">预计字数</div>
              <div>{chapter.target_words} 字</div>
            </div>

            <div className="flex gap-2 pt-4">
              {!chapter.confirmed && (
                <Button onClick={() => onConfirm(chapter.chapter_number)}>
                  确认章节大纲
                </Button>
              )}
              {chapter.confirmed && (
                <Link to={`/project/${projectId}/write`}>
                  <Button>
                    {chapter.has_content ? '编辑正文' : '开始写作'}
                  </Button>
                </Link>
              )}
              {chapter.has_content && (
                <Link to={`/project/${projectId}/read/${chapter.chapter_number}`}>
                  <Button variant="outline">阅读正文</Button>
                </Link>
              )}
            </div>
          </div>
        ) : (
          <div className="text-center text-muted-foreground py-10">
            选择左侧章节查看详情
          </div>
        )}
      </CardContent>
    </Card>
  )
}
