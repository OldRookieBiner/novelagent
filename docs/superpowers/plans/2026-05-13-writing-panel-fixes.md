# 章节正文生成状态持久化与校验优化 实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 修复章节正文生成切换标签状态丢失、跳章生成、审核反馈不显示三个 bug

**Architecture:** 问题1 将 WritingPanel 的生成状态从组件内 useState 提升到 workflowStore（与 ChapterOutlinePanel 已有模式一致）；问题2 在前后端增加前序章节校验；问题3 修正审核反馈数据结构和渲染逻辑

**Tech Stack:** React 18 + Zustand + FastAPI + SQLAlchemy

---

## File Structure

| 文件 | 职责 | 操作 |
|------|------|------|
| `frontend/src/stores/workflowStore.ts` | 新增章节正文生成状态和 actions | 修改 |
| `frontend/src/components/workbench/creation/WritingPanel.tsx` | 替换本地状态为 store；移除 abort cleanup；增加按序生成校验 | 修改 |
| `frontend/src/types/index.ts` | 新增 ReviewIssue 类型；更新 ReviewResponse | 修改 |
| `frontend/src/components/workbench/creation/AIAssistantPanel.tsx` | issues 结构化渲染；新增评分展示 | 修改 |
| `backend/app/api/chapters.py` | generate_chapter 前序校验；review done 事件字段修正 | 修改 |

---

### Task 1: workflowStore 新增章节正文生成状态

**Files:**
- Modify: `frontend/src/stores/workflowStore.ts:16-134` (interface + initialState)
- Modify: `frontend/src/stores/workflowStore.ts:205-215` (actions 区域)

- [ ] **Step 1: 在 WorkflowState interface 中新增写作生成状态声明**

在 `// ========== 写作状态 ==========` 区块（第41行）之后，`writtenChapters` 之前，新增：

```typescript
  // ========== 章节正文生成状态 ==========
  writingChapterGenerating: boolean
  writingGeneratingChapterId: number | null
```

在 actions 声明区域（`setCurrentChapter` 之后，第91行附近）新增：

```typescript

  // 章节正文生成
  setWritingChapterGenerating: (generating: boolean) => void
  setWritingGeneratingChapterId: (id: number | null) => void
  clearWritingGenerationState: () => void
```

- [ ] **Step 2: 在 initialState 中新增写作生成初始值**

在 `chapterOutlineAbortController: null,` 之后（第123行），新增：

```typescript
  writingChapterGenerating: false,
  writingGeneratingChapterId: null,
```

- [ ] **Step 3: 在 store 实现中新增写作生成 actions**

在 `setCurrentChapter: (chapter) => set({ currentChapter: chapter }),` 之后（第215行），新增：

```typescript

  // ========== 章节正文生成 Actions ==========

  setWritingChapterGenerating: (generating) => set({ writingChapterGenerating: generating }),

  setWritingGeneratingChapterId: (id) => set({ writingGeneratingChapterId: id }),

  // 生成完成后清理状态
  clearWritingGenerationState: () => set({
    writingChapterGenerating: false,
    writingGeneratingChapterId: null,
  }),
```

注：AbortController 保留在组件内（用 `useRef` 管理），不存入 store。原因：SSE 回调需要访问组件闭包中的 `setContent` 等状态，AbortController 的生命周期应与组件绑定。store 只管理"是否在生成"的标记。

- [ ] **Step 4: 在 reset action 中新增写作生成状态清理**

将 `reset` action 修改为：

```typescript
  reset: () =>
  {
    const state = useWorkflowStore.getState()
    if (state.chapterOutlineAbortController)
    {
      state.chapterOutlineAbortController.abort()
    }
    set(initialState)
  },
```

注：`writingAbortController` 不在 store 中，不需要在 reset 中处理。

- [ ] **Step 5: 验证 TypeScript 编译通过**

