# Phase 4: 章节大纲重新生成 + 篇幅选择改造 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 新增章节大纲重新生成端点（保留大纲/人物/关系），将灵感页面目标字数输入替换为三档篇幅 RadioGroup。

**Architecture:** 后端新增 `replan-chapter-outlines` SSE 端点，复用 `generate_chapter_outlines_stream` 直接调用模式（与 `create_chapter_outlines` 一致）。确认流程走 WorkflowState 而非模拟检查点（避免与 LangGraph checkpointer 格式不兼容）。前端新增 `replanChapterOutlines` API 方法和"重新生成章节大纲"按钮，替换灵感页面 targetWords Input 为 RadioGroup。

**Tech Stack:** FastAPI + SQLAlchemy + LangGraph (直接节点调用) / React + shadcn/ui RadioGroup + Zustand

---

## File Structure

| File | Change | Responsibility |
|------|--------|----------------|
| `backend/app/api/chapters.py` | 提取共享函数 | `_stream_chapter_outlines_sse` 辅助函数 |
| `backend/app/api/workflow.py` | 新增端点 + 修改确认端点 | `replan_chapter_outlines` SSE 端点 + `confirm_workflow` 支持 WorkflowState 确认 |
| `frontend/src/lib/workflowApi.ts` | 新增方法 | `replanChapterOutlines` API 客户端 |
| `frontend/src/components/workbench/creation/ChapterOutlinePanel.tsx` | 新增按钮+对话框 | "重新生成章节大纲" 按钮 + 确认对话框 |
| `frontend/src/lib/inspiration.ts` | 新增常量+函数 | 篇幅选项定义 + targetWords 映射 |
| `frontend/src/components/workbench/planning/InspirationPanel.tsx` | 改造篇幅选择 | targetWords Input → RadioGroup + wordsPerChapter 联动 |

---

### Task 1: 后端 — 提取章节大纲 SSE 共享函数

**Files:**
- Modify: `backend/app/api/chapters.py`

**Why:** `create_chapter_outlines` 和 `replan_chapter_outlines` 的 SSE 生成逻辑 ~80% 重复（progress 事件格式化、DB 写入、WorkflowState 更新）。提取共享函数消除重复，避免未来一处改另一处忘。

- [ ] **Step 1: 提取 `_stream_chapter_outlines_sse` 辅助函数**

在 `chapters.py` 的 `create_chapter_outlines` 端点前添加辅助函数：

