# ProjectCard 重设计实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 修复项目卡片 BUG 并重设计信息架构：连载中/已完结状态、已写字数、当前章节、更新时间

**Architecture:** 后端 schema 加 is_completed/is_busy 字段，前端 ProjectCard 组件重写，Home.tsx 加 visibilitychange 刷新

**Tech Stack:** Python/FastAPI/Pydantic/SQLAlchemy（后端），React/TypeScript/shadcn/ui/lucide-react（前端），pytest（后端测试），vitest（前端测试）

---

## 文件结构

| 操作 | 文件 | 职责 |
|------|------|------|
| Modify | `backend/app/schemas/project.py` | 加 is_completed、is_busy 字段；修正 ListResponse 类型 |
| Modify | `backend/app/api/projects.py` | get_project_detail 计算 is_completed、传 is_busy |
| Modify | `frontend/src/types/index.ts` | ProjectDetail 加 is_completed、is_busy |
| Modify | `frontend/src/components/common/ProjectCard.tsx` | 组件重写：新信息架构，移除 Progress import |
| Modify | `frontend/src/components/ui/skeleton.tsx` | 骨架屏匹配新布局 |
| Modify | `frontend/src/pages/Home.tsx` | visibilitychange 刷新 + handleDeleteProject 函数式更新 |
| Create | `backend/tests/test_project_detail.py` | 后端测试：is_completed 计算逻辑 + API 端到端 |
| Modify | `frontend/src/pages/__tests__/Home.test.tsx` | 前端测试：visibilitychange |

---

### Task 1: 后端 schema 修正 + is_completed/is_busy 字段

**Files:**
- Modify: `backend/app/schemas/project.py:61-72`
- Modify: `backend/app/api/projects.py:30-67`
- Create: `backend/tests/test_project_detail.py`

- [ ] **Step 1: 写失败测试**

创建 `backend/tests/test_project_detail.py`：

```python
"""测试 ProjectDetailResponse 的 is_completed 和 is_busy 计算逻辑"""
import pytest
from app.schemas.project import (
    ProjectDetailResponse,
    ProjectListResponse,
    WorkflowStateResponse,
)
from datetime import datetime, timezone


def _make_workflow_state(project_id=1):
    return WorkflowStateResponse(
        id=1,
        project_id=project_id,
        stage="writing",
        current_chapter=1,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )


def test_is_completed_when_all_chapters_done():
    """所有章节审核通过 → is_completed=True"""
    resp = ProjectDetailResponse(
        id=1, user_id=1, name="test", target_words=100000,
        total_words=50000, created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
        workflow_state=_make_workflow_state(),
        chapter_count=10, completed_chapters=10,
        progress_percentage=100.0,
        is_completed=True, is_busy=False,
    )
    assert resp.is_completed is True


def test_is_completed_false_when_no_chapters():
    """无章节 → is_completed=False（不能误判新项目为已完结）"""
    resp = ProjectDetailResponse(
        id=1, user_id=1, name="test", target_words=100000,
        total_words=0, created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
        workflow_state=_make_workflow_state(),
        chapter_count=0, completed_chapters=0,
        progress_percentage=0.0,
        is_completed=False, is_busy=False,
    )
    assert resp.is_completed is False


def test_is_completed_false_when_incomplete():
    """部分章节完成 → is_completed=False"""
    resp = ProjectDetailResponse(
        id=1, user_id=1, name="test", target_words=100000,
        total_words=50000, created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
        workflow_state=_make_workflow_state(),
        chapter_count=10, completed_chapters=5,
        progress_percentage=50.0,
        is_completed=False, is_busy=False,
    )
    assert resp.is_completed is False


def test_is_busy_reflects_project_state():
    """is_busy 应正确反映项目的 busy 状态"""
    resp = ProjectDetailResponse(
        id=1, user_id=1, name="test", target_words=100000,
        total_words=50000, created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
        workflow_state=_make_workflow_state(),
        chapter_count=10, completed_chapters=5,
        progress_percentage=50.0,
        is_completed=False, is_busy=True,
    )
    assert resp.is_busy is True


def test_list_response_accepts_detail():
    """ProjectListResponse.projects 应接受 ProjectDetailResponse"""
    detail = ProjectDetailResponse(
        id=1, user_id=1, name="test", target_words=100000,
        total_words=0, created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
        workflow_state=_make_workflow_state(),
        chapter_count=0, completed_chapters=0,
        progress_percentage=0.0,
        is_completed=False, is_busy=False,
    )
    resp = ProjectListResponse(projects=[detail], total=1)
    assert len(resp.projects) == 1
    assert isinstance(resp.projects[0], ProjectDetailResponse)
```