Run: `cd /opt/project/novelagent/frontend && npx tsc --noEmit 2>&1 | head -20`
Expected: 无类型错误（或仅有与本次修改无关的已有错误）

- [ ] **Step 6: Commit**

```bash
git add frontend/src/stores/workflowStore.ts
git commit -m "feat(workflowStore): add chapter content generation state and actions"
```

---

### Task 2: WritingPanel 状态提升到 store + 移除 abort cleanup

**设计说明**：
- `generating` 和 `generatingChapterId` 状态提升到 store，用于切换标签后恢复"是否在生成"的标记
- AbortController 仍在组件内创建和管理，因为 SSE 回调需要访问组件闭包中的 `setContent` 等状态
- 移除 useEffect cleanup 中的 abort，不是为了保留 SSE 流（这是 React 组件化的固有限制），而是避免组件卸载时误终止正在进行的请求
- 组件挂载时检查 store 中 `writingChapterGenerating`，如果为 true 说明上次生成可能中断，从后端恢复内容

**Files:**
- Modify: `frontend/src/components/workbench/creation/WritingPanel.tsx`

- [ ] **Step 1: 新增 store 导入和状态读取**

在文件顶部 import 区域新增：

```typescript
import { useWorkflowStore } from '@/stores/workflowStore'
import { useShallow } from 'zustand/react/shallow'
```

在 `WritingPanel` 函数体内（第76行之后），在现有 `useState` 声明之前新增 store 读取：

```typescript
  // 从 workflowStore 读取章节正文生成状态（持久化，切换标签不丢失）
  const {
    writingChapterGenerating: generating,
    writingGeneratingChapterId: generatingChapterId,
    setWritingChapterGenerating,
    setWritingGeneratingChapterId,
    clearWritingGenerationState,
  } = useWorkflowStore(useShallow(s => ({
    writingChapterGenerating: s.writingChapterGenerating,
    writingGeneratingChapterId: s.writingGeneratingChapterId,
    setWritingChapterGenerating: s.setWritingChapterGenerating,
    setWritingGeneratingChapterId: s.setWritingGeneratingChapterId,
    clearWritingGenerationState: s.clearWritingGenerationState,
  })))
```

注：`AbortController` 保留在组件内（用 `useRef`），因为 SSE 回调需要访问组件闭包中的 `setContent` 等。Store 只管理"是否在生成"的状态标记。

- [ ] **Step 2: 移除被 store 替代的本地状态**

删除以下两行（原第85、89行）：

```typescript
  const [generating, setGenerating] = useState(false)
  const [generatingChapterId, setGeneratingChapterId] = useState<number | null>(null)
```

保留 `abortControllerRef`（原第86行），AbortController 仍在组件内管理：

```typescript
  const abortControllerRef = useRef<AbortController | null>(null)
```

- [ ] **Step 3: 移除 useEffect cleanup 中的 abort**

删除整个 useEffect（原第160-169行）：

```typescript
  useEffect(() =>
  {
    return () =>
    {
      if (abortControllerRef.current)
      {
        abortControllerRef.current.abort()
      }
    }
  }, [])
```

- [ ] **Step 4: 修改 handleGenerate 中的状态设置**

在 `handleGenerate` 函数中，将本地状态设置替换为 store 调用：

将：
```typescript
    setGenerating(true)
    setGeneratingChapterId(selectedChapter.id)
```

替换为：
```typescript
    setWritingChapterGenerating(true)
    setWritingGeneratingChapterId(selectedChapter.id)
```

在 `handleGenerate` 的 `try` 块中，`abortControllerRef` 保留在组件内，不需要改动：

```typescript
    const controller = new AbortController()
    abortControllerRef.current = controller
```

在 `finally` 块中，将：

```typescript
      setGenerating(false)
      setGeneratingChapterId(null)
      abortControllerRef.current = null
```

替换为：

```typescript
      clearWritingGenerationState()
      abortControllerRef.current = null
```