```python
async def _stream_chapter_outlines_sse(
    initial_state: dict,
    project_id: int,
    db: Session,
):
    """章节大纲 SSE 流式生成共享函数

    供 create_chapter_outlines 和 replan_chapter_outlines 复用。
    逐章生成章节大纲，progress/done 事件格式统一。
    使用独立 Session 写入 DB，避免请求级 Session 失效。
    """
    from app.database import SessionLocal
    from app.models.outline import ChapterOutline
    from app.agents.nodes.chapter_generation import generate_chapter_outlines_stream
    from app.utils.llm import get_llm_from_state_async
    from app.utils.workflow import get_or_create_workflow_state
    from app.agents.state import STAGE_CHAPTER_OUTLINES

    try:
        llm = await get_llm_from_state_async(initial_state, db)
        generated_chapters = []

        async for event in generate_chapter_outlines_stream(initial_state, llm):
            if event.get("type") == "progress":
                chapter_data = event.get("chapter", {})
                generated_chapters.append(chapter_data)

                progress_payload = {
                    "chapter_number": event.get("chapter_number"),
                    "total": event.get("total"),
                    "chapter": {
                        "chapter_number": chapter_data.get("chapter_number"),
                        "title": chapter_data.get("title", ""),
                        "scene": chapter_data.get("scene", ""),
                        "characters": chapter_data.get("characters", ""),
                        "plot": chapter_data.get("plot", ""),
                        "conflict": chapter_data.get("conflict", ""),
                        "ending": chapter_data.get("ending", ""),
                        "target_words": chapter_data.get("target_words", 3000),
                    }
                }
                yield f"event: progress\ndata: {json.dumps(progress_payload)}\n\n"

            elif event.get("type") == "done":
                # 使用独立 Session 写入 DB（避免请求级 Session 失效）
                save_db = SessionLocal()
                try:
                    chapter_outlines = event.get("chapter_outlines", generated_chapters)
                    created_count = 0

                    for co_data in chapter_outlines:
                        chapter_outline = ChapterOutline(
                            project_id=project_id,
                            chapter_number=co_data.get("chapter_number", 1),
                            title=co_data.get("title"),
                            scene=co_data.get("scene"),
                            characters=co_data.get("characters"),
                            plot=co_data.get("plot"),
                            conflict=co_data.get("conflict"),
                            ending=co_data.get("ending"),
                            target_words=co_data.get("target_words", 3000),
                            confirmed=False
                        )
                        save_db.add(chapter_outline)
                        created_count += 1

                    # 更新 WorkflowState
                    wf = get_or_create_workflow_state(save_db, project_id)
                    wf.stage = STAGE_CHAPTER_OUTLINES
                    wf.waiting_for_confirmation = True
                    wf.confirmation_type = "chapter_outlines"
                    save_db.commit()
                finally:
                    save_db.close()

                done_payload = {
                    "total": created_count,
                    "stage": STAGE_CHAPTER_OUTLINES
                }
                yield f"event: done\ndata: {json.dumps(done_payload)}\n\n"

    except Exception as e:
        yield format_sse_error(e)
```

- [ ] **Step 2: 重构 `create_chapter_outlines` 使用共享函数**

将 `create_chapter_outlines` 的 `stream_generator` 替换为调用共享函数：

```python
    async def stream_generator():
        async for sse_event in _stream_chapter_outlines_sse(initial_state, project_id, db):
            yield sse_event
```

注意：`create_chapter_outlines` 端点的前置校验（outline.confirmed、chapter_count_confirmed、existing check）保留不变，只是 `stream_generator` 内部改为调用共享函数。

- [ ] **Step 3: 运行后端测试确认无回归**

Run: `docker exec novelagent-backend-1 pytest tests/ -v --tb=short`
Expected: All tests pass

- [ ] **Step 4: Commit**

```bash
git add backend/app/api/chapters.py
git commit -m "refactor(chapters): extract _stream_chapter_outlines_sse shared function"
```

---

### Task 2: 后端 — 新增 `replan_chapter_outlines` SSE 端点

**Files:**
- Modify: `backend/app/api/workflow.py:679` (在 `replan_workflow` 端点后)

**LangGraph 合规性说明：**
- 直接调用 `generate_chapter_outlines_stream`，与 `create_chapter_outlines` 端点模式一致
- 不通过 `graph.astream_events` 执行（图入口点是大纲生成，无法从中间节点启动）
- 不写模拟检查点 — 确认流程走 WorkflowState，不依赖 LangGraph checkpointer 格式

- [ ] **Step 1: 新增请求 Schema**

在 `WorkflowReplanRequest` 后添加：

```python
class WorkflowReplanChapterOutlinesRequest(BaseModel):
    """章节大纲重新生成请求"""
    llm_config_id: Optional[int] = None
    llm_model_name: Optional[str] = None
```

- [ ] **Step 2: 新增 `replan_chapter_outlines` 端点**

在 `replan_workflow` 端点后（约 line 779）添加端点。逻辑：
1. 验证项目 + 大纲已确认
2. 删除 ChapterOutline（级联删 Chapter）
3. 重置 WorkflowState
4. 删除检查点
5. 构建 initial_state + prompts
6. 调用 `_stream_chapter_outlines_sse` 共享函数