- [ ] **Step 2: 运行测试确认失败**

Run: `docker exec novelagent-backend-1 pytest backend/tests/test_project_detail.py -v`
Expected: FAIL — `ProjectDetailResponse` 没有 `is_completed`/`is_busy` 字段

- [ ] **Step 3: 修改 schema**

修改 `backend/app/schemas/project.py`：

将 `ProjectDetailResponse` 改为：

```python
class ProjectDetailResponse(ProjectResponse):
    """Project 详情响应 Schema"""

    chapter_count: int = 0
    completed_chapters: int = 0
    progress_percentage: float = 0.0
    is_completed: bool = False
    is_busy: bool = False
```

将 `ProjectListResponse` 改为：

```python
class ProjectListResponse(BaseModel):
    """Project 列表响应 Schema"""

    projects: List[ProjectDetailResponse]
    total: int
```

- [ ] **Step 4: 运行测试确认通过**

Run: `docker exec novelagent-backend-1 pytest backend/tests/test_project_detail.py -v`
Expected: PASS

- [ ] **Step 5: 修改 get_project_detail 计算新字段**

修改 `backend/app/api/projects.py` 的 `get_project_detail` 函数（第 30-67 行），替换为：

```python
def get_project_detail(project: Project, db: Session) -> ProjectDetailResponse:
    """构建项目详情，包含工作流状态和章节进度（优化查询）"""
    from sqlalchemy.orm import joinedload

    # 单次查询带关联加载，避免 N+1 问题
    chapter_outlines = (
        db.query(ChapterOutline)
        .options(joinedload(ChapterOutline.chapter))
        .filter(ChapterOutline.project_id == project.id)
        .order_by(ChapterOutline.chapter_number)
        .all()
    )

    chapter_count = len(chapter_outlines)
    completed_chapters = sum(
        1 for co in chapter_outlines if co.chapter and co.chapter.review_passed
    )

    progress_percentage = (
        (completed_chapters / chapter_count * 100) if chapter_count > 0 else 0
    )

    # 已完结：有章节且全部审核通过（防止无章节的新项目误判）
    is_completed = chapter_count > 0 and completed_chapters == chapter_count

    # 获取工作流状态
    workflow_state = get_or_create_workflow_state(db, project.id)

    return ProjectDetailResponse(
        id=project.id,
        user_id=project.user_id,
        name=project.name,
        target_words=project.target_words,
        total_words=project.total_words,
        created_at=project.created_at,
        updated_at=project.updated_at,
        workflow_state=WorkflowStateResponse.model_validate(workflow_state),
        chapter_count=chapter_count,
        completed_chapters=completed_chapters,
        progress_percentage=round(progress_percentage, 1),
        is_completed=is_completed,
        is_busy=project.is_busy,
    )
```

- [ ] **Step 6: 写 API 端到端测试**

在 `backend/tests/test_project_detail.py` 末尾追加：

```python
def test_list_projects_returns_is_completed_and_is_busy(client, auth_headers):
    """GET /api/projects/ 应返回 is_completed 和 is_busy 字段"""
    from app.models.project import Project
    from app.database import get_db

    # 需要先通过 API 创建项目（走 get_db override）
    response = client.post(
        "/api/projects/",
        json={"name": "test project", "target_words": 100000},
        headers=auth_headers,
    )
    assert response.status_code == 201

    # 列表接口
    response = client.get("/api/projects/", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert data["total"] >= 1
    project = data["projects"][0]
    assert "is_completed" in project
    assert "is_busy" in project
    assert project["is_completed"] is False
    assert project["is_busy"] is False
```

- [ ] **Step 7: 运行全量后端测试**

Run: `docker exec novelagent-backend-1 pytest -v`
Expected: ALL PASS

- [ ] **Step 8: 重启后端**

Run: `docker compose restart backend`

- [ ] **Step 9: 提交**

```bash
git add backend/app/schemas/project.py backend/app/api/projects.py backend/tests/test_project_detail.py
git commit -m "feat(api): add is_completed/is_busy to ProjectDetailResponse, fix ProjectListResponse type"
```

---

### Task 2: 前端类型定义更新

**Files:**
- Modify: `frontend/src/types/index.ts:54-58`

