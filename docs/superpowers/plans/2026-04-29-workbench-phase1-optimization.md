# 工作台 Phase 1 优化实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 优化新工作台页面的基础功能，修复关键问题，提升用户体验一致性

**Architecture:** 四个独立任务：1) WorkbenchLayout 添加返回按钮 2) 移除无效保存按钮 3) 修复 WritingPanel console.log 4) Home 页面全屏布局

**Tech Stack:** React 18 + TypeScript + Tailwind CSS

---

## 文件变更规划

### 修改文件

| 文件 | 职责 | 变更内容 |
|------|------|----------|
| `frontend/src/components/workbench/WorkbenchLayout.tsx` | 工作台布局 | 添加返回按钮、移除无效保存按钮 |
| `frontend/src/components/workbench/creation/WritingPanel.tsx` | 写作面板 | 移除 console.log |
| `frontend/src/pages/Home.tsx` | 项目列表 | 使用全屏布局 |
| `frontend/src/App.tsx` | 路由配置 | Home 页面独立路由不经过 Layout |

---

## Task 1: WorkbenchLayout 添加返回按钮

**Files:**
- Modify: `frontend/src/components/workbench/WorkbenchLayout.tsx`

- [ ] **Step 1: 添加 Link 和 ArrowLeft import**

```typescript
import { Link } from 'react-router-dom'
import { ArrowLeft } from 'lucide-react'
```

- [ ] **Step 2: 修改顶部栏左侧添加返回按钮**

将 `frontend/src/components/workbench/WorkbenchLayout.tsx:19-21` 区域修改为：

```tsx
<header className="h-14 border-b bg-white flex items-center justify-between px-6">
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
      <span>{progress}%</span>
    </div>
  </div>
  {/* 右侧保存按钮已移除 */}
</header>
```

- [ ] **Step 3: 提交变更**

```bash
git add frontend/src/components/workbench/WorkbenchLayout.tsx
git commit -m "feat(workbench): add back button to header"
```

---

## Task 2: 移除无效保存按钮

**Files:**
- Modify: `frontend/src/components/workbench/WorkbenchLayout.tsx`

- [ ] **Step 1: 检查当前保存按钮代码**

当前文件第 32-36 行有：

```tsx
<div className="flex items-center gap-2">
  <button className="px-3 py-1.5 text-sm bg-primary text-white rounded-md hover:bg-primary/90">
    保存
  </button>
</div>
```

- [ ] **Step 2: 移除保存按钮代码块**

删除第 32-36 行（右侧按钮区域）

- [ ] **Step 3: 提交变更**

```bash
git add frontend/src/components/workbench/WorkbenchLayout.tsx
git commit -m "feat(workbench): remove non-functional save button"
```

---

## Task 3: 修复 WritingPanel console.log

**Files:**
- Modify: `frontend/src/components/workbench/creation/WritingPanel.tsx`

- [ ] **Step 1: 找到并移除 console.log**

当前文件第 333-336 行：

```tsx
onReviewComplete={(result) => {
  console.log('Review result:', result)
}}
```

修改为：

```tsx
onReviewComplete={(result) => {
  // 审核结果回调，可用于后续扩展
  if (!result.passed) {
    // 未通过审核可以给出提示
  }
}}
```

或者直接移除 onReviewComplete 属性

- [ ] **Step 2: 验证 TypeScript 编译**

```bash
cd /opt/project/novelagent/frontend && bun x tsc --noEmit
```

- [ ] **Step 3: 提交变更**

```bash
git add frontend/src/components/workbench/creation/WritingPanel.tsx
git commit -m "fix(workbench): remove console.log in WritingPanel"
```

---

## Task 4: Home 页面全屏布局

**Files:**
- Modify: `frontend/src/pages/Home.tsx`
- Modify: `frontend/src/App.tsx`

- [ ] **Step 1: 修改 App.tsx 路由将 Home 移出 Layout**

当前 App.tsx 结构：

```tsx
<Route path="/" element={<PrivateRoute><Layout /></PrivateRoute>}>
  <Route index element={<Home />} />
  <Route path="project/:id" element={<RedirectToWorkbench />} />
  <Route path="settings" element={<Settings />} />
</Route>
```

改为：

```tsx
// Home 独立路由（不在 Layout 内）
<Route
  path="/"
  element={
    <PrivateRoute>
      <Home />
    </PrivateRoute>
  }
  index
/>

// 其他页面使用 Layout
<Route
  path="/"
  element={
    <PrivateRoute>
      <Layout />
    </PrivateRoute>
  }
>
  <Route path="project/:id" element={<RedirectToWorkbench />} />
  <Route path="settings" element={<Settings />} />
</Route>
```

注意：不能有两个相同 path="/" 的 Route，需要使用可选参数或调整结构。更简单的方案：

```tsx
// 使用通配符处理非 Home 路由
<Route
  path="/"
  element={
    <PrivateRoute>
      <Layout />
    </PrivateRoute>
  }
>
  <Route index element={<Home />} />  // 移除 Home 使用通配符
  <Route path="settings" element={<Settings />} />
  <Route path="project/:id" element={<RedirectToWorkbench />} />
</Route>
```

- [ ] **Step 2: 重写 Home 页面使用全屏布局**

替换 `frontend/src/pages/Home.tsx` 内容使用类似 WorkbenchLayout 的布局：

```tsx
// frontend/src/pages/Home.tsx
import { useState, useEffect } from 'react'
import { Link, Plus } from 'lucide-react'
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
  // ... 保持现有逻辑不变 ...

  // 修改 return JSX 使用全屏布局
  return (
    <div className="flex flex-col h-screen bg-gray-50">
      {/* 顶部栏 */}
      <header className="h-14 border-b bg-white flex items-center justify-between px-6">
        <h1 className="text-xl font-semibold">我的项目</h1>
        <Button onClick={() => setShowNewProject(true)}>
          <Plus className="h-4 w-4 mr-2" />
          新建项目
        </Button>
      </header>

      {/* 主内容区 */}
      <main className="flex-1 overflow-auto p-6">
        {/* 保持现有内容不变 */}
        {error && (
          <div className="mb-6">
            <ErrorMessage message={error} onRetry={fetchProjects} onDismiss={() => setError(null)} />
          </div>
        )}

        {showNewProject && (
          <Card className="mb-6">
            <CardContent className="p-4">
              {/* 新建项目表单 */}
            </CardContent>
          </Card>
        )}

        {loading ? (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
            {Array.from({ length: 6 }).map((_, i) => (
              <ProjectCardSkeleton key={i} />
            ))}
          </div>
        ) : projects.length === 0 ? (
          <div className="text-center py-20 text-muted-foreground">
            <p>还没有项目点击上方按钮创建第一个项目</p>
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
      </main>

      {/* 删除确认弹窗 - 保持不变 */}
    </div>
  )
}
```

- [ ] **Step 3: 验证 TypeScript 编译**

```bash
cd /opt/project/novelagent/frontend && bun x tsc --noEmit
```

- [ ] **Step 4: 提交变更**

```bash
git add frontend/src/pages/Home.tsx frontend/src/App.tsx
git commit -m "feat(frontend): convert Home to fullscreen layout"
```

---

## 测试验证

### 手动测试清单

- [ ] 工作台页面 - 点击返回按钮返回项目列表
- [ ] 工作台页面 - 顶部栏无保存按钮
- [ ] WritingPanel - 审核后无 console.log 输出
- [ ] 项目列表页 - 全屏布局与工作台风格一致
- [ ] Settings 页面 - 保持 Layout 风格不变
- [ ] TypeScript 编译通过