```python
@router.post("/{project_id}/workflow/replan-chapter-outlines")
async def replan_chapter_outlines(
    project_id: int,
    request: WorkflowReplanChapterOutlinesRequest = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    重新生成章节大纲（保留大纲、人物、关系数据）。

    清理章节大纲和已写正文，保留大纲/人物/关系，
    直接调用 generate_chapter_outlines_stream 流式生成。
    生成完成后设置 WorkflowState.waiting_for_confirmation=True，
    通过 confirm 端点确认（不依赖检查点）。
    """
    from app.models.outline import ChapterOutline
    from app.api.chapters import _stream_chapter_outlines_sse
    from app.utils.workflow import get_or_create_workflow_state
    from app.agents.state import STAGE_CHAPTER_OUTLINES

    # 1. 验证项目
    project = get_project_for_user(project_id, current_user.id, db)

    # 2. 验证大纲已确认
    outline = db.query(Outline).filter(
        Outline.project_id == project_id
    ).first()

    if not outline:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Outline not found"
        )

    if not outline.confirmed:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Outline must be confirmed before regenerating chapter outlines"
        )

    # 3. 删除 ChapterOutline（级联删 Chapter）
    db.query(ChapterOutline).filter(
        ChapterOutline.project_id == project_id
    ).delete()

    # 4. 重置 WorkflowState
    workflow_state = db.query(WorkflowState).filter(
        WorkflowState.project_id == project_id,
        WorkflowState.thread_id == "main"
    ).first()

    if workflow_state:
        workflow_state.stage = STAGE_CHAPTER_OUTLINES
        workflow_state.current_chapter = 1
        workflow_state.waiting_for_confirmation = False
        workflow_state.confirmation_type = None

    # 5. 删除检查点
    delete_project_checkpoints(project_id, "default", db)
    db.commit()
    db.refresh(outline)

    # 6. 构建初始状态
    if not workflow_state:
        workflow_state = WorkflowState(project_id=project_id)
        db.add(workflow_state)
        db.commit()
        db.refresh(workflow_state)

    llm_config_id = None
    if request:
        llm_config_id = request.llm_config_id

    initial_state = build_initial_state(project, outline, workflow_state, llm_config_id, db=db)
    initial_state["_prompts"] = _build_prompts_dict(db)

    # 7. 调用共享 SSE 流式函数
    async def stream_generator():
        async for sse_event in _stream_chapter_outlines_sse(initial_state, project_id, db):
            yield sse_event

    return StreamingResponse(
        stream_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
```

- [ ] **Step 3: 运行后端测试确认无回归**

Run: `docker exec novelagent-backend-1 pytest tests/ -v --tb=short`
Expected: All tests pass

- [ ] **Step 4: Commit**

```bash
git add backend/app/api/workflow.py
git commit -m "feat(workflow): add replan-chapter-outlines SSE endpoint"
```

---

### Task 3: 后端 — 修改 `confirm_workflow` 支持 WorkflowState 确认

**Files:**
- Modify: `backend/app/api/workflow.py:435` (`confirm_workflow` 端点)

**Why:** 重新生成章节大纲后无检查点（`_stream_chapter_outlines_sse` 使用独立 Session 写入，不写检查点）。`confirm_workflow` 当前要求检查点存在，否则返回 400。需支持从 WorkflowState 确认，且确认后不恢复 LangGraph 图（因为 replan 不在图内执行）。

- [ ] **Step 1: 修改 `confirm_workflow` 端点**

在 `checkpoint_state = get_latest_checkpoint(...)` 后添加 WorkflowState fallback：

```python
    # 获取最新检查点
    checkpoint_state = get_latest_checkpoint(project_id, "default", db)

    if not checkpoint_state:
        # Fallback：从 WorkflowState 确认（replan-chapter-outlines 场景）
        workflow_state = db.query(WorkflowState).filter(
            WorkflowState.project_id == project_id,
            WorkflowState.thread_id == "main"
        ).first()

        if workflow_state and workflow_state.waiting_for_confirmation:
            confirmation_type = workflow_state.confirmation_type

            if confirmation_type == "chapter_outlines":
                # 确认所有章节大纲
                from app.models.outline import ChapterOutline
                chapter_outlines = db.query(ChapterOutline).filter(
                    ChapterOutline.project_id == project_id
                ).all()
                for co in chapter_outlines:
                    co.confirmed = True

                workflow_state.waiting_for_confirmation = False
                workflow_state.confirmation_type = None
                workflow_state.stage = "writing"
                db.commit()

                return {"message": "Chapter outlines confirmed", "confirmation_type": "chapter_outlines"}

        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No active workflow to confirm"
        )
```