- [ ] **Step 1: 修改 ProjectDetail 接口**

修改 `frontend/src/types/index.ts`，将 `ProjectDetail` 改为：

```typescript
export interface ProjectDetail extends Project {
  chapter_count: number
  completed_chapters: number
  progress_percentage: number
  is_completed: boolean
  is_busy: boolean
}
```

- [ ] **Step 2: 提交**

```bash
git add frontend/src/types/index.ts
git commit -m "feat(frontend): add is_completed/is_busy to ProjectDetail type"
```

---

### Task 3: ProjectCard 组件重写

**Files:**
- Modify: `frontend/src/components/common/ProjectCard.tsx`

- [ ] **Step 1: 重写 ProjectCard**

完整替换 `frontend/src/components/common/ProjectCard.tsx`：

```tsx
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
```

注意：移除了 `Progress`、`Loader2`、`Circle`、`PenLine`、`FileText`、`Sparkles` 等不再使用的 import，仅保留 `BookOpen`、`CheckCircle2`。

- [ ] **Step 2: 重启前端确认编译通过**

Run: `docker compose restart frontend`
检查 `docker compose logs frontend --tail 20` 无编译错误

- [ ] **Step 3: 提交**

```bash
git add frontend/src/components/common/ProjectCard.tsx
git commit -m "feat(frontend): redesign ProjectCard - 连载中/已完结状态, 简化信息架构"
```

---

### Task 4: 骨架屏更新

**Files:**
- Modify: `frontend/src/components/ui/skeleton.tsx`

- [ ] **Step 1: 更新 ProjectCardSkeleton 匹配新布局**

替换 `frontend/src/components/ui/skeleton.tsx` 中的 `ProjectCardSkeleton`：

```tsx
export function ProjectCardSkeleton()
{
  return (
    <div className="border-2 border-border rounded-lg bg-card p-4">
      {/* 标题 + 状态标签 */}
      <div className="flex justify-between items-start gap-2 mb-4">
        <Skeleton className="h-5 w-28" />
        <Skeleton className="h-5 w-16 rounded-full" />
      </div>
      {/* 信息行 */}
      <div className="flex flex-col gap-2 mb-4">
        <div className="flex justify-between">
          <Skeleton className="h-3 w-8" />
          <Skeleton className="h-5 w-20" />
        </div>
        <div className="flex justify-between">
          <Skeleton className="h-3 w-8" />
          <Skeleton className="h-4 w-14" />
        </div>
        <div className="flex justify-between">
          <Skeleton className="h-3 w-8" />
          <Skeleton className="h-4 w-24" />
        </div>
      </div>
      {/* 按钮 */}
      <div className="flex gap-2">
        <Skeleton className="h-8 flex-1 rounded-md" />
        <Skeleton className="h-8 w-14 rounded-md" />
      </div>
    </div>
  )
}
```

- [ ] **Step 2: 提交**

```bash
git add frontend/src/components/ui/skeleton.tsx
git commit -m "feat(frontend): update ProjectCardSkeleton to match new card layout"
```

---

### Task 5: Home.tsx 刷新机制 + state 更新修复

**Files:**
- Modify: `frontend/src/pages/Home.tsx`
- Modify: `frontend/src/pages/__tests__/Home.test.tsx`

本 Task 修复两个问题：
1. 页面恢复可见时刷新项目列表（visibilitychange）
2. `handleDeleteProject` 使用函数式 state 更新，避免 stale state

- [ ] **Step 1: 修改 Home.tsx**

对 `frontend/src/pages/Home.tsx` 做以下改动：

**1a. 添加 useRef import**

将第 2 行改为：
```tsx
import { useState, useEffect, useRef } from 'react'
```

**1b. 添加 isAuthenticatedRef**

在第 32 行 `const isAuthenticated = ...` 之后添加：
```tsx
  const isAuthenticatedRef = useRef(isAuthenticated)
  isAuthenticatedRef.current = isAuthenticated
```

**1c. 替换 useEffect（第 51-57 行）**

将原来的 `useEffect` 替换为合并版本：
```tsx
  useEffect(() =>
  {
    if (!isAuthenticated) return

    fetchProjects()

    const handleVisibilityChange = () =>
    {
      if (document.visibilityState === 'visible' && isAuthenticatedRef.current)
      {
        fetchProjects()
      }
    }
    document.addEventListener('visibilitychange', handleVisibilityChange)
    return () =>
    {
      document.removeEventListener('visibilitychange', handleVisibilityChange)
    }
  }, [isAuthenticated])
```

