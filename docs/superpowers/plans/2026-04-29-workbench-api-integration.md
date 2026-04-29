# 工作台页面 API 对接实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 为工作台页面对接后端 API，实现大纲、章节大纲、写作页面的完整 CRUD 和 AI 生成功能

**Architecture:** 直接修改现有组件，调用 `api.ts` 中已定义的 API 客户端（outlineApi、chapterOutlinesApi、chaptersApi），实现数据保存、AI 生成、审核等功能

**Tech Stack:** React 18 + TypeScript + Zustand + SSE 流式处理

---

## 文件变更规划

### 修改文件（不新增文件）

| 文件 | 职责 | 变更内容 |
|------|------|----------|
| `frontend/src/components/workbench/creation/OutlinePanel.tsx` | 大纲编辑 | 添加保存、AI 生成、确认功能 |
| `frontend/src/components/workbench/creation/ChapterOutlinePanel.tsx` | 章节大纲编辑 | 添加保存、确认、批量生成功能 |
| `frontend/src/components/workbench/creation/WritingPanel.tsx` | 写作页面 | 添加章节内容获取、保存、生成功能 |
| `frontend/src/components/workbench/creation/AIAssistantPanel.tsx` | AI 助手 | 添加审核功能对接 |

### API 客户端（已存在于 `api.ts`）

- `outlineApi` - 大纲 API（get, update, createStream, confirm）
- `chapterOutlinesApi` - 章节大纲 API（list, update, confirm, createStream）
- `chaptersApi` - 章节内容 API（get, create, update, review）

---

## Task 1: OutlinePanel 大纲页面 API 对接

**Files:**
- Modify: `frontend/src/components/workbench/creation/OutlinePanel.tsx`

### 当前状态分析

组件已经：
- 导入了 `outlineApi`
- 调用 `outlineApi.get()` 获取大纲数据
- 渲染了标题、简介、情节节点、章节数量

缺失功能：
- 保存按钮无事件绑定
- AI 生成按钮无事件绑定
- 确认大纲功能缺失
- 输入框未绑定 onChange 事件

### 实现步骤

- [ ] **Step 1: 添加状态管理**

在组件中添加本地编辑状态和保存状态：

```typescript
// 在 OutlinePanel 组件内添加
const [title, setTitle] = useState('')
const [summary, setSummary] = useState('')
const [saving, setSaving] = useState(false)
const [generating, setGenerating] = useState(false)
const [generatedContent, setGeneratedContent] = useState('')
```

- [ ] **Step 2: 初始化编辑状态**

在 `fetchOutline` 成功后初始化本地状态：

```typescript
// 在 fetchOutline 的 try 块内添加
setTitle(data.title || '')
setSummary(data.summary || '')
```

- [ ] **Step 3: 实现保存功能**

```typescript
const handleSave = async () =>
{
  if (!outline) return
  setSaving(true)
  try
  {
    const updated = await outlineApi.update(projectId, {
      title,
      summary,
      plot_points: plotPoints.map((event, index) => ({
        order: index + 1,
        event
      }))
    })
    setOutline(updated)
    toast.success('保存成功')
  }
  catch (err)
  {
    console.error('Failed to save outline:', err)
    toast.error('保存失败')
  }
  finally
  {
    setSaving(false)
  }
}
```

- [ ] **Step 4: 实现 AI 生成功能（SSE 流式）**

```typescript
const handleGenerate = async () =>
{
  setGenerating(true)
  setGeneratedContent('')
  try
  {
    await outlineApi.createStream(
      projectId,
      {
        onChunk: (chunk) =>
        {
          setGeneratedContent(prev => prev + chunk)
        },
        onDone: (result) =>
        {
          if (result.outline.title) setTitle(result.outline.title)
          if (result.outline.summary) setSummary(result.outline.summary)
          if (result.outline.plot_points)
          {
            setPlotPoints(result.outline.plot_points.map(p =>
              typeof p === 'string' ? p : p.event
            ))
          }
          setGenerating(false)
          toast.success('AI 生成完成')
        },
        onError: (error) =>
        {
          setGenerating(false)
          toast.error(`生成失败: ${error}`)
        }
      }
    )
  }
  catch (err)
  {
    setGenerating(false)
    toast.error('生成失败')
  }
}
```

- [ ] **Step 5: 实现确认大纲功能**

```typescript
const handleConfirm = async () =>
{
  if (!outline) return
  if (!title || !summary)
  {
    toast.error('请先填写标题和简介')
    return
  }
  try
  {
    await outlineApi.confirm(projectId)
    toast.success('大纲已确认')
    // 更新本地状态
    if (outline)
    {
      setOutline({ ...outline, confirmed: true })
    }
  }
  catch (err)
  {
    console.error('Failed to confirm outline:', err)
    toast.error('确认失败')
  }
}
```

