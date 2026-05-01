# 右栏优化、灵感保存与进度弹窗 实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 加宽右栏并增加收缩展开功能，修复灵感选项保存问题，用进度弹窗替代页面跳转

**Architecture:** 前端4个面板组件各自添加收缩状态和按钮；后端扩展 CollectedInfoUpdate schema 保存灵感全字段；新建 OutlineProgressDialog 组件替代页面跳转

**Tech Stack:** React 18, shadcn/ui Dialog, Tailwind CSS, FastAPI, Pydantic

---

## File Structure

| 文件 | 操作 | 职责 |
|------|------|------|
| `backend/app/schemas/outline.py` | 修改 | 扩展 CollectedInfoUpdate，增加灵感全字段 |
| `backend/app/api/outline.py` | 修改 | update_collected_info 端点处理新字段 |
| `frontend/src/components/workbench/planning/InspirationPanel.tsx` | 修改 | 右栏加宽+收缩按钮，handleConfirm 改为弹窗 |
| `frontend/src/components/workbench/planning/OutlineProgressDialog.tsx` | 新建 | 进度弹窗组件，3步骤进度条 |
| `frontend/src/components/workbench/creation/OutlinePanel.tsx` | 修改 | 右栏加宽+收缩按钮 |
| `frontend/src/components/workbench/creation/ChapterOutlinePanel.tsx` | 修改 | 右栏加宽+收缩按钮 |
| `frontend/src/components/workbench/creation/AIAssistantPanel.tsx` | 修改 | 右栏加宽+收缩按钮 |
| `frontend/src/components/workbench/creation/WritingPanel.tsx` | 修改 | 传递收缩状态给 AIAssistantPanel |

---

### Task 1: 后端 — 扩展 CollectedInfoUpdate schema

**Files:**
- Modify: `backend/app/schemas/outline.py:99-105`

- [ ] **Step 1: 扩展 CollectedInfoUpdate 类**

将 `backend/app/schemas/outline.py` 中的 `CollectedInfoUpdate` 替换为：

```python
class CollectedInfoUpdate(BaseModel):
    """灵感收集信息更新"""
    # 原有字段
    genre: Optional[str] = None
    theme: Optional[str] = None
    main_characters: Optional[str] = None
    world_setting: Optional[str] = None
    style_preference: Optional[str] = None
    # 新增灵感采集字段
    novelType: Optional[str] = None
    targetWords: Optional[int] = None
    coreTheme: Optional[str] = None
    targetReader: Optional[str] = None
    era: Optional[str] = None
    wordsPerChapter: Optional[str] = None
    customWordsPerChapter: Optional[int] = None
    maleLead: Optional[str] = None
    customMaleLead: Optional[str] = None
    femaleLead: Optional[str] = None
    customFemaleLead: Optional[str] = None
    protagonist: Optional[str] = None
    narrative: Optional[str] = None
    goldFinger: Optional[str] = None
    customGoldFinger: Optional[str] = None
    customGenre: Optional[str] = None
    customWorldSetting: Optional[str] = None
    inspiration_template: Optional[str] = None
```

- [ ] **Step 2: 更新 update_collected_info 端点**

在 `backend/app/api/outline.py` 的 `update_collected_info` 函数中，在原有5个字段的 if 块之后（约 line 361 之后），添加新字段处理：

```python
    # 处理新增灵感采集字段
    new_fields = [
        'novelType', 'targetWords', 'coreTheme', 'targetReader', 'era',
        'wordsPerChapter', 'customWordsPerChapter', 'maleLead', 'customMaleLead',
        'femaleLead', 'customFemaleLead', 'protagonist', 'narrative',
        'goldFinger', 'customGoldFinger', 'customGenre', 'customWorldSetting',
        'inspiration_template',
    ]
    for field in new_fields:
        value = getattr(request, field, None)
        if value is not None:
            current_info[field] = value
```

- [ ] **Step 3: 验证后端改动**

Run: `docker exec novelagent-backend-1 python -c "from app.schemas.outline import CollectedInfoUpdate; u = CollectedInfoUpdate(novelType='xuanhuan', targetWords=100000, coreTheme='revenge', targetReader='male', era='ancient', wordsPerChapter='3000', protagonist='hero', inspiration_template='test'); print('OK:', u.model_dump())"`

