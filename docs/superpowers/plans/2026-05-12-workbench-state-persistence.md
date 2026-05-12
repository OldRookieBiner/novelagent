# 工作台状态持久化优化 实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 修复灵感页面规划完成后按钮状态不更新、章节大纲生成时切换标签页丢失进度两个问题。

**Architecture:** 问题1通过添加 onComplete 回调刷新 outline 数据解决；问题2通过将 SSE 流管理和状态提升到 workflowStore，使 SSE 生命周期与组件解耦。

**Tech Stack:** React 18 + Zustand + TypeScript

---

## Task 1: 灵感页面 — 添加 onPlanningComplete 回调

**Files:**
- Modify: `frontend/src/pages/ProjectWorkbench.tsx:19,42`
- Modify: `frontend/src/components/workbench/planning/InspirationPanel.tsx:38-42,1139`

- [ ] **Step 1: 修改 InspirationPanelProps 接口，新增 onPlanningComplete prop**

在 `InspirationPanel.tsx` 的 `InspirationPanelProps` 接口中新增：

```typescript
interface InspirationPanelProps
{
  projectId: number
  hasOutline?: boolean
  onPlanningComplete?: () => void  // 规划完成后的回调
}
```

在组件函数签名中解构新 prop：

```typescript
export function InspirationPanel({ projectId, hasOutline, onPlanningComplete }: InspirationPanelProps)
```

- [ ] **Step 2: 修改 onComplete 回调，调用 onPlanningComplete**

在 `InspirationPanel.tsx` 第 1139 行，将空函数替换为调用 `onPlanningComplete`：

```tsx
<OutlineProgressDialog
  open={showProgressDialog}
  onClose={() => setShowProgressDialog(false)}
  projectId={projectId}
  modelConfigId={selectedModelKey ? parseInt(selectedModelKey.split(':')[0]) : undefined}
  modelName={selectedModelKey ? selectedModelKey.split(':').slice(1).join(':') : undefined}
  isReplan={hasOutline}
  collectedInfo={replanCollectedInfo}
  inspirationTemplate={template}
  onComplete={() => { onPlanningComplete?.() }}
  onViewOutline={() =>
  {
    onPlanningComplete?.()
    setShowProgressDialog(false)
    setActiveMenuItem('outline')
  }}
/>
```

注意：`onViewOutline` 也需要调用 `onPlanningComplete`，因为用户点"查看大纲"时规划同样已完成。

- [ ] **Step 3: 在 ProjectWorkbench 中传入 refreshOutline**

在 `ProjectWorkbench.tsx` 中，从 `useProjectData` 解构 `refreshOutline`，并传给 `InspirationPanel`：

```tsx
const { project, outline, loading, refreshOutline } = useProjectData(projectId)

// ...

<InspirationPanel
  projectId={projectId!}
  hasOutline={!!outline?.title}
  onPlanningComplete={() => refreshOutline()}
/>
```

- [ ] **Step 4: 验证**

启动前端开发服务器，在灵感页面完成规划后，确认按钮立即从"开始规划"变为"重新规划"，无需刷新页面。

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/workbench/planning/InspirationPanel.tsx frontend/src/pages/ProjectWorkbench.tsx
git commit -m "fix(inspiration): update button state after planning completes"
```

---

## Task 2: workflowStore — 新增章节大纲生成状态和 actions

**Files:**
- Modify: `frontend/src/stores/workflowStore.ts`

- [ ] **Step 1: 在 WorkflowState 接口中新增章节大纲生成相关状态和 actions**

在 `chapterOutlinesConfirmed` 字段后面，新增状态字段：

```typescript
// ========== 章节大纲生成状态 ==========
chapterOutlineGenerating: boolean
chapterOutlineReplaning: boolean
chapterOutlineProgress: {
  current: number
  total: number
  currentTitle?: string
  completed?: string[]
} | null
chapterOutlineAbortController: AbortController | null
```

在 `setChapterOutlinesConfirmed` action 后面，新增 actions：

```typescript
// 章节大纲生成
setChapterOutlineGenerating: (generating: boolean) => void
setChapterOutlineReplaning: (replaning: boolean) => void
setChapterOutlineProgress: (progress: {
  current: number
  total: number
  currentTitle?: string
  completed?: string[]
} | null) => void
setChapterOutlineAbortController: (controller: AbortController | null) => void
cancelChapterOutlineGeneration: () => void
clearChapterOutlineGenerationState: () => void
```

- [ ] **Step 2: 在 initialState 中新增默认值**

在 `chapterOutlinesConfirmed: false` 后面新增：

```typescript
chapterOutlineGenerating: false,
chapterOutlineReplaning: false,
chapterOutlineProgress: null,
chapterOutlineAbortController: null,
```

- [ ] **Step 3: 实现 actions**

在 `setChapterOutlinesConfirmed` action 后面新增：

```typescript
setChapterOutlineGenerating: (generating) => set({ chapterOutlineGenerating: generating }),

