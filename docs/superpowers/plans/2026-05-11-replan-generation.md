# 重新生成规划 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 支持重新生成规划（大纲+人物+关系），解决规划失败无法重试和对结果不满意无法重新生成的问题。

**Architecture:** 后端新增 `POST /workflow/replan` 端点统一处理数据清理和工作流重启，新增 `POST /workflow/cleanup` 端点修复缺失的清理接口。前端灵感面板添加"重新规划"按钮，复用 OutlineProgressDialog 展示进度。

**Tech Stack:** FastAPI + LangGraph + SQLAlchemy (后端), React + Zustand + SSE (前端)

---

## File Structure

| 文件 | 责任 | 动作 |
|------|------|------|
| `backend/app/api/workflow.py` | 新增 replan、cleanup 端点 | 修改 |
| `backend/tests/test_workflow.py` | replan、cleanup 端点测试 | 修改 |
| `frontend/src/lib/workflowApi.ts` | 新增 replanWorkflow 方法 | 修改 |
| `frontend/src/components/workbench/planning/InspirationPanel.tsx` | 添加"重新规划"按钮 | 修改 |
| `frontend/src/components/workbench/planning/OutlineProgressDialog.tsx` | 新增 isReplan prop | 修改 |
| `frontend/src/pages/ProjectWorkbench.tsx` | 传递 hasOutline prop | 修改 |

---

### Task 1: 后端 — 新增 `POST /workflow/cleanup` 端点

**Files:**
- Modify: `backend/app/api/workflow.py`
- Test: `backend/tests/test_workflow.py`

- [ ] **Step 1: 编写 cleanup 端点测试**

在 `backend/tests/test_workflow.py` 的 `TestWorkflowAPI` 类中添加：

```python
def test_cleanup_workflow(
    self,
    client: TestClient,
    auth_headers: dict,
    project_with_outline: int,
    db: Session,
):
    """Should cleanup workflow checkpoints"""
    # 创建测试检查点
    checkpoint = WorkflowCheckpoint(
        project_id=project_with_outline,
        thread_id="default",
        checkpoint={"channel_values": {"stage": "outline"}},
    )
    db.add(checkpoint)
    db.commit()

    # 清理工作流
    response = client.post(
        f"/api/projects/{project_with_outline}/workflow/cleanup",
        headers=auth_headers,
    )

    assert response.status_code == 200
    data = response.json()
    assert data["deleted"] >= 1

    # 验证检查点已删除
    remaining = (
        db.query(WorkflowCheckpoint)
        .filter(WorkflowCheckpoint.project_id == project_with_outline)
        .count()
    )
    assert remaining == 0
```

- [ ] **Step 2: 运行测试确认失败**

Run: `docker exec novelagent-backend-1 pytest tests/test_workflow.py::TestWorkflowAPI::test_cleanup_workflow -v`
Expected: FAIL (404 或 405，端点不存在)

- [ ] **Step 3: 实现 cleanup 端点**

在 `backend/app/api/workflow.py` 的 `cancel_workflow` 端点后面添加：

```python
class WorkflowCleanupResponse(BaseModel):
    """工作流清理响应"""
    message: str
    deleted: int


@router.post("/{project_id}/workflow/cleanup", response_model=WorkflowCleanupResponse)
async def cleanup_workflow(
    project_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    清理工作流检查点（不删业务数据）。

    用于规划生成失败后的重试清理。
    """
    # 验证项目所有权
    get_project_for_user(project_id, current_user.id, db)

    # 删除检查点
    deleted_count = delete_project_checkpoints(project_id, "default", db)

    return WorkflowCleanupResponse(
        message="Checkpoints cleaned up",
        deleted=deleted_count,
    )
```

- [ ] **Step 4: 运行测试确认通过**

Run: `docker exec novelagent-backend-1 pytest tests/test_workflow.py::TestWorkflowAPI::test_cleanup_workflow -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/api/workflow.py backend/tests/test_workflow.py
git commit -m "feat(workflow): add POST /workflow/cleanup endpoint"
```

---

### Task 2: 后端 — 新增 `POST /workflow/replan` 端点

**Files:**
- Modify: `backend/app/api/workflow.py`
- Test: `backend/tests/test_workflow.py`

- [ ] **Step 1: 编写 replan 端点测试**

在 `backend/tests/test_workflow.py` 的 `TestWorkflowAPI` 类中添加：