Expected: 输出包含所有新字段的字典

- [ ] **Step 4: Commit**

```bash
git add backend/app/schemas/outline.py backend/app/api/outline.py
git commit -m "feat(api): extend CollectedInfoUpdate to save all inspiration fields"
```

---

### Task 2: 新建 OutlineProgressDialog 进度弹窗组件

**Files:**
- Create: `frontend/src/components/workbench/planning/OutlineProgressDialog.tsx`

- [ ] **Step 1: 创建进度弹窗组件**

创建 `frontend/src/components/workbench/planning/OutlineProgressDialog.tsx`：

```tsx
// frontend/src/components/workbench/planning/OutlineProgressDialog.tsx

import { useState, useEffect, useRef } from 'react'
import { Sparkles, Check, Loader2, PartyPopper, AlertCircle, RefreshCw } from 'lucide-react'
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
} from '@/components/ui/dialog'
import { Button } from '@/components/ui/button'
import { outlineApi } from '@/lib/api'
import type { OutlineStreamResult } from '@/lib/api'

type StepStatus = 'pending' | 'active' | 'done'

interface Step
{
  label: string
  status: StepStatus
}

interface OutlineProgressDialogProps
{
  open: boolean
  onClose: () => void
  projectId: number
  onComplete: () => void
  onViewOutline: () => void
}

export function OutlineProgressDialog({
  open,
  onClose,
  projectId,
  onComplete,
  onViewOutline,
}: OutlineProgressDialogProps)
{
  const [steps, setSteps] = useState<Step[]>([
    { label: '生成大纲', status: 'pending' },
    { label: '生成人物', status: 'pending' },
    { label: '生成关系', status: 'pending' },
  ])
  const [error, setError] = useState<string | null>(null)
  const [completed, setCompleted] = useState(false)
  const abortRef = useRef<AbortController | null>(null)
  const startedRef = useRef(false)

  // 弹窗打开时自动开始生成
  useEffect(() =>
  {
    if (open && !startedRef.current)
    {
      startedRef.current = true
      handleGenerate()
    }
    if (!open)
    {
      // 弹窗关闭时重置
      startedRef.current = false
    }
  }, [open])

  const handleGenerate = async () =>
  {
    setError(null)
    setCompleted(false)
    setSteps([
      { label: '生成大纲', status: 'active' },
      { label: '生成人物', status: 'pending' },
      { label: '生成关系', status: 'pending' },
    ])

    const controller = new AbortController()
    abortRef.current = controller

    try
    {
      await outlineApi.createStream(
        projectId,
        {
          onChunk: () =>
          {
            // 大纲生成中，步骤1保持 active
          },
          onDone: (result: OutlineStreamResult) =>
          {
            abortRef.current = null
            // 大纲完成 → 人物瞬间完成 → 关系瞬间完成
            setSteps([
              { label: '生成大纲', status: 'done' },
              { label: '生成人物', status: 'active' },
              { label: '生成关系', status: 'pending' },
            ])
            // 人物从大纲结果中提取，瞬间完成
            setTimeout(() =>
            {
              setSteps([
                { label: '生成大纲', status: 'done' },
                { label: '生成人物', status: 'done' },
                { label: '生成关系', status: 'active' },
              ])
              // 关系也瞬间完成
              setTimeout(() =>
              {
                setSteps([
                  { label: '生成大纲', status: 'done' },
                  { label: '生成人物', status: 'done' },
                  { label: '生成关系', status: 'done' },
                ])
                setCompleted(true)
                onComplete()
              }, 500)
            }, 500)
          },
          onError: (errMsg: string) =>
          {
            abortRef.current = null
            setError(errMsg)
            setSteps(prev => prev.map(s => s.status === 'active' ? { ...s, status: 'pending' } : s))
          },
        },
        { signal: controller.signal }
      )
    }
    catch (err)
    {
      abortRef.current = null
      setError('生成失败，请重试')
      setSteps(prev => prev.map(s => s.status === 'active' ? { ...s, status: 'pending' } : s))
    }
  }

  // 组件卸载时取消请求
  useEffect(() =>
  {
    return () =>
    {
      if (abortRef.current)
      {
        abortRef.current.abort()
        abortRef.current = null
      }
    }
  }, [])

  const stepIcon = (status: StepStatus) =>
  {
    switch (status)
    {
      case 'done':
        return <Check className="h-4 w-4 text-green-600" />
      case 'active':
        return <Loader2 className="h-4 w-4 text-blue-600 animate-spin" />
      default:
        return <div className="h-4 w-4 rounded-full border-2 border-gray-300" />
    }
  }

  const stepBarColor = (status: StepStatus) =>
  {
    switch (status)
    {
      case 'done':
        return 'bg-green-500'
      case 'active':
        return 'bg-blue-500 animate-pulse'
      default:
        return 'bg-gray-200'
    }
  }

  const stepLabelColor = (status: StepStatus) =>
  {
    switch (status)
    {
      case 'done':
        return 'text-green-600'
      case 'active':
        return 'text-blue-600'
      default:
        return 'text-muted-foreground'
    }
  }

  return (
    <Dialog open={open} onOpenChange={() =>
    {
      // 生成中不可关闭
      if (completed || error) onClose()
    }}>
      <DialogContent className="sm:max-w-md" onPointerDownOutside={(e) =>
      {
        // 生成中阻止点击外部关闭
        if (!completed && !error) e.preventDefault()
      }}>
        <DialogHeader>
          <DialogTitle className="flex items-center justify-center gap-2 text-center">
            {completed ? (
              <>
                <PartyPopper className="h-5 w-5 text-green-500" />
                规划已完成
              </>
            ) : error ? (
              <>
                <AlertCircle className="h-5 w-5 text-red-500" />
                生成失败
              </>
            ) : (
              <>
                <Sparkles className="h-5 w-5 text-blue-500" />
                正在规划你的小说
              </>
            )}
          </DialogTitle>
          <DialogDescription className="text-center">
            {completed
              ? '小说大纲已成功生成，快去查看吧'
              : error
                ? '生成过程中出现错误'
                : 'AI 正在基于你的灵感构思大纲...'}
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-4 py-4">
          {steps.map((step, index) => (
            <div key={index}>
              <div className="flex items-center justify-between mb-1.5">
                <span className={`text-sm ${stepLabelColor(step.status)}`}>
                  {step.label}
                </span>
                <div className="flex items-center gap-1.5">
                  {step.status === 'done' && <span className="text-xs text-green-600">完成</span>}
                  {stepIcon(step.status)}
                </div>
              </div>
              <div className="h-2 bg-gray-100 rounded-full overflow-hidden">
                <div
                  className={`h-full rounded-full transition-all duration-500 ${stepBarColor(step.status)}`}
                  style={{
                    width: step.status === 'done' ? '100%' : step.status === 'active' ? '60%' : '0%',
                  }}
                />
              </div>
            </div>
          ))}
        </div>

        {!completed && !error && (
          <p className="text-center text-xs text-muted-foreground">
            预计需要 30-60 秒，请耐心等待
          </p>
        )}

        {error && (
          <div className="p-3 bg-red-50 border border-red-200 rounded-md">
            <p className="text-sm text-red-700">{error}</p>
          </div>
        )}

        <div className="flex gap-2 pt-2">
          {completed ? (
            <>
              <Button variant="outline" className="flex-1" onClick={onClose}>
                留在灵感页
              </Button>
              <Button className="flex-1" onClick={onViewOutline}>
                查看大纲
              </Button>
            </>
          ) : error ? (
            <>
              <Button variant="outline" className="flex-1" onClick={onClose}>
                关闭
              </Button>
              <Button className="flex-1" onClick={handleGenerate}>
                <RefreshCw className="h-4 w-4 mr-1.5" />
                重试
              </Button>
            </>
          ) : (
            <p className="text-xs text-muted-foreground text-center w-full">
              生成中，请勿关闭...
            </p>
          )}
        </div>
      </DialogContent>
    </Dialog>
  )
}
```

