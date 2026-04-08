// frontend/src/pages/Home.tsx
import { useState, useEffect } from 'react'
import { Plus } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Card, CardContent } from '@/components/ui/card'
import ProjectCard from '@/components/common/ProjectCard'
import { projectsApi } from '@/lib/api'
import { useAuthStore } from '@/stores/authStore'
import type { ProjectDetail } from '@/types'

export default function Home() {
  const [projects, setProjects] = useState<ProjectDetail[]>([])
  const [loading, setLoading] = useState(true)
  const [showNewProject, setShowNewProject] = useState(false)
  const [newProjectName, setNewProjectName] = useState('')
  const [creating, setCreating] = useState(false)

  const isAuthenticated = useAuthStore((state) => state.isAuthenticated)

  const fetchProjects = async () => {
    try {
      const response = await projectsApi.list()
      // Fetch details for each project
      const details = await Promise.all(
        response.projects.map(p => projectsApi.get(p.id))
      )
      setProjects(details)
    } catch (err) {
      console.error('Failed to fetch projects:', err)
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

    setCreating(true)
    try {
      await projectsApi.create({ name: newProjectName })
      setShowNewProject(false)
      setNewProjectName('')
      fetchProjects()
    } catch (err) {
      console.error('Failed to create project:', err)
    } finally {
      setCreating(false)
    }
  }

  const handleDeleteProject = async (id: number) => {
    if (!confirm('确定要删除这个项目吗？')) return

    try {
      await projectsApi.delete(id)
      setProjects(projects.filter(p => p.id !== id))
    } catch (err) {
      console.error('Failed to delete project:', err)
    }
  }

  if (loading) {
    return <div className="text-center py-10">加载中...</div>
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

      {showNewProject && (
        <Card className="mb-6">
          <CardContent className="p-4">
            <div className="flex gap-2">
              <Input
                placeholder="项目名称"
                value={newProjectName}
                onChange={(e) => setNewProjectName(e.target.value)}
                onKeyDown={(e) => e.key === 'Enter' && handleCreateProject()}
              />
              <Button onClick={handleCreateProject} disabled={creating}>
                {creating ? '创建中...' : '创建'}
              </Button>
              <Button variant="outline" onClick={() => setShowNewProject(false)}>
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
              onDelete={handleDeleteProject}
            />
          ))}
        </div>
      )}
    </div>
  )
}