- [ ] **Step 5: 修改 handleCancelGenerate**

将：

```typescript
  const handleCancelGenerate = () =>
  {
    if (abortControllerRef.current)
    {
      abortControllerRef.current.abort()
      setGenerating(false)
      setGeneratingChapterId(null)
      toast.info('已取消生成')
    }
  }
```

替换为（使用 store 清理状态，但 abort 仍在组件内）：

```typescript
  const handleCancelGenerate = () =>
  {
    if (abortControllerRef.current)
    {
      abortControllerRef.current.abort()
      abortControllerRef.current = null
    }
    clearWritingGenerationState()
    toast.info('已取消生成')
  }
```

- [ ] **Step 6: 修改 done 回调中的 has_content 更新**

在 `handleGenerate` 的 `onDone` 回调中，原代码引用 `selectedChapter.id` 和 `setGenerating`/`setGeneratingChapterId` 不再存在。需要确认 `setChapters` 和 `setSaved` 仍用组件本地状态（它们不受影响）。

将 `onDone` 回调中的：
```typescript
            setChapters(prev => prev.map(c =>
              c.id === selectedChapter.id ? { ...c, has_content: true } : c
            ))
```

替换为（使用 generatingChapterId 从 store 获取）：
```typescript
            setChapters(prev => prev.map(c =>
              c.id === selectedChapter.id ? { ...c, has_content: true } : c
            ))
```

这部分不变，因为 `selectedChapter` 仍是组件本地状态。

- [ ] **Step 7: 修改 chunk 回调中的 has_content 更新**

在 `onChunk` 回调中无需修改（`accumulated` 和 `setContent` 仍用组件本地状态）。

在 `onDone` 回调中的 `setSaved(true)` 和 `setTimeout` 不变。

- [ ] **Step 8: 新增组件挂载恢复逻辑**

在 `fetchChapters` useEffect（原第92-115行）中，在 `finally` 块之前新增恢复逻辑：

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

      // 如果 store 中标记为正在生成，尝试从后端恢复内容
      const { writingChapterGenerating, writingGeneratingChapterId } = useWorkflowStore.getState()
      if (writingChapterGenerating && writingGeneratingChapterId)
      {
        const currentSelected = useWorkflowStore.getState()
        // 标记生成中断，因为 SSE 回调已无法传递到新组件实例
        clearWritingGenerationState()
        toast.info('生成因切换页面中断，请重新生成')
      }
    }
    fetchChapters()
  }, [projectId])
```

- [ ] **Step 9: 验证 TypeScript 编译通过**

Run: `cd /opt/project/novelagent/frontend && npx tsc --noEmit 2>&1 | head -20`
Expected: 无类型错误

- [ ] **Step 10: Commit**

```bash
git add frontend/src/components/workbench/creation/WritingPanel.tsx
git commit -m "fix(writing): lift generation state to workflowStore to persist across tab switches"
```

---

### Task 3: 后端章节按序生成校验

**Files:**
- Modify: `backend/app/api/chapters.py:607-611` (confirmed 校验之后)

- [ ] **Step 1: 在 generate_chapter API 中增加前序章节校验**

在 `if not chapter_outline.confirmed:` 校验之后（第611行），新增：

```python
    # 按序生成校验：前一章必须已生成内容
    if chapter_num > 1:
        prev_outline = db.query(ChapterOutline).filter(
            ChapterOutline.project_id == project_id,
            ChapterOutline.chapter_number == chapter_num - 1
        ).first()
        if prev_outline:
            prev_chapter = db.query(Chapter).filter(
                Chapter.chapter_outline_id == prev_outline.id
            ).first()
            if not prev_chapter or not prev_chapter.content:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Please generate chapter {chapter_num - 1} first"
                )