- [ ] **Step 2: 验证组件创建**

Run: `ls -la frontend/src/components/workbench/planning/OutlineProgressDialog.tsx`

Expected: 文件存在

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/workbench/planning/OutlineProgressDialog.tsx
git commit -m "feat(frontend): add OutlineProgressDialog component"
```

---

### Task 3: InspirationPanel — 右栏加宽+收缩 + 进度弹窗集成

**Files:**
- Modify: `frontend/src/components/workbench/planning/InspirationPanel.tsx`

- [ ] **Step 1: 添加 import 和状态**

在 InspirationPanel.tsx 顶部 import 中添加：

```tsx
import { ChevronLeft, ChevronRight } from 'lucide-react'
import { OutlineProgressDialog } from './OutlineProgressDialog'
```

在组件内 `const [errors, setErrors]` 之后添加收缩和弹窗状态：

```tsx
  const [rightCollapsed, setRightCollapsed] = useState(false)
  const [showProgressDialog, setShowProgressDialog] = useState(false)
```

- [ ] **Step 2: 修改 handleConfirm 函数**

将 `handleConfirm` 函数中的 `setActiveMenuItem('outline')` 替换为 `setShowProgressDialog(true)`，并移除 `toast.success('灵感已确认')` 后面的跳转逻辑。

完整替换 `handleConfirm` 函数（从 `const handleConfirm` 到函数结尾 `}`）：

```tsx
  const handleConfirm = async () =>
  {
    // 验证必填项
    const newErrors: Record<string, string> = {}
    if (!targetReader) newErrors.targetReader = '请选择目标读者'
    if (!novelType) newErrors.novelType = '请选择小说类型'
    if (!targetWords) newErrors.targetWords = '请输入目标字数'
    else if (targetWords < 10000) newErrors.targetWords = '目标字数不能少于1万字'
    if (!wordsPerChapter) newErrors.wordsPerChapter = '请选择每章字数'
    if (!era) newErrors.era = '请选择年代'
    if (!coreTheme) newErrors.coreTheme = '请选择核心主题'
    if (targetReader === 'male' && !maleLead) newErrors.maleLead = '请选择男主人设'
    if (targetReader === 'female' && !femaleLead) newErrors.femaleLead = '请选择女主人设'

    if (Object.keys(newErrors).length > 0)
    {
      setErrors(newErrors)
      toast.error('请完善必填信息')
      return
    }

    setConfirming(true)
    try
    {
      // 构建 collected_info 数据
      const collectedInfoData: Record<string, unknown> = {
        inspiration_template: template,
      }

      if (novelType) collectedInfoData.novelType = novelType
      if (targetWords) collectedInfoData.targetWords = targetWords
      if (coreTheme) collectedInfoData.coreTheme = coreTheme
      if (worldSetting)
      {
        collectedInfoData.worldSetting = worldSetting
        if (customWorldSetting) collectedInfoData.customWorldSetting = customWorldSetting
      }
      if (targetReader) collectedInfoData.targetReader = targetReader
      if (wordsPerChapter)
      {
        collectedInfoData.wordsPerChapter = wordsPerChapter
        if (customWordsPerChapter) collectedInfoData.customWordsPerChapter = customWordsPerChapter
      }
      if (narrative) collectedInfoData.narrative = narrative
      if (stylePreference) collectedInfoData.stylePreference = stylePreference
      if (era) collectedInfoData.era = era

      if (targetReader === 'male')
      {
        const lead = maleLead === 'custom' ? customMaleLead : maleLead
        if (lead) collectedInfoData.protagonist = lead
        const genreVal = genre === 'custom' ? customGenre : genre
        if (genreVal) collectedInfoData.genre = genreVal
        const gf = goldFinger === 'custom' ? customGoldFinger : goldFinger
        if (gf) collectedInfoData.goldFinger = gf
      }
      else if (targetReader === 'female')
      {
        const lead = femaleLead === 'custom' ? customFemaleLead : femaleLead
        if (lead) collectedInfoData.protagonist = lead
      }

      await collectedInfoApi.update(projectId, collectedInfoData)
      toast.success('灵感已确认')
      clearInspirationDraft()

      // 弹出进度弹窗，不跳转
      setShowProgressDialog(true)
    }
    catch (err)
    {
      console.error('Failed to confirm inspiration:', err)
      toast.error('保存失败')
    }
    finally
    {
      setConfirming(false)
    }
  }