- [ ] **Step 6: 绑定事件到 UI**

- 为标题、简介输入框添加 `value` 和 `onChange`
- 保存按钮添加 `onClick={handleSave}` 和 `disabled={saving}`
- AI 生成按钮添加 `onClick={handleGenerate}` 和 `disabled={generating}`
- 添加确认大纲按钮（在确认前显示）

- [ ] **Step 7: 提交变更**

```bash
git add frontend/src/components/workbench/creation/OutlinePanel.tsx
git commit -m "feat(workbench): add outline API integration with save, generate and confirm"
```

---

## Task 2: ChapterOutlinePanel 章节大纲页面 API 对接

**Files:**
- Modify: `frontend/src/components/workbench/creation/ChapterOutlinePanel.tsx`

### 当前状态分析

组件已经：
- 导入了 `chapterOutlinesApi`
- 调用 `chapterOutlinesApi.list()` 获取章节列表
- 渲染了章节列表、章节标题、场景、情节、目标字数

缺失功能：
- 保存按钮无事件绑定
- AI 生成按钮无事件绑定
- 确认章节功能缺失
- 批量生成功能缺失
- 输入框未绑定 onChange 事件

### 实现步骤

- [ ] **Step 1: 添加状态管理**

```typescript
// 在 ChapterOutlinePanel 组件内添加
const [editingTitle, setEditingTitle] = useState('')
const [editingScene, setEditingScene] = useState('')
const [editingPlot, setEditingPlot] = useState('')
const [editingTargetWords, setEditingTargetWords] = useState(3000)
const [saving, setSaving] = useState(false)
const [generating, setGenerating] = useState(false)
const [progress, setProgress] = useState<{ current: number; total: number } | null>(null)
```

- [ ] **Step 2: 选中章节时初始化编辑状态**

```typescript
// 添加 useEffect 监听选中章节变化
useEffect(() =>
{
  if (selectedChapter)
  {
    setEditingTitle(selectedChapter.title || '')
    setEditingScene(selectedChapter.scene || '')
    setEditingPlot(selectedChapter.plot || '')
    setEditingTargetWords(selectedChapter.target_words || 3000)
  }
}, [selectedChapter])
```

- [ ] **Step 3: 实现保存功能**

```typescript
const handleSave = async () =>
{
  if (!selectedChapter) return
  setSaving(true)
  try
  {
    const updated = await chapterOutlinesApi.update(
      projectId,
      selectedChapter.chapter_number,
      {
        title: editingTitle,
        scene: editingScene,
        plot: editingPlot,
        target_words: editingTargetWords
      }
    )
    // 更新列表中的章节
    setChapters(chapters.map(c =>
      c.id === updated.id ? updated : c
    ))
    toast.success('保存成功')
  }
  catch (err)
  {
    console.error('Failed to save chapter outline:', err)
    toast.error('保存失败')
  }
  finally
  {
    setSaving(false)
  }
}
```

- [ ] **Step 4: 实现确认章节功能**

```typescript
const handleConfirm = async () =>
{
  if (!selectedChapter) return
  try
  {
    await chapterOutlinesApi.confirm(projectId, selectedChapter.chapter_number)
    // 更新章节状态
    setChapters(chapters.map(c =>
      c.id === selectedChapter.id ? { ...c, confirmed: true } : c
    ))
    toast.success('章节已确认')
  }
  catch (err)
  {
    console.error('Failed to confirm chapter:', err)
    toast.error('确认失败')
  }
}
```

- [ ] **Step 5: 实现批量生成功能（SSE 流式）**

```typescript
const handleGenerateAll = async () =>
{
  setGenerating(true)
  setProgress(null)
  try
  {
    await chapterOutlinesApi.createStream(
      projectId,
      {
        onProgress: (chapterNumber, total, chapter) =>
        {
          setProgress({ current: chapterNumber, total })
          // 添加新章节到列表
          setChapters(prev =>
          {
            const exists = prev.find(c => c.id === chapter.id)
            if (exists) return prev
            return [...prev, {
              id: chapter.id,
              project_id: projectId,
              chapter_number: chapter.chapter_number,
              title: chapter.title,
              scene: '',
              plot: '',
              target_words: 3000,
              confirmed: false,
              created_at: new Date().toISOString(),
              has_content: false
            } as ChapterOutline]
          })
        },
        onDone: (total) =>
        {
          setGenerating(false)
          setProgress(null)
          toast.success(`已生成 ${total} 个章节大纲`)
        },
        onError: (error) =>
        {
          setGenerating(false)
          setProgress(null)
          toast.error(`生成失败: ${error}`)
        }
      }
    )
  }
  catch (err)
  {
    setGenerating(false)
    toast.error('生成失败')
  }
}
```

