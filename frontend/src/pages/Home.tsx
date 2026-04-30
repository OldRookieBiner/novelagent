// frontend/src/pages/Home.tsx
import { useState, useEffect } from 'react'
import { Plus } from 'lucide-react'
import { toast } from 'sonner'
import Header from '@/components/layout/Header'
import ProjectCard from '@/components/common/ProjectCard'
import CreateProjectDialog from '@/components/project/CreateProjectDialog'
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

export default function Home()
{
  const [projects, setProjects] = useState<ProjectDetail[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [showCreateDialog, setShowCreateDialog] = useState(false)
  const [deleteTarget, setDeleteTarget] = useState<{ id: number; name: string } | null>(null)

  const isAuthenticated = useAuthStore((state) => state.isAuthenticated)

  const fetchProjects = async () =>
  {
    setError(null)
    try
    {
      const response = await projectsApi.list()
      setProjects(response.projects)
    } catch (err)
    {
      console.error('Failed to fetch projects:', err)
      setError(err instanceof Error ? err.message : '加载项目列表失败')
    } finally
    {
      setLoading(false)
    }
  }

  useEffect(() =>
  {
    if (isAuthenticated)
    {
      fetchProjects()
    }
  }, [isAuthenticated])

  const handleDeleteProject = async (id: number) =>
  {
    try
    {
      await projectsApi.delete(id)
      setProjects(projects.filter(p => p.id !== id))
      setDeleteTarget(null)
    } catch (err)
    {
      console.error('Failed to delete project:', err)
      toast.error(err instanceof Error ? err.message : '删除项目失败')
    }
  }

  const handleDeleteClick = (project: ProjectDetail) =>
  {
    setDeleteTarget({ id: project.id, name: project.name })
  }

  // 加载状态
  if (loading)
  {
    return (
      <div className="flex flex-col h-screen bg-gray-50">
        <Header />
        <main className="flex-1 overflow-auto p-6">
          <h2 className="text-lg font-semibold mb-6">我的项目</h2>
          <div className="grid gap-4 max-w-[1600px] mx-auto" style={{ gridTemplateColumns: 'repeat(auto-fill, minmax(240px, 1fr))' }}>
            {Array.from({ length: 6 }).map((_, i) => (
              <ProjectCardSkeleton key={i} />
            ))}
          </div>
        </main>
      </div>
    )
  }

  return (
    <div className="flex flex-col h-screen bg-gray-50">
      <Header />

      <main className="flex-1 overflow-auto p-6">
        {error && (
          <div className="mb-6">
            <ErrorMessage message={error} onRetry={fetchProjects} onDismiss={() => setError(null)} />
          </div>
        )}

        <h2 className="text-lg font-semibold mb-6">我的项目</h2>

        {projects.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-20">
            <div
              className="border-2 border-dashed border-border rounded-lg p-8 max-w-xs w-full text-center cursor-pointer hover:border-primary/50 hover:bg-primary/5 transition-colors"
              onClick={() => setShowCreateDialog(true)}
            >
              <div className="w-12 h-12 rounded-full bg-muted flex items-center justify-center mx-auto mb-3">
                <Plus className="h-6 w-6 text-muted-foreground" />
              </div>
              <p className="text-sm font-medium text-muted-foreground">创建新项目</p>
            </div>
            <p className="text-sm text-muted-foreground mt-4">创建你的第一个项目，开始写作之旅</p>
          </div>
        ) : (
          <div className="grid gap-4 max-w-[1600px] mx-auto" style={{ gridTemplateColumns: 'repeat(auto-fill, minmax(240px, 1fr))' }}>
            {/* 占位新建卡片 */}
            <div
              className="border-2 border-dashed border-border rounded-lg p-4 flex flex-col items-center justify-center min-h-[180px] cursor-pointer hover:border-primary/50 hover:bg-primary/5 transition-colors"
              onClick={() => setShowCreateDialog(true)}
            >
              <div className="w-10 h-10 rounded-full bg-muted flex items-center justify-center mb-2">
                <Plus className="h-5 w-5 text-muted-foreground" />
              </div>
              <span className="text-sm font-medium text-muted-foreground">新建项目</span>
            </div>

            {projects.map((project) => (
              <ProjectCard
                key={project.id}
                project={project}
                onDelete={() => handleDeleteClick(project)}
              />
            ))}
          </div>
        )}
      </main>

      <CreateProjectDialog
        open={showCreateDialog}
        onOpenChange={setShowCreateDialog}
        onCreated={fetchProjects}
      />

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