```python
def test_replan_workflow_clears_data(
    self,
    client: TestClient,
    auth_headers: dict,
    project_with_outline: int,
    db: Session,
):
    """Should clear checkpoints, characters, relations, chapter outlines on replan"""
    from app.models.outline import Outline, ChapterOutline
    from app.models.character import Character, Relation

    # 创建检查点
    checkpoint = WorkflowCheckpoint(
        project_id=project_with_outline,
        thread_id="default",
        checkpoint={"channel_values": {"stage": "relations"}},
    )
    db.add(checkpoint)

    # 创建大纲（带生成数据）
    outline = db.query(Outline).filter(Outline.project_id == project_with_outline).first()
    if outline:
        outline.title = "测试大纲"
        outline.summary = "测试概述"
        outline.confirmed = True

    # 创建人物
    character = Character(
        project_id=project_with_outline,
        name="测试人物",
        role="主角",
    )
    db.add(character)
    db.flush()

    # 创建关系
    relation = Relation(
        project_id=project_with_outline,
        character_a_id=character.id,
        character_b_id=character.id,
        relation_type="测试",
    )
    db.add(relation)

    # 创建章节大纲
    chapter_outline = ChapterOutline(
        project_id=project_with_outline,
        chapter_number=1,
        title="第一章",
    )
    db.add(chapter_outline)
    db.commit()

    # 调用 replan（SSE 流会因没有真实 LLM 而失败，但我们只验证数据清理）
    response = client.post(
        f"/api/projects/{project_with_outline}/workflow/replan",
        headers=auth_headers,
        json={},
    )

    # replan 返回 SSE 流（200）或因 LLM 报错
    # 无论哪种，数据清理应已完成
    # 验证检查点已删除
    remaining_checkpoints = (
        db.query(WorkflowCheckpoint)
        .filter(WorkflowCheckpoint.project_id == project_with_outline)
        .count()
    )
    assert remaining_checkpoints == 0

    # 验证人物已删除
    remaining_characters = (
        db.query(Character)
        .filter(Character.project_id == project_with_outline)
        .count()
    )
    assert remaining_characters == 0

    # 验证章节大纲已删除
    remaining_outlines = (
        db.query(ChapterOutline)
        .filter(ChapterOutline.project_id == project_with_outline)
        .count()
    )
    assert remaining_outlines == 0

    # 验证大纲生成字段已清除，但 collected_info 保留
    db.refresh(outline)
    assert outline.title is None
    assert outline.summary is None
    assert outline.confirmed is False
    assert outline.collected_info is not None
```

- [ ] **Step 2: 运行测试确认失败**

Run: `docker exec novelagent-backend-1 pytest tests/test_workflow.py::TestWorkflowAPI::test_replan_workflow_clears_data -v`
Expected: FAIL (端点不存在)

- [ ] **Step 3: 实现 replan 端点**

在 `backend/app/api/workflow.py` 中添加：

1. 在 Request/Response Schemas 区域添加：

```python
class WorkflowReplanRequest(BaseModel):
    """重新规划请求"""
    llm_config_id: Optional[int] = None
    llm_model_name: Optional[str] = None
```

2. 在 `cleanup_workflow` 端点后面添加：

