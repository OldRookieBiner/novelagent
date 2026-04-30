# 项目列表页与工作台协调优化 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 优化 Home 页和 WorkbenchLayout，使其共享全局 Header，并将 ProjectCard 重新设计为与 Workbench 组件视觉一致。

**Architecture:** Home 和 Workbench 直接复用现有 `Header` 组件作为全局 Header；ProjectCard 重写为 border-2 卡片风格；新建项目从内联表单改为占位卡片 + Dialog；WorkbenchLayout 在项目 Header 上层叠加全局 Header。

**Tech Stack:** React 18 + TypeScript + shadcn/ui + Tailwind CSS + lucide-react

---

## 文件结构

| 文件 | 操作 | 职责 |
|------|------|------|
| `frontend/src/components/layout/Header.tsx` | 修改 | 提取到全局 Header，支持 Home/Workbench 直接引用 |
| `frontend/src/pages/Home.tsx` | 修改 | 引入 Header；重构内容区（auto-fill 网格）；占位卡片替换内联表单 |
| `frontend/src/components/common/ProjectCard.tsx` | 重写 | border-2 风格；柔和 pill 标签；元数据横向排列 |
| `frontend/src/components/workbench/WorkbenchLayout.tsx` | 修改 | 在项目 Header 上方添加全局 Header |
| `frontend/src/components/project/CreateProjectDialog.tsx` | 创建 | 新建项目 Dialog 组件 |
| `frontend/src/components/ui/skeleton.tsx` | 修改 | 骨架屏卡片适配新风格 |

---

### Task 1: CreateProjectDialog 组件

**Files:**
- Create: `frontend/src/components/project/CreateProjectDialog.tsx`

- [ ] **Step 1: 创建 CreateProjectDialog 组件**

```tsx
// frontend/src/components/project/CreateProjectDialog.tsx
import { useState } from 'react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { projectsApi } from '@/lib/api'

interface CreateProjectDialogProps
{
  open: boolean
  onOpenChange: (open: boolean) => void
  onCreated: () => void
}

export default function CreateProjectDialog({ open, onOpenChange, onCreated }: CreateProjectDialogProps)
{
  const [name, setName] = useState('')
  const [creating, setCreating] = useState(false)
  const [error, setError] = useState('')

  const handleCreate = async () =>
  {
    if (!name.trim()) return
    if (name.length > 100)
    {
      setError('项目名称不能超过 100 个字符')
      return
    }

    setCreating(true)
    setError('')
    try
    {
      await projectsApi.create({ name })
      setName('')
      onOpenChange(false)
      onCreated()
    } catch (err)
    {
      setError(err instanceof Error ? err.message : '创建项目失败')
    } finally
    {
      setCreating(false)
    }
  }

  const handleOpenChange = (open: boolean) =>
  {
    if (!open)
    {
      setName('')
      setError('')
    }
    onOpenChange(open)
  }

  return (
    <Dialog open={open} onOpenChange={handleOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>新建项目</DialogTitle>
          <DialogDescription>输入项目名称开始创作你的小说</DialogDescription>
        </DialogHeader>
        <div className="space-y-4 py-2">
          <Input
            placeholder="项目名称"
            value={name}
            onChange={(e) => { setName(e.target.value); setError('') }}
            onKeyDown={(e) => e.key === 'Enter' && handleCreate()}
            maxLength={100}
            autoFocus
          />
          {error && (
            <p className="text-sm text-destructive">{error}</p>
          )}
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)}>取消</Button>
          <Button onClick={handleCreate} disabled={creating || !name.trim()}>
            {creating ? '创建中...' : '创建'}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/components/project/CreateProjectDialog.tsx
git commit -m "feat(frontend): add CreateProjectDialog component"
```

---

### Task 2: 重写 ProjectCard 组件

**Files:**
- Modify: `frontend/src/components/common/ProjectCard.tsx` (全文重写)

- [ ] **Step 1: 重写 ProjectCard**

```tsx
// frontend/src/components/common/ProjectCard.tsx
import { Link } from 'react-router-dom'
import { Loader2, CheckCircle, Circle, PenLine, FileText, Sparkles, BookOpen, FileText as ChapterIcon } from 'lucide-react'
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
        <Button asChild className="flex-1" size="sm">
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
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/components/common/ProjectCard.tsx
git commit -m "refactor(frontend): redesign ProjectCard with border-2 style and soft pill labels"
```

---

### Task 3: ProjectCardSkeleton 适配新风格

**Files:**
- Modify: `frontend/src/components/ui/skeleton.tsx`

- [ ] **Step 1: 读取当前 skeleton 文件找到 ProjectCardSkeleton**

Run: `grep -n "ProjectCardSkeleton" frontend/src/components/ui/skeleton.tsx`
Expected: 找到 ProjectCardSkeleton 定义位置

- [ ] **Step 2: 更新 ProjectCardSkeleton**

将 `ProjectCardSkeleton` 替换为适配新卡片风格的骨架屏：