```

- [ ] **Step 3: 修改底部按钮提示文案**

将底部的 `<p className="text-xs text-muted-foreground">确认后自动跳转到大纲生成</p>` 替换为：

```tsx
          <p className="text-xs text-muted-foreground">确认后自动生成小说大纲</p>
```

- [ ] **Step 4: 修改右栏 — 加宽和收缩按钮**

将右侧 Prompt 模板区的 div（约 line 824）：

```tsx
      <div className="flex-[3] border-l bg-white flex flex-col max-w-[280px]">
```

替换为：

```tsx
      <div className={`border-l bg-white flex flex-col shrink-0 transition-all duration-300 ${rightCollapsed ? 'w-12' : 'w-[360px]'} relative`}>
        {/* 收缩展开按钮 */}
        <button
          onClick={() => setRightCollapsed(!rightCollapsed)}
          className="absolute left-[-14px] top-1/2 -translate-y-1/2 z-10 w-7 h-7 bg-indigo-600 hover:bg-indigo-700 text-white rounded-full flex items-center justify-center shadow-md transition-colors"
        >
          {rightCollapsed ? <ChevronRight className="h-3.5 w-3.5" /> : <ChevronLeft className="h-3.5 w-3.5" />}
        </button>
```

- [ ] **Step 5: 右栏收缩时隐藏内容**

在右栏内部（收缩按钮之后），将所有内容包裹在条件渲染中：

将右栏内现有内容（标题栏 `div` + 手动编辑提示 `div` + Textarea 区 + 快捷模板区）包裹在：

```tsx
        {!rightCollapsed && (
          <>
            {/* 现有内容保持不变 */}
            <div className="flex items-center justify-between px-4 py-3 border-b">
              ...existing content...
            </div>
            ...all the rest...
          </>
        )}
