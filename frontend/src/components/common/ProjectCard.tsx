// frontend/src/components/common/ProjectCard.tsx
import { Loader2, CheckCircle, Circle, PenLine, FileText, Sparkles, BookOpen, FileText as ChapterIcon } from 'lucide-react'
import { Link } from 'react-router-dom'
import { Button } from '@/components/ui/button'
import { Progress } from '@/components/ui/progress'
import type { ProjectDetail } from '@/types'

interface ProjectCardProps
{
  project: ProjectDetail
  onDelete: (id: number) => void
}

// 工作流阶段配置：标签、柔和背景色、文字色、图标
const STAGE_CONFIG: Record<string, { label: string; bg: string; text: string; icon: React.ElementType; isProcessing: boolean; isCompleted: boolean }> = {
  inspiration: { label: '灵感采集', bg: 'bg-yellow-50', text: 'text-yellow-700', icon: Sparkles, isProcessing: false, isCompleted: false },
  outline: { label: '大纲生成', bg: 'bg-blue-50', text: 'text-blue-700', icon: FileText, isProcessing: false, isCompleted: false },
  chapter_outlines: { label: '章节纲', bg: 'bg-purple-50', text: 'text-purple-700', icon: BookOpen, isProcessing: false, isCompleted: false },
  writing: { label: '写作中', bg: 'bg-green-50', text: 'text-green-700', icon: PenLine, isProcessing: false, isCompleted: false },
  review: { label: '审核中', bg: 'bg-orange-50', text: 'text-orange-700', icon: Loader2, isProcessing: true, isCompleted: false },
  complete: { label: '已完成', bg: 'bg-emerald-50', text: 'text-emerald-700', icon: CheckCircle, isProcessing: false, isCompleted: true },
  paused: { label: '暂停', bg: 'bg-gray-100', text: 'text-gray-600', icon: Circle, isProcessing: false, isCompleted: false },
}

export default function ProjectCard({ project, onDelete }: ProjectCardProps)
{
  const stage = project.workflow_state?.stage || 'inspiration'
  const stageConfig = STAGE_CONFIG[stage] || {
    label: stage || '未知',
    bg: 'bg-gray-100',
    text: 'text-gray-600',
    icon: Circle,
    isProcessing: false,
    isCompleted: false
  }
  const StageIcon = stageConfig.icon

  const statusText = stageConfig.isCompleted ? '已完成' : stageConfig.isProcessing ? '处理中' : '进行中'
  const isComplete = project.progress_percentage === 100
  const progressColor = isComplete ? 'bg-emerald-500' : 'bg-primary'

  return (
    <div className="border-2 border-border rounded-lg bg-card p-4 hover:border-primary/30 transition-colors">
      {/* 标题 + 标签 */}
      <div className="flex justify-between items-start gap-2 mb-3">
        <h3 className="font-semibold text-sm truncate">{project.name}</h3>
        <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium ${stageConfig.bg} ${stageConfig.text} shrink-0`}>
          <StageIcon className={`h-3 w-3 ${stageConfig.isProcessing ? 'animate-spin' : ''}`} />
          {stageConfig.label}
        </span>
      </div>

      {/* 元数据 */}
      <div className="flex items-center gap-3 text-xs text-muted-foreground mb-3">
        <span className="flex items-center gap-1">
          <ChapterIcon className="h-3 w-3" />
          {project.completed_chapters}/{project.chapter_count} 章
        </span>
        <span className="text-border">·</span>
        <span>{project.total_words.toLocaleString()} 字</span>
        <span className="text-border">·</span>
        <span>{new Date(project.updated_at).toLocaleDateString()}</span>
      </div>

      {/* 进度条 */}
      <div className="mb-3">
        <div className="flex justify-between items-center mb-1">
          <span className="text-xs text-muted-foreground">{statusText}</span>
          <span className="text-xs font-medium">{project.progress_percentage}%</span>
        </div>
        <Progress value={project.progress_percentage} className={`h-1.5 [&>div]:${progressColor}`} />
      </div>

      {/* 操作按钮 */}
      <div className="flex gap-2">
        <Button asChild size="sm" className="flex-1">
          <Link to={`/project/${project.id}/workbench`}>
            {stage === 'complete' ? '查看' : '继续'}
          </Link>
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