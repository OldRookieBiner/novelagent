# 清理老界面代码 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 删除 NovelAgent 前端老界面代码，全面启动新工作台界面，清理技术债。

**Architecture:** 迁移 2 个被新界面引用的通用组件到新目录，删除 20 个不再使用的老页面/组件/测试文件，清理 skeleton 中的废弃函数，更新 import 路径，运行测试验证无破坏。

**Tech Stack:** React + TypeScript + Vite

---

## File Structure

### 迁移文件
- `frontend/src/components/project/CreateProjectDialog.tsx` → `frontend/src/components/common/CreateProjectDialog.tsx`
- `frontend/src/components/project/ReviewModeSelect.tsx` → `frontend/src/components/settings/ReviewModeSelect.tsx`

### 删除文件（20 个）
**老页面（3）：**
- `frontend/src/pages/ProjectDetail.tsx`
- `frontend/src/pages/Writing.tsx`
- `frontend/src/pages/Reading.tsx`

**老项目组件（11）：**
- `frontend/src/components/project/OutlineWorkflow.tsx`
- `frontend/src/components/project/StepNavigation.tsx`
- `frontend/src/components/project/InspirationForm.tsx`
- `frontend/src/components/project/InspirationEditor.tsx`
- `frontend/src/components/project/InspirationDisplay.tsx`
- `frontend/src/components/project/ResumeDialog.tsx`
- `frontend/src/components/project/ResumeDialog.test.tsx`
- `frontend/src/components/project/HistoryContent.tsx`
- `frontend/src/components/project/ChapterList.tsx`
- `frontend/src/components/project/ChapterOutlineDetail.tsx`
- `frontend/src/components/project/WorkflowStatus.tsx`
- `frontend/src/components/project/WorkflowStatus.test.tsx`

**老写作组件（6）：**
- `frontend/src/components/writing/ChapterEditor.tsx`
- `frontend/src/components/writing/ChapterNav.tsx`
- `frontend/src/components/writing/__tests__/ChapterEditor.test.tsx`
- `frontend/src/components/writing/__tests__/ChapterNav.test.tsx`
- `frontend/src/components/writing/hooks/useWriting.ts`
- `frontend/src/components/writing/hooks/__tests__/useWriting.test.ts`

### 修改文件（3 个）
- `frontend/src/pages/Home.tsx` — 更新 CreateProjectDialog import 路径
- `frontend/src/components/settings/ReviewConfigPanel.tsx` — 更新 ReviewModeSelect import 路径
- `frontend/src/components/ui/skeleton.tsx` — 删除 ProjectDetailSkeleton 函数

---

## Task 1: 迁移 CreateProjectDialog

**Files:**
- Create: `frontend/src/components/common/CreateProjectDialog.tsx`
- Delete: `frontend/src/components/project/CreateProjectDialog.tsx`

- [ ] **Step 1: 复制文件到新位置**

```bash
cp frontend/src/components/project/CreateProjectDialog.tsx frontend/src/components/common/CreateProjectDialog.tsx
```

- [ ] **Step 2: 删除旧文件**

```bash
rm frontend/src/components/project/CreateProjectDialog.tsx
```

- [ ] **Step 3: 更新 Home.tsx 的 import**

修改 `frontend/src/pages/Home.tsx` 第 7 行：

```typescript
// 旧
import CreateProjectDialog from '@/components/project/CreateProjectDialog'

// 新
import CreateProjectDialog from '@/components/common/CreateProjectDialog'
```

---

## Task 2: 迁移 ReviewModeSelect

**Files:**
- Create: `frontend/src/components/settings/ReviewModeSelect.tsx`
- Delete: `frontend/src/components/project/ReviewModeSelect.tsx`

- [ ] **Step 1: 复制文件到新位置**

```bash
cp frontend/src/components/project/ReviewModeSelect.tsx frontend/src/components/settings/ReviewModeSelect.tsx
```

- [ ] **Step 2: 删除旧文件**

```bash
rm frontend/src/components/project/ReviewModeSelect.tsx
```

- [ ] **Step 3: 更新 ReviewConfigPanel.tsx 的 import**

修改 `frontend/src/components/settings/ReviewConfigPanel.tsx` 第 4 行：

```typescript
// 旧
import { ReviewModeSelect } from '@/components/project/ReviewModeSelect'

// 新
import { ReviewModeSelect } from '@/components/settings/ReviewModeSelect'
```

---

## Task 3: 清理 skeleton.tsx 中的废弃函数

**Files:**
- Modify: `frontend/src/components/ui/skeleton.tsx`

- [ ] **Step 1: 删除 ProjectDetailSkeleton 函数**

在 `frontend/src/components/ui/skeleton.tsx` 中删除以下代码：

```tsx
export function ProjectDetailSkeleton() {
  return (
    <div className="space-y-6">
      {/* Header skeleton */}
      <div className="space-y-2">
        <Skeleton className="h-8 w-[250px]" />
        <Skeleton className="h-4 w-[200px]" />
      </div>

      {/* Content skeleton */}
      <div className="space-y-4">
        <Skeleton className="h-4 w-full" />
        <Skeleton className="h-4 w-full" />
        <Skeleton className="h-4 w-[80%]" />
      </div>

      {/* Card skeleton */}
      <div className="space-y-3">
        <Skeleton className="h-[125px] w-full rounded-xl" />
        <Skeleton className="h-[125px] w-full rounded-xl" />
      </div>
    </div>
  )
}
```

---

## Task 4: 批量删除老页面文件

**Files:**
- Delete: `frontend/src/pages/ProjectDetail.tsx`
- Delete: `frontend/src/pages/Writing.tsx`
- Delete: `frontend/src/pages/Reading.tsx`

