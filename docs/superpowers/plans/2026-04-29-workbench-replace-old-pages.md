# 新工作台替换旧界面实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将项目主入口指向新工作台页面，删除旧页面路由，全面启用新工作台。

**Architecture:** 修改 App.tsx 路由配置（/project/:id 重定向到 workbench，删除 write/read/characters 路由），修改 ProjectCard 链接指向新工作台，旧组件保留不删。

**Tech Stack:** React 18 + TypeScript + React Router

---

## 文件变更规划

### 修改文件

| 文件 | 职责 | 变更内容 |
|------|------|----------|
| `frontend/src/App.tsx` | 路由配置 | 重定向 /project/:id → workbench，删除旧路由和旧 import |
| `frontend/src/components/common/ProjectCard.tsx` | 项目卡片 | 链接从 /project/:id 改为 /project/:id/workbench |

---

## Task 1: 修改 App.tsx 路由配置

**Files:**
- Modify: `frontend/src/App.tsx`

### 当前状态分析

- `/project/:id` → ProjectDetail（需改为重定向到 workbench）
- `/project/:id/write` → Writing（需删除）
- `/project/:id/read/:chapterNum` → Reading（需删除）
- `/project/:id/characters` → CharacterSetting（需删除）
- `/project/:id/workbench` → ProjectWorkbench（保持不变）

- [ ] **Step 1: 删除旧页面 import**

移除以下 import：
- `import ProjectDetail from '@/pages/ProjectDetail'`
- `import Writing from '@/pages/Writing'`
- `import Reading from '@/pages/Reading'`
- `import CharacterSetting from '@/pages/CharacterSetting'`

保留：
- `import ProjectWorkbench from '@/pages/ProjectWorkbench'`

- [ ] **Step 2: 添加 Navigate import**

在 `react-router-dom` import 中确认已包含 `Navigate`：

```typescript
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
```

当前文件已包含该 import，无需修改。

- [ ] **Step 3: 修改 /project/:id 路由为重定向**

将：
```tsx
<Route path="project/:id" element={<ProjectDetail />} />
```

改为：
```tsx
<Route path="project/:id" element={<Navigate to={`/project/${window.location.pathname.split('/')[2]}/workbench`} replace />} />
```

注意：此处不能直接用 `:id` 参数，需要使用 `useParams` 获取，更适合的方式是使用 `Navigate` 配合当前路径：

实际上，React Router 支持在 Route 中使用 `:id` 参数重定向，但 `Navigate` 的 `to` 属性在 Route element 中无法直接访问 params。更好的做法是使用一个包装组件：

```tsx
// 重定向组件
function RedirectToWorkbench() {
  const { id } = useParams()
  return <Navigate to={`/project/${id}/workbench`} replace />
}

// 路由中使用
<Route path="project/:id" element={<RedirectToWorkbench />} />
```

但为了最小改动，直接在 App.tsx 中添加这个小组件即可。

- [ ] **Step 4: 删除旧路由**

删除以下三行：
```tsx
<Route path="project/:id/write" element={<Writing />} />
<Route path="project/:id/read/:chapterNum" element={<Reading />} />
<Route path="project/:id/characters" element={<CharacterSetting />} />
```

- [ ] **Step 5: 完整修改后的 App.tsx**

```tsx
// frontend/src/App.tsx
import { BrowserRouter, Routes, Route, Navigate, useParams } from 'react-router-dom'
import { useAuthStore } from '@/stores/authStore'
import { Toaster } from '@/components/ui/sonner'
import Layout from '@/components/layout/Layout'
import ErrorBoundary from '@/components/common/ErrorBoundary'
import Login from '@/pages/Login'
import Home from '@/pages/Home'
import Settings from '@/pages/Settings'
import ProjectWorkbench from '@/pages/ProjectWorkbench'

function RedirectToWorkbench() {
  const { id } = useParams()
  return <Navigate to={`/project/${id}/workbench`} replace />
}

function PrivateRoute({ children }: { children: React.ReactNode }) {
  const token = useAuthStore((state) => state.token)
  const hasHydrated = useAuthStore((state) => state._hasHydrated)

  // 从 token 推导认证状态，而不是依赖 isAuthenticated（可能未正确恢复）
  const isAuthenticated = !!token

  // 等待 rehydration 完成
  if (!hasHydrated) {
    return (
      <div className="flex items-center justify-center h-screen">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary"></div>
      </div>
    )
  }

  return isAuthenticated ? <>{children}</> : <Navigate to="/login" replace />
}

function App() {
  return (
    <ErrorBoundary>
      <BrowserRouter>
        <Routes>
          <Route path="/login" element={<Login />} />
          {/* 工作台页面使用独立布局（全屏） */}
          <Route
            path="/project/:id/workbench"
            element={
              <PrivateRoute>
                <ProjectWorkbench />
              </PrivateRoute>
            }
          />
          {/* 其他页面使用 Layout */}
          <Route
            path="/"
            element={
              <PrivateRoute>
                <Layout />
              </PrivateRoute>
            }
          >
            <Route index element={<Home />} />
            <Route path="project/:id" element={<RedirectToWorkbench />} />
            <Route path="settings" element={<Settings />} />
          </Route>
        </Routes>
        <Toaster />
      </BrowserRouter>
    </ErrorBoundary>
  )
}

export default App
```

- [ ] **Step 6: 提交变更**

```bash
git add frontend/src/App.tsx
git commit -m "feat(routing): redirect old project pages to new workbench"
```

---

## Task 2: 修改 ProjectCard 链接

**Files:**
- Modify: `frontend/src/components/common/ProjectCard.tsx:81`

- [ ] **Step 1: 修改链接路径**

将 `to={/project/${project.id}}` 改为 `to={/project/${project.id}/workbench}`：

```tsx
<Button asChild className="flex-1" size="sm">
  <Link to={`/project/${project.id}/workbench`}>
    {project.workflow_state?.stage === 'complete' ? '查看' : '继续'}
  </Link>
</Button>
```

- [ ] **Step 2: 提交变更**

```bash
git add frontend/src/components/common/ProjectCard.tsx
git commit -m "feat(frontend): point project card link to new workbench"
```

---

## 测试验证

### 手动测试清单

- [ ] 项目列表页 — 点击项目卡片跳转到 `/project/:id/workbench`
- [ ] 直接访问 `/project/:id` — 自动重定向到 `/project/:id/workbench`
- [ ] 直接访问 `/project/:id/write` — 404 或空白
- [ ] 直接访问 `/project/:id/read/1` — 404 或空白
- [ ] 直接访问 `/project/:id/characters` — 404 或空白
- [ ] 工作台页面正常渲染各面板（灵感、人物、关系、大纲、章节大纲、写作）
- [ ] TypeScript 编译通过

---

## 注意事项

1. **旧组件不删除** — 渐进清理策略，后续确认无引用后再删
2. **RedirectToWorkbench 放在 Layout 路由内** — 保持与旧 /project/:id 相同的位置
3. **不做顶部栏改动** — 按设计约定，最小改动