- [ ] **Step 6: 绑定事件到 UI**

- 为输入框添加 `value` 和 `onChange`
- 保存按钮添加 `onClick={handleSave}`
- AI 生成按钮添加 `onClick={handleGenerateAll}`
- 添加确认按钮
- 添加生成进度显示

- [ ] **Step 7: 提交变更**

```bash
git add frontend/src/components/workbench/creation/ChapterOutlinePanel.tsx
git commit -m "feat(workbench): add chapter outline API integration with save, confirm and generate"
```

---

## Task 3: WritingPanel 写作页面 API 对接

**Files:**
- Modify: `frontend/src/components/workbench/creation/WritingPanel.tsx`

### 当前状态分析

组件已经：
- 导入了 `chapterOutlinesApi`
- 调用 `chapterOutlinesApi.list()` 获取章节列表
- 渲染了章节列表和写作区域

缺失功能：
- 未导入 `chaptersApi`
- 未获取章节内容
- 保存按钮无事件绑定
- AI 生成功能缺失
- 切换章节时未加载内容

### 实现步骤

- [ ] **Step 1: 导入 chaptersApi**

```typescript
import { chapterOutlinesApi, chaptersApi } from '@/lib/api'
import type { ChapterOutline, Chapter } from '@/types'
```

- [ ] **Step 2: 添加状态管理**

```typescript
const [chapterContent, setChapterContent] = useState<Chapter | null>(null)
const [content, setContent] = useState('')
const [saving, setSaving] = useState(false)
const [generating, setGenerating] = useState(false)
const [generatedContent, setGeneratedContent] = useState('')
const [loadingContent, setLoadingContent] = useState(false)
```

- [ ] **Step 3: 加载章节内容**

```typescript
// 添加 useEffect 监听选中章节变化
useEffect(() =>
{
  if (!selectedChapter) return
  const loadContent = async () =>
  {
    setLoadingContent(true)
    try
    {
      const chapter = await chaptersApi.get(projectId, selectedChapter.chapter_number)
      setChapterContent(chapter)
      setContent(chapter.content || '')
    }
    catch (err)
    {
      // 章节内容不存在，清空内容
      setChapterContent(null)
      setContent('')
    }
    finally
    {
      setLoadingContent(false)
    }
  }
  loadContent()
}, [projectId, selectedChapter])
```

- [ ] **Step 4: 实现保存功能**

```typescript
const handleSave = async () =>
{
  if (!selectedChapter) return
  setSaving(true)
  try
  {
    // 如果章节不存在，先创建
    if (!chapterContent)
    {
      const created = await chaptersApi.create(projectId, selectedChapter.chapter_number)
      setChapterContent(created)
    }
    const updated = await chaptersApi.update(
      projectId,
      selectedChapter.chapter_number,
      { content }
    )
    setChapterContent(updated)
    toast.success('保存成功')
  }
  catch (err)
  {
    console.error('Failed to save chapter:', err)
    toast.error('保存失败')
  }
  finally
  {
    setSaving(false)
  }
}
```

- [ ] **Step 5: 实现 AI 生成功能**

需要先检查后端是否有章节内容生成的 SSE 端点。根据 `chapters.py`，端点是 `POST /{project_id}/chapters/{chapter_num}/generate`。

```typescript
const handleGenerate = async () =>
{
  if (!selectedChapter) return
  setGenerating(true)
  setGeneratedContent('')
  try
  {
    // 使用 fetch 直接处理 SSE
    const response = await fetch(`/api/projects/${projectId}/chapters/${selectedChapter.chapter_number}/generate`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Basic ${btoa(`${getSessionToken()}:`)}`
      }
    })
    
    const reader = response.body?.getReader()
    if (!reader) throw new Error('No reader')
    
    let accumulated = ''
    const decoder = new TextDecoder()
    
    while (true)
    {
      const { done, value } = await reader.read()
      if (done) break
      
      const chunk = decoder.decode(value)
      accumulated += chunk
      setContent(accumulated)
    }
    
    toast.success('AI 生成完成')
  }
  catch (err)
  {
    console.error('Failed to generate:', err)
    toast.error('生成失败')
  }
  finally
  {
    setGenerating(false)
  }
}
```

- [ ] **Step 6: 绑定事件到 UI**

- 保存按钮添加 `onClick={handleSave}`
- 添加 AI 生成按钮
- 切换章节时自动保存提示

- [ ] **Step 7: 传递审核所需参数给 AIAssistantPanel**

```typescript
<AIAssistantPanel
  projectId={projectId}
  chapterNumber={selectedChapter?.chapter_number}
  chapterContent={content}
  onReviewComplete={(result) =>
  {
    // 处理审核结果
  }}
