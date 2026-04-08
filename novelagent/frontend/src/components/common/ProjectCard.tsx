// frontend/src/components/common/ProjectCard.tsx
import { Link } from 'react-router-dom'
import { Card, CardContent } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Progress } from '@/components/ui/progress'
import type { ProjectDetail } from '@/types'

interface ProjectCardProps {
  project: ProjectDetail
  onDelete: (id: number) => void
}

const STAGE_LABELS: Record<string, { label: string; color: string }> = {
  collecting_info: { label: '信息收集', color: 'bg-yellow-500' },
  outline_generating: { label: '生成大纲', color: 'bg-blue-500' },
  outline_confirming: { label: '确认大纲', color: 'bg-blue-500' },
  chapter_outlines_generating: { label: '生成章节纲', color: 'bg-purple-500' },
  chapter_writing: { label: '写作中', color: 'bg-green-500' },
  completed: { label: '已完成', color: 'bg-emerald-500' },
  paused: { label: '暂停', color: 'bg-gray-500' },
}

export default function ProjectCard({ project, onDelete }: ProjectCardProps) {
  const stageInfo = STAGE_LABELS[project.stage] || { label: project.stage, color: 'bg-gray-500' }

  return (
    <Card className="hover:shadow-lg transition-shadow">
      <CardContent className="p-4">
        <div className="flex justify-between items-start mb-3">
          <h3 className="font-semibold text-lg truncate">{project.name}</h3>
          <span className={`px-2 py-0.5 rounded text-xs text-white ${stageInfo.color}`}>
            {stageInfo.label}
          </span>
        </div>

        <div className="space-y-1 text-sm text-muted-foreground mb-3">
          <div>📝 第 {project.completed_chapters} 章 / 共 {project.chapter_count} 章</div>
          <div>📏 {project.total_words.toLocaleString()} 字</div>
          <div>🕐 {new Date(project.updated_at).toLocaleDateString()}</div>
        </div>

        <div className="mb-3">
          <Progress value={project.progress_percentage} className="h-2" />
          <div className="text-xs text-muted-foreground mt-1">
            进度 {project.progress_percentage}%
          </div>
        </div>

        <div className="flex gap-2">
          <Link to={`/project/${project.id}`} className="flex-1">
            <Button className="w-full" size="sm">
              {project.stage === 'completed' ? '查看' : '继续'}
            </Button>
          </Link>
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