```python
@router.post("/{project_id}/workflow/replan")
async def replan_workflow(
    project_id: int,
    request: WorkflowReplanRequest = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    重新生成规划（大纲+人物+关系）。

    清理旧的检查点、大纲生成数据、人物、关系、章节大纲，
    然后重新启动工作流从大纲生成开始。
    """
    # 验证项目所有权
    project = get_project_for_user(project_id, current_user.id, db)

    # 获取大纲
    outline = db.query(Outline).filter(
        Outline.project_id == project_id
    ).first()

    if not outline:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Outline not found"
        )

    # 1. 清理检查点
    delete_project_checkpoints(project_id, "default", db)

    # 2. 重置 WorkflowState
    workflow_state = db.query(WorkflowState).filter(
        WorkflowState.project_id == project_id,
        WorkflowState.thread_id == "main"
    ).first()

    if workflow_state:
        workflow_state.stage = "inspiration"
        workflow_state.waiting_for_confirmation = False
        workflow_state.confirmation_type = None
        workflow_state.current_chapter = 1

    # 3. 重置大纲生成字段（保留 collected_info 和 inspiration_template）
    outline.title = None
    outline.summary = None
    outline.plot_points = []
    outline.characters = []
    outline.world_setting = None
    outline.emotional_curve = None
    outline.confirmed = False
    outline.chapter_count_suggested = 0
    outline.chapter_count_confirmed = False

    # 4. 删除旧的人物和关系
    from app.models.character import Character, Relation
    from app.models.outline import ChapterOutline

    # 先删关系（外键依赖人物），再删人物
    db.query(Relation).filter(Relation.project_id == project_id).delete()
    db.query(Character).filter(Character.project_id == project_id).delete()

    # 5. 删除章节大纲（cascade 会自动删除关联的 Chapter）
    db.query(ChapterOutline).filter(ChapterOutline.project_id == project_id).delete()

    # 提交所有清理
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

    # 预加载 prompts
    from app.services.prompt_loader import get_system_prompt
    initial_state["_prompts"] = {
        "outline_generation": get_system_prompt(db, "outline_generation"),
        "character_generation": get_system_prompt(db, "character_generation"),
        "relation_generation": get_system_prompt(db, "relation_generation"),
    }

    # 7. 创建带检查点的图并启动工作流
    graph = create_novel_graph_with_checkpointer(project_id, "default")
    config = {"configurable": {"thread_id": "default"}}

    def stream_generator():
        return stream_workflow_events(graph, config, initial_state)

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

- [ ] **Step 4: 运行测试确认通过**

Run: `docker exec novelagent-backend-1 pytest tests/test_workflow.py::TestWorkflowAPI::test_replan_workflow_clears_data -v`
Expected: PASS

- [ ] **Step 5: 运行全部 workflow 测试确认无回归**

Run: `docker exec novelagent-backend-1 pytest tests/test_workflow.py -v`
Expected: 全部 PASS

- [ ] **Step 6: Commit**

```bash
git add backend/app/api/workflow.py backend/tests/test_workflow.py
git commit -m "feat(workflow): add POST /workflow/replan endpoint for re-generating plan"
```

---

### Task 3: 前端 — workflowApi 新增 replanWorkflow 方法

**Files:**
- Modify: `frontend/src/lib/workflowApi.ts`

- [ ] **Step 1: 添加 replanWorkflow 方法**

在 `frontend/src/lib/workflowApi.ts` 的 `workflowApi` 对象中，`runWorkflow` 方法后面添加：

```typescript
/**
 * 重新规划工作流（SSE 流式）
 * 清理旧的大纲/人物/关系数据，重新生成规划
 * @param projectId - 项目 ID
 * @param callbacks - 回调函数
 * @param options - 流式请求选项
 */