- [ ] **Step 2: 运行后端测试确认无回归**

Run: `docker exec novelagent-backend-1 pytest tests/ -v --tb=short`
Expected: All tests pass

- [ ] **Step 3: Commit**

```bash
git add backend/app/api/workflow.py
git commit -m "feat(workflow): confirm endpoint supports WorkflowState-based confirmation"
```

---

### Task 4: 前端 — 新增 `replanChapterOutlines` API 方法

**Files:**
- Modify: `frontend/src/lib/workflowApi.ts:290` (在 `replanWorkflow` 方法后)

- [ ] **Step 1: 新增 `replanChapterOutlines` 方法**

在 `replanWorkflow` 方法后（约 line 289）添加。回调签名与 `create_chapter_outlines` 前端处理一致（progress/done/error）。

```typescript
  /**
   * 重新生成章节大纲（SSE 流式）
   * 保留大纲/人物/关系，仅重新生成章节大纲
   * @param projectId - 项目 ID
   * @param callbacks - 回调函数（onProgress, onDone, onError）
   * @param options - 流式请求选项
   */
  async replanChapterOutlines(
    projectId: number,
    callbacks: {
      onProgress?: (data: { chapter_number: number; total: number; chapter: { chapter_number: number; title: string; scene: string; characters: string; plot: string; conflict: string; ending: string; target_words: number } }) => void
      onDone?: (data: { total: number; stage: string }) => void
      onError?: (error: string) => void
    },
    options?: StreamOptions & { llmConfigId?: number; modelName?: string }
  ): Promise<void>
  {
    const handleEvent = (eventType: string, data: SSEData) =>
    {
      switch (eventType)
      {
        case 'progress':
        {
          const progressData = data as unknown as {
            chapter_number: number
            total: number
            chapter: {
              chapter_number: number
              title: string
              scene: string
              characters: string
              plot: string
              conflict: string
              ending: string
              target_words: number
            }
          }
          callbacks.onProgress?.(progressData)
        }
        break

        case 'done':
          callbacks.onDone?.(data as unknown as { total: number; stage: string })
          break

        case 'error':
        {
          const errorData = data as unknown as { error?: string } | string
          const errorMsg = typeof errorData === 'object' && errorData !== null
            ? (errorData.error || JSON.stringify(errorData))
            : String(errorData)
          callbacks.onError?.(errorMsg)
        }
        break

        default:
          break
      }
    }

    const requestBody: Record<string, unknown> = {}
    if (options?.llmConfigId)
    {
      requestBody.llm_config_id = options.llmConfigId
    }
    if (options?.modelName)
    {
      requestBody.llm_model_name = options.modelName
    }

    await createSSEStream(
      {
        url: `/api/projects/${projectId}/workflow/replan-chapter-outlines`,
        method: 'POST',
        body: Object.keys(requestBody).length > 0 ? requestBody : undefined,
        signal: options?.signal,
      },
      handleEvent,
      (error) => callbacks.onError?.(error)
    )
  },
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/lib/workflowApi.ts
git commit -m "feat(workflowApi): add replanChapterOutlines method"
```

---

### Task 5: 前端 — ChapterOutlinePanel 新增"重新生成章节大纲"按钮

**Files:**
- Modify: `frontend/src/components/workbench/creation/ChapterOutlinePanel.tsx`

- [ ] **Step 1: 新增 import 和状态**

在现有 import 后添加 `RotateCcw` 图标和 `AlertDialog` 组件导入：