```tsx
export function ProjectCardSkeleton()
{
  return (
    <div className="border-2 border-border rounded-lg bg-card p-4">
      <div className="flex justify-between items-start gap-2 mb-3">
        <Skeleton className="h-5 w-28" />
        <Skeleton className="h-5 w-16 rounded-full" />
      </div>
      <div className="flex items-center gap-3 mb-3">
        <Skeleton className="h-3 w-16" />
        <Skeleton className="h-3 w-12" />
        <Skeleton className="h-3 w-16" />
      </div>
      <div className="mb-3 space-y-1">
        <div className="flex justify-between">
          <Skeleton className="h-3 w-10" />
          <Skeleton className="h-3 w-8" />
        </div>
        <Skeleton className="h-1.5 w-full rounded-full" />
      </div>
      <div className="flex gap-2">
        <Skeleton className="h-8 flex-1 rounded-md" />
        <Skeleton className="h-8 w-14 rounded-md" />
      </div>
    </div>
  )
}
```

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/ui/skeleton.tsx
git commit -m "fix(frontend): update ProjectCardSkeleton to match new card style"
```

---

### Task 4: Home 页重构

**Files:**
- Modify: `frontend/src/pages/Home.tsx` (全文重写)

- [ ] **Step 1: 重写 Home 页**

```tsx
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
          <div className="grid gap-4" style={{ gridTemplateColumns: 'repeat(auto-fill, minmax(260px, 1fr))' }}>
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
          <div className="grid gap-4" style={{ gridTemplateColumns: 'repeat(auto-fill, minmax(260px, 1fr))' }}>
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
```

- [ ] **Step 4: Commit**

```bash
git add frontend/src/pages/Home.tsx
git commit -m "refactor(frontend): add global Header to Home, use auto-fill grid, create project dialog"
```

---

### Task 5: WorkbenchLayout 添加全局 Header

**Files:**
- Modify: `frontend/src/components/workbench/WorkbenchLayout.tsx`

- [ ] **Step 1: 添加全局 Header 到 WorkbenchLayout**

```tsx
// frontend/src/components/workbench/WorkbenchLayout.tsx

import { ReactNode } from 'react'
import { Link } from 'react-router-dom'
import { ArrowLeft } from 'lucide-react'
import Header from '@/components/layout/Header'
import { TabNavigation } from './TabNavigation'
import { WorkbenchSidebar } from './WorkbenchSidebar'

interface WorkbenchLayoutProps
{
  projectName: string
  progress: number
  children: ReactNode
}

export function WorkbenchLayout({ projectName, progress, children }: WorkbenchLayoutProps)
{
  return (
    <div className="flex flex-col h-screen bg-gray-50">
      {/* 全局 Header */}
      <Header />

      {/* 项目 Header */}
      <header className="h-14 border-b bg-white flex items-center justify-between px-6 shrink-0">
        <div className="flex items-center gap-4">
          <Link to="/" className="flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground transition-colors">
            <ArrowLeft className="h-4 w-4" />
            <span>返回</span>
          </Link>
          <h1 className="text-lg font-semibold">{projectName}</h1>
          <div className="flex items-center gap-2 text-sm text-muted-foreground">
            <div className="w-32 h-2 bg-gray-200 rounded-full overflow-hidden">
              <div
                className="h-full bg-primary rounded-full transition-all"
                style={{ width: `${progress}%` }}
              />
            </div>
          </div>
        </div>
      </header>

      {/* Tab 导航 */}
      <TabNavigation />

      {/* 主内容区 */}
      <div className="flex flex-1 overflow-hidden">
        <WorkbenchSidebar />
        <main className="flex-1 overflow-auto">
          {children}
        </main>
      </div>
    </div>
  )
}
```

- [ ] **Step 4: Commit**

```bash
git add frontend/src/components/workbench/WorkbenchLayout.tsx
git commit -m "feat(frontend): add global Header to WorkbenchLayout"
```

---

### Task 6: 验证与收尾

- [ ] **Step 1: 运行前端 tests**

```bash
cd frontend && npm run test:run
```

验证所有测试通过。

- [ ] **Step 2: 运行 lint/typecheck**

```bash
cd frontend && npm run lint
cd frontend && npx tsc --noEmit
```

验证无错误。

- [ ] **Step 3: 构建验证**

```bash
cd frontend && npm run build
```

验证构建成功。

---

## 自审

**1. Spec 覆盖检查：**
- 全局 Header 复用 → Task 4 (Home) + Task 5 (WorkbenchLayout) ✓
- ProjectCard 重写 → Task 2 ✓
- auto-fill 网格 → Task 4 ✓
- 占位卡片 + Dialog → Task 1 + Task 4 ✓
- Workbench Header 优化 → Task 5 ✓
- 骨架屏适配 → Task 3 ✓
- 空状态处理 → Task 4 ✓

**2. Placeholder 扫描：** 无 TBD/TODO/模糊描述 ✓

**3. 类型一致性：** `CreateProjectDialogProps` 接口与 Home 中使用一致；`ProjectCardProps` 未变化；Header 直接复用无改接口 ✓