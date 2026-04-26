// frontend/src/pages/Home.tsx
import { useState, useEffect } from 'react'
import { Plus } from 'lucide-react'
import { toast } from 'sonner'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Card, CardContent } from '@/components/ui/card'
import ProjectCard from '@/components/common/ProjectCard'
import ErrorMessage from '@/components/common/ErrorMessage'
import { ProjectCardSkeleton } from '@/components/ui/skeleton'
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from '@/components/ui/alert-dialog'
import { projectsApi } from '@/lib/api'
import { useAuthStore } from '@/stores/authStore'
import type { ProjectDetail } from '@/types'

export default function Home() {
  const [projects, setProjects] = useState<ProjectDetail[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [showNewProject, setShowNewProject] = useState(false)
  const [newProjectName, setNewProjectName] = useState('')
  const [creating, setCreating] = useState(false)
  const [createError, setCreateError] = useState<string | null>(null)
  const [deleteTarget, setDeleteTarget] = useState<{ id: number; name: string } | null>(null)

  const isAuthenticated = useAuthStore((state) => state.isAuthenticated)

  const fetchProjects = async () => {
    // 获取项目列表，后端已直接返回详情，无需额外请求
    setError(null)
    try {
      const response = await projectsApi.list()
      // 后端现在直接返回 ProjectDetail 列表
      setProjects(response.projects as ProjectDetail[])
    } catch (err) {
      console.error('Failed to fetch projects:', err)
      setError(err instanceof Error ? err.message : '加载项目列表失败')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    if (isAuthenticated) {
      fetchProjects()
    }
  }, [isAuthenticated])

  const handleCreateProject = async () => {
    if (!newProjectName.trim()) return
    if (newProjectName.length > 100) {
      setCreateError('项目名称不能超过 100 个字符')
      return
    }

    setCreating(true)
    setCreateError(null)
    try {
      await projectsApi.create({ name: newProjectName })
      setShowNewProject(false)
      setNewProjectName('')
      fetchProjects()
    } catch (err) {
      console.error('Failed to create project:', err)
      setCreateError(err instanceof Error ? err.message : '创建项目失败')
    } finally {
      setCreating(false)
    }
  }

  const handleDeleteProject = async (id: number) => {
    try {
      await projectsApi.delete(id)
      setProjects(projects.filter(p => p.id !== id))
      setDeleteTarget(null)
    } catch (err) {
      console.error('Failed to delete project:', err)
      toast.error(err instanceof Error ? err.message : '删除项目失败')
    }
  }

  const handleDeleteClick = (project: ProjectDetail) => {
    setDeleteTarget({ id: project.id, name: project.name })
  }

  if (loading) {
    return (
      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
        {Array.from({ length: 6 }).map((_, i) => (
          <ProjectCardSkeleton key={i} />
        ))}
      </div>
    )
  }

  return (
    <div>
      <div className="flex justify-between items-center mb-6">
        <h1 className="text-2xl font-bold">我的项目</h1>
        <Button onClick={() => setShowNewProject(true)}>
          <Plus className="h-4 w-4 mr-2" />
          新建项目
        </Button>
      </div>

      {error && (
        <div className="mb-6">
          <ErrorMessage message={error} onRetry={fetchProjects} onDismiss={() => setError(null)} />
        </div>
      )}

      {showNewProject && (
        <Card className="mb-6">
          <CardContent className="p-4">
            {createError && (
              <div className="mb-3">
                <ErrorMessage message={createError} onDismiss={() => setCreateError(null)} />
              </div>
            )}
            <div className="flex gap-2">
              <Input
                placeholder="项目名称"
                value={newProjectName}
                onChange={(e) => setNewProjectName(e.target.value)}
                onKeyDown={(e) => e.key === 'Enter' && handleCreateProject()}
                maxLength={100}
              />
              <Button onClick={handleCreateProject} disabled={creating}>
                {creating ? '创建中...' : '创建'}
              </Button>
              <Button variant="outline" onClick={() => {
                setShowNewProject(false)
                setNewProjectName('')
                setCreateError(null)
              }}>
                取消
              </Button>
            </div>
          </CardContent>
        </Card>
      )}

      {projects.length === 0 ? (
        <div className="text-center py-20 text-muted-foreground">
          <p>还没有项目，点击上方按钮创建第一个项目</p>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
          {projects.map((project) => (
            <ProjectCard
              key={project.id}
              project={project}
              onDelete={() => handleDeleteClick(project)}
            />
          ))}
        </div>
      )}

      {/* Delete Confirmation Dialog */}
      <AlertDialog open={!!deleteTarget} onOpenChange={(open) => !open && setDeleteTarget(null)}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>删除项目</AlertDialogTitle>
            <AlertDialogDescription>
              确定要删除项目「{deleteTarget?.name}」吗？此操作不可撤销。
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>取消</AlertDialogCancel>
            <AlertDialogAction
              className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
              onClick={() => deleteTarget && handleDeleteProject(deleteTarget.id)}
            >
              确认删除
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  )
}