// frontend/src/components/common/ProjectCard.tsx
import { Link } from 'react-router-dom'
import { Loader2, CheckCircle, Circle, PenLine, FileText, Sparkles, BookOpen } from 'lucide-react'
import { Card, CardContent } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Progress } from '@/components/ui/progress'
import type { ProjectDetail } from '@/types'

interface ProjectCardProps {
  project: ProjectDetail
  onDelete: (id: number) => void
}

// 工作流阶段配置：标签、颜色、图标
const STAGE_CONFIG: Record<string, { label: string; color: string; icon: React.ElementType; isProcessing: boolean; isCompleted: boolean }> = {
  inspiration_collecting: { label: '灵感采集', color: 'bg-yellow-500', icon: Sparkles, isProcessing: false, isCompleted: false },
  outline_generating: { label: '生成大纲', color: 'bg-blue-500', icon: Loader2, isProcessing: true, isCompleted: false },
  outline_confirming: { label: '确认大纲', color: 'bg-blue-500', icon: FileText, isProcessing: false, isCompleted: false },
  chapter_outlines_generating: { label: '生成章节纲', color: 'bg-purple-500', icon: Loader2, isProcessing: true, isCompleted: false },
  chapter_outlines_confirming: { label: '确认章节纲', color: 'bg-purple-500', icon: BookOpen, isProcessing: false, isCompleted: false },
  chapter_writing: { label: '写作中', color: 'bg-green-500', icon: PenLine, isProcessing: false, isCompleted: false },
  chapter_reviewing: { label: '审核中', color: 'bg-orange-500', icon: Loader2, isProcessing: true, isCompleted: false },
  completed: { label: '已完成', color: 'bg-emerald-500', icon: CheckCircle, isProcessing: false, isCompleted: true },
  paused: { label: '暂停', color: 'bg-gray-500', icon: Circle, isProcessing: false, isCompleted: false },
}

export default function ProjectCard({ project, onDelete }: ProjectCardProps) {
  const stageConfig = STAGE_CONFIG[project.stage] || {
    label: project.stage,
    color: 'bg-gray-500',
    icon: Circle,
    isProcessing: false,
    isCompleted: false
  }
  const StageIcon = stageConfig.icon

  // 确定进度状态文字
  const getProgressStatus = () => {
    if (stageConfig.isCompleted) return '已完成'
    if (stageConfig.isProcessing) return '处理中'
    return '进行中'
  }

  return (
    <Card className="hover:shadow-lg transition-shadow">
      <CardContent className="p-4">
        <div className="flex justify-between items-start mb-3">
          <h3 className="font-semibold text-lg truncate">{project.name}</h3>
          <div className={`flex items-center gap-1 px-2 py-0.5 rounded text-xs text-white ${stageConfig.color}`}>
            <StageIcon className={`h-3 w-3 ${stageConfig.isProcessing ? 'animate-spin' : ''}`} />
            <span>{stageConfig.label}</span>
          </div>
        </div>

        <div className="space-y-1 text-sm text-muted-foreground mb-3">
          <div className="flex items-center gap-1.5">
            <FileText className="h-3.5 w-3.5" />
            <span>第 {project.completed_chapters} 章 / 共 {project.chapter_count} 章</span>
          </div>
          <div>📏 {project.total_words.toLocaleString()} 字</div>
          <div>🕐 {new Date(project.updated_at).toLocaleDateString()}</div>
        </div>

        <div className="mb-3">
          <div className="flex items-center justify-between mb-1">
            <div className="flex items-center gap-1.5">
              {stageConfig.isCompleted ? (
                <CheckCircle className="h-3.5 w-3.5 text-green-600" />
              ) : stageConfig.isProcessing ? (
                <Loader2 className="h-3.5 w-3.5 text-blue-600 animate-spin" />
              ) : (
                <Circle className="h-3.5 w-3.5 text-gray-400" />
              )}
              <span className="text-xs text-muted-foreground">{getProgressStatus()}</span>
            </div>
            <span className="text-xs font-medium">{project.progress_percentage}%</span>
          </div>
          <Progress value={project.progress_percentage} className="h-2" />
        </div>

        <div className="flex gap-2">
          <Button asChild className="flex-1" size="sm">
            <Link to={`/project/${project.id}`}>
              {project.stage === 'completed' ? '查看' : '继续'}
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
      </CardContent>
    </Card>
  )
}