/>
```

- [ ] **Step 8: 提交变更**

```bash
git add frontend/src/components/workbench/creation/WritingPanel.tsx
git commit -m "feat(workbench): add writing page API integration with save and generate"
```

---

## Task 4: AIAssistantPanel 审核功能对接

**Files:**
- Modify: `frontend/src/components/workbench/creation/AIAssistantPanel.tsx`

### 当前状态分析

组件已经：
- 渲染了写作辅助和质量检测两个 Tab
- 显示了模拟的审核数据

缺失功能：
- 未导入 `chaptersApi`
- 审核功能未对接真实 API
- 写作辅助功能未实现

### 实现步骤

- [ ] **Step 1: 添加 props 和导入**

```typescript
import { chaptersApi } from '@/lib/api'
import type { ReviewResponse } from '@/types'

interface AIAssistantPanelProps
{
  projectId: number
  chapterNumber?: number
  chapterContent?: string
  onReviewComplete?: (result: ReviewResponse) => void
}
```

- [ ] **Step 2: 添加审核状态**

```typescript
const [reviewing, setReviewing] = useState(false)
const [reviewResult, setReviewResult] = useState<ReviewResponse | null>(null)
```

- [ ] **Step 3: 实现审核功能**

```typescript
const handleReview = async () =>
{
  if (!chapterNumber) return
  setReviewing(true)
  try
  {
    const result = await chaptersApi.review(projectId, chapterNumber)
    setReviewResult(result)
    onReviewComplete?.(result)
    
    if (result.passed)
    {
      toast.success('审核通过')
    }
    else
    {
      toast.warning('审核未通过，请根据建议修改')
    }
  }
  catch (err)
  {
    console.error('Failed to review:', err)
    toast.error('审核失败')
  }
  finally
  {
    setReviewing(false)
  }
}
```

- [ ] **Step 4: 使用真实审核数据渲染**

```typescript
// 在质量检测 Tab 中使用 reviewResult
{reviewResult ? (
  <>
    {/* 整体评分 */}
    <div className="p-4 bg-muted rounded-md text-center">
      <div className="text-3xl font-bold text-primary">
        {reviewResult.passed ? '通过' : '未通过'}
      </div>
      <div className="text-sm text-muted-foreground">审核结果</div>
    </div>
    
    {/* 反馈 */}
    <div className="p-3 bg-muted rounded-md">
      <span className="text-sm font-medium">反馈</span>
      <p className="text-sm text-muted-foreground mt-1">
        {reviewResult.feedback}
      </p>
    </div>
    
    {/* 问题列表 */}
    {reviewResult.issues.length > 0 && (
      <div className="space-y-2">
        <span className="text-sm font-medium">发现问题</span>
        {reviewResult.issues.map((issue, index) => (
          <div key={index} className="p-2 bg-yellow-50 border border-yellow-200 rounded text-sm">
            <AlertCircle className="h-4 w-4 inline text-yellow-600 mr-1" />
            <span>{issue}</span>
          </div>
        ))}
      </div>
    )}
  </>
) : (
  <Button onClick={handleReview} disabled={reviewing || !chapterContent}>
    {reviewing ? '审核中...' : '开始审核'}
  </Button>
)}
```

- [ ] **Step 5: 提交变更**

```bash
git add frontend/src/components/workbench/creation/AIAssistantPanel.tsx
git commit -m "feat(workbench): add review API integration to AIAssistantPanel"
```

---

## 测试验证

### 手动测试清单

- [ ] 大纲页面 - 获取大纲数据
- [ ] 大纲页面 - 保存大纲
- [ ] 大纲页面 - AI 生成大纲（流式输出）
- [ ] 大纲页面 - 确认大纲
- [ ] 章节大纲页面 - 获取章节列表
- [ ] 章节大纲页面 - 编辑并保存章节
- [ ] 章节大纲页面 - 确认章节
- [ ] 章节大纲页面 - 批量生成（流式输出）
- [ ] 写作页面 - 切换章节加载内容
- [ ] 写作页面 - 保存内容
- [ ] 写作页面 - AI 生成内容（流式输出）
- [ ] AI 助手 - 质量检测审核

---

## 注意事项

1. **不修改 UI 布局** - 仅添加事件绑定和 API 调用
2. **SSE 流式处理** - 使用现有的 `createSSEStream` 工具
3. **错误处理** - 使用 `toast` 显示错误信息
4. **加载状态** - 添加 loading 和 disabled 状态