```

- [ ] **Step 2: 验证后端 API 行为**

Run: `docker compose restart backend && sleep 3`

然后测试跳章生成被拒绝：
```bash
curl -s -X POST "http://localhost:8000/api/projects/1/chapters/3/generate" -H "Content-Type: application/json" -H "Cookie: session_token=test" 2>&1 | head -5
```

Expected: 返回 400 错误（需先确认项目中有数据；若无项目则 404，说明代码编译无误即可）

- [ ] **Step 3: Commit**

```bash
git add backend/app/api/chapters.py
git commit -m "fix(api): add sequential chapter generation validation"
```

---

### Task 4: 前端章节按序生成校验

**Files:**
- Modify: `frontend/src/components/workbench/creation/WritingPanel.tsx`

- [ ] **Step 1: 新增 canGenerateChapter 函数**

在 `WritingPanel` 函数体内（store 读取之后），新增：

```typescript
  // 判断章节是否可生成（前一章已生成 或 为第1章）
  const canGenerateChapter = (chapter: ChapterOutline): boolean =>
  {
    if (!chapter.confirmed) return false
    if (chapter.chapter_number === 1) return true
    const prevChapter = chapters.find(c => c.chapter_number === chapter.chapter_number - 1)
    return prevChapter?.has_content === true
  }
```

- [ ] **Step 2: 修改 handleGenerate 增加前序校验**

在 `handleGenerate` 函数中，将现有的 `confirmed` 校验：

```typescript
    if (!selectedChapter.confirmed)
    {
      toast.error('请先确认章节大纲')
      return
    }
```

替换为：

```typescript
    if (!selectedChapter.confirmed)
    {
      toast.error('请先确认章节大纲')
      return
    }

    if (!canGenerateChapter(selectedChapter))
    {
      toast.error('请先生成前一章的正文')
      return
    }