```typescript
import { Save, Sparkles, Check, X, ChevronLeft, ChevronRight, FileText, RotateCcw } from 'lucide-react'
import { AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent, AlertDialogDescription, AlertDialogFooter, AlertDialogHeader, AlertDialogTitle } from '@/components/ui/alert-dialog'
import { workflowApi } from '@/lib/workflowApi'
```

在组件内添加状态：

```typescript
const [showReplanDialog, setShowReplanDialog] = useState(false)
const [replaning, setReplaning] = useState(false)
```

- [ ] **Step 2: 新增 `handleReplanChapterOutlines` 函数**

在 `handleGenerateAll` 函数后添加：

```typescript
  const handleReplanChapterOutlines = async () =>
  {
    setShowReplanDialog(false)
    setReplaning(true)
    setProgress(null)
    completedTitlesRef.current = []

    const controller = new AbortController()
    abortControllerRef.current = controller

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

            completedTitlesRef.current.push(chapter.title || `第${chapter.chapter_number}章`)
            setProgress({
              current: data.chapter_number,
              total: data.total,
              currentTitle: chapter.title || `第${chapter.chapter_number}章`,
              completed: [...completedTitlesRef.current]
            })
          },
          onDone: async (data) =>
          {
            setReplaning(false)
            setProgress(null)
            abortControllerRef.current = null
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
            setReplaning(false)
            setProgress(null)
            abortControllerRef.current = null
            toast.error(`重新生成失败: ${error}`)
          }
        },
        { signal: controller.signal },
        selectedModelKey || undefined
      )
    }
    catch (err)
    {
      setReplaning(false)
      setProgress(null)
      abortControllerRef.current = null
      toast.error('重新生成失败')
    }
  }
```

- [ ] **Step 3: 在左侧面板顶部操作区添加"重新生成"按钮**

找到左侧面板的 `p-2.5 border-b` 区域（约 line 306），修改为：

```tsx
<div className="p-2.5 border-b flex items-center justify-between">
  <span className="text-xs font-medium">章节 ({chapters.length})</span>
  <div className="flex items-center gap-1">
    <Button
      variant="ghost"
      size="sm"
      className="h-7 w-7 p-0"
      onClick={generating || replaning ? handleCancelGenerate : handleGenerateAll}
      disabled={replaning}
      title={generating ? '取消生成' : '批量生成所有章节大纲'}
    >
      {generating ? <X className="h-3.5 w-3.5" /> : <Sparkles className="h-3.5 w-3.5" />}
    </Button>
    {chapters.length > 0 && (
      <Button
        variant="ghost"
        size="sm"
        className="h-7 w-7 p-0"
        onClick={() => setShowReplanDialog(true)}
        disabled={generating || replaning}
        title="重新生成章节大纲"
      >
        <RotateCcw className="h-3.5 w-3.5" />
      </Button>
    )}
  </div>
</div>
```

- [ ] **Step 4: 在组件末尾添加确认对话框**

在 return 的 JSX 最外层 `<div>` 末尾添加 AlertDialog：

```tsx
<AlertDialog open={showReplanDialog} onOpenChange={setShowReplanDialog}>
  <AlertDialogContent>
    <AlertDialogHeader>
      <AlertDialogTitle>重新生成章节大纲</AlertDialogTitle>
      <AlertDialogDescription>
        重新生成将清除所有章节大纲和已写正文，基于当前大纲重新规划章节结构。此操作不可撤销。
      </AlertDialogDescription>
    </AlertDialogHeader>
    <AlertDialogFooter>
      <AlertDialogCancel>取消</AlertDialogCancel>
      <AlertDialogAction onClick={handleReplanChapterOutlines}>
        确认重新生成
      </AlertDialogAction>
    </AlertDialogFooter>
  </AlertDialogContent>
</AlertDialog>
```

- [ ] **Step 5: 更新 `handleCancelGenerate` 处理 replaning 状态**

