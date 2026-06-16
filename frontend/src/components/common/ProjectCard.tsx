// frontend/src/components/common/ProjectCard.tsx
import { BookOpen, CheckCircle2 } from 'lucide-react'
import { Link } from 'react-router-dom'
import { Button } from '@/components/ui/button'
import type { ProjectDetail } from '@/types'

interface ProjectCardProps
{
  project: ProjectDetail
  onDelete: (id: number) => void
}

export default function ProjectCard({ project, onDelete }: ProjectCardProps)
{
  const isCompleted = project.is_completed

  // 当前章节：有章节时显示章节号，否则显示 "—"
  const currentChapter = project.workflow_state?.current_chapter ?? 0
  const hasChapters = project.chapter_count > 0
  const chapterDisplay = hasChapters && currentChapter > 0
    ? `第 ${currentChapter} 章`
    : '—'

  // 更新时间：带时分
  const updatedDate = new Date(project.updated_at)
  const timeStr = `${updatedDate.getMonth() + 1}月${updatedDate.getDate()}日 ${String(updatedDate.getHours()).padStart(2, '0')}:${String(updatedDate.getMinutes()).padStart(2, '0')}`

  return (
    <div className="border-2 border-border rounded-lg bg-card p-4 hover:border-primary/30 transition-colors">
      {/* 标题 + 状态标签 */}
      <div className="flex justify-between items-start gap-2 mb-4">
        <h3 className="font-semibold text-sm truncate">{project.name}</h3>
        {isCompleted ? (
          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium bg-emerald-50 text-emerald-700 shrink-0">
            <CheckCircle2 className="h-3 w-3" />
            已完结
          </span>
        ) : (
          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium bg-blue-50 text-blue-700 shrink-0">
            <BookOpen className="h-3 w-3" />
            连载中
          </span>
        )}
      </div>

      {/* 信息行 */}
      <div className="flex flex-col gap-2 mb-4">
        <div className="flex justify-between items-baseline">
          <span className="text-xs text-muted-foreground">已写</span>
          <span className="text-base font-semibold">{project.total_words.toLocaleString()} 字</span>
        </div>
        <div className="flex justify-between items-baseline">
          <span className="text-xs text-muted-foreground">当前</span>
          <span className="text-sm text-foreground">{chapterDisplay}</span>
        </div>
        <div className="flex justify-between items-baseline">
          <span className="text-xs text-muted-foreground">更新</span>
          <span className="text-sm text-foreground">{timeStr}</span>
        </div>
      </div>

      {/* 操作按钮 */}
      <div className="flex gap-2">
        <Button asChild size="sm" className="flex-1">
          <Link to={`/project/${project.id}/workbench`}>继续</Link>
        </Button>
        <Button
          variant="outline"
          size="sm"
          onClick={() => onDelete(project.id)}
        >
          删除
        </Button>
      </div>
    </div>
  )
}