```

- [ ] **Step 3: 修改章节列表中不可生成章节的显示**

在章节列表渲染区域（约第408-429行），修改按钮的 className 和禁用逻辑。

将按钮的 `onClick` 处理中，对不可生成的章节添加禁用样式和 tooltip：

```tsx
              {chapters.map((chapter) =>
              {
                const icon = getChapterIcon(chapter, generatingChapterId)
                const isActive = selectedChapter?.id === chapter.id
                const canGenerate = canGenerateChapter(chapter)

                return (
                  <button
                    key={chapter.id}
                    onClick={() => setSelectedChapter(chapter)}
                    className={`w-full px-2.5 py-2 text-left text-xs border-b hover:bg-muted/50 transition-colors ${
                      isActive ? 'bg-primary/10 border-l-2 border-l-primary' : ''
                    } ${!canGenerate && chapter.confirmed ? 'opacity-50' : ''}`}
                    title={!canGenerate && chapter.confirmed ? '请先生成前一章正文' : undefined}
                  >
```

- [ ] **Step 4: 修改 AI 生成按钮的禁用逻辑**

在"AI 生成"按钮处（约第484行），将：

```tsx
                      <Button size="sm" variant="outline" onClick={handleGenerate} title="Ctrl+Enter">
```

替换为：

```tsx
                      <Button size="sm" variant="outline" onClick={handleGenerate} disabled={!canGenerateChapter(selectedChapter)} title="Ctrl+Enter">
```

- [ ] **Step 5: 验证 TypeScript 编译通过**

Run: `cd /opt/project/novelagent/frontend && npx tsc --noEmit 2>&1 | head -20`
Expected: 无类型错误

- [ ] **Step 6: Commit**

```bash
git add frontend/src/components/workbench/creation/WritingPanel.tsx
git commit -m "fix(writing): add sequential chapter generation validation in frontend"
```

---

### Task 5: 审核反馈类型定义更新

**Files:**
- Modify: `frontend/src/types/index.ts:206-210`

- [ ] **Step 1: 新增 ReviewIssue 类型并更新 ReviewResponse**

将：

```typescript
export interface ReviewResponse {
  passed: boolean;
  feedback: string;
  issues: string[];
}
```

替换为：

```typescript
// 审核问题条目（兼容后端两种格式：JSON 返回结构化对象，旧格式返回字符串）
export interface ReviewIssue {
  type?: string;
  location?: string;
  description: string;
}

export interface ReviewResponse {
  passed: boolean;
  feedback: string;
  issues: ReviewIssue[];
  scores?: Record<string, number>;
}
```

- [ ] **Step 2: 验证 TypeScript 编译通过**

Run: `cd /opt/project/novelagent/frontend && npx tsc --noEmit 2>&1 | head -20`
Expected: 会出现 AIAssistantPanel.tsx 的类型错误（issues 从 string[] 变为 ReviewIssue[]），这是预期的，Task 6 会修复

- [ ] **Step 3: Commit**

```bash
git add frontend/src/types/index.ts
git commit -m "feat(types): add ReviewIssue type and update ReviewResponse with scores"
```

---

### Task 6: 审核反馈渲染修复

**Files:**
- Modify: `frontend/src/components/workbench/creation/AIAssistantPanel.tsx:142-161`

- [ ] **Step 1: 新增审核评分标签映射常量**

在文件顶部 import 之后、`AIAssistantPanelProps` interface 之前，新增：

```typescript
// 审核评分维度中文标签
const SCORE_LABELS: Record<string, string> = {
  plot_consistency: '情节一致性',
  character_consistency: '人物一致性',
  writing_quality: '文笔质量',
  emotional_tension: '情感张力',
  ai_flavor: 'AI味程度',
  outline_deviation: '大纲偏离度',
}
```

- [ ] **Step 2: 修改反馈意见区域显示**

将反馈区域（约第142-148行）：

```tsx
            {/* 反馈 */}
            <div className="p-3 bg-muted rounded-md">
              <span className="text-xs font-medium">反馈意见</span>
              <p className="text-xs text-muted-foreground mt-1 leading-relaxed whitespace-pre-wrap">
                {reviewResult.feedback}
              </p>
            </div>
```

替换为：

```tsx
            {/* 反馈意见 */}
            {reviewResult.feedback && (
              <div className="p-3 bg-muted rounded-md">
                <span className="text-xs font-medium">修改建议</span>
                <p className="text-xs text-muted-foreground mt-1 leading-relaxed whitespace-pre-wrap">
                  {reviewResult.feedback}
                </p>
              </div>
            )}

            {/* 评分详情 */}
            {reviewResult.scores && Object.keys(reviewResult.scores).length > 0 && (
              <div className="p-3 bg-blue-50 border border-blue-200 rounded-md">
                <span className="text-xs font-medium text-blue-800">评分详情</span>
                <div className="mt-1.5 space-y-1">
                  {Object.entries(reviewResult.scores).map(([key, value]) => (
                    <div key={key} className="flex items-center justify-between text-xs">
                      <span className="text-blue-700">{SCORE_LABELS[key] || key}</span>
                      <span className={`font-medium ${
                        (key === 'ai_flavor' || key === 'outline_deviation')
                          ? (value <= 3 ? 'text-green-600' : value <= 5 ? 'text-yellow-600' : 'text-red-600')
                          : (value >= 7 ? 'text-green-600' : value >= 5 ? 'text-yellow-600' : 'text-red-600')
                      }`}>
                        {value}/10
                      </span>
                    </div>
                  ))}
                </div>
              </div>
            )}
```

- [ ] **Step 3: 修改问题列表渲染为结构化显示**

将问题列表区域（约第150-161行）：

```tsx
            {/* 问题列表 */}
            {reviewResult.issues.length > 0 && (
              <div className="space-y-1.5">
                <span className="text-xs font-medium">发现问题 ({reviewResult.issues.length})</span>
                {reviewResult.issues.map((issue, index) => (
                  <div key={index} className="p-2 bg-yellow-50 border border-yellow-200 rounded text-xs flex items-start gap-1.5">
                    <AlertCircle className="h-3 w-3 text-yellow-600 mt-0.5 flex-shrink-0" />
                    <span className="leading-relaxed">{issue}</span>
                  </div>
                ))}
              </div>
            )}
```

替换为：

```tsx
            {/* 问题列表 */}
            {reviewResult.issues.length > 0 && (
              <div className="space-y-1.5">
                <span className="text-xs font-medium">发现问题 ({reviewResult.issues.length})</span>
                {reviewResult.issues.map((issue, index) =>
                {
                  // 兼容：后端旧格式 issues 是 string，新格式是 ReviewIssue 对象
                  const description = typeof issue === 'string' ? issue : issue.description
                  const type = typeof issue === 'string' ? '' : issue.type
                  const location = typeof issue === 'string' ? '' : issue.location
                  return (
                    <div key={index} className="p-2 bg-yellow-50 border border-yellow-200 rounded text-xs flex items-start gap-1.5">
                      <AlertCircle className="h-3 w-3 text-yellow-600 mt-0.5 flex-shrink-0" />
                      <span className="leading-relaxed">
                        {type ? <span className="font-medium text-yellow-800">[{type}]</span> : ''}{type ? ' ' : ''}{location ? `${location}：` : ''}{description}
                      </span>
                    </div>
                  )
                })}
              </div>
            )}
```

- [ ] **Step 4: 验证 TypeScript 编译通过**

Run: `cd /opt/project/novelagent/frontend && npx tsc --noEmit 2>&1 | head -20`
Expected: 无类型错误

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/workbench/creation/AIAssistantPanel.tsx
git commit -m "fix(review): render structured issues and scores, fix [object Object] display"
```

---

### Task 7: 后端审核反馈字段修正

**Files:**
- Modify: `backend/app/api/chapters.py:850-856`

- [ ] **Step 1: 修改 review done 事件的 feedback 和新增 scores 字段**

将：

```python
            # 发送完成事件
            result_data = {
                "passed": ch.review_passed if ch else False,
                "feedback": ch.review_feedback if ch else "",
                "issues": review_result.get("issues", []),
            }
```

替换为：

```python
            # 发送完成事件
            result_data = {
                "passed": ch.review_passed if ch else False,
                "feedback": review_result.get("suggestions", ""),
                "issues": review_result.get("issues", []),
                "scores": review_result.get("scores", {}),
            }
```

注：`review_feedback` 字段继续存储 `raw_response`（第846行不动），仅 `done` 事件的 `feedback` 返回值从 `ch.review_feedback`（原始输出）改为 `review_result.get("suggestions", "")`（修改建议）。

- [ ] **Step 2: 重启后端验证编译无误**

Run: `docker compose restart backend && sleep 3 && docker compose logs backend --tail 5`
Expected: 无启动错误

- [ ] **Step 3: Commit**

```bash
git add backend/app/api/chapters.py
git commit -m "fix(api): return suggestions as review feedback instead of raw response, add scores"
```

---

### Task 8: 集成验证

- [ ] **Step 1: 重建前端并验证编译**

Run: `docker compose build --no-cache frontend && docker compose up -d frontend`
Expected: 构建成功

- [ ] **Step 2: 验证后端 API**

Run: `curl -s "http://localhost:8000/api/system/prompts/" | jq '.prompts | length'`
Expected: 7（API 正常）

- [ ] **Step 3: 手动验证三个修复**

1. 在浏览器打开 `http://localhost:3001`，进入项目工作台
2. 章节正文生成时切换标签再切回 → 生成状态应保留（已完成的可通过 API 恢复内容）
3. 尝试跳章生成 → 应被阻止（按钮禁用 + toast 提示）
4. 对章节执行审核 → 未通过时反馈意见和问题列表应正常显示，评分详情可见

- [ ] **Step 4: Final commit (if any fixes needed)**

```bash
git add -A
git commit -m "fix: writing panel state persistence, sequential validation, and review feedback display"
```