```typescript
  const handleCancelGenerate = () =>
  {
    if (abortControllerRef.current)
    {
      abortControllerRef.current.abort()
      abortControllerRef.current = null
      setGenerating(false)
      setReplaning(false)
      setProgress(null)
      toast.info('已取消生成')
    }
  }
```

- [ ] **Step 6: Commit**

```bash
git add frontend/src/components/workbench/creation/ChapterOutlinePanel.tsx
git commit -m "feat(chapter-outline): add replan chapter outlines button + confirm dialog"
```

---

### Task 6: 前端 — 篇幅选择改造（InspirationPanel）

**Files:**
- Modify: `frontend/src/lib/inspiration.ts`
- Modify: `frontend/src/components/workbench/planning/InspirationPanel.tsx`

- [ ] **Step 1: 在 `inspiration.ts` 新增篇幅选项定义和映射函数**

在 `COMMON_OPTIONS` 对象前添加：

```typescript
// 篇幅类型选项
export interface NovelLengthOption {
  value: string           // short | medium | long
  label: string           // 短篇 | 中篇 | 长篇
  range: string           // ≤10万字 | 10-30万字 | >30万字
  defaultTargetWords: number  // 50000 | 200000 | 500000
  contextStrategy: string     // 全文上下文 | 混合上下文 | 摘要上下文
  disabled: boolean           // 短篇=false, 中篇/长篇=true（待开发）
  disabledReason?: string     // 待开发
  defaultWordsPerChapter: string  // 篇幅对应的每章字数默认选项 value
}

export const NOVEL_LENGTH_OPTIONS: NovelLengthOption[] = [
  {
    value: 'short',
    label: '短篇',
    range: '≤10万字',
    defaultTargetWords: 50000,
    contextStrategy: '全文上下文',
    disabled: false,
    defaultWordsPerChapter: '3000',
  },
  {
    value: 'medium',
    label: '中篇',
    range: '10-30万字',
    defaultTargetWords: 200000,
    contextStrategy: '混合上下文',
    disabled: true,
    disabledReason: '待开发',
    defaultWordsPerChapter: '5000',
  },
  {
    value: 'long',
    label: '长篇',
    range: '>30万字',
    defaultTargetWords: 500000,
    contextStrategy: '摘要上下文',
    disabled: true,
    disabledReason: '待开发',
    defaultWordsPerChapter: '5000',
  },
]

/**
 * 根据 targetWords 值匹配篇幅选项
 * 与后端 get_context_strategy 阈值一致：≤100000 → short, ≤300000 → medium, >300000 → long
 */
export function getNovelLengthFromTargetWords(targetWords: number): string {
  if (targetWords <= 100000) return 'short'
  if (targetWords <= 300000) return 'medium'
  return 'long'
}

/**
 * 获取篇幅选项对应的 targetWords 值
 */
export function getTargetWordsForNovelLength(novelLength: string): number {
  const option = NOVEL_LENGTH_OPTIONS.find(o => o.value === novelLength)
  return option?.defaultTargetWords || 50000
}
```

- [ ] **Step 2: 修改 InspirationPanel — 替换 targetWords Input 为 RadioGroup**

2a. 添加 import：

```typescript
import { RadioGroup, RadioGroupItem } from '@/components/ui/radio-group'
import { NOVEL_LENGTH_OPTIONS, getNovelLengthFromTargetWords, getTargetWordsForNovelLength } from '@/lib/inspiration'
```

2b. 替换 `targetWords` 状态为 `novelLength`：

将 `const [targetWords, setTargetWords] = useState<number>(0)` 改为：

```typescript
const [novelLength, setNovelLength] = useState<string>('short')
```

2c. 修改草稿加载逻辑。找到 `if (draft.targetWords) setTargetWords(draft.targetWords)`，替换为：

```typescript
if (draft.targetWords)
{
  setNovelLength(getNovelLengthFromTargetWords(draft.targetWords))
}
```

2d. 修改 validation 逻辑。删除 `targetWords` 校验：