async replanWorkflow(
  projectId: number,
  callbacks: WorkflowStreamCallbacks,
  options?: StreamOptions & { llmConfigId?: number; modelName?: string }
): Promise<void>
{
  // 事件处理函数（与 runWorkflow 完全一致）
  const handleEvent = (eventType: string, data: SSEData) =>
  {
    switch (eventType)
    {
      case 'node_start':
      {
        const nodeData = data as unknown as { node: string; message?: string }
        callbacks.onNodeStart?.(nodeData.node)
      }
      break

      case 'node_done':
      {
        const nodeData = data as unknown as { node: string; state: unknown }
        callbacks.onNodeDone?.(nodeData.node, nodeData.state)
      }
      break

      case 'chunk':
      {
        const chunkData = data as unknown as { content: string } | string
        const chunkText = typeof chunkData === 'string' ? chunkData : chunkData.content
        if (chunkText)
        {
          callbacks.onChunk?.(chunkText)
        }
      }
      break

      case 'checkpoint':
        callbacks.onCheckpoint?.(data as unknown as WorkflowStateResponse)
        break

      case 'waiting':
      {
        const waitingData = data as unknown as { node: string; confirmation_type: string }
        callbacks.onWaiting?.(waitingData.confirmation_type)
      }
      break

      case 'done':
        callbacks.onDone?.(data as unknown as { stage: string; chapters: WrittenChapter[] })
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
      url: `/api/projects/${projectId}/workflow/replan`,
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
git commit -m "feat(frontend): add replanWorkflow method to workflowApi"
```

---

### Task 4: 前端 — OutlineProgressDialog 支持 isReplan

**Files:**
- Modify: `frontend/src/components/workbench/planning/OutlineProgressDialog.tsx`

- [ ] **Step 1: 添加 isReplan prop 并切换 API 调用**

1. 修改 `OutlineProgressDialogProps` 接口，添加 `isReplan`：

```typescript
interface OutlineProgressDialogProps
{
  open: boolean
  onClose: () => void
  projectId: number
  /** 可选的模型配置 ID */
  modelConfigId?: number
  /** 可选的模型名称 */
  modelName?: string
  /** 是否为重新规划模式 */
  isReplan?: boolean
  onComplete: () => void
  onViewOutline: () => void
}
```

2. 修改组件函数签名：

```typescript
export function OutlineProgressDialog({
  open,
  onClose,
  projectId,
  modelConfigId,
  modelName,
  isReplan = false,
  onComplete,
  onViewOutline,
}: OutlineProgressDialogProps)
```

3. 修改 `handleGenerate` 函数中的 API 调用逻辑。将 `handleGenerate` 中 try 块内的 `workflowApi.runWorkflow` 调用替换为条件调用：

找到这段代码：
```typescript
    try
    {
      await workflowApi.runWorkflow(
```

替换为：
```typescript
    try
    {
      const workflowFn = isReplan ? workflowApi.replanWorkflow.bind(workflowApi) : workflowApi.runWorkflow.bind(workflowApi)
      await workflowFn(
```

4. 修改 `handleGenerate` 中的清理逻辑。当 `isReplan=true` 时跳过 `workflowCleanupApi.cleanup` 调用（replan 端点内部已处理清理）。

找到这段代码：
```typescript
    // 重试前先清除旧的 checkpoint，防止状态污染
    try
    {
      await workflowCleanupApi.cleanup(projectId)
    }
```

替换为：
```typescript
    // 重新规划模式由后端 replan 端点处理清理；非重新规划模式先清除旧 checkpoint
    if (!isReplan)
    {
      try
      {
        await workflowCleanupApi.cleanup(projectId)
      }
      catch (cleanupErr)
      {
        console.warn('Failed to cleanup checkpoints before retry:', cleanupErr)
      }
    }
```

5. 修改弹窗标题，当 `isReplan` 时显示不同文案。

找到 `DialogTitle` 中的内容，修改 `正在规划你的小说` 为条件渲染：

```typescript
              <>
                <Sparkles className="h-5 w-5 text-blue-500" />
                {isReplan ? '正在重新规划' : '正在规划你的小说'}
              </>
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/components/workbench/planning/OutlineProgressDialog.tsx
git commit -m "feat(frontend): OutlineProgressDialog supports isReplan mode"
```

---

### Task 5: 前端 — 灵感面板添加"重新规划"按钮

**Files:**
- Modify: `frontend/src/components/workbench/planning/InspirationPanel.tsx`
- Modify: `frontend/src/pages/ProjectWorkbench.tsx`

- [ ] **Step 1: 在 ProjectWorkbench 中传递 hasOutline prop**

修改 `frontend/src/pages/ProjectWorkbench.tsx`：

1. 从 `useProjectData` 解构 `outline`：
```typescript
const { project, outline, loading } = useProjectData(projectId)
```

2. 修改 `InspirationPanel` 渲染，传入 `hasOutline`：
```typescript
return <InspirationPanel projectId={projectId!} hasOutline={!!outline?.title} />
```

- [ ] **Step 2: 在 InspirationPanel 中添加"重新规划"按钮**

1. 修改 `InspirationPanelProps` 接口：

```typescript
interface InspirationPanelProps
{
  projectId: number
  hasOutline?: boolean
}
```

2. 修改组件函数签名：

```typescript
export function InspirationPanel({ projectId, hasOutline = false }: InspirationPanelProps)
```

3. 添加确认对话框状态和重新规划状态：

在现有 state 声明区域（`const [showProgressDialog, setShowProgressDialog]` 附近）添加：

```typescript
const [showReplanConfirm, setShowReplanConfirm] = useState(false)
```

4. 在 `handleConfirm` 附近添加 `handleReplan` 函数：

```typescript
const handleReplan = () =>
{
  setShowReplanConfirm(false)
  setShowProgressDialog(true)
}
```

5. 修改"开始规划"按钮区域。找到现有的确认按钮：

```typescript
{/* 确认按钮 */}
<Button onClick={handleConfirm} disabled={confirming} className="px-6 mt-[22px]">
```

替换整个按钮区域为条件渲染：

```tsx
{/* 确认/重新规划按钮 */}
{hasOutline ? (
  <Button onClick={() => setShowReplanConfirm(true)} className="px-6 mt-[22px]" variant="outline">
    <RefreshCw className="h-4 w-4 mr-2" />
    重新规划
    <ArrowRight className="h-4 w-4 ml-2" />
  </Button>
) : (
  <Button onClick={handleConfirm} disabled={confirming} className="px-6 mt-[22px]">
    {confirming ? (
      <>保存中...</>
    ) : (
      <>
        <Check className="h-4 w-4 mr-2" />
        开始规划
        <ArrowRight className="h-4 w-4 ml-2" />
      </>
    )}
  </Button>
)}
```

6. 修改提示文字。找到：

```typescript
<p className="text-xs text-muted-foreground text-center mt-1.5">确认后自动开始规划</p>
```

替换为：

```tsx
<p className="text-xs text-muted-foreground text-center mt-1.5">
  {hasOutline ? '重新生成大纲、人物和关系' : '确认后自动开始规划'}
</p>
```

7. 修改 `OutlineProgressDialog` 组件调用，传入 `isReplan`：

```tsx
<OutlineProgressDialog
  open={showProgressDialog}
  onClose={() => setShowProgressDialog(false)}
  projectId={projectId}
  modelConfigId={selectedModelKey ? parseInt(selectedModelKey.split(':')[0]) : undefined}
  modelName={selectedModelKey ? selectedModelKey.split(':').slice(1).join(':') : undefined}
  isReplan={hasOutline}
  onComplete={() => {}}
  onViewOutline={() =>
  {
    setShowProgressDialog(false)
    setActiveMenuItem('outline')
  }}
/>
```

8. 在组件 return 的最外层 `<div>` 内、`OutlineProgressDialog` 前面添加确认对话框：

```tsx
{/* 重新规划确认对话框 */}
<AlertDialog open={showReplanConfirm} onOpenChange={setShowReplanConfirm}>
  <AlertDialogContent>
    <AlertDialogHeader>
      <AlertDialogTitle>确认重新规划？</AlertDialogTitle>
      <AlertDialogDescription>
        重新规划将清除当前的大纲、人物和关系数据，基于当前灵感重新生成。此操作不可撤销。
      </AlertDialogDescription>
    </AlertDialogHeader>
    <AlertDialogFooter>
      <AlertDialogCancel>取消</AlertDialogCancel>
      <AlertDialogAction onClick={handleReplan}>确认重新规划</AlertDialogAction>
    </AlertDialogFooter>
  </AlertDialogContent>
</AlertDialog>
```

9. 在文件顶部添加 import：

```typescript
import { AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent, AlertDialogDescription, AlertDialogFooter, AlertDialogHeader, AlertDialogTitle } from '@/components/ui/alert-dialog'
```

注意：`RefreshCw` 已在现有 import 中。

- [ ] **Step 3: 验证前端构建**

Run: `docker compose build --no-cache frontend && docker compose up -d frontend`
Expected: 构建成功无错误

- [ ] **Step 4: Commit**

```bash
git add frontend/src/components/workbench/planning/InspirationPanel.tsx frontend/src/pages/ProjectWorkbench.tsx
git commit -m "feat(frontend): add replan button to InspirationPanel with confirmation dialog"
```

---

### Task 6: 集成测试 — 端到端验证

**Files:** 无新增

- [ ] **Step 1: 运行后端全部测试**

Run: `docker exec novelagent-backend-1 pytest tests/ -v`
Expected: 全部 PASS

- [ ] **Step 2: 验证前端构建**

Run: `docker compose build --no-cache frontend && docker compose up -d frontend`
Expected: 构建成功

- [ ] **Step 3: 手动冒烟测试**

1. 访问 http://localhost:3001，登录
2. 创建新项目，填写灵感信息，点击"开始规划"
3. 等待规划完成，验证大纲、人物、关系已生成
4. 回到灵感页面，验证"重新规划"按钮已显示
5. 点击"重新规划"，确认对话框
6. 验证进度弹窗显示"正在重新规划"
7. 等待重新规划完成，验证大纲、人物、关系已被新数据替换

- [ ] **Step 4: Final commit (if any fixes needed)**

```bash
git add -A
git commit -m "fix: integration test fixes for replan feature"
```