- [ ] **Step 1: 删除 3 个老页面文件**

```bash
rm frontend/src/pages/ProjectDetail.tsx
rm frontend/src/pages/Writing.tsx
rm frontend/src/pages/Reading.tsx
```

---

## Task 5: 批量删除老项目组件

**Files:**
- Delete: `frontend/src/components/project/OutlineWorkflow.tsx`
- Delete: `frontend/src/components/project/StepNavigation.tsx`
- Delete: `frontend/src/components/project/InspirationForm.tsx`
- Delete: `frontend/src/components/project/InspirationEditor.tsx`
- Delete: `frontend/src/components/project/InspirationDisplay.tsx`
- Delete: `frontend/src/components/project/ResumeDialog.tsx`
- Delete: `frontend/src/components/project/ResumeDialog.test.tsx`
- Delete: `frontend/src/components/project/HistoryContent.tsx`
- Delete: `frontend/src/components/project/ChapterList.tsx`
- Delete: `frontend/src/components/project/ChapterOutlineDetail.tsx`
- Delete: `frontend/src/components/project/WorkflowStatus.tsx`
- Delete: `frontend/src/components/project/WorkflowStatus.test.tsx`

- [ ] **Step 1: 删除所有老项目组件**

```bash
rm frontend/src/components/project/OutlineWorkflow.tsx
rm frontend/src/components/project/StepNavigation.tsx
rm frontend/src/components/project/InspirationForm.tsx
rm frontend/src/components/project/InspirationEditor.tsx
rm frontend/src/components/project/InspirationDisplay.tsx
rm frontend/src/components/project/ResumeDialog.tsx
rm frontend/src/components/project/ResumeDialog.test.tsx
rm frontend/src/components/project/HistoryContent.tsx
rm frontend/src/components/project/ChapterList.tsx
rm frontend/src/components/project/ChapterOutlineDetail.tsx
rm frontend/src/components/project/WorkflowStatus.tsx
rm frontend/src/components/project/WorkflowStatus.test.tsx
```

---

## Task 6: 批量删除老写作组件

**Files:**
- Delete: `frontend/src/components/writing/ChapterEditor.tsx`
- Delete: `frontend/src/components/writing/ChapterNav.tsx`
- Delete: `frontend/src/components/writing/__tests__/ChapterEditor.test.tsx`
- Delete: `frontend/src/components/writing/__tests__/ChapterNav.test.tsx`
- Delete: `frontend/src/components/writing/hooks/useWriting.ts`
- Delete: `frontend/src/components/writing/hooks/__tests__/useWriting.test.ts`

- [ ] **Step 1: 删除所有老写作组件**

```bash
rm frontend/src/components/writing/ChapterEditor.tsx
rm frontend/src/components/writing/ChapterNav.tsx
rm frontend/src/components/writing/__tests__/ChapterEditor.test.tsx
rm frontend/src/components/writing/__tests__/ChapterNav.test.tsx
rm frontend/src/components/writing/hooks/useWriting.ts
rm frontend/src/components/writing/hooks/__tests__/useWriting.test.ts
```

---

## Task 7: 验证无残留无效引用

**Files:**
- 检查整个 `frontend/src/` 目录

- [ ] **Step 1: 运行 grep 检查是否还有对老组件的 import**

```bash
cd /opt/project/novelagent/frontend/src
rg "from '@/components/project/" --type tsx
rg "from '@/components/writing/" --type tsx
rg "ProjectDetailSkeleton" --type tsx
```

**预期结果：** 没有任何匹配（0 个结果）

- [ ] **Step 2: 确认空目录并删除**

```bash
# components/writing/ 目录应该已空
rmdir frontend/src/components/writing/hooks/__tests__ 2>/dev/null
rmdir frontend/src/components/writing/hooks 2>/dev/null
rmdir frontend/src/components/writing/__tests__ 2>/dev/null
rmdir frontend/src/components/writing 2>/dev/null

# components/project/ 目录应该只剩 CreateProjectDialog.tsx 和 ReviewModeSelect.tsx（已被迁移走）
# 理论上是空的，但需要确认没有其他文件
ls frontend/src/components/project/
```

**预期结果：** `ls` 返回空或目录不存在

---

## Task 8: 运行前端测试验证

- [ ] **Step 1: 运行前端测试**

```bash
cd /opt/project/novelagent/frontend && npm run test:run
```

**预期结果：** 所有测试通过（注意：之前已有的 test 文件可能有失败，我们需要确认没有新增的失败）

- [ ] **Step 2: 运行 TypeScript 类型检查**

```bash
cd /opt/project/novelagent/frontend && npx tsc --noEmit
```

**预期结果：** 无类型错误（0 errors）

---

## Task 9: 运行后端测试验证

- [ ] **Step 1: 运行后端测试**

```bash
docker exec novelagent-backend-1 pytest -v
```

**预期结果：** 所有测试通过

---

## Task 10: 提交代码

- [ ] **Step 1: 查看变更**

```bash
cd /opt/project/novelagent
git status
git diff --stat
```

**预期结果：** 显示删除约 20 个文件、修改 3 个文件、迁移（新增+删除）2 个文件

- [ ] **Step 2: 提交**

```bash
git add -A
git commit -m "refactor(frontend): remove old interface code, migrate to workbench"
```

---

## Self-Review Checklist

- [ ] Spec coverage：所有 20 个待删除文件是否都在 plan 中？
- [ ] Placeholder scan：无 "TBD"/"TODO" 占位符
- [ ] Type consistency：修改的 import 路径是否正确？
- [ ] 验证步骤：测试和类型检查是否覆盖？