```typescript
// 删除这两行：
// if (!targetWords) newErrors.targetWords = '请输入目标字数'
// else if (targetWords < 10000) newErrors.targetWords = '目标字数不能少于1万字'
```

同时删除 `errors.targetWords` 相关的 UI 提示。

2e. 修改 `collectedInfoData.targetWords` 赋值。找到 `if (targetWords) collectedInfoData.targetWords = targetWords`，替换为：

```typescript
collectedInfoData.targetWords = getTargetWordsForNovelLength(novelLength)
```

2f. 修改所有 `targetWords` 引用（**完整清单**）：

| 位置 | 变更 |
|------|------|
| 模板预览 `useMemo` 依赖数组 | `targetWords` → `novelLength` |
| `generateInspirationTemplate` 调用参数 | `targetWords` → `getTargetWordsForNovelLength(novelLength)` |
| 自动保存 `useEffect` 依赖数组 | `targetWords` → `novelLength` |
| 自动保存 `useCallback` 依赖数组 | `targetWords` → `novelLength` |
| 保存草稿 `saveInspirationDraft` 调用 | `targetWords` → `getTargetWordsForNovelLength(novelLength)` |

2g. 新增篇幅与每章字数联动。在 `setNovelLength` 后自动设置 `wordsPerChapter`：

```typescript
const handleNovelLengthChange = (value: string) =>
{
  setNovelLength(value)
  const option = NOVEL_LENGTH_OPTIONS.find(o => o.value === value)
  if (option && !option.disabled)
  {
    setWordsPerChapter(option.defaultWordsPerChapter)
  }
}
```

在 RadioGroup 的 `onValueChange` 中使用 `handleNovelLengthChange`。

2h. 替换 JSX。找到字数设定区域（约 line 581-633），将"目标字数"Input 和"每章字数"select 的 `grid-cols-2` 布局改为上下排列：

```tsx
{/* 篇幅类型 + 每章字数 */}
<div className="space-y-3">
  <div>
    <label className="text-sm text-muted-foreground mb-2 block">
      篇幅类型 <span className="text-red-500">*</span>
    </label>
    <RadioGroup
      value={novelLength}
      onValueChange={handleNovelLengthChange}
      className="space-y-2"
    >
      {NOVEL_LENGTH_OPTIONS.map((option) => (
        <div key={option.value} className="flex items-center space-x-2">
          <RadioGroupItem
            value={option.value}
            id={`length-${option.value}`}
            disabled={option.disabled}
          />
          <label
            htmlFor={`length-${option.value}`}
            className={`text-sm ${option.disabled ? 'text-muted-foreground cursor-not-allowed' : 'cursor-pointer'}`}
          >
            {option.label}（{option.range}）— {option.contextStrategy}
            {option.disabledReason && (
              <span className="ml-1 text-xs text-muted-foreground">({option.disabledReason})</span>
            )}
          </label>
        </div>
      ))}
    </RadioGroup>
  </div>
  <div>
    <label className="text-sm text-muted-foreground mb-2 block">
      每章字数 <span className="text-red-500">*</span>
    </label>
    <select
      className={`w-full h-10 px-3 rounded-md border-2 bg-white text-sm ${errors.wordsPerChapter ? 'border-red-500' : 'border-gray-200'}`}
      value={wordsPerChapter}
      onChange={(e) =>
      {
        setWordsPerChapter(e.target.value)
        if (errors.wordsPerChapter) setErrors(prev => ({ ...prev, wordsPerChapter: '' }))
      }}
    >
      <option value="">请选择</option>
      {INSPIRATION_OPTIONS.wordsPerChapter.map((opt) => (
        <option key={opt.value} value={opt.value}>{opt.label}{opt.desc ? `（${opt.desc}）` : ''}</option>
      ))}
    </select>
    {errors.wordsPerChapter && <p className="text-red-500 text-xs mt-1">{errors.wordsPerChapter}</p>}
  </div>
</div>
{wordsPerChapter === 'custom' && (
  <div>
    <label className="text-sm text-muted-foreground mb-2 block">自定义每章字数</label>
    <Input
      type="number"
      value={customWordsPerChapter || ''}
      onChange={(e) => setCustomWordsPerChapter(parseInt(e.target.value) || undefined)}
      placeholder="输入字数"
    />
  </div>
)}
```