```

具体操作：在收缩按钮 `</button>` 之后添加 `{!rightCollapsed && (<>`，在右栏 div 结束 `</div>` 之前添加 `</>)}`

收缩状态下显示简化图标：

```tsx
        {rightCollapsed && (
          <div className="flex flex-col items-center pt-4 gap-3">
            <Lightbulb className="h-4 w-4 text-muted-foreground" />
            <Copy className="h-4 w-4 text-muted-foreground" />
          </div>
        )}
```

- [ ] **Step 6: 添加 OutlineProgressDialog 到 JSX**

在 InspirationPanel 的 return JSX 最外层 `</div>` 之前添加：

```tsx
      {/* 大纲生成进度弹窗 */}
      <OutlineProgressDialog
        open={showProgressDialog}
        onClose={() => setShowProgressDialog(false)}
        projectId={projectId}
        onComplete={() => {}}
        onViewOutline={() =>
        {
          setShowProgressDialog(false)
          setActiveMenuItem('outline')
        }}
      />
```

- [ ] **Step 7: 验证前端编译**

Run: `cd /opt/project/novelagent/frontend && npx tsc --noEmit 2>&1 | head -30`

Expected: 无错误或只有无关的类型警告

- [ ] **Step 8: Commit**

```bash
git add frontend/src/components/workbench/planning/InspirationPanel.tsx
git commit -m "feat(frontend): widen InspirationPanel right panel, add collapse button, integrate progress dialog"
```

---

### Task 4: OutlinePanel — 右栏加宽+收缩按钮

**Files:**
- Modify: `frontend/src/components/workbench/creation/OutlinePanel.tsx`

- [ ] **Step 1: 添加 import 和状态**

在 OutlinePanel.tsx 顶部 import 中添加：

```tsx
import { ChevronLeft, ChevronRight } from 'lucide-react'
```

在组件内 `const [analysisResult, setAnalysisResult]` 之后添加：

```tsx
  const [rightCollapsed, setRightCollapsed] = useState(false)
