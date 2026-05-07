# 工作台全局模型选择器实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将灵感面板的 selectedModelKey 提升到 workbenchStore，使章节大纲面板生成时使用同一模型。

**Architecture:** selectedModelKey 从 InspirationPanel 的 useState 提升到 workbenchStore 的 Zustand state。灵感面板写入 store，章节大纲面板从 store 读取并传 llmConfigId 给 API。

**Tech Stack:** React + Zustand + TypeScript

---

### Task 1: workbenchStore 新增 selectedModelKey 状态

**Files:**
- Modify: `frontend/src/stores/workbenchStore.ts`

- [ ] **Step 1: 在 WorkbenchState 接口中新增状态和 setter**

在 `frontend/src/stores/workbenchStore.ts` 的 `WorkbenchState` 接口中新增：

```typescript
interface WorkbenchState
{
  // ... 现有字段 ...

  // 模型选择状态（灵感面板写入，全局读取）
  selectedModelKey: string
  setSelectedModelKey: (key: string) => void
}
```

- [ ] **Step 2: 在 initialState 和 create 中实现**

```typescript
const initialState = {
  // ... 现有字段 ...
  selectedModelKey: '' as string,
}

export const useWorkbenchStore = create<WorkbenchState>((set) => ({
  ...initialState,

  // ... 现有 setter ...

  setSelectedModelKey: (key) => set({ selectedModelKey: key }),

  reset: () => set(initialState),
}))
```

- [ ] **Step 3: TypeScript 编译验证**

Run: `cd frontend && npx tsc --noEmit`
Expected: 无错误

- [ ] **Step 4: Commit**

```bash
git add frontend/src/stores/workbenchStore.ts
git commit -m "feat(frontend): add selectedModelKey to workbenchStore"
```

---

### Task 2: InspirationPanel 改用 workbenchStore

**Files:**
- Modify: `frontend/src/components/workbench/planning/InspirationPanel.tsx:120-121,124,255,909`

- [ ] **Step 1: 移除本地 selectedModelKey 状态，改用 store**

将第 120-121 行：
```typescript
const [modelOptions, setModelOptions] = useState<ModelOption[]>([])
const [selectedModelKey, setSelectedModelKey] = useState<string>('')
```

改为：
```typescript
const [modelOptions, setModelOptions] = useState<ModelOption[]>([])
const { selectedModelKey, setSelectedModelKey } = useWorkbenchStore()
```

同时移除第 124 行对 `useWorkbenchStore` 旧用法的引用，改为：
```typescript
const { setActiveMenuItem, selectedModelKey, setSelectedModelKey } = useWorkbenchStore()
```

合并后删除原来的 `const { setActiveMenuItem } = useWorkbenchStore()` 行。

- [ ] **Step 2: 修改初始化默认模型的逻辑**

第 255 行的 `setSelectedModelKey` 调用无需改动，因为它现在指向 store 的 setter，语义不变。

但需要确认：只在 `selectedModelKey` 为空时设置默认值，避免覆盖已有选择。将初始化逻辑改为：

```typescript
// 设置默认选中：仅当 store 中没有选择时
if (!selectedModelKey)
{
  const defaultOption = options.find(o => o.isDefault) || options[0]
  if (defaultOption)
  {
    setSelectedModelKey(`${defaultOption.modelConfigId}:${defaultOption.modelName}`)
  }
}
```

- [ ] **Step 3: TypeScript 编译验证**

Run: `cd frontend && npx tsc --noEmit`
Expected: 无错误

- [ ] **Step 4: Commit**

```bash
git add frontend/src/components/workbench/planning/InspirationPanel.tsx
git commit -m "refactor(frontend): lift selectedModelKey from InspirationPanel to workbenchStore"
```

---

### Task 3: ChapterOutlinePanel 读取 store 模型并传给 API

**Files:**
- Modify: `frontend/src/components/workbench/creation/ChapterOutlinePanel.tsx:168-177`

- [ ] **Step 1: 从 store 读取 selectedModelKey 并解析 llmConfigId**

在 `ChapterOutlinePanel` 组件中引入 store：

```typescript
const { selectedModelKey } = useWorkbenchStore()
```

在 `handleGenerateAll` 中解析 llmConfigId：

```typescript
const handleGenerateAll = async () =>
{
  setGenerating(true)
  setProgress(null)
  completedTitlesRef.current = []
  const controller = new AbortController()
  abortControllerRef.current = controller

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
      { /* callbacks 不变 */ },
      { signal: controller.signal },
      llmConfigId  // 传入模型配置 ID
    )
  }
  // ... catch 不变
}
```

- [ ] **Step 2: TypeScript 编译验证**

Run: `cd frontend && npx tsc --noEmit`
Expected: 无错误

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/workbench/creation/ChapterOutlinePanel.tsx
git commit -m "feat(frontend): pass selected model to chapter outlines API"
```

---

### Task 4: 重建前端并验证

- [ ] **Step 1: 重建前端容器**

Run: `docker compose build --no-cache frontend && docker compose up -d frontend`

- [ ] **Step 2: 验证功能**

1. 在灵感面板选择一个模型 → 切换到章节大纲 Tab → 点击"生成章节大纲" → 确认使用灵感面板选择的模型
2. 在灵感面板切换模型 → 回到章节大纲面板 → 再次生成 → 确认使用新选择的模型
3. 后端日志确认 `llm_config_id` 被正确传递

- [ ] **Step 3: Commit（如有修复）**