setChapterOutlineReplaning: (replaning) => set({ chapterOutlineReplaning: replaning }),

setChapterOutlineProgress: (progress) => set({ chapterOutlineProgress: progress }),

setChapterOutlineAbortController: (controller) => set({ chapterOutlineAbortController: controller }),

// 取消章节大纲生成（用户主动取消时调用）
cancelChapterOutlineGeneration: () =>
{
  const state = useWorkflowStore.getState()
  if (state.chapterOutlineAbortController)
  {
    state.chapterOutlineAbortController.abort()
  }
  set({
    chapterOutlineGenerating: false,
    chapterOutlineReplaning: false,
    chapterOutlineProgress: null,
    chapterOutlineAbortController: null,
  })
},

// 清理章节大纲生成状态（生成完成后调用）
clearChapterOutlineGenerationState: () => set({
  chapterOutlineGenerating: false,
  chapterOutlineReplaning: false,
  chapterOutlineProgress: null,
  chapterOutlineAbortController: null,
}),
```

- [ ] **Step 4: 在 reset action 中包含新增状态**

确认 `reset: () => set(initialState)` 已自动包含所有新增的 initialState 字段，无需额外修改。

- [ ] **Step 5: Commit**

```bash
git add frontend/src/stores/workflowStore.ts
git commit -m "feat(workflow-store): add chapter outline generation state and actions"
```

---

## Task 3: ChapterOutlinePanel — 将生成状态替换为 store 状态，SSE 流管理提升到 store

**Files:**
- Modify: `frontend/src/components/workbench/creation/ChapterOutlinePanel.tsx`

- [ ] **Step 1: 添加 useWorkflowStore 导入，移除生成相关的本地状态**

将第 13 行 `import { useWorkbenchStore } from '@/stores/workbenchStore'` 改为同时导入两个 store：

```typescript
import { useWorkbenchStore } from '@/stores/workbenchStore'
import { useWorkflowStore } from '@/stores/workflowStore'
```

删除以下本地状态（第 38-44 行）：

```typescript
// 删除这些：
const [generating, setGenerating] = useState(false)
const [replaning, setReplaning] = useState(false)
const [progress, setProgress] = useState<...>(null)
const abortControllerRef = useRef<AbortController | null>(null)
const completedTitlesRef = useRef<string[]>([])
```

替换为从 store 读取：

```typescript
const {
  chapterOutlineGenerating: generating,
  chapterOutlineReplaning: replaning,
  chapterOutlineProgress: progress,
  setChapterOutlines,
  addChapterOutline,
  setChapterOutlineGenerating,
  setChapterOutlineReplaning,
  setChapterOutlineProgress,
  setChapterOutlineAbortController,
  cancelChapterOutlineGeneration,
  clearChapterOutlineGenerationState,
} = useWorkflowStore()
```

- [ ] **Step 2: 移除 useEffect cleanup中的 abort 调用**

删除第 83-93 行的 useEffect：

```typescript
// 删除整个 useEffect：
useEffect(() =>
{
  return () =>
  {
    if (abortControllerRef.current)
    {
      abortControllerRef.current.abort()
      abortControllerRef.current = null
    }
  }
}, [])
```

这是核心修改：组件卸载时不再 abort SSE 流，流在 store 层管理。

- [ ] **Step 3: 改造 handleGenerateAll 函数**

将 `handleGenerateAll`（第 174-268 行）改为使用 store actions：

```typescript
const handleGenerateAll = async () =>
{
  setChapterOutlineGenerating(true)
  setChapterOutlineProgress(null)
  const controller = new AbortController()
  setChapterOutlineAbortController(controller)
  const completedTitles: string[] = []

  // 从 store 解析模型配置 ID
  let llmConfigId: number | undefined
  if (selectedModelKey)
  {
    const configIdStr = selectedModelKey.split(':')[0]
    const parsed = parseInt(configIdStr)
    if (!isNaN(parsed)) llmConfigId = parsed
  }

  try
  {
    await chapterOutlinesApi.createStream(
      projectId,
      {
        onProgress: (chapterNumber, total, chapter) =>
        {
          const tempId = -(chapter.chapter_number)
          const newChapter: ChapterOutline = {
            id: tempId,
            project_id: projectId,
            chapter_number: chapter.chapter_number,
            title: chapter.title || '',
            scene: chapter.scene || '',
            characters: chapter.characters || '',
            plot: chapter.plot || '',
            conflict: chapter.conflict || '',
            ending: chapter.ending || '',
            target_words: chapter.target_words || 3000,
            confirmed: false,
            has_content: false,
            created_at: new Date().toISOString(),
          }
          // 使用 setChapters（组件本地）更新列表
          setChapters(prev =>
          {
            if (prev.some(c => c.chapter_number === chapter.chapter_number)) return prev
            return [...prev, newChapter].sort((a, b) => a.chapter_number - b.chapter_number)
          })

          // 更新 store 中的进度
          completedTitles.push(chapter.title || `第${chapter.chapter_number}章`)
          setChapterOutlineProgress({
            current: chapterNumber,
            total,
            currentTitle: chapter.title || `第${chapter.chapter_number}章`,
            completed: [...completedTitles]
          })
        },
        onDone: async (total) =>
        {
          clearChapterOutlineGenerationState()
          try
          {
            const data = await chapterOutlinesApi.list(projectId)
            setChapters(data)
            toast.success(`已生成 ${total} 个章节大纲`)
          }
          catch (err)
          {
            console.error('Failed to refresh chapter outlines:', err)
            toast.success(`已生成 ${total} 个章节大纲，请刷新页面查看`)
          }
        },
        onError: (error) =>
        {
          clearChapterOutlineGenerationState()
          toast.error(`生成失败: ${error}`)
        }
      },
      { signal: controller.signal },
      llmConfigId
    )
  }
  catch (err)
  {
    clearChapterOutlineGenerationState()
    toast.error('生成失败')
  }
}
```

- [ ] **Step 4: 改造 handleCancelGenerate 函数**

将 `handleCancelGenerate`（第 270-281 行）改为使用 store action：

```typescript
const handleCancelGenerate = () =>
{
  cancelChapterOutlineGeneration()
  toast.info('已取消生成')
}
```

- [ ] **Step 5: 改造 handleReplanChapterOutlines 函数**

将 `handleReplanChapterOutlines`（第 283-365 行）改为使用 store actions：

```typescript
const handleReplanChapterOutlines = async () =>
{
  setShowReplanDialog(false)
  setChapterOutlineReplaning(true)
  setChapters([])  // 清除旧章节
  setChapterOutlineProgress(null)
  const completedTitles: string[] = []

  const controller = new AbortController()
  setChapterOutlineAbortController(controller)

  // 解析模型配置 ID
  let llmConfigId: number | undefined
  if (selectedModelKey)
  {
    const p = parseInt(selectedModelKey.split(':')[0])
    if (!isNaN(p)) llmConfigId = p
  }

  try
  {
    await workflowApi.replanChapterOutlines(
      projectId,
      {
        onProgress: (data) =>
        {
          const chapter = data.chapter
          const newChapter: ChapterOutline = {
            id: Date.now() + chapter.chapter_number,
            project_id: projectId,
            chapter_number: chapter.chapter_number,
            title: chapter.title || '',
            scene: chapter.scene || '',
            characters: chapter.characters || '',
            plot: chapter.plot || '',
            conflict: chapter.conflict || '',
            ending: chapter.ending || '',
            target_words: chapter.target_words || 3000,
            confirmed: false,
            has_content: false,
            created_at: new Date().toISOString(),
          }
          setChapters(prev =>
          {
            if (prev.some(c => c.chapter_number === chapter.chapter_number)) return prev
            return [...prev, newChapter].sort((a, b) => a.chapter_number - b.chapter_number)
          })

          completedTitles.push(chapter.title || `第${chapter.chapter_number}章`)
          setChapterOutlineProgress({
            current: data.chapter_number,
            total: data.total,
            currentTitle: chapter.title || `第${chapter.chapter_number}章`,
            completed: [...completedTitles]
          })
        },
        onDone: async (data) =>
        {
          clearChapterOutlineGenerationState()
          try
          {
            const refreshedData = await chapterOutlinesApi.list(projectId)
            setChapters(refreshedData)
            toast.success(`已重新生成 ${data.total} 个章节大纲`)
          }
          catch (err)
          {
            toast.success(`已重新生成 ${data.total} 个章节大纲，请刷新页面查看`)
          }
        },
        onError: (error) =>
        {
          clearChapterOutlineGenerationState()
          toast.error(`重新生成失败: ${error}`)
        }
      },
      { signal: controller.signal, llmConfigId }
    )
  }
  catch (err)
  {
    clearChapterOutlineGenerationState()
    toast.error('重新生成失败')
  }
}
```

- [ ] **Step 6: 添加组件挂载恢复逻辑**

在初始数据获取的 useEffect 中，增加对 store 中残留生成状态的处理：

```typescript
useEffect(() =>
{
  const fetchChapters = async () =>
  {
    try
    {
      const data = await chapterOutlinesApi.list(projectId)
      setChapters(data)
      if (data.length > 0)
      {
        setSelectedChapter(data[0])
      }
    }
    catch (err)
    {
      console.error('Failed to fetch chapters:', err)
    }
    finally
    {
      setLoading(false)
    }
  }
  fetchChapters()

  // 如果 store 中没有正在生成的状态，清理可能残留的进度
  const { chapterOutlineGenerating, chapterOutlineReplaning } = useWorkflowStore.getState()
  if (!chapterOutlineGenerating && !chapterOutlineReplaning)
  {
    clearChapterOutlineGenerationState()
  }
}, [projectId])
```

- [ ] **Step 7: 验证**

启动前端，测试以下场景：
1. 章节大纲生成中切换到其他标签页再切回来，进度和章节列表保留
2. 取消生成功能正常
3. 重新生成功能正常
4. 灵感页面规划完成后按钮状态更新

- [ ] **Step 8: Commit**

```bash
git add frontend/src/components/workbench/creation/ChapterOutlinePanel.tsx
git commit -m "feat(chapter-outline): lift generation state and SSE management to workflowStore"
```

---

## Task 4: 最终验证和清理

- [ ] **Step 1: 完整功能验证**

测试所有场景：
1. 灵感页面：完成规划 → 按钮变为"重新规划"（无需刷新）
2. 灵感页面：点"查看大纲" → 按钮也变为"重新规划"
3. 灵感页面：点"重新规划" → 正常工作
4. 章节大纲：生成中切换标签页 → 切回来 → 进度保留
5. 章节大纲：生成中取消 → 状态正确清理
6. 章节大纲：重新生成中切换标签页 → 切回来 → 进度保留
7. 章节大纲：编辑、保存、确认功能不受影响

- [ ] **Step 2: 更新 wolf 文件**

更新 `.wolf/anatomy.md` 和 `.wolf/memory.md` 记录本次修改。

- [ ] **Step 3: Commit**

```bash
git add -A
git commit -m "chore: update wolf docs for workbench state persistence"
```