```

- [ ] **Step 2: 修改右栏 div**

将 `className="w-[240px] border-l bg-white flex flex-col"` 替换为：

```tsx
      <div className={`border-l bg-white flex flex-col shrink-0 transition-all duration-300 ${rightCollapsed ? 'w-12' : 'w-[360px]'} relative`}>
        {/* 收缩展开按钮 */}
        <button
          onClick={() => setRightCollapsed(!rightCollapsed)}
          className="absolute left-[-14px] top-1/2 -translate-y-1/2 z-10 w-7 h-7 bg-indigo-600 hover:bg-indigo-700 text-white rounded-full flex items-center justify-center shadow-md transition-colors"
        >
          {rightCollapsed ? <ChevronRight className="h-3.5 w-3.5" /> : <ChevronLeft className="h-3.5 w-3.5" />}
        </button>
```

- [ ] **Step 3: 条件渲染右栏内容**

将右栏内的现有内容（AI 分析标题和内容区）包裹在 `{!rightCollapsed && (<> ... </>)}` 中。

收缩状态添加简化图标：

```tsx
        {rightCollapsed && (
          <div className="flex flex-col items-center pt-4 gap-3">
            <Sparkles className="h-4 w-4 text-muted-foreground" />
          </div>
        )}
```

- [ ] **Step 4: 验证编译**

Run: `cd /opt/project/novelagent/frontend && npx tsc --noEmit 2>&1 | head -30`

Expected: 无错误

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/workbench/creation/OutlinePanel.tsx
git commit -m "feat(frontend): widen OutlinePanel right panel, add collapse button"
```

---

### Task 5: ChapterOutlinePanel — 右栏加宽+收缩按钮

**Files:**
- Modify: `frontend/src/components/workbench/creation/ChapterOutlinePanel.tsx`

- [ ] **Step 1: 添加 import 和状态**

在 ChapterOutlinePanel.tsx 顶部 import 中添加：

```tsx
import { ChevronLeft, ChevronRight } from 'lucide-react'
```

在组件内 `const [generating, setGenerating]` 之后添加：

```tsx
  const [rightCollapsed, setRightCollapsed] = useState(false)
```

- [ ] **Step 2: 修改右栏 div**

将 `className="w-56 border-l bg-white p-3"` 替换为：

```tsx
      <div className={`border-l bg-white shrink-0 transition-all duration-300 ${rightCollapsed ? 'w-12' : 'w-[360px]'} relative ${rightCollapsed ? '' : 'p-3'}`}>
        {/* 收缩展开按钮 */}
        <button
          onClick={() => setRightCollapsed(!rightCollapsed)}
          className="absolute left-[-14px] top-1/2 -translate-y-1/2 z-10 w-7 h-7 bg-indigo-600 hover:bg-indigo-700 text-white rounded-full flex items-center justify-center shadow-md transition-colors"
        >
          {rightCollapsed ? <ChevronRight className="h-3.5 w-3.5" /> : <ChevronLeft className="h-3.5 w-3.5" />}
        </button>
```

- [ ] **Step 3: 条件渲染右栏内容**

将右栏内的现有内容包裹在 `{!rightCollapsed && (<> ... </>)}` 中。

收缩状态添加简化图标：

```tsx
        {rightCollapsed && (
          <div className="flex flex-col items-center pt-4 gap-3">
            <FileText className="h-4 w-4 text-muted-foreground" />
          </div>
        )}
```

需要额外添加 `FileText` 到 lucide-react import 中（如果尚未导入）。

- [ ] **Step 4: 验证编译**

Run: `cd /opt/project/novelagent/frontend && npx tsc --noEmit 2>&1 | head -30`