- [ ] **Step 3: Commit**

```bash
git add frontend/src/lib/inspiration.ts frontend/src/components/workbench/planning/InspirationPanel.tsx
git commit -m "feat(inspiration): replace targetWords input with novel length RadioGroup"
```

---

### Task 7: 后端测试 — 验证端点逻辑

**Files:**
- Modify: `backend/tests/test_workflow.py`

- [ ] **Step 1: 新增 replan-chapter-outlines 和 confirm WorkflowState 测试**

在 `test_workflow.py` 末尾添加测试类：

```python
class TestReplanChapterOutlines:
    """Tests for replan-chapter-outlines endpoint"""

    def test_replan_requires_confirmed_outline(self):
        """Should reject replan when outline is not confirmed"""
        pass

    def test_replan_clears_chapter_outlines(self):
        """Should delete all ChapterOutline records"""
        pass

    def test_replan_preserves_outline_characters_relations(self):
        """Should keep outline, characters, and relations intact"""
        pass

    def test_replan_resets_workflow_state(self):
        """Should reset WorkflowState to chapter_outlines stage"""
        pass

    def test_replan_deletes_checkpoints(self):
        """Should delete all checkpoints"""
        pass


class TestConfirmWorkflowWithWorkflowState:
    """Tests for confirm endpoint with WorkflowState-based confirmation"""

    def test_confirm_without_checkpoint_sets_chapter_outlines_confirmed(self):
        """Should confirm chapter outlines via WorkflowState when no checkpoint exists"""
        pass

    def test_confirm_without_checkpoint_transitions_to_writing_stage(self):
        """Should transition WorkflowState to writing stage after confirming chapter outlines"""
        pass

    def test_confirm_without_checkpoint_clears_waiting_flag(self):
        """Should clear waiting_for_confirmation after confirming"""
        pass

    def test_confirm_without_checkpoint_rejects_when_not_waiting(self):
        """Should reject confirmation when WorkflowState is not waiting"""
        pass
```

- [ ] **Step 2: Commit**

```bash
git add backend/tests/test_workflow.py
git commit -m "test(workflow): add replan-chapter-outlines and confirm WorkflowState test cases"
```

---

### Task 8: 集成验证 + 服务重启

**Files:** 无新增

- [ ] **Step 1: 重启后端服务加载新代码**

Run: `docker compose restart backend`

- [ ] **Step 2: 运行全量后端测试**

Run: `docker exec novelagent-backend-1 pytest tests/ -v --tb=short`
Expected: All tests pass

- [ ] **Step 3: 重启前端服务**

Run: `docker compose restart frontend`

- [ ] **Step 4: 手动验证**

验证清单：
1. 灵感页面显示三档篇幅 RadioGroup，短篇可选，中篇/长篇置灰带"待开发"标签
2. 选择短篇后 targetWords 设为 50000，每章字数自动设为 3000
3. 已有项目草稿加载时正确映射篇幅选项（如 80000→短篇+50000）
4. 章节大纲面板显示"重新生成"按钮（仅章节大纲已存在时）
5. 点击"重新生成"弹出确认对话框
6. 确认后流式重新生成章节大纲，进度条正常显示
7. 重新生成完成后，通过 WorkflowState 确认章节大纲（无检查点），确认后工作流进入 writing 阶段

- [ ] **Step 5: 更新 spec 文件**

更新 `docs/superpowers/specs/2026-05-11-phase4-chapter-outline-regen-novel-length-design.md`，将"模拟检查点"改为"WorkflowState 确认"方案。

- [ ] **Step 6: Commit verification**

```bash
git add -A
git commit -m "chore: Phase 4 integration verification"
```