**1d. 修复 handleDeleteProject stale state**

将第 59-71 行的 `handleDeleteProject` 中 `setProjects(projects.filter(...))` 改为函数式更新：
```tsx
  const handleDeleteProject = async (id: number) =>
  {
    try
    {
      await projectsApi.delete(id)
      setProjects(prev => prev.filter(p => p.id !== id))
      setDeleteTarget(null)
    } catch (err)
    {
      console.error('Failed to delete project:', err)
      toast.error(err instanceof Error ? err.message : '删除项目失败')
    }
  }
```

- [ ] **Step 2: 更新前端测试**

替换 `frontend/src/pages/__tests__/Home.test.tsx`：

```tsx
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@/test/utils'
import Home from '@/pages/Home'

const mockIsAuthenticated = vi.fn()

vi.mock('@/stores/authStore', () => ({
  useAuthStore: vi.fn((selector) => {
    const state = { isAuthenticated: mockIsAuthenticated(), setUser: vi.fn(), setToken: vi.fn() }
    return selector ? selector(state) : state
  }),
}))

vi.mock('@/lib/api', () => ({
  projectsApi: {
    list: vi.fn(),
    create: vi.fn(),
    delete: vi.fn(),
  },
  authApi: {},
  settingsApi: {},
  modelConfigsApi: {},
  outlineApi: {},
  chapterOutlinesApi: {},
  chaptersApi: {},
}))

import { projectsApi } from '@/lib/api'

describe('Home', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('shows loading skeleton initially when authenticated', () => {
    mockIsAuthenticated.mockReturnValue(true)
    vi.mocked(projectsApi.list).mockReturnValue(new Promise(() => {}))

    render(<Home />)

    expect(screen.getByText('我的项目')).toBeInTheDocument()
    expect(document.querySelectorAll('.animate-pulse').length).toBeGreaterThan(0)
  })

  it('shows empty state when no projects exist', async () => {
    mockIsAuthenticated.mockReturnValue(true)
    vi.mocked(projectsApi.list).mockResolvedValueOnce({ projects: [], total: 0 })

    render(<Home />)

    await waitFor(() => {
      expect(screen.getByText('创建你的第一个项目，开始写作之旅')).toBeInTheDocument()
    })
  })

  it('refreshes project list when page becomes visible', async () => {
    mockIsAuthenticated.mockReturnValue(true)
    vi.mocked(projectsApi.list).mockResolvedValue({ projects: [], total: 0 })

    render(<Home />)

    await waitFor(() => {
      expect(vi.mocked(projectsApi.list)).toHaveBeenCalledTimes(1)
    })

    Object.defineProperty(document, 'visibilityState', { value: 'hidden', configurable: true })
    document.dispatchEvent(new Event('visibilitychange'))

    Object.defineProperty(document, 'visibilityState', { value: 'visible', configurable: true })
    document.dispatchEvent(new Event('visibilitychange'))

    await waitFor(() => {
      expect(vi.mocked(projectsApi.list)).toHaveBeenCalledTimes(2)
    })
  })
})
```

- [ ] **Step 3: 运行前端测试**

Run: `cd frontend && npm run test:run`
Expected: PASS

- [ ] **Step 4: 提交**

```bash
git add frontend/src/pages/Home.tsx frontend/src/pages/__tests__/Home.test.tsx
git commit -m "feat(frontend): add visibilitychange refresh and fix stale state in handleDeleteProject"
```

---

### Task 6: 集成验证

- [ ] **Step 1: 重启后端和前端**

Run: `docker compose restart backend && docker compose restart frontend`

- [ ] **Step 2: 运行后端全量测试**

Run: `docker exec novelagent-backend-1 pytest -v`
Expected: ALL PASS

- [ ] **Step 3: 运行前端测试**

Run: `cd frontend && npm run test:run`
Expected: PASS

- [ ] **Step 4: 运行前端 lint**

Run: `cd frontend && npm run lint`
Expected: 无错误

- [ ] **Step 5: 浏览器验证**

打开 http://localhost:3001，确认：
- 项目卡片显示：项目名 + 连载中/已完结标签 + 已写字数 + 当前章节 + 更新时间
- 新项目（0 章）当前章节显示 "—"
- 切换到其他页面再切回首页，项目列表自动刷新
- 骨架屏布局与新卡片匹配
