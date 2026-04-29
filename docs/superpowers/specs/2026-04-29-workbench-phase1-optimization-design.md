# 工作台 Phase 1 优化设计

> 日期：2026-04-29

## 目标

优化新工作台页面的基础功能，修复关键问题，提升用户体验一致性。

## 设计

### 任务清单

| 任务 | 文件 | 说明 |
|------|------|------|
| 1. 添加返回按钮 | `WorkbenchLayout.tsx` | 顶部栏添加返回项目列表的导航 |
| 2. 移除无效保存按钮 | `WorkbenchLayout.tsx` | 按钮无功能，改为显示项目状态或移除 |
| 3. 修复 console.log | `WritingPanel.tsx` | 移除无用的调试日志 |
| 4. 项目列表全屏布局 | `Home.tsx` | 使用类似 WorkbenchLayout 的全屏风格 |

### 详细设计

#### Task 1: WorkbenchLayout 添加返回按钮

**位置**: `frontend/src/components/workbench/WorkbenchLayout.tsx`

**改动**:
- 顶部栏左侧添加返回按钮（ArrowLeft 图标）
- 点击跳转到 `/`

```tsx
// 顶部栏左侧
<div className="flex items-center gap-4">
  <Link to="/" className="flex items-center gap-1 text-muted-foreground hover:text-foreground">
    <ArrowLeft className="h-4 w-4" />
    <span className="text-sm">返回</span>
  </Link>
  <h1 className="text-lg font-semibold">{projectName}</h1>
  ...
</div>
```

#### Task 2: 移除无效保存按钮

**位置**: `frontend/src/components/workbench/WorkbenchLayout.tsx`

**改动**:
- 移除顶部栏右侧的「保存」按钮（无实际功能）
- 或者改为显示当前阶段状态文字

**方案**: 直接移除，简化顶部栏

#### Task 3: 修复 WritingPanel console.log

**位置**: `frontend/src/components/workbench/creation/WritingPanel.tsx:335`

**改动**:
- 移除 `console.log('Review result:', result)` 调试代码
- 或者实现实际的审核结果处理逻辑

**方案**: 移除 console.log，保留 onReviewComplete 回调（后续可扩展）

#### Task 4: 项目列表全屏布局

**位置**: `frontend/src/pages/Home.tsx`

**改动**:
- 不再使用 Layout 组件包裹
- 使用全屏布局（类似 WorkbenchLayout）
- 顶部栏：项目标题 + 新建按钮
- 主内容区：项目卡片网格（4列）

**路由变更**:
- Home 页面路由从 Layout 内部移出
- 使用独立的全屏布局

```tsx
// App.tsx 路由变更
<Route
  path="/"
  element={
    <PrivateRoute>
      <Home />
    </PrivateRoute>
  }
/>
// Settings 保持 Layout 包裹
<Route
  path="/"
  element={
    <PrivateRoute>
      <Layout />
    </PrivateRoute>
  }
>
  <Route path="settings" element={<Settings />} />
</Route>
```

### 文件变更

| 文件 | 变更类型 |
|------|----------|
| `frontend/src/components/workbench/WorkbenchLayout.tsx` | 修改 |
| `frontend/src/components/workbench/creation/WritingPanel.tsx` | 修改 |
| `frontend/src/pages/Home.tsx` | 修改 |
| `frontend/src/App.tsx` | 修改（路由） |

### 不变的部分

- Settings 页面保持 Layout 布局
- Login 页面不变
- ProjectWorkbench 页面不变