Expected: 无错误

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/workbench/creation/ChapterOutlinePanel.tsx
git commit -m "feat(frontend): widen ChapterOutlinePanel right panel, add collapse button"
```

---

### Task 6: AIAssistantPanel + WritingPanel — 右栏加宽+收缩按钮

**Files:**
- Modify: `frontend/src/components/workbench/creation/AIAssistantPanel.tsx`
- Modify: `frontend/src/components/workbench/creation/WritingPanel.tsx`

- [ ] **Step 1: 修改 AIAssistantPanel — 添加收缩支持**

在 AIAssistantPanel.tsx 中：

添加 import：
```tsx
import { ChevronLeft, ChevronRight, ShieldCheck } from 'lucide-react'
```

注意：`ShieldCheck` 已在 import 中，只需添加 `ChevronLeft, ChevronRight`。

修改 Props 接口，添加 `collapsed` 和 `onToggleCollapse`：

```tsx
interface AIAssistantPanelProps
{
  projectId?: number
  chapterNumber?: number
  chapterContent?: string
  onReviewComplete?: (result: ReviewResponse) => void
  collapsed?: boolean
  onToggleCollapse?: () => void
}
```

修改组件解构：

```tsx
export function AIAssistantPanel({ projectId, chapterNumber, chapterContent, onReviewComplete, collapsed, onToggleCollapse }: AIAssistantPanelProps)
```

修改外层 div：

```tsx
    <div className={`border-l bg-white flex flex-col h-full shrink-0 transition-all duration-300 ${collapsed ? 'w-12' : 'w-[360px]'} relative`}>
      {/* 收缩展开按钮 */}
      <button
        onClick={onToggleCollapse}
        className="absolute left-[-14px] top-1/2 -translate-y-1/2 z-10 w-7 h-7 bg-indigo-600 hover:bg-indigo-700 text-white rounded-full flex items-center justify-center shadow-md transition-colors"
      >
        {collapsed ? <ChevronRight className="h-3.5 w-3.5" /> : <ChevronLeft className="h-3.5 w-3.5" />}
      </button>
```

将现有内容包裹在 `{!collapsed && (<> ... </>)}` 中，收缩状态显示图标：

```tsx
      {collapsed && (
        <div className="flex flex-col items-center pt-4 gap-3">
          <ShieldCheck className="h-4 w-4 text-muted-foreground" />
        </div>
      )}
```

- [ ] **Step 2: 修改 WritingPanel — 传递收缩状态**

在 WritingPanel.tsx 中添加状态：

```tsx
  const [rightCollapsed, setRightCollapsed] = useState(false)
```

修改 AIAssistantPanel 调用：

```tsx
      <AIAssistantPanel
        projectId={projectId}
        chapterNumber={selectedChapter?.chapter_number}
        chapterContent={content}
        onReviewComplete={() =>
        {
          // 审核结果回调
        }}
        collapsed={rightCollapsed}
        onToggleCollapse={() => setRightCollapsed(!rightCollapsed)}
      />
```

- [ ] **Step 3: 验证编译**

Run: `cd /opt/project/novelagent/frontend && npx tsc --noEmit 2>&1 | head -30`

Expected: 无错误

- [ ] **Step 4: Commit**

```bash
git add frontend/src/components/workbench/creation/AIAssistantPanel.tsx frontend/src/components/workbench/creation/WritingPanel.tsx
git commit -m "feat(frontend): widen AIAssistantPanel right panel, add collapse button"
```

---

### Task 7: 集成验证

- [ ] **Step 1: 前端类型检查**

Run: `cd /opt/project/novelagent/frontend && npx tsc --noEmit`

Expected: 无错误

- [ ] **Step 2: 重建前端并测试**

Run: `docker compose build --no-cache frontend && docker compose up -d frontend`

Expected: 构建成功

- [ ] **Step 3: 重启后端测试**

Run: `docker compose restart backend`

Expected: 后端正常启动

- [ ] **Step 4: 端到端手动验证**

在浏览器 http://localhost:3001 验证：

1. **右栏加宽**：灵感页右栏应显示 360px，大纲/章节大纲/正文页右栏也是 360px
2. **收缩展开**：点击右栏左边缘的圆形按钮，右栏收缩到 48px；再点展开到 360px
3. **灵感保存**：填写灵感表单 → 点"确认灵感" → 检查后端 `outlines.collected_info` 是否包含所有字段
4. **进度弹窗**：点"确认灵感"后弹出进度弹窗，3步骤依次完成，显示"规划已完成"
5. **查看大纲**：完成后点"查看大纲"跳转到大纲页，点"留在灵感页"关闭弹窗

- [ ] **Step 5: Final commit (if any fixes needed)**

```bash
git add -A
git commit -m "fix: integration fixes for right panel and progress dialog"
```
